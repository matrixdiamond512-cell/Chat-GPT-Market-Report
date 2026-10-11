#!/usr/bin/env python3
"""Normalize previously acquired private Sheets rows for one historical report.

The input is a values export of Personal_Report_Ready and
Personal_Reference_Values plus the matching structured detailed report. It does
not fetch data. The resulting snapshot retains per-observation lineage and marks
continuous futures closes as references unless settlement evidence is explicit.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.build_chatgpt_report_input import ITEMS

JST = dt.timezone(dt.timedelta(hours=9))
DERIVATIVE_TYPES = {"continuous_futures", "futures_cme", "futures_ose"}
READY_COLUMNS = [
    "Snapshot ID", "Report Field", "Observed Value", "Unit", "Market Type",
    "Market Session", "Source Market Date", "Bar Anchor (UTC)", "Source",
    "Verification Basis", "Status", "Retrieved At (UTC)",
]
REFERENCE_COLUMNS = [
    "Snapshot ID", "Report Field", "Observed Value", "Unit", "TradingView Symbol",
    "Reference Type", "Market Session", "Source Market Date", "Bar Anchor (UTC)",
    "Source", "Use Status", "Settlement Evidence", "Retrieved At (UTC)",
]
READY_MAP = {
    "dow": "dow", "nasdaq": "nasdaq", "sp500": "sp500", "russell2000": "russell2000",
    "usdjpy": "usdjpy", "eurusd": "eurusd", "btcusd": "btcusd", "vix": "vix", "us10y": "us10y",
    "nikkei225_cash": "nikkei225_cash", "nikkei_vi": "nikkei_vi",
    "nikkei225_dev25": "nikkei225_dev25", "nikkei225_dev200": "nikkei225_dev200",
    "nikkei225_per": "nikkei225_per", "nikkei225_pbr": "nikkei225_pbr", "nikkei225_eps": "nikkei225_eps",
}
ACCEPTED_SOURCE_UNITS = {
    "usdjpy": {"JPY per USD"}, "eurusd": {"USD per EUR"},
}
REFERENCE_MAP = {
    "gold": "gold", "wti": "wti", "nikkei225_futures_ose": "nikkei225_futures_ose",
    "cme_nikkei225_jpy": "nikkei225_futures_cme_yen",
    "cme_nikkei225_usd": "nikkei225_futures_cme_usd",
}


class SnapshotError(ValueError):
    pass


def _parse_date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        return dt.date.fromisoformat(text[:10]).isoformat()
    except ValueError as exc:
        raise SnapshotError("source row has invalid market date") from exc


def _parse_timestamp(value: Any) -> str:
    text = str(value or "").strip()
    try:
        stamp = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SnapshotError("source row has invalid retrieval timestamp") from exc
    if stamp.tzinfo is None:
        raise SnapshotError("source retrieval timestamp must include a timezone")
    return stamp.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _indexed_rows(matrix: Any, expected: list[str]) -> list[dict[str, Any]]:
    if not isinstance(matrix, list) or not matrix:
        raise SnapshotError("source sheet values are empty")
    headers = list(matrix[0])
    missing = [column for column in expected if column not in headers]
    if missing:
        raise SnapshotError("source sheet headers do not match the known schema")
    return [dict(zip(headers, row)) for row in matrix[1:] if isinstance(row, list) and any(v not in (None, "") for v in row)]


def build_snapshot(source: dict[str, Any], generated_at: str) -> dict[str, Any]:
    ready = _indexed_rows(source.get("reportReadyValues"), READY_COLUMNS)
    references = _indexed_rows(source.get("referenceValues"), REFERENCE_COLUMNS)
    # Analysis prose is generated later from this exact snapshot. Do not require or
    # attach a prior report body: its timestamp may differ from the quote records.
    if not ready or not references:
        raise SnapshotError("both acquired verified rows and futures references are required")

    items_by_id = {symbol: (label, unit, market_type, session) for label, symbol, unit, market_type, session in ITEMS}
    markets: dict[str, dict[str, Any]] = {
        symbol: {
            "id": symbol, "displayName": label, "unit": unit, "marketType": market_type,
            "session": session, "value": None, "displayValue": "—", "asOf": "",
            "verificationStatus": "unavailable", "sourceName": "", "fetchedAt": "",
        }
        for label, symbol, unit, market_type, session in ITEMS
    }
    max_retrieved: dt.datetime | None = None
    date_values: list[str] = []
    seen_ids: set[str] = set()

    for row in ready:
        source_id = str(row.get("Report Field") or "")
        symbol = READY_MAP.get(source_id)
        evidence_status = str(row.get("Status") or "")
        if not symbol or evidence_status not in {"VERIFIED", "VERIFIED_MANUAL"}:
            continue
        if symbol in seen_ids:
            raise SnapshotError("duplicate observation for one report field")
        seen_ids.add(symbol)
        label, expected_unit, market_type, session = items_by_id[symbol]
        if str(row.get("Unit") or "") != expected_unit and str(row.get("Unit") or "") not in ACCEPTED_SOURCE_UNITS.get(symbol, set()):
            raise SnapshotError("verified source unit does not match its report field")
        try:
            value = float(row["Observed Value"])
        except (ValueError, TypeError, KeyError) as exc:
            raise SnapshotError("verified source value is not numeric") from exc
        market_date = _parse_date(row.get("Source Market Date"))
        retrieved = _parse_timestamp(row.get("Retrieved At (UTC)"))
        retrieved_dt = dt.datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
        if market_date > retrieved_dt.astimezone(JST).date().isoformat():
            raise SnapshotError("market observation is future-dated relative to retrieval")
        max_retrieved = max(max_retrieved, retrieved_dt) if max_retrieved else retrieved_dt
        date_values.append(market_date)
        markets[symbol].update({
            "value": value, "displayValue": str(row["Observed Value"]),
            "unit": str(row["Unit"]), "marketType": str(row.get("Market Type") or market_type),
            "session": str(row.get("Market Session") or session), "asOf": market_date,
            "fetchedAt": retrieved, "sourceId": (
                "us_treasury_yield_curve" if source_id == "us10y" else
                "manual_official_nikkei" if evidence_status == "VERIFIED_MANUAL" else
                "tradingview_official_mcp"
            ),
            "sourceName": str(row.get("Source") or ""), "verificationStatus": "verified",
            "verificationBasis": (
                ("Operator reviewed the manual source date and value. " if evidence_status == "VERIFIED_MANUAL" else "")
                + str(row.get("Verification Basis") or "")
            ),
            "barAnchorUTC": str(row.get("Bar Anchor (UTC)") or ""),
            "snapshotId": str(row.get("Snapshot ID") or ""), "note": "",
        })

    for row in references:
        source_id = str(row.get("Report Field") or "")
        symbol = REFERENCE_MAP.get(source_id)
        if not symbol or str(row.get("Use Status") or "") != "REFERENCE_ONLY":
            continue
        if symbol in seen_ids:
            raise SnapshotError("duplicate observation for one report field")
        seen_ids.add(symbol)
        _, _, market_type, _ = items_by_id[symbol]
        try:
            value = float(row["Observed Value"])
        except (ValueError, TypeError, KeyError) as exc:
            raise SnapshotError("reference value is not numeric") from exc
        market_date = _parse_date(row.get("Source Market Date"))
        retrieved = _parse_timestamp(row.get("Retrieved At (UTC)"))
        retrieved_dt = dt.datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
        if market_date > retrieved_dt.astimezone(JST).date().isoformat():
            raise SnapshotError("market observation is future-dated relative to retrieval")
        max_retrieved = max(max_retrieved, retrieved_dt) if max_retrieved else retrieved_dt
        date_values.append(market_date)
        settlement = str(row.get("Settlement Evidence") or "")
        markets[symbol].update({
            "value": value, "displayValue": str(row["Observed Value"]), "unit": str(row["Unit"]),
            "marketType": market_type, "session": str(row.get("Market Session") or ""),
            "asOf": market_date, "fetchedAt": retrieved,
            "sourceId": "tradingview_official_mcp", "sourceName": str(row.get("Source") or ""),
            "verificationStatus": "reference_only", "referenceOnly": True,
            "priceType": "continuous_bar_close", "referenceType": str(row.get("Reference Type") or ""),
            "verificationBasis": settlement, "barAnchorUTC": str(row.get("Bar Anchor (UTC)") or ""),
            "snapshotId": str(row.get("Snapshot ID") or ""), "symbol": str(row.get("TradingView Symbol") or ""),
            "note": "連続足の終値。限月別の公式清算値は未確認。",
        })

    if len([m for m in markets.values() if m.get("verificationStatus") == "verified"]) < 9:
        raise SnapshotError("at least the nine previously verified report-ready observations are required")
    if len([m for m in markets.values() if m.get("referenceOnly")]) < 5:
        raise SnapshotError("at least the five separately labeled futures references are required")
    if max_retrieved is None:
        raise SnapshotError("no dated observations were loaded")

    min_date, max_date = min(date_values), max(date_values)
    generated = _parse_timestamp(generated_at)
    snapshot_basis = "\n".join(sorted(f"{key}|{value.get('snapshotId')}|{value.get('asOf')}|{value.get('value')}" for key, value in markets.items() if value.get("value") is not None))
    snapshot_id = hashlib.sha256(snapshot_basis.encode("utf-8")).hexdigest()[:24]
    return {
        "schemaVersion": "1.0.0", "snapshotId": snapshot_id,
        "generatedAt": generated, "sourceSnapshotRetrievedAt": max_retrieved.isoformat().replace("+00:00", "Z"),
        "reportDate": f"{min_date}〜{max_date}", "dataDateRange": f"{min_date}〜{max_date}",
        "reportSlot": "履歴再構成", "overallStatus": "historical_only", "historicalSnapshot": True,
        "sourceSheet": {"reportReadyTab": "Personal_Report_Ready", "referenceTab": "Personal_Reference_Values"},
        "markets": markets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--generated-at", required=True)
    args = parser.parse_args()
    try:
        source = json.loads(args.input.read_text(encoding="utf-8"))
        payload = build_snapshot(source, args.generated_at)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        counts = {
            "verifiedCount": sum(m.get("verificationStatus") == "verified" for m in payload["markets"].values()),
            "referenceCount": sum(bool(m.get("referenceOnly")) for m in payload["markets"].values()),
            "unavailableCount": sum(m.get("value") is None for m in payload["markets"].values()),
            "snapshotId": payload["snapshotId"], "dataDateRange": payload["dataDateRange"],
        }
        print(json.dumps(counts, ensure_ascii=False))
        return 0
    except (OSError, json.JSONDecodeError, SnapshotError) as exc:
        print(json.dumps({"status": "failed", "errorCode": type(exc).__name__}), file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

