#!/usr/bin/env python3
"""Recover Monday 08:00 previous-close rows from the Saturday 08:00 report.

A Monday morning previous-close table refers to Friday's close. The Saturday 08:00
report also refers to Friday's close. Therefore a verified/usable row already saved
in the Saturday canonical report is a date-matched source for Monday when a live
repair feed later fails to reproduce that exact Friday record.

This recovery only fills currently unavailable rows. It never overwrites a usable
Monday value or any exact-date value already applied by a higher-priority source.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data" / "latest-report.json"
REPORTS = ROOT / "reports"
UNAVAILABLE_RE = re.compile(r"取得不能|未取得|未公表|入力に値なし|入力待ち|取得継続")
ALIASES = {
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


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_label(value: Any) -> str:
    label = str(value or "").strip()
    return ALIASES.get(label, label)


def usable(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and not UNAVAILABLE_RE.search(text))


def report_object(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    report = payload.get("latestReport") or payload.get("report") or payload
    return report if isinstance(report, dict) else None


def rows(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    table = report.get("marketDataTable") or {}
    raw = table.get("rows") if isinstance(table, dict) else None
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(raw, list):
        return result
    for row in raw:
        if not isinstance(row, dict):
            continue
        label = normalize_label(row.get("label") or row.get("item") or row.get("name"))
        if label and label not in result:
            result[label] = row
    return result


def current_report(payload: dict[str, Any]) -> dict[str, Any] | None:
    return report_object(payload)


def main() -> int:
    payload = load(LATEST)
    current = current_report(payload)
    if not current or current.get("time") != "08:00":
        print("Latest report is not 08:00; Monday/Saturday recovery skipped")
        return 0

    try:
        report_date = dt.date.fromisoformat(str(current.get("date") or ""))
    except ValueError:
        print("Latest report date is invalid; recovery skipped")
        return 0

    if report_date.weekday() != 0:  # Monday only
        print("Latest report is not Monday; Monday/Saturday recovery skipped")
        return 0

    saturday = report_date - dt.timedelta(days=2)
    saturday_path = REPORTS / f"{saturday.isoformat()}_08-00.json"
    if not saturday_path.is_file():
        print(f"Saturday report not found: {saturday_path.relative_to(ROOT)}")
        return 0

    prior = report_object(load(saturday_path))
    if not prior:
        print("Saturday report payload invalid; recovery skipped")
        return 0

    current_rows = rows(current)
    prior_rows = rows(prior)
    restored: list[str] = []
    for label, target in current_rows.items():
        source = prior_rows.get(label)
        if not source:
            continue
        if usable(target.get("value")):
            continue
        if not usable(source.get("value")):
            continue
        for key in ("value", "change", "rate", "direction"):
            if key in source:
                target[key] = source.get(key)
        target["label"] = label
        restored.append(label)

    current.setdefault("dataProvenance", {})["mondaySaturdayRecovery"] = {
        "sourceReport": str(saturday_path.relative_to(ROOT)),
        "sourceReportDate": saturday.isoformat(),
        "rule": "Monday 08:00 and Saturday 08:00 both reference Friday close; fill only unavailable Monday rows",
        "restoredRows": restored,
    }
    save(LATEST, payload)
    print(json.dumps({
        "sourceReport": str(saturday_path.relative_to(ROOT)),
        "restoredRows": restored,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
