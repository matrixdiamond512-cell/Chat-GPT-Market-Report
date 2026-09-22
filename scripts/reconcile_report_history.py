from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path("reports")
INDEX_FILE = Path("reports.json")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def validate(report: dict, source: str) -> dict:
    if not isinstance(report, dict):
        raise ValueError(f"{source}: report must be an object")
    # Some older canonical files retain the latest-report.json envelope.
    # Normalize in memory without rewriting or discarding their original bytes.
    if not all(report.get(key) for key in ("date", "time", "title")):
        nested = report.get("latestReport")
        if isinstance(nested, dict) and all(nested.get(key) for key in ("date", "time", "title")):
            report = nested
    for key in ("date", "time", "title"):
        if not report.get(key):
            raise ValueError(f"{source}: missing {key}")
    if not DATE_PATTERN.fullmatch(str(report["date"])):
        raise ValueError(f"{source}: invalid date")
    if not TIME_PATTERN.fullmatch(str(report["time"])):
        raise ValueError(f"{source}: invalid time")
    return report


def slot(report: dict) -> tuple[str, str]:
    return str(report["date"]), str(report["time"])


def canonical_path(report: dict) -> Path:
    return REPORTS_DIR / f"{report['date']}_{str(report['time']).replace(':', '-')}.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _revision_number(report: dict) -> int | None:
    value = report.get("revision") or report.get("version")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _updated_at(report: dict) -> datetime | None:
    values = [
        report.get("updatedAt"),
        report.get("savedAt"),
        report.get("generatedAt"),
        (report.get("sourceDocument") or {}).get("updatedAt")
        if isinstance(report.get("sourceDocument"), dict)
        else None,
    ]
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def _should_replace(current: dict, incoming: dict, key: tuple[str, str]) -> bool:
    if current == incoming:
        return False

    current_revision = _revision_number(current)
    incoming_revision = _revision_number(incoming)
    if current_revision is not None or incoming_revision is not None:
        if incoming_revision is not None and (
            current_revision is None or incoming_revision > current_revision
        ):
            return True
        raise ValueError(
            f"refusing stale or ambiguous correction for {key[0]} {key[1]}: "
            f"incoming revision={incoming_revision!r}, canonical revision={current_revision!r}"
        )

    current_updated = _updated_at(current)
    incoming_updated = _updated_at(incoming)
    if current_updated is not None or incoming_updated is not None:
        if incoming_updated is not None and (
            current_updated is None or incoming_updated > current_updated
        ):
            return True
        raise ValueError(
            f"refusing stale or ambiguous correction for {key[0]} {key[1]}: "
            f"incoming updatedAt={incoming_updated!r}, canonical updatedAt={current_updated!r}"
        )

    raise ValueError(
        f"conflicting payloads for {key[0]} {key[1]}; "
        "add a monotonic revision or updatedAt before publishing a correction"
    )


def load_index() -> list[dict]:
    if not INDEX_FILE.exists():
        return []
    data = read_json(INDEX_FILE)
    if not isinstance(data, list):
        raise ValueError("reports.json must be an array")
    return [validate(item, f"reports.json[{i}]") for i, item in enumerate(data)]


def load_canonical() -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(REPORTS_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        report = validate(read_json(path), str(path))
        key = slot(report)
        if key in seen:
            raise ValueError(f"duplicate canonical slot: {key[0]} {key[1]}")
        seen.add(key)
        rows.append(report)
    return rows


def main() -> None:
    incoming = load_index()

    # Preserve missing direct-publication slots. Existing slots may be
    # corrected only with an explicit newer revision or timestamp; slot order
    # and body length are not version signals.
    for report in incoming:
        path = canonical_path(report)
        if not path.exists():
            write_report(path, report)
            print(f"Recovered missing canonical report: {path}")
        else:
            current = validate(read_json(path), str(path))
            if _should_replace(current, report, slot(report)):
                write_report(path, report)
                print(f"Updated canonical report from direct publication: {path}")

    canonical = load_canonical()
    canonical.sort(key=lambda item: f"{item['date']} {item['time']}", reverse=True)
    INDEX_FILE.write_text(
        json.dumps(canonical, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    index_keys = [slot(item) for item in canonical]
    file_keys = [slot(item) for item in load_canonical()]
    if set(index_keys) != set(file_keys):
        raise SystemExit("report history reconciliation failed")
    if len(index_keys) != len(set(index_keys)):
        raise SystemExit("duplicate slot detected after reconciliation")

    print(f"Reconciled {len(canonical)} canonical market-report slots.")


if __name__ == "__main__":
    main()
