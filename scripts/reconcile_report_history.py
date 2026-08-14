from __future__ import annotations

import json
import re
from pathlib import Path

REPORTS_DIR = Path("reports")
INDEX_FILE = Path("reports.json")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def validate(report: dict, source: str) -> dict:
    if not isinstance(report, dict):
        raise ValueError(f"{source}: report must be an object")
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

    # A direct publisher may update reports.json without writing a canonical
    # reports/YYYY-MM-DD_HH-MM.json file. Preserve every missing incoming slot.
    # For the newest incoming slot only, also carry the latest edited payload
    # into its canonical file so a richer direct publication is not lost.
    newest_key = slot(incoming[0]) if incoming else None
    for report in incoming:
        path = canonical_path(report)
        if not path.exists():
            write_report(path, report)
            print(f"Recovered missing canonical report: {path}")
        elif newest_key == slot(report):
            current = validate(read_json(path), str(path))
            if current != report:
                write_report(path, report)
                print(f"Updated newest canonical report from direct publication: {path}")

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
