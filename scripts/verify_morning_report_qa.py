#!/usr/bin/env python3
"""Validate the effective 08:00 28-item / 5-column publication table."""

from __future__ import annotations
import argparse, datetime as dt, json, re
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
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return default


def normalize_label(value: str) -> str:
    label = NUMBER_PREFIX.sub("", str(value or "").strip())
    return {
        "日経225先物・大阪取引所": "日経225先物（大阪取引所）",
        "日経225先物(大阪取引所)": "日経225先物（大阪取引所）",
        "日経225 25日乖離率": "日経225 25日移動平均乖離率",
        "日経225 200日乖離率": "日経225 200日移動平均乖離率",
    }.get(label, label)


def parse_rows(text: str) -> list[dict[str, str]]:
    lines = [x.strip() for x in str(text or "").replace("\r", "").split("\n") if x.strip()]
    start = next((i for i, x in enumerate(lines) if "主要市場データ" in x), -1)
    if start < 0: return []
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^3[.．]\s*", lines[i])), len(lines))
    block, rows, i = lines[start + 1:end], [], 0
    while i < len(block):
        if NUMBER_PREFIX.match(block[i]) and i + 4 < len(block):
            rows.append({"label": normalize_label(block[i]), "value": block[i+1], "change": block[i+2], "rate": block[i+3], "direction": block[i+4]})
            i += 5
        else: i += 1
    return rows


def find_report(reports: Any, date: str, slot: str) -> dict[str, Any] | None:
    return next((x for x in reports if isinstance(x, dict) and x.get("date") == date and x.get("time") == slot), None) if isinstance(reports, list) else None


def apply_reference(rows: list[dict[str, str]], reference: dict[str, Any], date: str, slot: str, warnings: list[str]) -> list[dict[str, str]]:
    if reference.get("reportDate") != date or reference.get("reportSlot") != slot: return rows
    items = reference.get("items") or {}
    out = []
    for row in rows:
        ref = items.get(row["label"])
        if isinstance(ref, dict) and str(ref.get("status") or "").startswith("verified") and ref.get("value") not in (None, ""):
            replaced = dict(row)
            for key, source_key in (("value", "value"), ("change", "change"), ("rate", "rate"), ("direction", "direction")):
                if ref.get(source_key) is not None: replaced[key] = str(ref.get(source_key))
            if replaced != row: warnings.append(f"{row['label']}: verified morning-reference overlay applied")
            out.append(replaced)
        else: out.append(row)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=dt.datetime.now(JST).date().isoformat()); p.add_argument("--slot", default="08:00", choices=("08:00",))
    p.add_argument("--reports", default=str(ROOT / "reports.json")); p.add_argument("--reference", default=str(ROOT / "data/market/morning-reference.json"))
    p.add_argument("--output", default=str(ROOT / "data/market/morning_report_qa.json")); a = p.parse_args()
    blocking, warnings = [], []
    report = find_report(load_json(Path(a.reports), []), a.date, a.slot)
    raw_rows = [] if not report else parse_rows(str(report.get("fullText") or report.get("rawText") or report.get("body") or ""))
    if not report: blocking.append(f"report not found: {a.date} {a.slot}")
    elif not raw_rows: blocking.append("28-item market table could not be parsed from report text")
    reference = load_json(Path(a.reference), {})
    rows = apply_reference(raw_rows, reference, a.date, a.slot, warnings)
    if report:
        if len(rows) != 28: blocking.append(f"market table row count must be 28, got {len(rows)}")
        labels = [r["label"] for r in rows]
        if len(labels) != len(set(labels)): blocking.append("market table contains duplicate labels")
        if labels and labels != ITEMS: blocking.append("market table order/labels mismatch")
        by = {r["label"]: r for r in rows}
        for r in rows:
            cells = [r["value"], r["change"], r["rate"], r["direction"]]; joined = " | ".join(cells)
            if any(m in joined for m in BAD_MARKERS): blocking.append(f"{r['label']}: parser failure marker remains")
            if not all(str(c).strip() for c in cells): blocking.append(f"{r['label']}: 5-column empty cell")
            if r["value"] == "取得不能": blocking.append(f"{r['label']}: generic 取得不能 without reason")
            if not re.search(r"取得不能|未公表", r["value"]) and r["direction"] == "取得不能": blocking.append(f"{r['label']}: value exists but direction is 取得不能")
        for label in REQUIRED_SIX:
            r = by.get(label)
            if not r: blocking.append(f"required six-market row missing: {label}")
            elif re.search(r"取得不能|未公表", r["value"]): blocking.append(f"required six-market value unavailable: {label}")
    ready = not blocking
    result = {"checkedAt": dt.datetime.now(JST).replace(microsecond=0).isoformat(), "reportDate": a.date, "reportSlot": a.slot, "ready": ready,
              "expectedRowCount": 28, "actualRowCount": len(rows), "expectedColumns": ["項目","終値・値","前日比","騰落率","方向感"],
              "labels": [r.get("label") for r in rows], "blockingReasons": blocking, "warnings": warnings,
              "rule": "Publish only the effective 28-item / 5-column table after verified morning-reference overlays pass QA."}
    out = Path(a.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if ready else 1

if __name__ == "__main__": raise SystemExit(main())
