from __future__ import annotations

import json
import re
from pathlib import Path

REPORTS_DIR = Path("reports")
OUTPUT_FILE = Path("reports.json")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def validate_report(report: dict, source: str) -> dict:
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


def canonical_path(report: dict) -> Path:
    return REPORTS_DIR / f"{report['date']}_{str(report['time']).replace(':', '-')}.json"


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_index() -> list[dict]:
    if not OUTPUT_FILE.exists():
        return []
    payload = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{OUTPUT_FILE}: root must be a JSON array")
    return [validate_report(report, f"{OUTPUT_FILE}[{i}]") for i, report in enumerate(payload)]


def load_canonical_reports() -> list[dict]:
    reports: list[dict] = []
    seen: dict[tuple[str, str], Path] = {}
    for path in sorted(REPORTS_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        report = validate_report(json.loads(path.read_text(encoding="utf-8")), str(path))
        key = (str(report["date"]), str(report["time"]))
        if key in seen:
            raise ValueError(f"duplicate report slot {key[0]} {key[1]}: {seen[key]} and {path}")
        seen[key] = path
        reports.append(report)
    return reports


def synchronize() -> None:
    # The index is the incoming publication. Persist every entry first, but do
    # not delete canonical files that are absent from the index. This means a
    # later report cannot erase an older time slot simply by rebuilding the
    # index from an incomplete list.
    index_reports = load_index()
    for report in index_reports:
        write_report(canonical_path(report), report)

    canonical_reports = load_canonical_reports()
    canonical_reports.sort(key=lambda item: f"{item['date']} {item['time']}", reverse=True)
    OUTPUT_FILE.write_text(
        json.dumps(canonical_reports, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    index_keys = {(str(r["date"]), str(r["time"])) for r in canonical_reports}
    file_keys = {
        (str(r["date"]), str(r["time"]))
        for r in load_canonical_reports()
    }
    if index_keys != file_keys:
        missing_in_index = sorted(file_keys - index_keys)
        missing_in_files = sorted(index_keys - file_keys)
        raise SystemExit(
            f"report history mismatch: missing_in_index={missing_in_index}, missing_in_files={missing_in_files}"
        )

    print(f"Synchronized {len(canonical_reports)} market report slots without deleting history.")


if __name__ == "__main__":
    synchronize()
