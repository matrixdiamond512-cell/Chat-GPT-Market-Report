#!/usr/bin/env python3
"""Run one configured market-data source without persisting quote values."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if __package__:
    from scripts import fetch_market_data as market_data
else:
    sys.path.insert(0, str(ROOT / "scripts"))
    import fetch_market_data as market_data  # noqa: E402


def validate(symbol_id: str, source_id: str) -> dict[str, Any]:
    config = market_data.load_json(ROOT / "config" / "market_data_sources.json", {})
    validation_config = market_data.load_json(ROOT / "config" / "market_data_validation.json", {})
    symbol = (config.get("symbols") or {}).get(symbol_id)
    if not symbol:
        raise ValueError(f"unknown configured symbol: {symbol_id}")
    source = next((item for item in symbol.get("sources", []) if item.get("id") == source_id), None)
    if not source:
        raise ValueError(f"source {source_id!r} is not configured for {symbol_id}")
    fetcher = market_data.FETCHERS.get(str(source.get("kind") or ""))
    if not fetcher:
        raise ValueError(f"unsupported source kind: {source.get('kind')}")

    raw = fetcher(source)
    checks = dict((validation_config.get("defaults") or {}))
    checks.update((validation_config.get("symbols") or {}).get(symbol_id, {}))
    ok, code, _reason = market_data.validate_candidate(symbol_id, symbol, checks, raw, None)
    timestamp = market_data.parse_iso(raw.get("asOf"))
    now = market_data.now_jst()
    not_future_dated = bool(timestamp and timestamp <= now)
    valid = ok and not_future_dated
    return {
        "symbol": symbol_id,
        "sourceId": source_id,
        "status": "verified" if valid else "rejected",
        "asOf": raw.get("asOf"),
        "marketDate": timestamp.date().isoformat() if timestamp else None,
        "valuePresent": raw.get("value") is not None,
        "sourceMatches": raw.get("sourceId") == source_id,
        "notFutureDated": not_future_dated,
        "validationCode": "OK" if valid else "FUTURE_DATE" if ok else code,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--source-id", required=True)
    args = parser.parse_args()
    try:
        result = validate(args.symbol, args.source_id)
    except (ValueError, market_data.FetchError) as exc:
        code = exc.code if isinstance(exc, market_data.FetchError) else "CONFIGURATION_ERROR"
        print(json.dumps({"symbol": args.symbol, "sourceId": args.source_id, "status": "failed", "errorCode": code}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "verified" and result["notFutureDated"] and result["valuePresent"] and result["sourceMatches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

