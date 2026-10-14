from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from reconcile_latest_report_market_data import load_json
from report_identity import canonical_path as shared_canonical_path, slot_key as shared_slot_key
from report_source_contract import validate_saved_body

REPORTS_DIR = Path("reports")
OUTPUT_FILE = Path("reports.json")
LATEST_FILE = Path("data/latest-report.json")
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

    try:
        shared_slot_key(report)
    except ValueError as exc:
        raise ValueError(f"{source}: {exc}") from exc

    return report


def slot_key(report: dict) -> tuple[str, str]:
    return shared_slot_key(report)


def canonical_path(report: dict) -> Path:
    return shared_canonical_path(report, REPORTS_DIR)


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


_DERIVED_REPORT_FIELDS = {
    "marketData",
    "marketDataUpdatedAt",
    "marketDataTable",
    "markets",
    "dataProvenance",
    "structuredFromFullText",
    "structureVersion",
}


def _source_document_id(report: dict) -> str:
    source = report.get("sourceDocument")
    if isinstance(source, dict):
        return str(source.get("id") or "")
    return str(report.get("sourceDocId") or report.get("documentId") or "")


def _verified_source_revision(report: dict) -> None:
    """Require a verifiable original for a canonical correction/new report."""
    full_text = report.get("fullText")
    body_hash = str(report.get("bodyHash") or "")
    if _revision_number(report) is None:
        raise SystemExit("canonical update requires a monotonic source revision")
    if not _source_document_id(report) or not isinstance(full_text, str) or not full_text.strip():
        raise SystemExit("canonical update requires a source document ID and fullText")
    if not body_hash or body_hash != hashlib.sha256(full_text.encode("utf-8")).hexdigest():
        raise SystemExit("canonical update blocked: source body hash is missing or mismatched")
    try:
        validate_saved_body(report)
    except (KeyError, ValueError) as exc:
        raise SystemExit(f"canonical update blocked: source verification failed: {exc}") from exc


def _choose_canonical_update(current: dict, incoming: dict, source: str) -> str:
    """Return write/keep while protecting same-revision source identity.

    Derived structured values can be refreshed independently, but are never
    merged into a report revision. Conflicts in source content remain blocked.
    """
    if current == incoming:
        return "keep"

    current_revision = _revision_number(current)
    incoming_revision = _revision_number(incoming)
    if current_revision is not None and incoming_revision == current_revision:
        same_source_id = bool(_source_document_id(current)) and (
            _source_document_id(current) == _source_document_id(incoming)
        )
        same_body_hash = bool(current.get("bodyHash")) and (
            current.get("bodyHash") == incoming.get("bodyHash")
        )
        same_body = bool(current.get("fullText")) and (
            current.get("fullText") == incoming.get("fullText")
        )
        if same_source_id and same_body_hash and same_body:
            _verified_source_revision(current)
            _verified_source_revision(incoming)
            current_contract = {k: v for k, v in current.items() if k not in _DERIVED_REPORT_FIELDS}
            incoming_contract = {k: v for k, v in incoming.items() if k not in _DERIVED_REPORT_FIELDS}
            if current_contract == incoming_contract:
                return "keep"
        raise SystemExit(
            f"same-revision canonical conflict for {source}: "
            "source ID, body hash, body text, or canonical content differs"
        )

    if current_revision is not None or incoming_revision is not None:
        if incoming_revision is None or current_revision is None or incoming_revision < current_revision:
            raise SystemExit(
                f"refusing ambiguous canonical overwrite for {source}: "
                f"incoming revision {incoming_revision!r} is not newer than "
                f"canonical revision {current_revision!r}"
            )
        if _source_document_id(current) != _source_document_id(incoming):
            raise SystemExit(f"canonical update blocked for {source}: source document ID changed")
        _verified_source_revision(incoming)
        return "write"

    raise SystemExit(
        f"conflicting payloads for canonical report slot {source}; "
        "add a verified newer revision before publishing a correction"
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
    else:
        _verified_source_revision(report)

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


def load_canonical_reports(
    previous_by_slot: dict[tuple[str, str], dict] | None = None,
) -> list[dict]:
    reports: list[dict] = []
    seen: dict[tuple[str, str], Path] = {}

    for path in report_paths():
        data = json.loads(path.read_text(encoding="utf-8"))
        report = validate_report(data, str(path))
        key = slot_key(report)
        previous = (previous_by_slot or {}).get(key)
        legacy_unchanged = previous == report
        full_text = report.get("fullText")
        if not isinstance(full_text, str) or not full_text.strip():
            if not legacy_unchanged:
                raise ValueError(f"{path}: new report is missing required fullText")
        elif not full_text.startswith(str(report.get("title") or "")) and not legacy_unchanged:
            raise ValueError(f"{path}: new report title/fullText mismatch")
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


def verify_no_history_loss(
    previous_keys: set[tuple[str, str]],
    previous_by_slot: dict[tuple[str, str], dict],
) -> None:
    rebuilt_payload = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    rebuilt_reports = [
        validate_report(item, f"{OUTPUT_FILE}[{index}]")
        for index, item in enumerate(rebuilt_payload)
    ]
    rebuilt_keys = {slot_key(report) for report in rebuilt_reports}

    canonical_reports = load_canonical_reports(previous_by_slot)
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--canonical-only",
        action="store_true",
        help=(
            "Rebuild reports.json strictly from canonical report files without "
            "re-importing data/latest-report.json. Intended for the post-persistence "
            "verification pass after reports.json has already been structured and "
            "persisted to canonical files."
        ),
    )
    args = parser.parse_args()

    # Index construction must not change the saved report's content/revision.
    previous_index = load_existing_index()
    previous_keys = {slot_key(report) for report in previous_index}

    if args.canonical_only:
        latest_path = None
        backfilled: list[Path] = []
    else:
        latest_path = sync_latest_to_canonical()
        backfilled = backfill_missing_canonical_files(previous_index)

    previous_by_slot = {slot_key(report): report for report in previous_index}
    reports = load_canonical_reports(previous_by_slot)
    write_index(reports)
    verify_no_history_loss(previous_keys, previous_by_slot)

    if not args.canonical_only:
        verify_latest_is_published()

    print(
        f"Built {OUTPUT_FILE} from {len(reports)} canonical report files; "
        f"mode={'canonical-only' if args.canonical_only else 'latest-sync'}; "
        f"latest={'skipped' if args.canonical_only else ('synced' if latest_path else 'absent')}; "
        f"backfilled {len(backfilled)} legacy slot(s); no report history lost."
    )


if __name__ == "__main__":
    main()
