from __future__ import annotations

import json
import re
from pathlib import Path

REPORTS_DIR = Path("reports")
INDEX_FILE = Path("reports.json")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def validate_report(report: object, source: str) -> dict:
    if not isinstance(report, dict):
        raise ValueError(f"{source}: report must be a JSON object")
    for key in ("date", "time", "title"):
        if not report.get(key):
            raise ValueError(f"{source}: missing required field {key}")
    if not DATE_PATTERN.fullmatch(str(report["date"])):
        raise ValueError(f"{source}: date must be YYYY-MM-DD")
    if not TIME_PATTERN.fullmatch(str(report["time"])):
        raise ValueError(f"{source}: time must be HH:MM")
    return report


def slot_key(report: dict) -> tuple[str, str]:
    return str(report["date"]), str(report["time"])


def canonical_path(report: dict) -> Path:
    date, time = slot_key(report)
    return REPORTS_DIR / f"{date}_{time.replace(':', '-')}.json"


def load_index() -> list[dict]:
    payload = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{INDEX_FILE}: root must be a JSON array")

    reports: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(payload):
        report = validate_report(item, f"{INDEX_FILE}[{index}]")
        key = slot_key(report)
        if key in seen:
            raise ValueError(f"{INDEX_FILE}: duplicate report slot {key[0]} {key[1]}")
        seen.add(key)
        reports.append(report)
    return reports


def canonical_keys() -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for path in sorted(REPORTS_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        report = validate_report(
            json.loads(path.read_text(encoding="utf-8")),
            str(path),
        )
        key = slot_key(report)
        if path != canonical_path(report):
            raise ValueError(
                f"{path}: canonical filename mismatch; expected {canonical_path(report)}"
            )
        if key in keys:
            raise ValueError(f"duplicate canonical report slot {key[0]} {key[1]}")
        keys.add(key)
    return keys


def main() -> None:
    reports = load_index()
    index_keys = {slot_key(report) for report in reports}
    file_keys = canonical_keys()

    if index_keys != file_keys:
        raise SystemExit(
            "refusing to persist reports.json to canonical files because slot sets differ: "
            f"only_in_index={sorted(index_keys - file_keys)}, "
            f"only_in_files={sorted(file_keys - index_keys)}"
        )

    for report in reports:
        canonical_path(report).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"Persisted {len(reports)} validated report slots to canonical files.")


if __name__ == "__main__":
    main()
