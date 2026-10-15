#!/usr/bin/env python3
"""Fail-closed historical as-of projection for private report snapshots.

This does not fetch or publish any market data. A later historical archive may
contain values that were NOT observable at the requested earlier cutoff.
Only a source retrieval at/before cutoff, or timestamped publication evidence,
can establish that an observation was available then. The original archive
is never modified.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
from typing import Any

JST = dt.timezone(dt.timedelta(hours=9))
VALUATION_FIELDS = {"nikkei225_per", "nikkei225_pbr", "nikkei225_eps"}
DEVIATION_FIELDS = {"nikkei225_dev25", "nikkei225_dev200"}
PRIME_FIELDS = {
    "tse_prime_turnover", "tse_prime_volume", "tse_prime_advancers",
    "tse_prime_decliners", "tse_prime_ad_ratio25",
}
ALLOWED_BASIS = {"weighted_average", "index_basis"}


class AsOfProjectionError(ValueError):
    pass


def _instant(value: Any) -> dt.datetime:
    raw = str(value or "").strip()
    if not raw:
        raise AsOfProjectionError("timestamp is required")
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AsOfProjectionError("timestamp must be ISO 8601") from exc
    if parsed.tzinfo is None:
        raise AsOfProjectionError("timestamp must have timezone")
    return parsed.astimezone(dt.timezone.utc)


def _market_date(value: Any) -> dt.date:
    raw = str(value or "").strip()
    try:
        return dt.date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise AsOfProjectionError("market observation must have a valid date") from exc


def _availability(observation: dict[str, Any], cutoff: dt.datetime) -> tuple[bool, str]:
    if observation.get("value") in ("", None):
        return False, "no_value"
    status = str(observation.get("verificationStatus") or "")
    if status not in {"verified", "reference_only"}:
        return False, "not_verified_or_reference"
    try:
        raw_as_of = str(observation.get("asOf") or "")
        if _market_date(raw_as_of) > cutoff.astimezone(JST).date():
            return False, "market_date_after_cutoff"
        if "T" in raw_as_of and _instant(raw_as_of) > cutoff:
            return False, "observation_timestamp_after_cutoff"
    except AsOfProjectionError:
        return False, "invalid_market_date_or_timestamp"
    finalized = observation.get("finalizedAt") or observation.get("marketCloseAt")
    if finalized:
        try:
            if _instant(finalized) > cutoff:
                return False, "daily_boundary_after_cutoff"
        except AsOfProjectionError:
            return False, "invalid_daily_boundary"
    retrieved = observation.get("fetchedAt") or observation.get("retrievedAt")
    retrieved_in_time = False
    if retrieved:
        try:
            retrieved_in_time = _instant(retrieved) <= cutoff
        except AsOfProjectionError:
            return False, "invalid_retrieval_time"
    # Later retrieval is acceptable only with separate, dated documentary proof
    # that the identical series was published before the requested cutoff.
    proof_time = observation.get("publishedAt")
    proof_url = str(observation.get("publicationEvidenceUrl") or "")
    published_in_time = False
    if proof_time and proof_url.startswith("https://") and observation.get("publicationEvidence"):
        try:
            published_in_time = _instant(proof_time) <= cutoff
        except AsOfProjectionError:
            return False, "invalid_publication_time"
    if not retrieved_in_time and not published_in_time:
        return False, "no_proof_available_at_cutoff"
    if published_in_time and not retrieved_in_time:
        # Retrospective publication proof alone must not precede finalization.
        # Otherwise a later close could be labeled as already published.
        if not finalized:
            return False, "market_finalization_time_unproven"
        if _instant(proof_time) < _instant(finalized):
            return False, "publication_predates_finalization"
    if status == "verified" and observation.get("fallbackUsed"):
        return False, "fallback_not_verified"
    field = str(observation.get("id") or "")
    if field in VALUATION_FIELDS:
        basis = str(observation.get("seriesBasis") or "")
        if basis not in ALLOWED_BASIS:
            return False, "valuation_basis_unproven"
        if field in {"nikkei225_per", "nikkei225_pbr"} and basis != "weighted_average":
            return False, "valuation_basis_does_not_match_report_field"
        if field == "nikkei225_eps" and basis != "index_basis":
            return False, "eps_basis_does_not_match_report_field"
        if field == "nikkei225_eps" and observation.get("derivedFromRoundedPER"):
            return False, "rounded_per_derived_eps"
    if field in DEVIATION_FIELDS and status == "verified":
        expected_window = 25 if field == "nikkei225_dev25" else 200
        if (observation.get("windowSessions") != expected_window
                or not observation.get("historySeriesId")
                or not observation.get("officialCloseMatched")):
            return False, "official_same_series_window_unproven"
    if field in PRIME_FIELDS:
        if observation.get("marketSegment") not in {"TSE Prime", "東証プライム"}:
            return False, "prime_market_scope_unproven"
        if field == "tse_prime_ad_ratio25" and observation.get("windowSessions") != 25:
            return False, "prime_25_session_window_unproven"
    return True, "available"


def project_snapshot_asof(payload: dict[str, Any], cutoff_iso: str) -> dict[str, Any]:
    """Create a new immutable report input without any post-cutoff values."""
    cutoff = _instant(cutoff_iso)
    if not isinstance(payload, dict) or not isinstance(payload.get("markets"), dict):
        raise AsOfProjectionError("snapshot must contain a markets mapping")
    result = copy.deepcopy(payload)
    excluded: list[dict[str, str]] = []
    retained: list[str] = []
    markets = result["markets"]
    for symbol, market in markets.items():
        if not isinstance(market, dict):
            raise AsOfProjectionError("market must be an object")
        market["id"] = symbol
        allowed, reason = _availability(market, cutoff)
        if allowed:
            retained.append(symbol)
            # Historical as-of reports are never eligible for production close-list writes.
            market["productionEligible"] = False
            continue
        if market.get("value") not in (None, ""):
            excluded.append({"symbol": symbol, "reason": reason})
        # Strip excluded numeric values AND directional signals. Do not merely
        # downgrade their status while leaving their numbers in report output.
        for field in ("value", "displayValue", "previousClose", "changePercent",
                      "change", "changeAmount", "price", "last"):
            market.pop(field, None)
        market.update({"value": None, "displayValue": "—", "verificationStatus": "unavailable",
                       "referenceOnly": False, "productionEligible": False,
                       "asOf": "", "fetchedAt": "", "sourceName": "",
                       "verificationBasis": "", "note": "対象時点で利用可能だった証拠がないため除外"})
    valid_news = []
    for article in result.get("news") or []:
        if not isinstance(article, dict):
            continue
        try:
            if _instant(article.get("publishedAt")) <= cutoff:
                valid_news.append(article)
        except AsOfProjectionError:
            continue
    result["news"] = valid_news
    result["validationNotes"] = [
        "対象日時より後に取得した値は、同一系列の公表時刻の証拠がない限り除外。"
        "参考値と系列未確定値を本番確定値へ昇格しません。"
    ]
    result["asOfCutoff"] = cutoff.isoformat().replace("+00:00", "Z")
    result["asOfRetainedFields"] = retained
    result["asOfExcluded"] = excluded  # symbols and reasons only; no future prices
    result["asOfExcludedCount"] = len(excluded)
    result["reportDate"] = cutoff.astimezone(JST).date().isoformat()
    result["reportSlot"] = cutoff.astimezone(JST).strftime("%H:%M JST 厳格時点再構成")
    result["dataDateRange"] = result["reportDate"]
    result["historicalSnapshot"] = True
    result["overallStatus"] = "historical_asof_partial"
    result["snapshotFreshness"] = "strict_as_of_with_documented_availability"
    result["sourceSnapshotRetrievedAt"] = payload.get("sourceSnapshotRetrievedAt") or ""
    canonical = json.dumps(
        {"asOfCutoff": result["asOfCutoff"],
         "data": [(key, markets[key].get("value"), markets[key].get("sourceId"),
                   markets[key].get("asOf"), markets[key].get("verificationStatus"),
                   markets[key].get("seriesBasis")) for key in sorted(markets)]},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    result["snapshotId"] = "asof-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return result
