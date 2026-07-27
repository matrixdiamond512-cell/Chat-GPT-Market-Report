from __future__ import annotations

import json
import re
from pathlib import Path

REPORTS_DIR = Path("reports")
OUTPUT_FILE = Path("reports.json")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def load_report(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    required = {"date", "time", "title"}
    missing = sorted(required - data.keys())
    if missing:
        raise ValueError(f"{path}: required fields missing: {', '.join(missing)}")

    if not DATE_PATTERN.fullmatch(str(data["date"])):
        raise ValueError(f"{path}: date must be YYYY-MM-DD")
    if not TIME_PATTERN.fullmatch(str(data["time"])):
        raise ValueError(f"{path}: time must be HH:MM")

    return data


def report_paths() -> list[Path]:
    return [
        path
        for path in sorted(REPORTS_DIR.glob("*.json"))
        if not path.name.startswith("_")
    ]


def main() -> None:
    reports = [load_report(path) for path in report_paths()]
    reports.sort(key=lambda item: f"{item['date']} {item['time']}", reverse=True)

    OUTPUT_FILE.write_text(
        json.dumps(reports, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Built {OUTPUT_FILE} from {len(reports)} report files.")


if __name__ == "__main__":
    main()
