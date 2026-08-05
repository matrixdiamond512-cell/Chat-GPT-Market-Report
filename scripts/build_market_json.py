#!/usr/bin/env python3
"""Merge independent market data into data/dashboard.json."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def attach_market_data(dashboard: dict[str, Any], market_data: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(dashboard)
    result["marketData"] = market_data
    result["marketDataUpdatedAt"] = market_data.get("generatedAt", "")
    sources = list(result.get("sources") or [])
    source_entry = {
        "id": "INDEPENDENT_MARKET_DATA",
        "name": "独立市場データ取得・検証基盤",
        "path": "data/market/latest.json",
        "asOf": market_data.get("generatedAt", ""),
        "status": market_data.get("overallStatus", "unknown"),
        "note": "価格カードと市場温度カードは、この検証済み市場データを本文解析より優先します。"
    }
    sources = [source for source in sources if source.get("id") != source_entry["id"]]
    sources.append(source_entry)
    result["sources"] = sources

    errors = list(result.get("errors") or [])
    if market_data.get("overallStatus") != "verified":
        errors.append(
            "市場データ取得基盤: "
            + market_data.get("overallStatus", "unknown")
            + " / missing="
            + ",".join(market_data.get("missingRequired") or [])
        )
    result["errors"] = errors

    latest_report = result.get("latestReport")
    if isinstance(latest_report, dict):
        latest_report = deepcopy(latest_report)
        latest_report["marketData"] = market_data
        result["latestReport"] = latest_report

    reports = result.get("reports")
    if isinstance(reports, list) and reports:
        reports = deepcopy(reports)
        current_key = result.get("currentReportKey") or ""
        for index, report in enumerate(reports):
            if index == 0 or f"{report.get('date', '')} {report.get('time', '')}" == current_key:
                report["marketData"] = market_data
                break
        result["reports"] = reports
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market-data", default=str(ROOT / "data" / "market" / "latest.json"))
    parser.add_argument("--dashboard", default=str(ROOT / "data" / "dashboard.json"))
    parser.add_argument("--allow-blocked", action="store_true")
    args = parser.parse_args()

    market_path = Path(args.market_data)
    dashboard_path = Path(args.dashboard)
    if not market_path.is_absolute():
        market_path = ROOT / market_path
    if not dashboard_path.is_absolute():
        dashboard_path = ROOT / dashboard_path

    market_data = load_json(market_path)
    if market_data.get("overallStatus") == "blocked" and not args.allow_blocked:
        raise SystemExit("Market data is blocked; refusing to update dashboard.json")

    dashboard = load_json(dashboard_path, {})
    merged = attach_market_data(dashboard, market_data)
    write_json(dashboard_path, merged)
    print(f"Updated {dashboard_path} with market data status {market_data.get('overallStatus')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
