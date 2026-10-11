from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo

OFFICIAL_INDEX_REFERENCE_SOURCES = {
    "nasdaq": "nasdaq_global_index_watch",
}


def _decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("close evidence contains a nonnumeric value") from exc
    if not result.is_finite():
        raise ValueError("close evidence contains a nonfinite value")
    return result


def _aware(value: object) -> dt.datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO-8601 string")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def verify_close_evidence(candidate: dict, evidence: dict | None) -> dict:
    """Return a conservative close-review result; unsupported evidence never promotes."""
    base = {
        "status": "CANDIDATE_CLOSE_AND_SESSION_REVIEW_REQUIRED",
        "basis": "no qualifying close evidence supplied",
    }
    if evidence is None:
        return base
    if not isinstance(evidence, dict):
        raise ValueError("closeValidation must be an object")

    field_id = candidate.get("id")
    market_type = candidate.get("marketType")
    if market_type == "index":
        expected_source = OFFICIAL_INDEX_REFERENCE_SOURCES.get(str(field_id))
        if not expected_source or evidence.get("type") != "official_index_close":
            return base
        if evidence.get("sourceId") != expected_source:
            return base
        if evidence.get("marketDate") != candidate.get("marketDate"):
            return {"status": "CONFLICT", "basis": "official reference market date differs"}
        if evidence.get("timezone") != "America/New_York" or evidence.get("closeTime") != "16:00":
            return base
        precision = evidence.get("publishedDecimals")
        if isinstance(precision, bool) or not isinstance(precision, int) or not 0 <= precision <= 8:
            raise ValueError("publishedDecimals must be an integer from 0 to 8")
        quantizer = Decimal(1).scaleb(-precision)
        observed = _decimal(candidate.get("value")).quantize(quantizer, rounding=ROUND_HALF_UP)
        published = _decimal(evidence.get("value")).quantize(quantizer, rounding=ROUND_HALF_UP)
        if observed != published:
            return {"status": "CONFLICT", "basis": "official published close differs at its stated precision"}
        return {
            "status": "VERIFIED",
            "basis": f"official close matched at {precision}-decimal published precision",
        }

    if market_type == "spot" and field_id in {"usdjpy", "eurusd"}:
        if evidence.get("type") != "forex_daily_close":
            return base
        if evidence.get("timezone") != "America/New_York" or evidence.get("closeTime") != "17:00":
            return base
        anchor = _aware(candidate.get("barAnchorUtc"))
        boundary = _aware(evidence.get("closeBoundaryUtc"))
        intraday_start = _aware(evidence.get("intradayBarStartUtc"))
        if boundary != anchor + dt.timedelta(days=1):
            return {"status": "CONFLICT", "basis": "daily bar does not end at the declared NY-close boundary"}
        if boundary != intraday_start + dt.timedelta(hours=1):
            return {"status": "CONFLICT", "basis": "intraday close bar does not end at the declared NY-close boundary"}
        local_date = boundary.astimezone(ZoneInfo("America/New_York")).date().isoformat()
        if evidence.get("marketDate") != local_date or candidate.get("marketDate") != local_date:
            return {"status": "CONFLICT", "basis": "source market date does not match the NY close date"}
        if _decimal(candidate.get("value")) != _decimal(evidence.get("intradayClose")):
            return {"status": "CONFLICT", "basis": "daily close differs from its 17:00 NY intraday close"}
        return {
            "status": "VERIFIED",
            "basis": "daily bar matches its 17:00 America/New_York close boundary and final 1-hour close",
        }

    if market_type in {"continuous_futures", "futures_ose", "futures_cme"}:
        contract = evidence.get("contract")
        settlement = evidence.get("settlement")
        if not isinstance(contract, str) or not contract or not isinstance(settlement, dict):
            return base
        if evidence.get("type") != "official_futures_settlement":
            return base
        if settlement.get("marketDate") != candidate.get("marketDate"):
            return {"status": "CONFLICT", "basis": "futures settlement date differs"}
        if _decimal(candidate.get("value")) != _decimal(settlement.get("value")):
            return {"status": "CONFLICT", "basis": "futures price differs from named-contract settlement"}
        if evidence.get("continuousSymbol") == candidate.get("symbol"):
            return {"status": "CONFLICT", "basis": "continuous-contract series cannot establish named-contract settlement"}
        return {
            "status": "VERIFIED",
            "basis": "named contract matched official settlement on the same market date",
        }

    if field_id == "btcusd":
        if evidence.get("type") != "same_exchange_utc_daily_close":
            return base
        if evidence.get("timezone") != "UTC" or evidence.get("exchange") != "BITSTAMP":
            return base
        if evidence.get("marketDate") != candidate.get("marketDate"):
            return {"status": "CONFLICT", "basis": "exchange candle date differs"}
        if _decimal(candidate.get("value")) != _decimal(evidence.get("value")):
            return {"status": "CONFLICT", "basis": "exchange UTC daily close differs"}
        return {"status": "VERIFIED", "basis": "same-exchange UTC daily close matched"}

    return base
