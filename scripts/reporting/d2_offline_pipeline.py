"""Offline-only D2 pipeline: exercise request, fixture, raw-byte storage and audit.

Never instantiate a network/API client or invoke a publisher. An injected
in-process fixture responder is the sole source of bytes. The persistent
slot claim is written BEFORE responder invocation. A crash or timeout leaves
the claim in place: retries require separate manual reconciliation.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
import re
from typing import Callable

from .context import ReportContext
from .snapshot import MarketDataSnapshot
from .d2_private_store import LocalPrivateEvidenceStore, EvidenceReceipt, PrivateEvidenceError
from .d2_responses_contract import (
    build_request, capture_response, estimate_usage_usd, MODEL,
    ResponsesContractError, _no_duplicate_keys, _bad_float,
)
from .shadow_worker import json_bytes, sha256_bytes


class OfflineD2Blocked(ValueError):
    pass


@dataclass(frozen=True)
class OfflineD2Result:
    status: str
    reason: str | None
    report_id: str
    claim_receipt: EvidenceReceipt
    response_receipt: EvidenceReceipt | None
    result_receipt: EvidenceReceipt
    # An offline fixture is never a real producer attestation.
    api_send_allowed: bool = False
    publishable: bool = False


def exercise_d2_offline(
    context: ReportContext, snapshot: MarketDataSnapshot,
    store: LocalPrivateEvidenceStore, responder: Callable[[dict], bytes], *,
    run_id: str, attempt_id: str,
    instructions: str = "Only use the pre-verified frozen observation bundle.",
    max_model_cost_usd: str = "0.03",
    max_input_tokens: int = 12000,
    max_output_tokens: int = 4000,
) -> OfflineD2Result:
    """One synthetic attempt, no network and zero public writes.

    The caller passes a local test-double, not an authenticated API SDK.
    The deterministic slot claim is never deleted, including after failures.
    """
    if type(store) is not LocalPrivateEvidenceStore:
        raise OfflineD2Blocked("PRIVATE_STAGING_STORE_REQUIRED")
    if not callable(responder):
        raise OfflineD2Blocked("OFFLINE_RESPONDER_REQUIRED")
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", s or "")
           for s in (run_id, attempt_id)):
        raise OfflineD2Blocked("RUN_OR_ATTEMPT_ID_INVALID")
    if (type(max_input_tokens) is not int or
            not 1 <= max_input_tokens <= 12000 or
            type(max_output_tokens) is not int or
            not 1 <= max_output_tokens <= 4000):
        raise OfflineD2Blocked("TOKEN_CAP_INVALID")
    if (type(max_model_cost_usd) is not str or
            not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?", max_model_cost_usd)):
        raise OfflineD2Blocked("COST_LIMIT_INVALID")
    limit = Decimal(max_model_cost_usd)
    if not limit.is_finite() or limit <= 0:
        raise OfflineD2Blocked("COST_LIMIT_INVALID")
    # Contractual offline quote, NOT a tokenizer-measured input count or
    # enforceable provider-side spending limit. No live cost authorization.
    planned = estimate_usage_usd({
        "input_tokens": max_input_tokens,
        "output_tokens": max_output_tokens,
    })
    if planned > limit:
        raise OfflineD2Blocked("PLANNED_BUDGET_EXCEEDED")

    # Build and validate BEFORE any slot claim and BEFORE responder call.
    request = build_request(context, snapshot, model=MODEL, instructions=instructions,
                            max_output_tokens=max_output_tokens)
    slot = f"slot-{context.report_id}-r{context.revision}"
    claim_id = f"shadow/{slot}/claim"
    claim_bytes = json_bytes({
        "schema": "d2-offline-slot-claim/v1",
        "report_id": context.report_id, "revision": context.revision,
        "snapshot_id": snapshot.snapshot_id, "run_id": run_id,
        "attempt_id": attempt_id, "request_sha256": sha256_bytes(json_bytes(request)),
        "max_input_tokens": max_input_tokens, "max_output_tokens": max_output_tokens,
        "max_model_cost_usd": str(limit),
        "planned_model_cost_usd": str(planned),
        "lane": "api-shadow", "api_send_allowed": False,
        "publication_allowed": False,
    })
    try:
        claim = store.put_once(claim_id, claim_bytes)
    except PrivateEvidenceError as exc:
        # Once claimed (even in an unknown state), a second attempt cannot
        # reach the responder in this filesystem staging environment.
        raise OfflineD2Blocked("SLOT_ALREADY_CLAIMED_OR_STORAGE_BLOCKED") from exc

    raw_receipt = None
    status = "OFFLINE_BLOCKED"
    reason = None
    captured = None
    try:
        # Exactly one in-process fixture call. No retries on timeout.
        wire = responder(json.loads(json_bytes(request)))
        if type(wire) is not bytes or not wire:
            raise OfflineD2Blocked("RAW_FIXTURE_BYTES_REQUIRED")
        raw_receipt = store.put_once(f"shadow/{run_id}/{attempt_id}-raw", wire)
        readback = store.read_verified(raw_receipt)
        if readback != wire:
            raise OfflineD2Blocked("RAW_READBACK_MISMATCH")
        try:
            raw_obj = json.loads(readback.decode("utf-8"),
                                 object_pairs_hook=_no_duplicate_keys,
                                 parse_constant=_bad_float)
        except (ValueError, UnicodeError) as exc:
            raise OfflineD2Blocked("RAW_FIXTURE_JSON_INVALID") from exc
        captured = capture_response(raw_obj, context, snapshot, raw_response_bytes=readback)
        estimate = estimate_usage_usd(captured.usage)
        if (captured.usage["input_tokens"] > max_input_tokens or
                captured.usage["output_tokens"] > max_output_tokens):
            raise OfflineD2Blocked("ACTUAL_TOKEN_CAP_EXCEEDED")
        if estimate > limit:
            raise OfflineD2Blocked("SIMULATED_BUDGET_EXCEEDED")
        if captured.raw_response_sha256 != raw_receipt.content_sha256:
            raise OfflineD2Blocked("RAW_RESPONSE_DIGEST_MISMATCH")
        status = "OFFLINE_FIXTURE_VALIDATED"
    except TimeoutError:
        status, reason = "UNKNOWN_FIXTURE_RESULT", "UNKNOWN_RESULT_NO_RETRY"
    except (OfflineD2Blocked, ResponsesContractError, PrivateEvidenceError,
            ValueError, UnicodeError, TypeError) as exc:
        status, reason = "OFFLINE_BLOCKED", type(exc).__name__
        if isinstance(exc, (OfflineD2Blocked, ResponsesContractError)):
            reason = str(exc)

    record = {
        "schema": "d2-offline-run-receipt/v1",
        "lane": "api-shadow", "status": status, "reason": reason,
        "report_id": context.report_id, "revision": context.revision,
        "run_id": run_id, "attempt_id": attempt_id,
        "snapshot_id": snapshot.snapshot_id,
        "request_sha256": sha256_bytes(json_bytes(request)),
        "slot_claim_sha256": claim.content_sha256,
        "max_input_tokens": max_input_tokens, "max_output_tokens": max_output_tokens,
        "max_model_cost_usd": str(limit), "planned_model_cost_usd": str(planned),
        "raw_response_sha256": (raw_receipt.content_sha256 if raw_receipt else None),
        "raw_response_object": (raw_receipt.object_id if raw_receipt else None),
        "body_sha256": (captured.body_sha256 if captured else None),
        "numeric_audit_bundle_sha256": (
            captured.numeric_audit_bundle_sha256 if captured else None),
        "api_send_allowed": False, "publication_allowed": False,
    }
    receipt = store.put_once(f"shadow/{run_id}/{attempt_id}-result", json_bytes(record))
    if json.loads(store.read_verified(receipt).decode("utf-8")) != record:
        raise OfflineD2Blocked("RESULT_READBACK_MISMATCH")
    return OfflineD2Result(status, reason, context.report_id, claim,
                           raw_receipt, receipt)
