#!/usr/bin/env python3
"""Build CSV exports consumed by the ChatGPT market-data Google Sheets tabs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

try:
    from scripts.write_market_data_to_sheets import SHEET_HEADERS, market_rows
except ModuleNotFoundError:  # Direct execution: python scripts/build_market_sheet_exports.py
    from write_market_data_to_sheets import SHEET_HEADERS, market_rows


ROOT = Path(__file__).resolve().parents[1]
MARKET_DIR = ROOT / "data" / "market"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_csv(path: Path, rows: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(SHEET_HEADERS)
        writer.writerows(rows)


def history_payloads(history_dir: Path) -> list[dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for path in sorted(history_dir.glob("*.json")):
        try:
            payload = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        generated_at = str(payload.get("generatedAt") or "")
        if generated_at and isinstance(payload.get("markets"), dict):
            payloads[generated_at] = payload
    return [payloads[key] for key in sorted(payloads)]


def build_exports(market_dir: Path = MARKET_DIR) -> tuple[int, int]:
    latest = load_json(market_dir / "latest.json")
    latest_rows = market_rows(latest)
    write_csv(market_dir / "chatgpt_input.csv", latest_rows)

    payloads = history_payloads(market_dir / "history")
    if not any(item.get("generatedAt") == latest.get("generatedAt") for item in payloads):
        payloads.append(latest)
    payloads.sort(key=lambda item: str(item.get("generatedAt") or ""))
    history_rows = [row for payload in payloads for row in market_rows(payload)]
    write_csv(market_dir / "verified_history.csv", history_rows)
    return len(latest_rows), len(history_rows)


def main() -> int:
    latest_count, history_count = build_exports()
    print(f"Built ChatGPT market CSV exports: latest={latest_count}, history={history_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
