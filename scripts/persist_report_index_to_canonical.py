from __future__ import annotations

import json
import re
from pathlib import Path

from reporting.publication_eligibility import is_publication_eligible

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


def canonical_reports() -> dict[tuple[str, str], dict]:
    reports: dict[tuple[str, str], dict] = {}
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
        if key in reports:
            raise ValueError(f"duplicate canonical report slot {key[0]} {key[1]}")
        reports[key] = report
    return reports


def validate_slot_sets(
    reports: list[dict],
    canonical_by_slot: dict[tuple[str, str], dict],
) -> None:
    """Permit only explicitly non-public canonical files outside the index."""
    index_keys = {slot_key(report) for report in reports}
    file_keys = set(canonical_by_slot)
    missing_files = index_keys - file_keys
    eligible_files_missing_from_index = {
        key for key in file_keys - index_keys
        if is_publication_eligible(canonical_by_slot[key])
    }
    if missing_files or eligible_files_missing_from_index:
        raise SystemExit(
            "refusing to persist reports.json to canonical files because slot sets differ: "
            f"missing_canonical={sorted(missing_files)}, "
            f"eligible_canonical_missing_from_index={sorted(eligible_files_missing_from_index)}"
        )


def main() -> None:
    reports = load_index()
    canonical_by_slot = canonical_reports()
    validate_slot_sets(reports, canonical_by_slot)

    for report in reports:
        canonical_path(report).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"Persisted {len(reports)} validated report slots to canonical files.")


if __name__ == "__main__":
    main()
