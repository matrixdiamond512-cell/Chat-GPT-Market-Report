#!/usr/bin/env python3
"""Restore usable 08:00 values that downstream repair accidentally degraded.

Precedence for the morning publication pipeline is:
1. canonical Google Sheets / exact-date specialist references,
2. verified repository history for exchange-session closes,
3. values already present in the originally published report for the same slot,
4. external repair sources,
5. reasoned unavailable markers.

The special OSE recovery is date-strict. The Friday Osaka night session closes at
06:00 JST on Saturday, so a Monday 08:00 previous-close report must accept that
Saturday 06:00 verified quote as the close of Friday's trading day.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data" / "latest-report.json"
VERIFIED_HISTORY = ROOT / "data" / "market" / "verified_history.csv"
UNAVAILABLE_RE = re.compile(r"取得不能|未取得|未公表|入力に値なし|入力待ち|取得継続")
ALIASES = {
    "Dow Jones": "NYダウ",
    "Dow": "NYダウ",
    "NASDAQ Composite": "NASDAQ総合",
    "Nasdaq Composite": "NASDAQ総合",
    "Nasdaq": "NASDAQ総合",
    "S&P 500": "S&P500",
    "Nikkei 225": "日経225現物",
    "日経225": "日経225現物",
    "日経平均": "日経225現物",
    "金": "COMEX金先物",
    "COMEX金": "COMEX金先物",
    "原油": "WTI原油",
    "日経225先物・大阪取引所": "日経225先物（大阪取引所）",
    "日経225先物(大阪取引所)": "日経225先物（大阪取引所）",
    "25日移動平均乖離率": "日経225 25日移動平均乖離率",
    "日経225 25日乖離率": "日経225 25日移動平均乖離率",
    "200日移動平均乖離率": "日経225 200日移動平均乖離率",
    "日経225 200日乖離率": "日経225 200日移動平均乖離率",
}
MARKET_TO_TABLE = {
    "金": "COMEX金先物",
    "原油": "WTI原油",
    "WTI原油": "WTI原油",
    "日経225先物": "日経225先物（大阪取引所）",
    "日経225先物（大阪取引所）": "日経225先物（大阪取引所）",
    "USD/JPY": "USD/JPY",
    "EUR/USD": "EUR/USD",
    "BTCUSD": "BTCUSD",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_label(value: Any) -> str:
    label = str(value or "").strip()
    return ALIASES.get(label, label)


def usable_value(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and not UNAVAILABLE_RE.search(text))


def report_object(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    report = payload.get("latestReport") or payload.get("report") or payload
    return report if isinstance(report, dict) else None


def rows_by_label(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    table = report.get("marketDataTable") or {}
    rows = table.get("rows") if isinstance(table, dict) else None
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = normalize_label(row.get("label") or row.get("item") or row.get("name"))
        if label and label not in result:
            result[label] = row
    return result


def canonical_protected_labels(report: dict[str, Any]) -> set[str]:
    protected: set[str] = set()
    provenance = report.get("dataProvenance") or {}
    if not isinstance(provenance, dict):
        return protected
    for detail in provenance.values():
        if not isinstance(detail, dict):
            continue
        for key in ("updatedLabels", "applied"):
            values = detail.get(key)
            if isinstance(values, list):
                protected.update(normalize_label(v) for v in values if str(v or "").strip())
    return protected


def git_history() -> list[str]:
    try:
        output = subprocess.check_output(
            ["git", "log", "--reverse", "--format=%H", "--", "data/latest-report.json"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def show_payload(commit: str) -> dict[str, Any] | None:
    try:
        text = subprocess.check_output(
            ["git", "show", f"{commit}:data/latest-report.json"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def find_original_report(date: str, slot: str) -> tuple[str, dict[str, Any] | None]:
    for commit in git_history():
        payload = show_payload(commit)
        report = report_object(payload)
        if not report:
            continue
        if str(report.get("date") or "") == date and str(report.get("time") or "") == slot:
            if rows_by_label(report):
                return commit, report
    return "", None


def previous_business_day(report_date: dt.date) -> dt.date:
    day = report_date - dt.timedelta(days=1)
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


def parse_iso(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text)
    except ValueError:
        return None


def verified_ose_previous_close(report_date: dt.date) -> dict[str, str] | None:
    """Find the verified OSE close belonging to the prior business session.

    OSE night trading for a Tokyo trading day ends at 06:00 JST on the next calendar
    day. Therefore the target timestamp date is previous_business_day + 1 day.
    Only verified, usable JPX/OSE rows are eligible; fallback/current report rows are
    rejected.
    """
    if not VERIFIED_HISTORY.is_file():
        return None
    prior_day = previous_business_day(report_date)
    session_end_date = prior_day + dt.timedelta(days=1)
    candidates: list[tuple[dt.datetime, dict[str, str]]] = []
    try:
        with VERIFIED_HISTORY.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if str(row.get("銘柄ID") or "") != "nikkei225_futures_ose":
                    continue
                if str(row.get("利用判定") or "") != "使用可":
                    continue
                if str(row.get("検証状態") or "") != "verified":
                    continue
                if str(row.get("前回確認値利用") or "").lower() == "true":
                    continue
                if "JPX/OSE" not in str(row.get("取得元") or ""):
                    continue
                target_at = parse_iso(row.get("対象時刻"))
                if target_at is None or target_at.date() != session_end_date:
                    continue
                if target_at.time() > dt.time(6, 5):
                    continue
                value = str(row.get("現在値") or "").strip()
                if not usable_value(value):
                    continue
                candidates.append((target_at, row))
    except (OSError, csv.Error):
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0])
    target_at, row = candidates[-1]
    value = float(str(row.get("現在値") or "0").replace(",", ""))
    change_raw = str(row.get("前回比") or "").strip()
    rate_raw = str(row.get("前回比率(%)") or "").strip()
    try:
        change = float(change_raw)
    except ValueError:
        change = None
    try:
        rate = float(rate_raw)
    except ValueError:
        rate = None
    return {
        "value": f"{value:,.0f}",
        "change": f"{change:+,.0f}" if change is not None else "—",
        "rate": f"{rate:+.2f}%" if rate is not None else "—",
        "direction": "上昇" if (change or 0) > 0 else "下落" if (change or 0) < 0 else "横ばい",
        "asOf": target_at.isoformat(),
        "tradingDate": prior_day.isoformat(),
        "sourceName": str(row.get("取得元") or "JPX/OSE Futures Quotes"),
        "sourceUrl": str(row.get("取得元URL") or ""),
    }


def apply_verified_ose_close(report: dict[str, Any], protected: set[str]) -> dict[str, str] | None:
    label = "日経225先物（大阪取引所）"
    if label in protected:
        return None
    try:
        report_date = dt.date.fromisoformat(str(report.get("date") or ""))
    except ValueError:
        return None
    recovered = verified_ose_previous_close(report_date)
    if not recovered:
        return None
    row = rows_by_label(report).get(label)
    if not row:
        return None
    for key in ("value", "change", "rate", "direction"):
        row[key] = recovered[key]

    markets = report.get("markets")
    if isinstance(markets, list):
        for market in markets:
            if not isinstance(market, dict):
                continue
            if str(market.get("name") or "").strip() in {"日経225先物", label}:
                market["price"] = f"{recovered['value']}円"
                market["direction"] = recovered["direction"]
                break
    return recovered


def restore_market_summaries(
    current: dict[str, Any], original: dict[str, Any], protected: set[str]
) -> list[str]:
    current_markets = current.get("markets")
    original_markets = original.get("markets")
    if not isinstance(current_markets, list) or not isinstance(original_markets, list):
        return []
    originals = {
        str(m.get("name") or "").strip(): m
        for m in original_markets
        if isinstance(m, dict) and str(m.get("name") or "").strip()
    }
    restored: list[str] = []
    for market in current_markets:
        if not isinstance(market, dict):
            continue
        name = str(market.get("name") or "").strip()
        source = originals.get(name)
        if not source:
            continue
        table_label = MARKET_TO_TABLE.get(name, name)
        if table_label in protected:
            continue
        if usable_value(source.get("price")):
            market["price"] = source.get("price")
            if str(source.get("direction") or "").strip():
                market["direction"] = source.get("direction")
            restored.append(name)
    return restored


def main() -> int:
    payload = load(LATEST)
    report = report_object(payload)
    if not report or report.get("time") != "08:00":
        print("Latest report is not 08:00; history recovery skipped")
        return 0

    date = str(report.get("date") or "")
    slot = str(report.get("time") or "")
    commit, original = find_original_report(date, slot)
    if not original:
        print("No earlier version of the same 08:00 report found; history recovery skipped")
        return 0

    protected = canonical_protected_labels(report)
    current_rows = rows_by_label(report)
    original_rows = rows_by_label(original)
    restored_rows: list[str] = []

    for label, source in original_rows.items():
        target = current_rows.get(label)
        if not target or label in protected:
            continue
        if not usable_value(source.get("value")):
            continue
        for key in ("value", "change", "rate", "direction"):
            if key in source:
                target[key] = source.get(key)
        target["label"] = label
        restored_rows.append(label)

    restored_markets = restore_market_summaries(report, original, protected)
    ose_recovery = apply_verified_ose_close(report, protected)
    if ose_recovery:
        label = "日経225先物（大阪取引所）"
        if label not in restored_rows:
            restored_rows.append(label)
        if "日経225先物" not in restored_markets:
            restored_markets.append("日経225先物")

    report.setdefault("dataProvenance", {})["publishedValueRecovery"] = {
        "sourceCommit": commit,
        "rule": "canonical source > verified exchange-session history > original published value > external repair > reasoned unavailable",
        "protectedCanonicalLabels": sorted(protected),
        "restoredRows": restored_rows,
        "restoredMarkets": restored_markets,
        "osePreviousCloseRecovery": ose_recovery,
    }
    save(LATEST, payload)
    print(json.dumps({
        "sourceCommit": commit,
        "restoredRows": restored_rows,
        "restoredMarkets": restored_markets,
        "osePreviousCloseRecovery": ose_recovery,
        "protected": sorted(protected),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
