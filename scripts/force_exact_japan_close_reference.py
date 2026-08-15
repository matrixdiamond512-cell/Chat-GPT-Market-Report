#!/usr/bin/env python3
"""Force exact-date Japanese close reference values into the 08:00 report.

The general previous-close repair can use broad market feeds. For Japanese close,
valuation, breadth and technical rows, the dedicated exact-date Japan reference is
more specific and must win when the dates match. This prevents a usable-looking but
incorrect broad-feed value from blocking the dedicated source.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data" / "latest-report.json"
REFERENCE = ROOT / "data" / "market" / "japan-close-reference.json"
JST = dt.timezone(dt.timedelta(hours=9))

ALLOWED = {
    "日経225現物",
    "日経225予想PER",
    "日経225 PBR",
    "日経225予想EPS",
    "日経225 25日移動平均乖離率",
    "日経225 200日移動平均乖離率",
    "東証プライム売買代金",
    "東証プライム売買高",
    "東証プライム値上がり銘柄数",
    "東証プライム値下がり銘柄数",
    "東証プライム25日騰落レシオ",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def expected_prior(report_date: dt.date) -> dt.date:
    return report_date - dt.timedelta(days=3 if report_date.weekday() == 0 else 1)


def rewrite_market_block(report: dict[str, Any]) -> None:
    text = str(report.get("fullText") or "")
    rows = ((report.get("marketDataTable") or {}).get("rows") or [])
    if not text or len(rows) != 28:
        return
    block = ["【主要市場データ】", "項目\t終値・値\t前日比\t騰落率\t方向感"]
    for row in rows:
        block.append("\t".join(str(row.get(key) or "—") for key in ("label", "value", "change", "rate", "direction")))
    replacement = "\n".join(block) + "\n\n"
    pattern = re.compile(r"【主要市場データ】\s*\n.*?(?=\n【[^\n]+】)", re.S)
    if pattern.search(text):
        report["fullText"] = pattern.sub(replacement.rstrip("\n"), text, count=1)


def main() -> int:
    payload = load(LATEST)
    report = payload.get("latestReport") or payload.get("report") or payload
    if not isinstance(report, dict) or report.get("time") != "08:00":
        print("Latest report is not 08:00; exact Japan overlay skipped")
        return 0

    report_date = dt.date.fromisoformat(str(report.get("date")))
    expected = expected_prior(report_date)
    reference = load(REFERENCE)
    if str(reference.get("dataDate") or "") != expected.isoformat():
        print(f"Exact Japan reference date mismatch: expected {expected}, got {reference.get('dataDate') or 'empty'}")
        return 0

    rows = ((report.get("marketDataTable") or {}).get("rows") or [])
    if len(rows) != 28:
        raise SystemExit("08:00 marketDataTable must contain 28 rows")
    by_label = {str(row.get("label") or "").strip(): row for row in rows if isinstance(row, dict)}

    applied: list[str] = []
    for label, item in (reference.get("items") or {}).items():
        if label not in ALLOWED or label not in by_label or not isinstance(item, dict):
            continue
        if str(item.get("date") or "") != expected.isoformat():
            continue
        value = str(item.get("value") or "").strip()
        if not value:
            continue
        row = by_label[label]
        row["value"] = value
        row["change"] = str(item.get("change") or "—")
        row["rate"] = str(item.get("rate") or "—")
        if item.get("direction"):
            row["direction"] = str(item["direction"])
        elif "乖離率" in label:
            try:
                number = float(value.replace("%", "").replace(",", ""))
                row["direction"] = "上方乖離" if number > 0 else "下方乖離" if number < 0 else "乖離なし"
            except ValueError:
                row["direction"] = "確定値"
        else:
            row["direction"] = "確定値"
        applied.append(label)

    rewrite_market_block(report)
    report.setdefault("dataProvenance", {})["exactJapanCloseOverride"] = {
        "dataDate": expected.isoformat(),
        "appliedAt": dt.datetime.now(JST).replace(microsecond=0).isoformat(),
        "appliedLabels": applied,
        "source": "data/market/japan-close-reference.json",
        "rule": "Exact-date dedicated Japanese reference overrides generic previous-close feeds for matching Japanese rows.",
    }
    save(LATEST, payload)
    print(json.dumps({"dataDate": expected.isoformat(), "applied": applied}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
