"""D2 Responses input-token COUNT contract, offline verification ONLY.

Official counter: POST /v1/responses/input_tokens; this module NEVER sends it.
The count response does NOT include model, request hash or provider signature.
Only an authenticated, independently restricted transport may bind a count to
a request. Locally passing this check does not authorize spending/publishing.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import copy
import json
import re

from .shadow_worker import json_bytes, sha256_bytes
from .d2_responses_contract import (
    MODEL, INPUT_RATE_USD_PER_MILLION, OUTPUT_RATE_USD_PER_MILLION,
    _no_duplicate_keys, _bad_float,
)

# Present in the frozen Responses create request. Dropping text schema or
# instructions would undercount model-visible context in an API count.
_CREATE_KEYS = frozenset((
    "model", "instructions", "input", "max_output_tokens", "store",
    "tools", "tool_choice", "text",
))
_COUNT_KEYS = ("model", "instructions", "input", "tools", "tool_choice", "text")
_CURRENCY = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?\Z")
SCHEMA = "d2-input-tokens-count-offline/v1"


class InputCountBlocked(ValueError):
    pass


def _money(value: str) -> Decimal:
    if type(value) is not str or not _CURRENCY.fullmatch(value):
        raise InputCountBlocked("COUNT_BUDGET_FORMAT_INVALID")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise InputCountBlocked("COUNT_BUDGET_FORMAT_INVALID") from exc
    if not result.is_finite() or result <= 0:
        raise InputCountBlocked("COUNT_BUDGET_NOT_POSITIVE")
    return result


@dataclass(frozen=True)
class InputCountPlan:
    count_endpoint: str
    create_request_sha256: str
    count_request_sha256: str
    payload: dict
    max_input_tokens: int
    max_output_tokens: int
    max_run_usd: str
    schema_version: str = SCHEMA
    api_send_allowed: bool = False


@dataclass(frozen=True)
class InputCountReview:
    status: str
    input_tokens: int
    planned_cost_usd: str
    raw_count_sha256: str
    create_request_sha256: str
    count_request_sha256: str
    # Only a provider-authenticated transport receipt can attest real origin.
    provider_authenticated: bool = False
    api_send_allowed: bool = False
    publication_allowed: bool = False


def build_count_plan(create_request: dict, *, max_input_tokens: int = 12000,
                     max_run_usd: str = "0.03") -> InputCountPlan:
    """Derive the token-count payload from the EXACT immutable create request."""
    if not isinstance(create_request, dict) or set(create_request) != _CREATE_KEYS:
        raise InputCountBlocked("CREATE_REQUEST_SCHEMA_DRIFT")
    if (create_request["model"] != MODEL or
            create_request["store"] is not False or
            create_request["tools"] != [] or
            create_request["tool_choice"] != "none" or
            type(create_request["max_output_tokens"]) is not int or
            not 1 <= create_request["max_output_tokens"] <= 4000 or
            type(create_request["instructions"]) is not str or
            not create_request["instructions"] or
            type(create_request["input"]) is not str or
            not create_request["input"] or
            not isinstance(create_request["text"], dict)):
        raise InputCountBlocked("CREATE_REQUEST_UNSAFE_OR_MISMATCH")
    if type(max_input_tokens) is not int or not 1 <= max_input_tokens <= 12000:
        raise InputCountBlocked("INPUT_COUNT_CAP_INVALID")
    max_run = _money(max_run_usd)
    max_output = create_request["max_output_tokens"]
    planned = (max_input_tokens * INPUT_RATE_USD_PER_MILLION +
               max_output * OUTPUT_RATE_USD_PER_MILLION) / 1000000
    if planned > max_run:
        raise InputCountBlocked("COUNT_WORST_CASE_BUDGET_EXCEEDED")
    projection = copy.deepcopy({key: create_request[key] for key in _COUNT_KEYS})
    # No network request. Caller must check input-count endpoint support,
    # project IAM, charge policy and external approval independently.
    return InputCountPlan(
        "/v1/responses/input_tokens",
        sha256_bytes(json_bytes(create_request)),
        sha256_bytes(json_bytes(projection)), projection,
        max_input_tokens, max_output, str(max_run),
    )


def review_count_fixture(plan: InputCountPlan, actual_create_request: dict,
                         raw_count_response: bytes) -> InputCountReview:
    """Test structural count response and request digest binding only.

    Response from a fixture, not a provider. The official raw count object
    contains only "object" and "input_tokens"; it cannot authenticate itself.
    """
    if not isinstance(plan, InputCountPlan) or (
            plan.schema_version != SCHEMA or plan.api_send_allowed is not False):
        raise InputCountBlocked("COUNT_PLAN_INVALID")
    fresh = build_count_plan(
        actual_create_request, max_input_tokens=plan.max_input_tokens,
        max_run_usd=plan.max_run_usd)
    if (fresh.create_request_sha256 != plan.create_request_sha256 or
            fresh.count_request_sha256 != plan.count_request_sha256 or
            fresh.payload != plan.payload or
            fresh.max_output_tokens != plan.max_output_tokens):
        raise InputCountBlocked("COUNT_REQUEST_CHANGED_AFTER_COUNT")
    if type(raw_count_response) is not bytes or not raw_count_response:
        raise InputCountBlocked("COUNT_ORIGINAL_BYTES_REQUIRED")
    try:
        count_obj = json.loads(raw_count_response.decode("utf-8"),
                               object_pairs_hook=_no_duplicate_keys,
                               parse_constant=_bad_float)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise InputCountBlocked("COUNT_RESPONSE_UNTRUSTED_OR_INVALID") from exc
    if (not isinstance(count_obj, dict) or
            set(count_obj) != {"object", "input_tokens"} or
            count_obj["object"] != "response.input_tokens" or
            type(count_obj["input_tokens"]) is not int or
            count_obj["input_tokens"] < 0):
        raise InputCountBlocked("COUNT_RESPONSE_SCHEMA_INVALID")
    count = count_obj["input_tokens"]
    if count > plan.max_input_tokens:
        raise InputCountBlocked("MODEL_INPUT_TOKEN_CAP_EXCEEDED")
    total = (count * INPUT_RATE_USD_PER_MILLION +
             plan.max_output_tokens * OUTPUT_RATE_USD_PER_MILLION) / 1000000
    if total > _money(plan.max_run_usd):
        raise InputCountBlocked("COUNTED_BUDGET_EXCEEDED")
    return InputCountReview(
        "OFFLINE_COUNT_SHAPE_PASS_NOT_ATTESTED", count, str(total),
        sha256_bytes(raw_count_response),
        plan.create_request_sha256, plan.count_request_sha256
    )
