"""Read-only forensic replay of the full D2.2 synthetic preparation chain.

Local files, supplied billing fixture and model count fixture are untrusted;
passing a replay cannot establish OpenAI response authenticity, authorization,
real spending or production eligibility. No network, writes or retries.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re

from .context import ReportContext
from .snapshot import MarketDataSnapshot
from .shadow_worker import sha256_bytes
from .d2_private_store import LocalPrivateEvidenceStore, PrivateEvidenceError
from .d2_responses_contract import build_request, MODEL, _no_duplicate_keys, _bad_float
from .d2_token_count_contract import (
    build_count_plan, review_count_fixture, InputCountBlocked,
)
from .d2_monthly_budget import (
    MonthlySpendInputs, review_monthly_budget, BudgetReviewBlocked,
    monthly_inputs_sha256,
)
from .d2_offline_prepared_run import SCHEMA
from .d2_reconciliation import reconcile_d2_offline

_ID = re.compile(r"[A-Za-z0-9_-]{1,60}\Z")
_PREP_KEYS = frozenset((
    "schema", "lane", "report_id", "revision", "snapshot_id",
    "run_id", "attempt_id", "create_request_sha256", "count_request_sha256",
    "raw_count_sha256", "counted_input_tokens", "counted_model_cost_usd",
    "max_input_tokens", "max_output_tokens", "max_model_cost_usd",
    "monthly_total_with_reservation_usd", "monthly_effective_cap_usd",
    "monthly_inputs_sha256",
    "count_evidence_kind", "billing_evidence_kind", "api_send_allowed",
    "publication_allowed",
))


@dataclass(frozen=True)
class PreparedRecoveryFinding:
    status: str
    reason: str
    report_id: str
    count_present: bool
    preparation_present: bool
    claim_present: bool
    raw_present: bool
    result_present: bool
    # A local replay is strictly diagnostic: never grant permissions.
    retry_allowed: bool = False
    api_send_allowed: bool = False
    publication_allowed: bool = False
    externally_attested: bool = False


def _untrusted_json(blob: bytes) -> dict:
    try:
        obj = json.loads(blob.decode("utf-8"),
                         object_pairs_hook=_no_duplicate_keys,
                         parse_constant=_bad_float)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise ValueError("LOCAL_PREPARATION_JSON_INVALID") from exc
    if type(obj) is not dict:
        raise ValueError("LOCAL_PREPARATION_NOT_OBJECT")
    return obj


def reconcile_prepared_offline(
    context: ReportContext,
    snapshot: MarketDataSnapshot,
    store: LocalPrivateEvidenceStore, *,
    monthly_inputs: MonthlySpendInputs,
    run_id: str,
    attempt_id: str,
    instructions: str = "Only use the pre-verified frozen observation bundle.",
) -> PreparedRecoveryFinding:
    """Compare frozen request and all local D2.2 artifacts; make NO modifications.

    The same externally UNAUTHENTICATED monthly inputs must be supplied.
    If those inputs are absent, invalid or different, no upgrade is possible.
    """
    if type(store) is not LocalPrivateEvidenceStore:
        raise ValueError("LOCAL_PRIVATE_STORE_REQUIRED")
    if type(run_id) is not str or type(attempt_id) is not str or (
            not _ID.fullmatch(run_id) or not _ID.fullmatch(attempt_id)):
        raise ValueError("PREPARATION_RECONCILIATION_ID_INVALID")
    if type(monthly_inputs) is not MonthlySpendInputs:
        raise ValueError("MONTHLY_INPUT_TYPE_INVALID")
    ids = (
        f"shadow/{run_id}/{attempt_id}-inputcount",
        f"shadow/{run_id}/{attempt_id}-preparation",
        f"shadow/slot-{context.report_id}-r{context.revision}/claim",
        f"shadow/{run_id}/{attempt_id}-raw",
        f"shadow/{run_id}/{attempt_id}-result",
    )
    present = [False] * 5

    def finding(status: str, reason: str):
        return PreparedRecoveryFinding(status, reason, context.report_id, *present)

    try:
        items = tuple(store.read_for_diagnostics(obj) for obj in ids)
        present[:] = [b is not None for b in items]
        count_bytes, prep_bytes, claim_bytes, raw_bytes, result_bytes = items

        if count_bytes is None and prep_bytes is None:
            if any(present[2:]):
                return finding("INCONSISTENT_UNTRUSTED",
                               "DOWNSTREAM_EVIDENCE_WITHOUT_PREPARATION")
            return finding("UNRESOLVED_NO_PREPARATION",
                           "ABSENCE_DOES_NOT_PROVE_NO_EXTERNAL_EXECUTION")
        if count_bytes is None:
            return finding("INCONSISTENT_UNTRUSTED",
                           "PREPARATION_MISSING_COUNT_RAW")
        if prep_bytes is None:
            if any(present[2:]):
                return finding("INCONSISTENT_UNTRUSTED",
                               "DOWNSTREAM_WITHOUT_PREPARATION_RECEIPT")
            return finding("INTERRUPTED_NEEDS_MANUAL_REVIEW",
                           "COUNT_RAW_ONLY_NO_PREPARATION")

        prep = _untrusted_json(prep_bytes)
        if set(prep) != _PREP_KEYS or (
                prep["schema"] != SCHEMA or prep["lane"] != "api-shadow"
                or prep["report_id"] != context.report_id
                or type(prep["revision"]) is not int
                or prep["revision"] != context.revision
                or prep["snapshot_id"] != snapshot.snapshot_id
                or prep["run_id"] != run_id or prep["attempt_id"] != attempt_id
                or prep["count_evidence_kind"] != "SYNTHETIC_FIXTURE_NOT_AUTHENTICATED"
                or prep["billing_evidence_kind"] != "SYNTHETIC_VALUES_NOT_AUTHENTICATED"
                or prep["api_send_allowed"] is not False
                or prep["publication_allowed"] is not False
                or type(prep["max_input_tokens"]) is not int
                or type(prep["max_output_tokens"]) is not int
                or type(prep["max_model_cost_usd"]) is not str):
            return finding("INCONSISTENT_UNTRUSTED",
                           "PREPARATION_CONTENT_INVALID")

        if monthly_inputs.report_id != context.report_id:
            return finding("INCONSISTENT_UNTRUSTED",
                           "MONTHLY_REPORT_ID_MISMATCH")
        # All inputs for reconstruction come from frozen Context/Snapshot and
        # explicitly supplied fixture. Re-run validators independently.
        request = build_request(
            context, snapshot, model=MODEL, instructions=instructions,
            max_output_tokens=prep["max_output_tokens"],
        )
        plan = build_count_plan(
            request, max_input_tokens=prep["max_input_tokens"],
            max_run_usd=prep["max_model_cost_usd"],
        )
        counted = review_count_fixture(plan, request, count_bytes)
        monthly = review_monthly_budget(plan, monthly_inputs)
        expected = {
            "create_request_sha256": plan.create_request_sha256,
            "count_request_sha256": plan.count_request_sha256,
            "raw_count_sha256": sha256_bytes(count_bytes),
            "counted_input_tokens": counted.input_tokens,
            "counted_model_cost_usd": counted.planned_cost_usd,
            "max_input_tokens": plan.max_input_tokens,
            "max_output_tokens": plan.max_output_tokens,
            "max_model_cost_usd": plan.max_run_usd,
            "monthly_total_with_reservation_usd":
                monthly.total_with_proposed_reservation_usd,
            "monthly_effective_cap_usd": monthly.strictest_cap_usd,
            "monthly_inputs_sha256": monthly_inputs_sha256(monthly_inputs),
        }
        if any(prep[key] != value or type(prep[key]) is not type(value)
               for key, value in expected.items()):
            return finding("INCONSISTENT_UNTRUSTED",
                           "PREPARATION_REPLAY_MISMATCH")
        if claim_bytes is None:
            if raw_bytes is not None or result_bytes is not None:
                return finding("INCONSISTENT_UNTRUSTED",
                               "DOWNSTREAM_RAW_WITHOUT_SLOT_CLAIM")
            return finding("INTERRUPTED_NEEDS_MANUAL_REVIEW",
                           "PREPARATION_SAVED_WITHOUT_SLOT_CLAIM")

        # Check exact slot claim contents, raw response and run receipt using
        # the existing strict fail-closed replay. Never assume success.
        follow = reconcile_d2_offline(
            context, snapshot, store, run_id=run_id, attempt_id=attempt_id,
        )
        if follow.status == "INCONSISTENT_UNTRUSTED":
            return finding("INCONSISTENT_UNTRUSTED",
                           "DOWNSTREAM_" + follow.reason)
        # The claim read through a second descriptor might have been changed:
        # require the request and caps to match the prepared intent too.
        claim = _untrusted_json(claim_bytes)
        if (claim.get("request_sha256") != plan.create_request_sha256
                or claim.get("max_input_tokens") != plan.max_input_tokens
                or claim.get("max_output_tokens") != plan.max_output_tokens
                or claim.get("max_model_cost_usd") != plan.max_run_usd
                or claim.get("report_id") != context.report_id
                or claim.get("run_id") != run_id
                or claim.get("attempt_id") != attempt_id):
            return finding("INCONSISTENT_UNTRUSTED", "PREPARATION_CLAIM_MISMATCH")
        if follow.status == "OFFLINE_CONSISTENT_UNATTESTED":
            return finding("OFFLINE_CHAIN_CONSISTENT_UNATTESTED",
                           "LOCAL_REPLAY_ONLY_NO_EXTERNAL_ATTESTATION")
        if follow.status == "OFFLINE_BLOCKED_RECORDED":
            return finding("OFFLINE_BLOCKED_RECORDED",
                           "VALID_PREPARATION_BUT_GENERATION_BLOCKED")
        if follow.status == "INTERRUPTED_NEEDS_MANUAL_REVIEW":
            return finding("INTERRUPTED_NEEDS_MANUAL_REVIEW",
                           "DOWNSTREAM_" + follow.reason)
        return finding("INCONSISTENT_UNTRUSTED",
                       "DOWNSTREAM_STATE_NOT_RECOGNIZED")
    except (PrivateEvidenceError, InputCountBlocked, BudgetReviewBlocked,
            ValueError, TypeError, KeyError, OverflowError):
        return finding("INCONSISTENT_UNTRUSTED",
                       "LOCAL_PREPARATION_UNSAFE_OR_UNREPLAYABLE")
