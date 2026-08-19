from __future__ import annotations

import json
import re
from pathlib import Path

REPORTS_DIR = Path("reports")
OUTPUT_FILE = Path("reports.json")
LATEST_FILE = Path("data/latest-report.json")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def validate_report(report: object, source: str) -> dict:
    if not isinstance(report, dict):
        raise ValueError(f"{source}: report must be a JSON object")

    required = {"date", "time", "title"}
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


def sync_latest_to_canonical() -> Path | None:
    """Guarantee that data/latest-report.json also exists as canonical history."""
    report = load_latest_report()
    if report is None:
        return None

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = canonical_path(report)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"

    if path.exists() and path.read_text(encoding="utf-8") == rendered:
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
