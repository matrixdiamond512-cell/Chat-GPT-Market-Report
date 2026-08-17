#!/usr/bin/env python3
"""Validate the effective 08:00 28-item / 5-column previous-close table.

The 08:00 report is a previous-close report. QA validates the structured table itself
and never overlays an intraday morning quote. A date-matched prior close may have been
retrieved after 08:00; that retrieval time is not a reason to reject the value.

A reasoned unavailable value (取得不能（理由） / 未公表（理由）) is publishable as a
degraded warning. Missing rows, empty cells, parser failures, and unavailable values
without a reason remain blocking.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
JST = dt.timezone(dt.timedelta(hours=9))
ITEMS = [
    "NYダウ", "NASDAQ総合", "S&P500", "Russell 2000", "日経225現物",
    "CME日経225先物・円建て", "CME日経225先物・ドル建て", "日経225先物（大阪取引所）",
    "USD/JPY", "EUR/USD", "COMEX金先物", "WTI原油", "BTCUSD", "VIX", "日経VI",
    "Fear & Greed Index", "米10年債利回り", "日本10年国債利回り", "日経225予想PER",
    "日経225 PBR", "日経225予想EPS", "日経225 25日移動平均乖離率",
    "日経225 200日移動平均乖離率", "東証プライム売買代金", "東証プライム売買高",
    "東証プライム値上がり銘柄数", "東証プライム値下がり銘柄数", "東証プライム25日騰落レシオ",
]
NUMBER_PREFIX = re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘]\s*")
REQUIRED_SIX = {"COMEX金先物", "WTI原油", "日経225先物（大阪取引所）", "USD/JPY", "EUR/USD", "BTCUSD"}
BAD_MARKERS = ("主要市場データ入力に該当行なし", "最終修正版本文に該当行なし", "undefined", "null")


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def normalize_label(value: str) -> str:
    label = NUMBER_PREFIX.sub("", str(value or "").strip())
    return {
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
        "日経225 25日乖離率": "日経225 25日移動平均乖離率",
        "25日移動平均乖離率": "日経225 25日移動平均乖離率",
        "日経225 200日乖離率": "日経225 200日移動平均乖離率",
        "200日移動平均乖離率": "日経225 200日移動平均乖離率",
    }.get(label, label)


def parse_rows(text: str) -> list[dict[str, str]]:
    lines = [x.strip() for x in str(text or "").replace("\r", "").split("\n") if x.strip()]
    start = next((i for i, x in enumerate(lines) if "主要市場データ" in x), -1)
    if start < 0:
        return []
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^3[.．]\s*", lines[i])), len(lines))
    block, rows, i = lines[start + 1:end], [], 0
    while i < len(block):
        if NUMBER_PREFIX.match(block[i]) and i + 4 < len(block):
            rows.append({
                "label": normalize_label(block[i]),
                "value": block[i + 1],
                "change": block[i + 2],
                "rate": block[i + 3],
                "direction": block[i + 4],
            })
            i += 5
        else:
            i += 1
    return rows


def structured_rows(report: dict[str, Any] | None) -> list[dict[str, str]]:
    if not isinstance(report, dict):
        return []
    table = report.get("marketDataTable") or {}
    raw = table.get("rows") if isinstance(table, dict) else None
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, str]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        rows.append({
            "label": normalize_label(row.get("label") or row.get("item") or row.get("name") or ""),
            "value": str(row.get("value") or ""),
            "change": str(row.get("change") or ""),
            "rate": str(row.get("rate") or row.get("changePercent") or ""),
            "direction": str(row.get("direction") or ""),
        })
    return rows


def find_report(reports: Any, date: str, slot: str) -> dict[str, Any] | None:
    if not isinstance(reports, list):
        return None
    return next((x for x in reports if isinstance(x, dict) and x.get("date") == date and x.get("time") == slot), None)


def select_report(reports: Any, latest_report_payload: dict[str, Any], date: str, slot: str) -> tuple[dict[str, Any] | None, str]:
    latest = latest_report_payload.get("latestReport") or latest_report_payload.get("report") or {}
    if isinstance(latest, dict) and latest.get("date") == date and latest.get("time") == slot:
        return latest, "latest-report"
    report = find_report(reports, date, slot)
    return report, "reports.json" if report else "none"


def reasoned_unavailable(value: str) -> bool:
    return bool(re.match(r"^(取得不能|未公表)（.+）$", str(value or "").strip()))


def expected_previous_weekday(report_date: dt.date) -> str:
    prior = report_date - dt.timedelta(days=3 if report_date.weekday() == 0 else 1)
    return prior.isoformat()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=dt.datetime.now(JST).date().isoformat())
    p.add_argument("--slot", default="08:00", choices=("08:00",))
    p.add_argument("--reports", default=str(ROOT / "reports.json"))
    p.add_argument("--latest-report", default=str(ROOT / "data/latest-report.json"))
    p.add_argument("--output", default=str(ROOT / "data/market/morning_report_qa.json"))
    p.add_argument("--allow-historical", action="store_true")
    a = p.parse_args()

    blocking: list[str] = []
    warnings: list[str] = []
    reports = load_json(Path(a.reports), [])
    latest_report_payload = load_json(Path(a.latest_report), {})
    report, report_source = select_report(reports, latest_report_payload, a.date, a.slot)

    today = dt.datetime.now(JST).date().isoformat()
    if not a.allow_historical and a.date != today:
        blocking.append(f"report date is stale: expected current JST date {today}, got {a.date}")

    latest_report = latest_report_payload.get("latestReport") or {}
    if not a.allow_historical:
        latest_date = str(latest_report.get("date") or "")
        latest_slot = str(latest_report.get("time") or "")
        if latest_date != a.date or latest_slot != a.slot:
            blocking.append(f"latest-report mismatch: expected {a.date} {a.slot}, got {latest_date or 'empty'} {latest_slot or 'empty'}")

    if not report:
        blocking.append(f"report not found: {a.date} {a.slot}")
        rows: list[dict[str, str]] = []
    else:
        rows = structured_rows(report)
        if rows:
            warnings.append(f"marketDataTable structured rows used from {report_source}")
        else:
            rows = parse_rows(str(report.get("fullText") or report.get("rawText") or report.get("body") or ""))
            if not rows:
                blocking.append("28-item market table could not be parsed from report text")

    if report:
        if len(rows) != 28:
            blocking.append(f"market table row count must be 28, got {len(rows)}")
        labels = [r["label"] for r in rows]
        if len(labels) != len(set(labels)):
            blocking.append("market table contains duplicate labels")
        if labels and labels != ITEMS:
            blocking.append("market table order/labels mismatch")
        by = {r["label"]: r for r in rows}
        for r in rows:
            cells = [r["value"], r["change"], r["rate"], r["direction"]]
            joined = " | ".join(cells)
            if any(m in joined for m in BAD_MARKERS):
                blocking.append(f"{r['label']}: parser failure marker remains")
            if not all(str(c).strip() for c in cells):
                blocking.append(f"{r['label']}: 5-column empty cell")
            if r["value"] == "取得不能":
                blocking.append(f"{r['label']}: generic 取得不能 without reason")
            if re.search(r"取得不能|未公表", r["value"]) and not reasoned_unavailable(r["value"]):
                blocking.append(f"{r['label']}: unavailable value without reason")
        for label in REQUIRED_SIX:
            r = by.get(label)
            if not r:
                blocking.append(f"required six-market row missing: {label}")
            elif re.search(r"取得不能|未公表", r["value"]):
                if reasoned_unavailable(r["value"]):
                    warnings.append(f"required six-market value unavailable with reason: {label}")
                else:
                    blocking.append(f"required six-market value unavailable without reason: {label}")

    provenance = (report or {}).get("dataProvenance") or {}
    close_sheet = provenance.get("closeSheet") or {}
    daily_repair = provenance.get("dailyCloseRepair") or {}
    if isinstance(close_sheet, dict) and close_sheet.get("semantics") not in (None, "previous_close"):
        blocking.append("closeSheet semantics is not previous_close")
    if isinstance(daily_repair, dict) and daily_repair.get("semantics") not in (None, "previous_close"):
        blocking.append("dailyCloseRepair semantics is not previous_close")

    report_date = dt.date.fromisoformat(a.date)
    expected_close_date = str(close_sheet.get("dataDate") or expected_previous_weekday(report_date))
    ready = not blocking
    result = {
        "checkedAt": dt.datetime.now(JST).replace(microsecond=0).isoformat(),
        "reportDate": a.date,
        "reportSlot": a.slot,
        "ready": ready,
        "historicalMode": bool(a.allow_historical),
        "reportSource": report_source,
        "latestReportDate": latest_report.get("date"),
        "latestReportTime": latest_report.get("time"),
        "dataSemantics": "previous_close",
        "expectedPreviousCloseDate": expected_close_date,
        "expectedRowCount": 28,
        "actualRowCount": len(rows),
        "expectedColumns": ["項目", "終値・値", "前日比", "騰落率", "方向感"],
        "labels": [r.get("label") for r in rows],
        "blockingReasons": sorted(set(blocking)),
        "warnings": warnings,
        "rule": "08:00 is a previous-close report. Validate market-data date, not retrieval clock time; reasoned unavailable values publish as degraded warnings.",
    }
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
