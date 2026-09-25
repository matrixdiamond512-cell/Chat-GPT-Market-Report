from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from reconcile_latest_report_market_data import load_json, update_latest_report

REPORTS_DIR = Path("reports")
OUTPUT_FILE = Path("reports.json")
LATEST_FILE = Path("data/latest-report.json")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def validate_report(report: object, source: str) -> dict:
    if not isinstance(report, dict):
        raise ValueError(f"{source}: report must be a JSON object")

    required = {"date", "time", "title"}
    # Accept historical report files that were accidentally stored in the
    # data/latest-report.json envelope, while normalizing them in memory to
    # the same canonical report object used by reports.json.
    if not required.issubset(report.keys()):
        nested = report.get("latestReport")
        if isinstance(nested, dict) and required.issubset(nested.keys()):
            report = nested

    missing = sorted(required - report.keys())
    if missing:
        raise ValueError(f"{source}: required fields missing: {', '.join(missing)}")

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


def report_paths() -> list[Path]:
    return [
        path
        for path in sorted(REPORTS_DIR.glob("*.json"))
        if not path.name.startswith("_")
    ]


def load_latest_report() -> dict | None:
    if not LATEST_FILE.exists():
        return None

    payload = json.loads(LATEST_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{LATEST_FILE}: root must be a JSON object")

    report = payload.get("latestReport", payload)
    return validate_report(report, str(LATEST_FILE))


def _revision_number(report: dict) -> int | None:
    value = report.get("revision") or report.get("version")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _updated_at(report: dict) -> datetime | None:
    candidates: list[Any] = [
        report.get("updatedAt"),
        report.get("savedAt"),
        report.get("generatedAt"),
        (report.get("sourceDocument") or {}).get("updatedAt")
        if isinstance(report.get("sourceDocument"), dict)
        else None,
    ]
    for value in candidates:
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def _choose_canonical_update(current: dict, incoming: dict, source: str) -> str:
    """Return write/keep, refusing ambiguous same-slot overwrites.

    A report slot is an identity, not a merge key. When two payloads for the
    same slot differ, only an explicit newer revision or timestamp can replace
    the canonical payload. This prevents a stale latest-report file from
    silently erasing a correction.
    """
    if current == incoming:
        return "keep"

    current_revision = _revision_number(current)
    incoming_revision = _revision_number(incoming)
    if current_revision is not None or incoming_revision is not None:
        if incoming_revision is None or (
            current_revision is not None and incoming_revision <= current_revision
        ):
            raise SystemExit(
                f"refusing ambiguous canonical overwrite for {source}: "
                f"incoming revision {incoming_revision!r} is not newer than "
                f"canonical revision {current_revision!r}"
            )
        return "write"

    current_updated = _updated_at(current)
    incoming_updated = _updated_at(incoming)
    if current_updated is not None or incoming_updated is not None:
        if incoming_updated is None or (
            current_updated is not None and incoming_updated <= current_updated
        ):
            raise SystemExit(
                f"refusing ambiguous canonical overwrite for {source}: "
                f"incoming updatedAt {incoming_updated!r} is not newer than "
                f"canonical updatedAt {current_updated!r}"
            )
        return "write"

    raise SystemExit(
        f"conflicting payloads for canonical report slot {source}; "
        "add a monotonic revision or updatedAt before publishing a correction"
    )


def sync_latest_to_canonical() -> Path | None:
    """Guarantee that data/latest-report.json also exists as canonical history."""
    report = load_latest_report()
    if report is None:
        return None

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = canonical_path(report)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"

    if path.exists():
        current = validate_report(
            json.loads(path.read_text(encoding="utf-8")), str(path)
        )
        decision = _choose_canonical_update(current, report, str(path))
        if decision == "keep":
            print(f"Latest report already archived: {path}")
            return path

    path.write_text(rendered, encoding="utf-8")
    print(f"Synchronized latest report into canonical history: {path}")
    return path


def load_existing_index() -> list[dict]:
    if not OUTPUT_FILE.exists():
        return []

    payload = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{OUTPUT_FILE}: root must be a JSON array")

    reports: list[dict] = []
    seen: dict[tuple[str, str], int] = {}
    for index, item in enumerate(payload):
        report = validate_report(item, f"{OUTPUT_FILE}[{index}]")
        key = slot_key(report)
        if key in seen:
            raise ValueError(
                f"{OUTPUT_FILE}: duplicate report slot {key[0]} {key[1]} "
                f"at indexes {seen[key]} and {index}"
            )
        seen[key] = index
        reports.append(report)

    return reports


def backfill_missing_canonical_files(index_reports: list[dict]) -> list[Path]:
    """Migrate index-only legacy reports without overwriting canonical reports."""
    created: list[Path] = []
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    for report in index_reports:
        path = canonical_path(report)
        if path.exists():
            continue

        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        created.append(path)
        print(f"Backfilled legacy report slot into {path}.")

    return created


def load_canonical_reports() -> list[dict]:
    reports: list[dict] = []
    seen: dict[tuple[str, str], Path] = {}

    for path in report_paths():
        data = json.loads(path.read_text(encoding="utf-8"))
        report = validate_report(data, str(path))
        key = slot_key(report)
        expected_path = canonical_path(report)

        if path != expected_path:
            raise ValueError(
                f"{path}: canonical filename mismatch; expected {expected_path}"
            )

        if key in seen:
            raise ValueError(
                f"duplicate report slot {key[0]} {key[1]}: {seen[key]} and {path}"
            )

        seen[key] = path
        reports.append(report)

    return reports


def write_index(reports: list[dict]) -> None:
    reports.sort(
        key=lambda item: f"{item['date']} {item['time']}",
        reverse=True,
    )
    OUTPUT_FILE.write_text(
        json.dumps(reports, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def verify_no_history_loss(previous_keys: set[tuple[str, str]]) -> None:
    rebuilt_payload = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    rebuilt_reports = [
        validate_report(item, f"{OUTPUT_FILE}[{index}]")
        for index, item in enumerate(rebuilt_payload)
    ]
    rebuilt_keys = {slot_key(report) for report in rebuilt_reports}

    canonical_reports = load_canonical_reports()
    canonical_keys = {slot_key(report) for report in canonical_reports}

    if rebuilt_keys != canonical_keys:
        missing_in_index = sorted(canonical_keys - rebuilt_keys)
        missing_in_files = sorted(rebuilt_keys - canonical_keys)
        raise SystemExit(
            "report history mismatch after rebuild: "
            f"missing_in_index={missing_in_index}, "
            f"missing_in_files={missing_in_files}"
        )

    lost_previous_slots = sorted(previous_keys - rebuilt_keys)
    if lost_previous_slots:
        raise SystemExit(
            "refusing to publish reports.json because previous report slots "
            f"would be lost: {lost_previous_slots}"
        )


def verify_latest_is_published() -> None:
    latest = load_latest_report()
    if latest is None:
        return

    key = slot_key(latest)
    path = canonical_path(latest)
    if not path.exists():
        raise SystemExit(f"latest report missing canonical file: {path}")

    canonical = validate_report(
        json.loads(path.read_text(encoding="utf-8")), str(path)
    )
    if canonical != latest:
        raise SystemExit(f"latest/canonical mismatch for {key[0]} {key[1]}")

    index = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    matches = [item for item in index if slot_key(item) == key]
    if len(matches) != 1:
        raise SystemExit(
            f"latest report must appear exactly once in reports.json: {key[0]} {key[1]}"
        )
    if matches[0] != latest:
        raise SystemExit(f"latest/index mismatch for {key[0]} {key[1]}")

    print(f"Latest publication verified end-to-end: {key[0]} {key[1]}")


def main() -> None:
    # Index construction must not change the saved report's content/revision.
    previous_index = load_existing_index()
    previous_keys = {slot_key(report) for report in previous_index}

    latest_path = sync_latest_to_canonical()
    backfilled = backfill_missing_canonical_files(previous_index)
    reports = load_canonical_reports()
    write_index(reports)
    verify_no_history_loss(previous_keys)
    verify_latest_is_published()

    print(
        f"Built {OUTPUT_FILE} from {len(reports)} canonical report files; "
        f"latest={'synced' if latest_path else 'absent'}; "
        f"backfilled {len(backfilled)} legacy slot(s); no report history lost."
    )


if __name__ == "__main__":
    main()
