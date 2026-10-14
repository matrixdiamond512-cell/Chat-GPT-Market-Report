"""D2 monthly spend *arithmetic* review, never an API authorization.

No billing API, no real account state or production reservation. In
particular OpenAI hard limits can have propagation delay and alerts are not
hard limits. Rechecking external authenticated usage at send time is required.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal, InvalidOperation
import re

from .d2_token_count_contract import InputCountPlan
from .shadow_worker import json_bytes, sha256_bytes
from .d2_responses_contract import (
    INPUT_RATE_USD_PER_MILLION, OUTPUT_RATE_USD_PER_MILLION,
)

_MONEY = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?\Z")
_SCHEMA = "d2-monthly-spend-arithmetic/v1"


class BudgetReviewBlocked(ValueError):
    pass


@dataclass(frozen=True)
class MonthlySpendInputs:
    report_id: str
    month_jst: str
    # Inputs below MUST eventually be obtained from independent authoritative
    # billing sources. A JSON fixture cannot prove their origin or recency.
    reported_month_spend_usd: str
    outstanding_reservations_usd: str
    approved_month_cap_usd: str
    project_hard_limit_usd: str
    org_hard_limit_usd: str
    project_hard_limit_enabled: bool
    org_hard_limit_enabled: bool


@dataclass(frozen=True)
class MonthlyBudgetReview:
    status: str
    total_with_proposed_reservation_usd: str
    strictest_cap_usd: str
    remaining_after_reservation_usd: str
    schema_version: str = _SCHEMA
    external_billing_attested: bool = False
    send_allowed: bool = False
    publication_allowed: bool = False

def monthly_inputs_sha256(inputs: MonthlySpendInputs) -> str:
    """Bind every supplied untrusted input field, not only calculated totals.

    This is a LOCAL SHA-256 commitment, not a verified billing-system receipt,
    external signature, or authorization for the API sender.
    """
    if type(inputs) is not MonthlySpendInputs:
        raise BudgetReviewBlocked("MONTHLY_INPUT_TYPE_INVALID")
    return sha256_bytes(json_bytes(asdict(inputs)))


def _amount(value: str, field: str, *, positive: bool = False) -> Decimal:
    if type(value) is not str or not _MONEY.fullmatch(value):
        raise BudgetReviewBlocked(field + "_FORMAT_INVALID")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise BudgetReviewBlocked(field + "_FORMAT_INVALID") from exc
    if not amount.is_finite() or amount < 0 or (positive and amount == 0):
        raise BudgetReviewBlocked(field + "_OUT_OF_BOUNDS")
    return amount


def review_monthly_budget(plan: InputCountPlan, values: MonthlySpendInputs
                          ) -> MonthlyBudgetReview:
    """Deterministic math on UNATTESTED monthly account figures. ALWAYS blocked."""
    if type(plan) is not InputCountPlan or (
            plan.api_send_allowed is not False or
            plan.schema_version != "d2-input-tokens-count-offline/v1"):
        raise BudgetReviewBlocked("COUNT_PLAN_NOT_VERIFIED")
    if type(values) is not MonthlySpendInputs:
        raise BudgetReviewBlocked("MONTHLY_SPEND_INPUT_INVALID")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}_(08|12|16|21)-00", values.report_id):
        raise BudgetReviewBlocked("REPORT_ID_FORMAT_INVALID")
    try:
        day = date.fromisoformat(values.report_id[:10])
    except ValueError as exc:
        raise BudgetReviewBlocked("MONTH_INVALID") from exc
    if values.month_jst != day.strftime("%Y-%m"):
        raise BudgetReviewBlocked("BILLING_MONTH_MISMATCH")
    if (values.project_hard_limit_enabled is not True or
            values.org_hard_limit_enabled is not True):
        raise BudgetReviewBlocked("BOTH_HARD_SPEND_LIMITS_REQUIRED")
    spent = _amount(values.reported_month_spend_usd, "REPORTED_SPEND")
    pending = _amount(values.outstanding_reservations_usd, "PENDING_RESERVATIONS")
    user_cap = _amount(values.approved_month_cap_usd, "APPROVED_MONTH_CAP", positive=True)
    project = _amount(values.project_hard_limit_usd, "PROJECT_HARD_CAP", positive=True)
    organization = _amount(values.org_hard_limit_usd, "ORG_HARD_CAP", positive=True)
    run_cap = _amount(plan.max_run_usd, "RUN_CAP", positive=True)
    # Reserve the MAXIMUM possible model cost, not a lower unverified fixture count.
    max_model = (plan.max_input_tokens * INPUT_RATE_USD_PER_MILLION +
                 plan.max_output_tokens * OUTPUT_RATE_USD_PER_MILLION) / Decimal(1000000)
    if max_model > run_cap:
        raise BudgetReviewBlocked("RUN_LIMIT_BELOW_PROPOSED_MODEL_COST")
    ceiling = min(user_cap, project, organization)
    total = spent + pending + max_model
    if total > ceiling:
        raise BudgetReviewBlocked("MONTHLY_BUDGET_RESERVATION_OVER_LIMIT")
    return MonthlyBudgetReview(
        status="OFFLINE_MONTHLY_ARITHMETIC_PASS_NOT_ATTESTED",
        total_with_proposed_reservation_usd=str(total),
        strictest_cap_usd=str(ceiling),
        remaining_after_reservation_usd=str(ceiling-total),
    )
