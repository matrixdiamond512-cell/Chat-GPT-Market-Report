"""Read-only D2 local crash reconciliation. NEVER authorize retry or publish.

Reads independent, untrusted POSIX staging evidence after a simulated crash.
Recomputing a SHA from locally found bytes is *not* trusted provenance, an
external signature, provider authentication or a production storage receipt.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re

from .context import ReportContext
from .snapshot import MarketDataSnapshot
from .shadow_worker import freeze_shadow_input, sha256_bytes
from .d2_private_store import LocalPrivateEvidenceStore, PrivateEvidenceError
from .d2_responses_contract import (
    capture_response, ResponsesContractError, _no_duplicate_keys, _bad_float,
)

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9_-]{1,60}\Z")
_CLAIM_KEYS = {
    "schema", "report_id", "revision", "snapshot_id", "run_id", "attempt_id",
    "request_sha256", "lane", "api_send_allowed", "publication_allowed",
}
_RESULT_KEYS = {
    "schema", "lane", "status", "reason", "report_id", "revision", "run_id",
    "attempt_id", "snapshot_id", "request_sha256", "slot_claim_sha256",
    "raw_response_sha256", "raw_response_object", "body_sha256",
    "numeric_audit_bundle_sha256", "api_send_allowed", "publication_allowed",
}
_VALID_STATUSES = {
    "OFFLINE_FIXTURE_VALIDATED",
    "OFFLINE_BLOCKED",
    "UNKNOWN_FIXTURE_RESULT",
}


@dataclass(frozen=True)
class RecoveryFinding:
    status: str
    reason: str
    report_id: str
    slot_claim_present: bool
    raw_present: bool
    result_present: bool
    # Diagnostics are not an authorization system.
    retry_allowed: bool = False
    api_send_allowed: bool = False
    publication_allowed: bool = False


def _parse(blob: bytes) -> dict:
    try:
        obj = json.loads(blob.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
                         parse_constant=_bad_float)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise ValueError("DIAGNOSTIC_JSON_UNTRUSTED_OR_INVALID") from exc
    if not isinstance(obj, dict):
        raise ValueError("DIAGNOSTIC_JSON_NOT_OBJECT")
    return obj


def _digest(s) -> bool:
    return type(s) is str and bool(_DIGEST.fullmatch(s))


def reconcile_d2_offline(
    context: ReportContext, snapshot: MarketDataSnapshot,
    store: LocalPrivateEvidenceStore, *, run_id: str, attempt_id: str,
) -> RecoveryFinding:
    """Inspect existing local claim/raw/result, with no writes or callbacks.

    Even OFFLINE_CONSISTENT_UNATTESTED is always non-retryable and nonpublic.
    An absent claim does NOT prove the provider was never contacted elsewhere.
    """
    if type(store) is not LocalPrivateEvidenceStore:
        raise ValueError("RECONCILIATION_STORE_MUST_BE_LOCAL")
    if type(run_id) is not str or type(attempt_id) is not str or (
        not _ID.fullmatch(run_id) or not _ID.fullmatch(attempt_id)
    ):
        raise ValueError("RECONCILIATION_ID_INVALID")
    freeze_shadow_input(context, snapshot)
    claim_key = f"shadow/slot-{context.report_id}-r{context.revision}/claim"
    raw_key = f"shadow/{run_id}/{attempt_id}-raw"
    result_key = f"shadow/{run_id}/{attempt_id}-result"
    present = [False, False, False]

    def finding(status: str, reason: str):
        return RecoveryFinding(status, reason, context.report_id, *present)

    try:
        claim_bytes = store.read_for_diagnostics(claim_key)
        raw_bytes = store.read_for_diagnostics(raw_key)
        result_bytes = store.read_for_diagnostics(result_key)
        present[:] = [p is not None for p in
                      (claim_bytes, raw_bytes, result_bytes)]
        if claim_bytes is None:
            if raw_bytes is not None or result_bytes is not None:
                return finding("INCONSISTENT_UNTRUSTED", "ORPHANED_EVIDENCE_NO_SLOT_CLAIM")
            return finding("UNRESOLVED_NO_CLAIM", "CANNOT_PROVE_NO_PRIOR_EXECUTION")
        claim = _parse(claim_bytes)
        if set(claim) != _CLAIM_KEYS or (
            claim["schema"] != "d2-offline-slot-claim/v1"
            or claim["lane"] != "api-shadow"
            or claim["report_id"] != context.report_id
            or type(claim["revision"]) is not int
            or claim["revision"] != context.revision
            or claim["snapshot_id"] != snapshot.snapshot_id
            or claim["run_id"] != run_id
            or claim["attempt_id"] != attempt_id
            or not _digest(claim["request_sha256"])
            or claim["api_send_allowed"] is not False
            or claim["publication_allowed"] is not False
        ):
            return finding("INCONSISTENT_UNTRUSTED", "SLOT_CLAIM_CONTENT_INVALID")
        if result_bytes is None:
            return finding(
                "INTERRUPTED_NEEDS_MANUAL_REVIEW",
                "RAW_PRESENT_WITHOUT_RESULT" if raw_bytes is not None
                else "SLOT_CLAIM_PRESENT_WITHOUT_RESULT",
            )
        result = _parse(result_bytes)
        if set(result) != _RESULT_KEYS or (
            result["schema"] != "d2-offline-run-receipt/v1"
            or result["lane"] != "api-shadow"
            or result["status"] not in _VALID_STATUSES
            or result["report_id"] != context.report_id
            or type(result["revision"]) is not int
            or result["revision"] != context.revision
            or result["run_id"] != run_id
            or result["attempt_id"] != attempt_id
            or result["snapshot_id"] != snapshot.snapshot_id
            or result["request_sha256"] != claim["request_sha256"]
            or result["slot_claim_sha256"] != sha256_bytes(claim_bytes)
            or result["api_send_allowed"] is not False
            or result["publication_allowed"] is not False
        ):
            return finding("INCONSISTENT_UNTRUSTED", "RUN_RESULT_CONTENT_INVALID")
        if raw_bytes is None:
            if result["raw_response_sha256"] is not None or (
                result["raw_response_object"] is not None
                or result["status"] == "OFFLINE_FIXTURE_VALIDATED"
            ):
                return finding("INCONSISTENT_UNTRUSTED", "RAW_OBJECT_MISSING")
        else:
            if (result["raw_response_object"] != raw_key or
                result["raw_response_sha256"] != sha256_bytes(raw_bytes)):
                return finding("INCONSISTENT_UNTRUSTED", "RAW_DIGEST_OR_ID_MISMATCH")
        if result["status"] == "UNKNOWN_FIXTURE_RESULT":
            if (result["reason"] != "UNKNOWN_RESULT_NO_RETRY"
                or raw_bytes is not None or result["body_sha256"] is not None
                or result["numeric_audit_bundle_sha256"] is not None):
                return finding("INCONSISTENT_UNTRUSTED", "UNKNOWN_STATE_CONTRADICTORY")
            return finding("INTERRUPTED_NEEDS_MANUAL_REVIEW",
                           "TIMEOUT_UNKNOWN_NO_AUTOMATIC_RETRY")
        if result["status"] == "OFFLINE_BLOCKED":
            if type(result["reason"]) is not str or not result["reason"]:
                return finding("INCONSISTENT_UNTRUSTED", "BLOCKED_REASON_INVALID")
            # A blocked run cannot be upgraded by an apparently valid raw.
            return finding("OFFLINE_BLOCKED_RECORDED", "BLOCKED_NEEDS_MANUAL_REVIEW")
        if (result["reason"] is not None or raw_bytes is None
            or not _digest(result["body_sha256"])
            or not _digest(result["numeric_audit_bundle_sha256"])):
            return finding("INCONSISTENT_UNTRUSTED", "VALIDATED_STATE_INCOMPLETE")
        try:
            parsed = _parse(raw_bytes)
            captured = capture_response(
                parsed, context, snapshot, raw_response_bytes=raw_bytes)
        except (ResponsesContractError, ValueError, TypeError):
            return finding("INCONSISTENT_UNTRUSTED", "RAW_RESPONSE_REVALIDATION_FAILED")
        if (captured.raw_response_sha256 != result["raw_response_sha256"] or
            captured.body_sha256 != result["body_sha256"] or
            captured.numeric_audit_bundle_sha256 != result["numeric_audit_bundle_sha256"]):
            return finding("INCONSISTENT_UNTRUSTED", "VALIDATED_DIGEST_MISMATCH")
        return finding("OFFLINE_CONSISTENT_UNATTESTED",
                       "LOCAL_REPLAY_MATCHES_NO_PROVIDER_ATTESTATION")
    except (PrivateEvidenceError, ValueError, TypeError):
        return finding("INCONSISTENT_UNTRUSTED",
                       "LOCAL_EVIDENCE_MALFORMED_OR_UNSAFE")
