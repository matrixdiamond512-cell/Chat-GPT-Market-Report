"""D2.2 offline-only count -> monthly budget -> fixture-generation orchestration.

The supplied count response is a fixture, NOT an authenticated OpenAI count.
This code does not call a count API or model API; it cannot authorize either.
Even a fully coherent local sequence remains SHADOW_NOT_ELIGIBLE.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Callable

from .context import ReportContext
from .snapshot import MarketDataSnapshot
from .shadow_worker import json_bytes, sha256_bytes
from .d2_responses_contract import build_request, MODEL
from .d2_token_count_contract import (
    InputCountBlocked, build_count_plan, review_count_fixture
)
from .d2_monthly_budget import (
    MonthlySpendInputs, BudgetReviewBlocked, review_monthly_budget
)
from .d2_private_store import LocalPrivateEvidenceStore, EvidenceReceipt, PrivateEvidenceError
from .d2_offline_pipeline import (
    exercise_d2_offline, OfflineD2Blocked, OfflineD2Result
)

SCHEMA = "d2-offline-preparation/v1"
_ID = re.compile(r"[A-Za-z0-9_-]{1,60}\Z")


class PreparedOfflineBlocked(ValueError):
    pass


@dataclass(frozen=True)
class PreparedOfflineResult:
    report_id: str
    preparation_receipt: EvidenceReceipt
    count_receipt: EvidenceReceipt
    execution: OfflineD2Result
    api_send_allowed: bool = False
    publication_allowed: bool = False


def run_prepared_offline(
    context: ReportContext,
    snapshot: MarketDataSnapshot,
    store: LocalPrivateEvidenceStore,
    responder: Callable[[dict], bytes], *,
    raw_count_fixture: bytes,
    monthly_inputs: MonthlySpendInputs,
    run_id: str,
    attempt_id: str,
    instructions: str = "Only use the pre-verified frozen observation bundle.",
    max_input_tokens: int = 12000,
    max_output_tokens: int = 4000,
    max_model_cost_usd: str = "0.03",
) -> PreparedOfflineResult:
    """Run read-validated, persisted *synthetic* prerequisites before responder.

    Preparation failures are pre-generation: no slot claim and no responder.
    Preparation receipt is immutable; a crash afterwards is never a request
    to resume blindly. The downstream pipeline always stays non-public.
    """
    if type(store) is not LocalPrivateEvidenceStore:
        raise PreparedOfflineBlocked("LOCAL_PRIVATE_STORE_REQUIRED")
    if not callable(responder):
        raise PreparedOfflineBlocked("FIXTURE_RESPONDER_REQUIRED")
    if any(type(s) is not str or not _ID.fullmatch(s) for s in (run_id, attempt_id)):
        raise PreparedOfflineBlocked("PREPARATION_ID_INVALID")
    if type(raw_count_fixture) is not bytes:
        raise PreparedOfflineBlocked("SYNTHETIC_COUNT_BYTES_REQUIRED")
    if type(monthly_inputs) is not MonthlySpendInputs:
        raise PreparedOfflineBlocked("MONTHLY_INPUT_TYPE_INVALID")
    if monthly_inputs.report_id != context.report_id:
        raise PreparedOfflineBlocked("MONTHLY_REPORT_ID_MISMATCH")

    try:
        request = build_request(
            context, snapshot, model=MODEL, instructions=instructions,
            max_output_tokens=max_output_tokens,
        )
        plan = build_count_plan(
            request, max_input_tokens=max_input_tokens,
            max_run_usd=max_model_cost_usd,
        )
        count_review = review_count_fixture(plan, request, raw_count_fixture)
        budget_review = review_monthly_budget(plan, monthly_inputs)
    except (InputCountBlocked, BudgetReviewBlocked, ValueError, TypeError) as exc:
        # Do not store a "passing" preparation record when any review fails.
        raise PreparedOfflineBlocked("PREPARATION_REJECTED:" + str(exc)) from exc

    if (plan.api_send_allowed is not False
            or count_review.api_send_allowed is not False
            or count_review.provider_authenticated is not False
            or budget_review.send_allowed is not False
            or budget_review.external_billing_attested is not False):
        raise PreparedOfflineBlocked("EXTERNAL_ATTESTATION_REQUIRED")

    prep = {
        "schema": SCHEMA,
        "lane": "api-shadow",
        "report_id": context.report_id,
        "revision": context.revision,
        "snapshot_id": snapshot.snapshot_id,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "create_request_sha256": plan.create_request_sha256,
        "count_request_sha256": plan.count_request_sha256,
        "raw_count_sha256": count_review.raw_count_sha256,
        "counted_input_tokens": count_review.input_tokens,
        "counted_model_cost_usd": count_review.planned_cost_usd,
        "max_input_tokens": plan.max_input_tokens,
        "max_output_tokens": plan.max_output_tokens,
        "max_model_cost_usd": plan.max_run_usd,
        "monthly_total_with_reservation_usd": (
            budget_review.total_with_proposed_reservation_usd),
        "monthly_effective_cap_usd": budget_review.strictest_cap_usd,
        "count_evidence_kind": "SYNTHETIC_FIXTURE_NOT_AUTHENTICATED",
        "billing_evidence_kind": "SYNTHETIC_VALUES_NOT_AUTHENTICATED",
        "api_send_allowed": False,
        "publication_allowed": False,
    }

    # Immutable evidence stored before invoking the generation fixture.
    # Raw count bytes are separate, untrusted evidence. Save/read back both.
    try:
        raw_receipt = store.put_once(
            f"shadow/{run_id}/{attempt_id}-inputcount", raw_count_fixture)
        if store.read_verified(raw_receipt) != raw_count_fixture:
            raise PreparedOfflineBlocked("COUNT_RAW_READBACK_MISMATCH")
        prepared = json_bytes(prep)
        receipt = store.put_once(
            f"shadow/{run_id}/{attempt_id}-preparation", prepared)
        if store.read_verified(receipt) != prepared:
            raise PreparedOfflineBlocked("PREPARATION_READBACK_MISMATCH")
        if raw_receipt.content_sha256 != prep["raw_count_sha256"]:
            raise PreparedOfflineBlocked("COUNT_RAW_DIGEST_MISMATCH")
    except PrivateEvidenceError as exc:
        raise PreparedOfflineBlocked("PREPARATION_STORAGE_BLOCKED") from exc

    result = exercise_d2_offline(
        context, snapshot, store, responder,
        run_id=run_id, attempt_id=attempt_id,
        instructions=instructions,
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
        max_model_cost_usd=max_model_cost_usd,
    )
    # Never confuse a successful fixture response with authorization to run.
    if result.api_send_allowed is not False or result.publishable is not False:
        raise PreparedOfflineBlocked("PUBLICATION_BOUNDARY_VIOLATED")
    claim = json.loads(store.read_verified(result.claim_receipt))
    if (claim["request_sha256"] != plan.create_request_sha256
            or claim["max_input_tokens"] != prep["max_input_tokens"]
            or claim["max_output_tokens"] != prep["max_output_tokens"]
            or claim["max_model_cost_usd"] != prep["max_model_cost_usd"]):
        raise PreparedOfflineBlocked("PREPARATION_TO_CLAIM_MISMATCH")
    return PreparedOfflineResult(context.report_id, receipt, raw_receipt, result)
