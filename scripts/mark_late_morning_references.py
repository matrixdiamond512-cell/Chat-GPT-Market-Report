#!/usr/bin/env python3
"""Annotate unresolved 08:00 rows when a later reference was captured.

Late reference values are useful diagnostics but must never be backfilled as if they
were known at 08:00. This script turns a temporary 'retrying' message into a precise
historical reason while preserving any value that was actually captured in the report.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data/latest-report.json"
REFERENCE = ROOT / "data/market/morning-reference.json"
UNAVAILABLE = re.compile(r"取得不能|未取得|再実行中|取得継続")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    latest_payload = load(LATEST)
    report = latest_payload.get("latestReport") or latest_payload.get("report") or latest_payload
    reference = load(REFERENCE)
    if not isinstance(report, dict) or report.get("time") != "08:00":
        print("Latest report is not 08:00; no late-reference annotation needed")
        return 0
    if reference.get("reportDate") != report.get("date") or reference.get("reportSlot") != report.get("time"):
        print("Reference does not match latest 08:00 report; no annotation")
        return 0

    table = report.get("marketDataTable") or {}
    rows = table.get("rows") or []
    by_label = {str(row.get("label") or ""): row for row in rows if isinstance(row, dict)}
    changed = []
    for label, ref in (reference.get("items") or {}).items():
        if not isinstance(ref, dict) or ref.get("status") != "reference_after_report":
            continue
        row = by_label.get(label)
        if not row:
            continue
        current_value = str(row.get("value") or "")
        if not UNAVAILABLE.search(current_value):
            # A report-time value already exists; keep it and ignore the later quote.
            continue
        as_of = str(ref.get("asOf") or "後刻")
        row["value"] = f"取得不能（08:00時点の参照値を保存できず。{as_of}取得値は時刻違いのため不採用）"
        row["change"] = "—"
        row["rate"] = "—"
        row["direction"] = "取得不能"
        changed.append(label)

    if changed:
        report.setdefault("dataProvenance", {})["lateMorningReferencePolicy"] = {
            "policy": "post-report references are diagnostic only and never backfilled",
            "labels": changed,
        }
        dump(LATEST, latest_payload)
    print(json.dumps({"changed": changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
