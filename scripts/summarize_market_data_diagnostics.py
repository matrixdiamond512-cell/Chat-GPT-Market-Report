#!/usr/bin/env python3
"""Print acquisition diagnostics without emitting market quote values."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def summarize(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    markets = payload.get("markets") or {}
    errors_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for error in payload.get("errors") or []:
        symbol_id = str(error.get("symbol") or "")
        errors_by_symbol.setdefault(symbol_id, []).append(
            {
                "sourceId": str(error.get("sourceId") or ""),
                "code": str(error.get("code") or "UNKNOWN_ERROR"),
                "attempt": error.get("attempt"),
            }
        )

    rows = []
    for symbol_id, definition in (config.get("symbols") or {}).items():
        if not definition.get("required", True):
            continue
        market = markets.get(symbol_id) or {}
        source_errors = errors_by_symbol.get(symbol_id, [])
        codes = {item["code"] for item in source_errors}
        fallback_used = bool(market.get("fallbackUsed"))
        if fallback_used and "SOURCE_DIVERGENCE" in codes:
            cause = "FALLBACK_AFTER_SOURCE_DIVERGENCE"
        elif fallback_used and source_errors:
            cause = "FALLBACK_AFTER_SOURCE_ERRORS"
        elif market.get("verificationStatus") == "unavailable":
            cause = "NO_CURRENT_SOURCE_PASSED_VALIDATION"
        else:
            cause = None
        rows.append(
            {
                "id": symbol_id,
                "routeConnected": bool(definition.get("sources")),
                "status": str(market.get("verificationStatus") or "missing"),
                "freshnessStatus": str(market.get("freshnessStatus") or "unknown"),
                "asOf": market.get("asOf"),
                "sourceId": str(market.get("sourceId") or ""),
                "fallbackUsed": fallback_used,
                "hasValue": market.get("value") is not None,
                "acquisitionResult": "SUCCESS" if market.get("verificationStatus") == "verified" and not fallback_used else "FAILED",
                "validationResult": "PASS" if market.get("verificationStatus") == "verified" and not fallback_used else "NOT_CURRENTLY_VERIFIED",
                "persistenceResult": "NOT_ATTEMPTED_BY_COLLECTOR",
                "diagnosis": cause,
                "sourceErrors": source_errors,
            }
        )

    return {
        "overallStatus": str(payload.get("overallStatus") or "unknown"),
        "generatedAt": payload.get("generatedAt"),
        "reportSlot": payload.get("reportSlot"),
        "requiredCount": len(rows),
        "connectedCount": sum(1 for row in rows if row["routeConnected"]),
        "items": rows,
    }


def main() -> int:
    payload_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "market" / "latest.json"
    config_path = ROOT / "config" / "market_data_sources.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    print(json.dumps(summarize(payload, config), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

