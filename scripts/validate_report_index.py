#!/usr/bin/env python3
"""Check report/index parity and exact local infographic-to-slot mappings."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date as Date
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="reports.json")
    parser.add_argument("--reports", default="reports")
    parser.add_argument("--root", default=".")
    parser.add_argument("--require", action="append", default=[], help="Required YYYY-MM-DD_HH-MM slot")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    index_path = root / args.index
    reports_dir = root / args.reports
    index = load(index_path)
    if not isinstance(index, list):
        raise SystemExit(f"{index_path}: expected an array")

    seen: set[tuple[str, str]] = set()
    keys: list[str] = []
    found: set[str] = set()
    for i, report in enumerate(index):
        if not isinstance(report, dict):
            raise SystemExit(f"{index_path}[{i}]: expected an object")
        date, time = str(report.get("date") or ""), str(report.get("time") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or time not in {"08:00", "12:00", "16:00", "21:00"}:
            raise SystemExit(f"{index_path}[{i}]: invalid report key {date} {time}")
        key = (date, time)
        if key in seen:
            raise SystemExit(f"duplicate report slot: {date} {time}")
        day = Date.fromisoformat(date)
        expected_title = f"マーケットレポート｜{day:%Y/%m/%d}（{'月火水木金土日'[day.weekday()]}）{time}"
        if report.get("title") != expected_title:
            raise SystemExit(f"report title does not match its JST slot: {date} {time}")
        seen.add(key)
        key_text = f"{date}_{time.replace(':', '-') }"
        keys.append(key_text)
        found.add(key_text)

        canonical_path = reports_dir / f"{key_text}.json"
        canonical = load(canonical_path) if canonical_path.is_file() else None
        if isinstance(canonical, dict) and not canonical.get("date"):
            canonical = canonical.get("latestReport") or canonical.get("report")
        if canonical != report:
            raise SystemExit(f"reports.json/canonical mismatch: {canonical_path}")

        full_text = str(report.get("fullText") or "")
        expected_hash = report.get("bodyHash")
        if expected_hash and hashlib.sha256(full_text.encode("utf-8")).hexdigest() != expected_hash:
            raise SystemExit(f"body hash mismatch: {date} {time}")

        image = report.get("infographic")
        if not image:
            continue
        expected_key = key_text
        expected_name = f"マーケットレポート_{key_text}.png"
        expected_src = f"images/reports/{key_text}.png"
        if image.get("slotKey") != expected_key:
            raise SystemExit(f"infographic slot key mismatch: report={date} {time}, image={image.get('slotKey')!r}")
        if image.get("sourceName") != expected_name or image.get("src") != expected_src:
            raise SystemExit(f"infographic source/path mismatch: {date} {time}")
        image_path = (root / expected_src).resolve()
        if root not in image_path.parents or not image_path.is_file():
            raise SystemExit(f"infographic file missing or outside repository: {expected_src}")
        data = image_path.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise SystemExit(f"infographic is not a PNG: {expected_src}")
        digest = hashlib.sha256(data).hexdigest()
        if image.get("sha256") != digest:
            raise SystemExit(f"infographic hash mismatch: {expected_src}")

    if keys != sorted(keys, reverse=True):
        raise SystemExit("reports.json is not ordered date descending, then time descending")
    missing = sorted(set(args.require) - found)
    if missing:
        raise SystemExit("required report slots missing from reports.json: " + ", ".join(missing))
    print(f"Verified {len(index)} indexed reports, canonical parity, descending order, and exact infographic mappings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
