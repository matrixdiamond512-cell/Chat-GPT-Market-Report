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
import re
from pathlib import Path
from typing import Any

try:
    from scripts.build_chatgpt_report_input import ITEMS
except ModuleNotFoundError:
    from build_chatgpt_report_input import ITEMS

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


def _valid_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", str(value or "").strip()))


def _publication_proof_matches(observation: dict[str, Any], published_at: Any) -> bool:
    """Require a hash-checked source record tied to this exact series and value."""
    proof = observation.get("publicationEvidence")
    if not isinstance(proof, dict):
        return False
    series_id = str(observation.get("sourceSeriesId") or "").strip()
    proof_series_id = str(proof.get("sourceSeriesId") or "").strip()
    original_id = str(proof.get("originalId") or observation.get("sourceOriginalId") or "").strip()
    raw_original = proof.get("originalContent")
    digest = str(proof.get("sha256") or observation.get("evidenceHash") or "").strip()
    if not series_id or proof_series_id != series_id or not original_id:
        return False
    if not isinstance(raw_original, str) or not raw_original or not _valid_sha256(digest):
        return False
    if hashlib.sha256(raw_original.encode("utf-8")).hexdigest().lower() != digest.lower():
        return False
    if proof.get("observedValue") != observation.get("value"):
        return False
    try:
        return _instant(proof.get("publishedAt")) == _instant(published_at)
    except AsOfProjectionError:
        return False


def _article_was_available(article: dict[str, Any], cutoff: dt.datetime) -> bool:
    try:
        if _instant(article.get("publishedAt")) > cutoff:
            return False
        if article.get("updatedAt") and _instant(article["updatedAt"]) > cutoff:
            return False
        fetched = article.get("fetchedAt") or article.get("retrievedAt")
        if fetched and _instant(fetched) <= cutoff:
            return True
        proof = article.get("publicationEvidence")
        if not isinstance(proof, dict):
            return False
        original = proof.get("originalContent")
        digest = str(proof.get("sha256") or "")
        if not isinstance(original, str) or not _valid_sha256(digest):
            return False
        if hashlib.sha256(original.encode("utf-8")).hexdigest().lower() != digest.lower():
            return False
        return (bool(proof.get("originalId"))
                and str(proof.get("title") or "") == str(article.get("title") or "")
                and _instant(proof.get("publishedAt")) == _instant(article.get("publishedAt")))
    except AsOfProjectionError:
        return False


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
    raw_as_of = str(observation.get("asOf") or "")
    retrieved = observation.get("fetchedAt") or observation.get("retrievedAt")
    intraday_capture_in_time = False
    if (status == "reference_only" and observation.get("referenceOnly") is True
            and observation.get("freshnessStatus") in {"intraday", "intraday_delayed"}
            and observation.get("quoteUpdateMode")
            and observation.get("sourceId") and retrieved):
        try:
            intraday_capture_in_time = _instant(retrieved) <= cutoff
        except AsOfProjectionError:
            return False, "invalid_retrieval_time"
    if "T" not in raw_as_of and not finalized and not intraday_capture_in_time:
        return False, "market_close_time_unproven"
    if finalized:
        try:
            if _instant(finalized) > cutoff:
                return False, "daily_boundary_after_cutoff"
        except AsOfProjectionError:
            return False, "invalid_daily_boundary"
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
    if proof_time and proof_url.startswith("https://") and _publication_proof_matches(observation, proof_time):
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
    for name, symbol, unit, market_type, session in ITEMS:
        markets.setdefault(symbol, {
            "id": symbol, "displayName": name, "unit": unit, "marketType": market_type,
            "session": session, "value": None, "displayValue": "—",
            "verificationStatus": "unavailable", "referenceOnly": False,
            "productionEligible": False, "asOf": "", "fetchedAt": "",
            "sourceName": "", "verificationBasis": "",
        })
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
        excluded.append({"symbol": symbol, "reason": reason,
                         "marketDate": str(market.get("asOf") or "")[:10]})
        # Strip excluded numeric values AND directional signals. Do not merely
        # downgrade their status while leaving their numbers in report output.
        safe = {key: market[key] for key in
                ("id", "displayName", "unit", "marketType", "session") if key in market}
        market.clear()
        market.update({**safe, "value": None, "displayValue": "—",
                       "verificationStatus": "unavailable", "referenceOnly": False,
                       "productionEligible": False, "asOf": "", "fetchedAt": "",
                       "sourceName": "", "verificationBasis": "",
                       "exclusionReason": reason,
                       "note": "対象時点で利用可能だった証拠がないため除外"})
    valid_news = []
    for article in result.get("news") or []:
        if isinstance(article, dict) and _article_was_available(article, cutoff):
            valid_news.append(article)
    result["news"] = valid_news
    valid_timeline = []
    for event in result.get("timelineEvidence") or []:
        if not isinstance(event, dict):
            continue
        try:
            if (_instant(event.get("observedAt")) <= cutoff
                    and _instant(event.get("fetchedAt")) <= cutoff
                    and (not event.get("publishedAt") or _instant(event["publishedAt"]) <= cutoff)):
                valid_timeline.append(event)
        except AsOfProjectionError:
            continue
    result["timelineEvidence"] = valid_timeline
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
                   markets[key].get("seriesBasis"), markets[key].get("sourceSeriesId"),
                   markets[key].get("evidenceHash"),
                   (markets[key].get("publicationEvidence") or {}).get("sha256")
                   if isinstance(markets[key].get("publicationEvidence"), dict) else None,
                   markets[key].get("finalizedAt") or markets[key].get("marketCloseAt"))
                  for key in sorted(markets)]},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    result["snapshotId"] = "asof-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return result


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_asof_artifacts(payload: dict[str, Any], cutoff_iso: str, archive_hash: str,
                         generated_at: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Build a 28-item snapshot, its evidence ledger, and its same-snapshot report."""
    projected = project_snapshot_asof(payload, cutoff_iso)
    projected["generatedAt"] = generated_at
    repeated = project_snapshot_asof(payload, cutoff_iso)
    if repeated["snapshotId"] != projected["snapshotId"] or repeated["markets"] != project_snapshot_asof(payload, cutoff_iso)["markets"]:
        raise AsOfProjectionError("repeated projection changed for an identical input")
    cutoff = _instant(cutoff_iso)
    source_markets = payload.get("markets", {})
    reasons = {item["symbol"]: item["reason"] for item in projected["asOfExcluded"]}
    evidence_rows = []
    counts = {"VERIFIED_AS_OF": 0, "REFERENCE_AS_OF": 0, "UNAVAILABLE_AS_OF": 0}
    for name, symbol, unit, market_type, session in ITEMS:
        source = source_markets.get(symbol) or {}
        current = projected["markets"][symbol]
        status = str(current.get("verificationStatus") or "unavailable")
        classification = {
            "verified": "VERIFIED_AS_OF",
            "reference_only": "REFERENCE_AS_OF",
        }.get(status, "UNAVAILABLE_AS_OF")
        counts[classification] += 1
        proof = current.get("publicationEvidence")
        proof = proof if isinstance(proof, dict) else {}
        evidence_rows.append({
            "symbol": symbol,
            "value": current.get("value") if classification != "UNAVAILABLE_AS_OF" else None,
            "unit": current.get("unit") or unit,
            "marketDate": str(source.get("asOf") or "")[:10],
            "observedAt": source.get("observedAt") or (source.get("asOf") if "T" in str(source.get("asOf") or "") else None),
            "finalizedAt": source.get("finalizedAt") or source.get("marketCloseAt"),
            "publishedAt": source.get("publishedAt") or proof.get("publishedAt"),
            "fetchedAt": source.get("fetchedAt") or source.get("retrievedAt"),
            "sourceSeriesId": source.get("sourceSeriesId"),
            "sourceUrl": source.get("sourceUrl"),
            "evidenceUrl": source.get("publicationEvidenceUrl"),
            "evidenceHash": source.get("evidenceHash") or proof.get("sha256"),
            "sourceSnapshotSha256": archive_hash,
            "classification": classification,
            "exclusionReason": reasons.get(symbol, ""),
            "productionEligible": False,
        })
    if sum(counts.values()) != 28 or len(evidence_rows) != 28:
        raise AsOfProjectionError("as-of evidence must account for exactly 28 report fields")
    body = _render_report(projected)
    body_hash = _sha256_text(body)
    analysis_body = re.sub(r"(?m)^生成日時:.*$", "生成日時: <generation metadata>", body)
    analysis_hash = _sha256_text(analysis_body)
    evidence = {
        "schemaVersion": "1.0.0",
        "targetAsOf": cutoff.isoformat(),
        "generatedAt": generated_at,
        "snapshotId": projected["snapshotId"],
        "sourceSnapshotId": payload.get("snapshotId"),
        "sourceSnapshotSha256": archive_hash,
        "classificationCounts": counts,
        "items": evidence_rows,
    }
    evidence_for_hash = {key: value for key, value in evidence.items() if key != "generatedAt"}
    evidence_canonical = json.dumps(evidence_for_hash, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    evidence_hash = _sha256_text(evidence_canonical)
    stable_snapshot = {
        "schemaVersion": "1.0.0",
        "artifactType": "historical_reconstruction_partial",
        "targetAsOf": cutoff.isoformat(),
        "generatedAt": generated_at,
        "marketDates": {row["symbol"]: row["marketDate"] for row in evidence_rows},
        "markets": projected["markets"],
        "classificationCounts": counts,
        "revision": 1,
        "snapshotId": projected["snapshotId"],
        "evidenceLedgerSha256": evidence_hash,
        "reportSha256": body_hash,
        "analysisSha256": analysis_hash,
        "productionEligible": False,
    }
    stable_for_hash = {key: value for key, value in stable_snapshot.items()
                       if key not in {"generatedAt", "reportSha256"}}
    snapshot_hash = _sha256_text(json.dumps(
        stable_for_hash, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    snapshot = {**stable_snapshot, "snapshotSha256": snapshot_hash,
                "reproducibility": {"status": "PASS", "basis": "identical projection was recomputed from the same archive and cutoff"}}
    evidence["evidenceLedgerSha256"] = evidence_hash
    return snapshot, evidence, body


def _render_report(payload: dict[str, Any]) -> str:
    try:
        from scripts.build_personal_market_report import render_report
    except ModuleNotFoundError:
        from build_personal_market_report import render_report
    return render_report(payload)


def write_asof_artifacts(input_path: Path, snapshot_path: Path, evidence_path: Path,
                         report_path: Path, cutoff_iso: str) -> dict[str, str]:
    raw = input_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    archive_hash = hashlib.sha256(raw).hexdigest()
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    snapshot, evidence, body = build_asof_artifacts(payload, cutoff_iso, archive_hash, generated_at)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(body, encoding="utf-8")
    return {"snapshotId": snapshot["snapshotId"], "snapshotSha256": snapshot["snapshotSha256"],
            "evidenceSha256": evidence["evidenceLedgerSha256"], "reportSha256": snapshot["reportSha256"],
            "generatedAt": generated_at}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate a fail-closed historical market report reconstruction.")
    parser.add_argument("--input", type=Path, required=True, help="Immutable archived market snapshot JSON")
    parser.add_argument("--as-of", required=True, help="ISO-8601 cutoff with timezone")
    parser.add_argument("--snapshot-output", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(write_asof_artifacts(
        args.input, args.snapshot_output, args.evidence_output, args.report_output, args.as_of),
        ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()


