#!/usr/bin/env python3
"""Validate the 08:00 report's canonical 28-item / 5-column market table.

This is a publication QA gate, not a market-data fetcher. It checks the report
artifact after generation and refuses to treat it as publishable when rows are
missing, shifted, duplicated, or contradicted by a verified morning reference.
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
REQUIRED_SIX = {
    "COMEX金先物", "WTI原油", "日経225先物（大阪取引所）",
    "USD/JPY", "EUR/USD", "BTCUSD",
}
BAD_MARKERS = (
    "主要市場データ入力に該当行なし",
    "最終修正版本文に該当行なし",
    "undefined",
    "null",
)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def normalize_label(value: str) -> str:
    label = NUMBER_PREFIX.sub("", str(value or "").strip())
    aliases = {
        "日経225先物・大阪取引所": "日経225先物（大阪取引所）",
        "日経225先物(大阪取引所)": "日経225先物（大阪取引所）",
        "日経225 25日乖離率": "日経225 25日移動平均乖離率",
        "日経225 200日乖離率": "日経225 200日移動平均乖離率",
    }
    return aliases.get(label, label)


def parse_rows(text: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
    start = next((i for i, line in enumerate(lines) if "主要市場データ" in line), -1)
    if start < 0:
        return []
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^3[.．]\s*", lines[i])), len(lines))
    block = lines[start + 1:end]
    rows: list[dict[str, str]] = []
    i = 0
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


def report_text(report: dict[str, Any]) -> str:
    return str(report.get("fullText") or report.get("rawText") or report.get("body") or "")


def find_report(reports: Any, date: str, slot: str) -> dict[str, Any] | None:
    if not isinstance(reports, list):
        return None
    for item in reports:
        if isinstance(item, dict) and item.get("date") == date and item.get("time") == slot:
            return item
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=dt.datetime.now(JST).date().isoformat())
    parser.add_argument("--slot", default="08:00", choices=("08:00",))
    parser.add_argument("--reports", default=str(ROOT / "reports.json"))
    parser.add_argument("--reference", default=str(ROOT / "data" / "market" / "morning-reference.json"))
    parser.add_argument("--output", default=str(ROOT / "data" / "market" / "morning_report_qa.json"))
    args = parser.parse_args()

    blocking: list[str] = []
    warnings: list[str] = []
    reports = load_json(Path(args.reports), [])
    report = find_report(reports, args.date, args.slot)
    rows: list[dict[str, str]] = []

    if not report:
        blocking.append(f"report not found: {args.date} {args.slot}")
    else:
        text = report_text(report)
        if not text:
            blocking.append("report fullText/rawText/body is empty")
        else:
            rows = parse_rows(text)

    if report:
        if len(rows) != 28:
            blocking.append(f"market table row count must be 28, got {len(rows)}")

        labels = [row["label"] for row in rows]
        if len(labels) != len(set(labels)):
            blocking.append("market table contains duplicate labels")
        if labels and labels != ITEMS:
            missing = [label for label in ITEMS if label not in labels]
            extra = [label for label in labels if label not in ITEMS]
            blocking.append(
                "market table order/labels mismatch"
                + (f"; missing={missing}" if missing else "")
                + (f"; extra={extra}" if extra else "")
            )

        by_label = {row["label"]: row for row in rows}
        for row in rows:
            cells = [row["value"], row["change"], row["rate"], row["direction"]]
            joined = " | ".join(cells)
            if any(marker in joined for marker in BAD_MARKERS):
                blocking.append(f"{row['label']}: parser failure marker remains: {joined}")
            if not all(str(cell).strip() for cell in cells):
                blocking.append(f"{row['label']}: one or more of the 5-column cells are empty")
            if "取得不能" in row["value"] and "（" not in row["value"] and "(" not in row["value"]:
                blocking.append(f"{row['label']}: generic 取得不能 without a concrete reason")
            if "取得不能" not in row["value"] and "未公表" not in row["value"] and row["direction"] == "取得不能":
                blocking.append(f"{row['label']}: numeric/value cell exists but direction says 取得不能")

        for label in REQUIRED_SIX:
            row = by_label.get(label)
            if not row:
                blocking.append(f"required six-market row missing: {label}")
            elif "取得不能" in row["value"] or "未公表" in row["value"]:
                blocking.append(f"required six-market value unavailable: {label} = {row['value']}")

        reference = load_json(Path(args.reference), {})
        if reference.get("reportDate") == args.date and reference.get("reportSlot") == args.slot:
            for label, ref in (reference.get("items") or {}).items():
                if not isinstance(ref, dict):
                    continue
                status = str(ref.get("status") or "")
                ref_value = ref.get("value")
                row = by_label.get(label)
                if row and status.startswith("verified") and ref_value not in (None, ""):
                    if "取得不能" in row["value"]:
                        blocking.append(
                            f"{label}: report says 取得不能 although verified reference value exists ({ref_value})"
                        )
                if row and status == "verified_unavailable" and "未公表" not in row["value"]:
                    warnings.append(f"{label}: verified unavailable should be labeled 未公表 rather than generic failure")

    ready = not blocking
    result = {
        "checkedAt": dt.datetime.now(JST).replace(microsecond=0).isoformat(),
        "reportDate": args.date,
        "reportSlot": args.slot,
        "ready": ready,
        "expectedRowCount": 28,
        "actualRowCount": len(rows),
        "expectedColumns": ["項目", "終値・値", "前日比", "騰落率", "方向感"],
        "labels": [row.get("label") for row in rows],
        "blockingReasons": blocking,
        "warnings": warnings,
        "rule": "08:00 report is publishable only after the canonical 28-item / 5-column table passes this QA gate.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
