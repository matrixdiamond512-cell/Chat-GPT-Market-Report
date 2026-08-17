#!/usr/bin/env python3
"""Restore usable 08:00 values that downstream repair accidentally degraded.

Precedence for the morning publication pipeline is:
1. canonical Google Sheets / exact-date specialist references,
2. values already present in the originally published report for the same slot,
3. external repair sources,
4. reasoned unavailable markers.

This script protects level 2. It scans git history for the earliest version of the
same report date/time and restores usable rows only when no canonical source has
explicitly updated that row. This prevents a later fallback/date-gate mismatch from
turning an already published numeric value into 取得不能.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data" / "latest-report.json"
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
        # The originally published value is the fallback source of truth whenever
        # canonical sources did not explicitly replace it.
        for key in ("value", "change", "rate", "direction"):
            if key in source:
                target[key] = source.get(key)
        target["label"] = label
        restored_rows.append(label)

    restored_markets = restore_market_summaries(report, original, protected)
    report.setdefault("dataProvenance", {})["publishedValueRecovery"] = {
        "sourceCommit": commit,
        "rule": "canonical source > original published value > external repair > reasoned unavailable",
        "protectedCanonicalLabels": sorted(protected),
        "restoredRows": restored_rows,
        "restoredMarkets": restored_markets,
    }
    save(LATEST, payload)
    print(json.dumps({
        "sourceCommit": commit,
        "restoredRows": restored_rows,
        "restoredMarkets": restored_markets,
        "protected": sorted(protected),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
