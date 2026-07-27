from __future__ import annotations

import json
from pathlib import Path

REPORTS_DIR = Path("reports")
OUTPUT_FILE = Path("reports.json")


def load_report(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    required = {"date", "time", "title"}
    missing = sorted(required - data.keys())
    if missing:
        raise ValueError(f"{path}: required fields missing: {', '.join(missing)}")

    return data


def main() -> None:
    reports = [load_report(path) for path in sorted(REPORTS_DIR.glob("*.json"))]
    reports.sort(key=lambda item: f"{item['date']} {item['time']}", reverse=True)

    OUTPUT_FILE.write_text(
        json.dumps(reports, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Built {OUTPUT_FILE} from {len(reports)} report files.")


if __name__ == "__main__":
    main()
