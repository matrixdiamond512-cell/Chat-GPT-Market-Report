#!/usr/bin/env python3
"""Build CSV exports consumed by the ChatGPT market-data Google Sheets tabs.

A live 10-symbol acquisition is NOT a newly published 08:00 report. Repair the
report BTCUSD 24-hour change only for a matching-date, published 28-row morning
contract. In particular, never mutate an older data/latest-report.json while
refreshing live quotes; that also leaves a dirty Git working tree and prevents
scheduled acquisition from rebasing/pushing its genuinely fetched market data.
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


def published_morning_contract_matches_current_input(market_dir: Path) -> bool:
    """Do not run report mutations from the independent live-data pipeline."""
    report_path = ROOT / "data" / "latest-report.json"
    if not report_path.is_file():
        return False
    try:
        publication = load_json(report_path)
        report = publication.get("latestReport") or publication.get("report") or {}
        current_input = current_input_payload(market_dir)
        rows = (report.get("marketDataTable") or {}).get("rows") or []
        markets = current_input.get("markets") or {}
        bitcoin = markets.get("btcusd") or {}
        return bool(
            str(report.get("time") or "") == "08:00"
            and len(rows) == 28
            and len(markets) == 28
            and str(report.get("date") or "") == str(current_input.get("generatedAt") or "")[:10]
            and bitcoin.get("sourceId") == "published_report_previous_close_table"
        )
    except (OSError, ValueError, TypeError, AttributeError):
        return False


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
    if published_morning_contract_matches_current_input(MARKET_DIR):
        try:
            repair_btc_24h_change()
        except SystemExit as exc:
            if "BTCUSD report value is not numeric" in str(exc):
                print("BTCUSD repair skipped: published price is unavailable")
            else:
                raise
    else:
        print("BTCUSD report repair skipped: no matching published 28-row morning contract")
    latest_count, history_count = build_exports()
    print(f"Built ChatGPT market CSV exports: latest={latest_count}, history={history_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
