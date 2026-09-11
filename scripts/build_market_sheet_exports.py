#!/usr/bin/env python3
"""Build CSV exports consumed by the ChatGPT market-data Google Sheets tabs.

The current ChatGPT input prefers data/market/chatgpt-input.json.  That file is
built from the published 28-row table for 08:00 and from the independent market
snapshot for intraday slots.  This prevents the 08:00 sheet from collapsing back
to the old 10-row raw quote contract.

For the 08:00 report, BTCUSD is repaired immediately before export when a usable
published BTC price exists. If BTCUSD is explicitly unavailable, publication must
continue with the unavailable reason preserved instead of failing the whole report.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

try:
    from scripts.write_market_data_to_sheets import SHEET_HEADERS, market_rows
    from scripts.repair_btc_24h_change import main as repair_btc_24h_change
except ModuleNotFoundError:  # Direct execution: python scripts/build_market_sheet_exports.py
    from write_market_data_to_sheets import SHEET_HEADERS, market_rows
    from repair_btc_24h_change import main as repair_btc_24h_change


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


def current_input_payload(market_dir: Path) -> dict[str, Any]:
    report_input = market_dir / "chatgpt-input.json"
    if report_input.exists():
        payload = load_json(report_input)
        if isinstance(payload.get("markets"), dict) and payload.get("markets"):
            return payload
    return load_json(market_dir / "latest.json")


def build_exports(market_dir: Path = MARKET_DIR) -> tuple[int, int]:
    latest = current_input_payload(market_dir)
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
    # build_chatgpt_report_input.py runs immediately before this script in the
    # publication workflow. Repair BTCUSD only when the report contains a usable
    # numeric price. An explicit 取得不能 is valid under the publication contract
    # and must not abort the remaining dashboard/history synchronization.
    try:
        repair_btc_24h_change()
    except SystemExit as exc:
        message = str(exc)
        if "BTCUSD report value is not numeric" in message:
            print("BTCUSD 24h repair skipped: published BTCUSD is unavailable; preserving unavailable state")
        else:
            raise
    latest_count, history_count = build_exports()
    print(f"Built ChatGPT market CSV exports: latest={latest_count}, history={history_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
