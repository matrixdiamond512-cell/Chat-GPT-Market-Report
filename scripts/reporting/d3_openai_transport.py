"""Authenticated OpenAI Responses transport for a *separately authorized* shadow run.

This is deliberately NOT a scheduled or production publisher. The caller must
supply a trusted, independent paid-send approver and private durable slot store.
No approval issuer, billing verifier, project secret, or publication token is
embedded here. There is no retry after an ambiguous send.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener

from .context import ReportContext
from .snapshot import MarketDataSnapshot
from .shadow_worker import json_bytes, sha256_bytes
from .d2_token_count_contract import build_count_plan, review_count_fixture, InputCountPlan
from .d2_responses_contract import (
    build_request, capture_response, estimate_usage_usd, MODEL,
    CapturedResponse, _no_duplicate_keys, _bad_float,
)
from .d2_private_store import LocalPrivateEvidenceStore

API_ROOT = "https://api.openai.com"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_ALLOWED_PROJECT = re.compile(r"proj_[A-Za-z0-9_-]{3,120}\Z")
_ALLOWED_KEY = re.compile(r"sk-[A-Za-z0-9_-]{12,512}\Z")


class LiveTransportBlocked(RuntimeError):
    """Fail closed without printing credentials or model output."""


@dataclass(frozen=True)
class AuthorizedPaidAttempt:
    """Proof passed in by an independently authenticated external authorizer.

    Creating this dataclass locally is NOT evidence. A real deployment must
    implement and independently audit the authorizer against genuine billing
    receipts and the owner's explicit approval. It is not bundled in this PR.
    """
    report_id: str
    snapshot_id: str
    project_id: str
    request_sha256: str
    count_response_sha256: str
    approved_run_usd: str
    billing_receipt: str
    approval_id: str
    sender_allowed: bool


class ExternalAuthorizationVerifier(Protocol):
    def __call__(self, *, context: ReportContext,
                 snapshot: MarketDataSnapshot, plan: InputCountPlan,
                 raw_count: bytes) -> AuthorizedPaidAttempt: ...


@dataclass(frozen=True)
class LiveShadowReceipt:
    report_id: str
    request_sha256: str
    count_response_sha256: str
    model_response_sha256: str
    body_sha256: str
    actual_model_cost_usd: str
    response_id: str
    # No standalone API response authenticates market facts or production release.
    publishable: bool = False


class _RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LiveTransportBlocked("OPENAI_PROVIDER_REDIRECT_REJECTED")


def _fixed_urlopen(request, timeout):
    # urllib's default opener follows redirects. Never forward a project-scoped
    # Authorization header or provider body to an unreviewed redirect target.
    return build_opener(_RejectRedirect()).open(request, timeout=timeout)


class FixedOpenAIHTTPS:
    """Minimal fixed-endpoint HTTP client. No redirect/URL override or retry."""
    def __init__(self, *, api_key: str, project_id: str,
                 opener: Callable = _fixed_urlopen):
        if not isinstance(api_key, str) or not _ALLOWED_KEY.fullmatch(api_key):
            raise LiveTransportBlocked("API_SECRET_MISSING_OR_FORMAT_INVALID")
        if not isinstance(project_id, str) or not _ALLOWED_PROJECT.fullmatch(project_id):
            raise LiveTransportBlocked("API_PROJECT_MISSING_OR_INVALID")
        self._api_key = api_key
        self.project_id = project_id
        self._opener = opener

    def post(self, relative_path: str, payload: dict) -> bytes:
        if relative_path not in ("/v1/responses/input_tokens", "/v1/responses"):
            raise LiveTransportBlocked("ENDPOINT_NOT_ALLOWED")
        request = Request(
            API_ROOT + relative_path, data=json_bytes(payload), method="POST",
            headers={
                "Authorization": "Bearer " + self._api_key,
                "OpenAI-Project": self.project_id,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        # Exactly one attempt. A timeout might mean OpenAI processed the call:
        # never resubmit the same frozen slot automatically.
        try:
            with self._opener(request, timeout=45) as response:
                if response.status != 200:
                    raise LiveTransportBlocked("OPENAI_PROVIDER_NON_200")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES or not raw:
                    raise LiveTransportBlocked("OPENAI_PROVIDER_RESPONSE_SIZE_INVALID")
                return raw
        except HTTPError as exc:
            # Only expose a documented structured error *code*, not the raw
            # provider body, headers, request, key or project identifier.
            # Never retry an ambiguous model send (including 429).
            provider_code = "UNKNOWN"
            if exc.code == 429:
                try:
                    body = exc.read(4097)
                    if len(body) <= 4096:
                        decoded = json.loads(body.decode("utf-8"))
                        raw_code = (decoded.get("error") or {}).get("code")
                        if isinstance(raw_code, str) and re.fullmatch(
                                r"[a-z][a-z0-9_]{1,75}", raw_code):
                            provider_code = raw_code
                except (UnicodeError, ValueError, TypeError, AttributeError):
                    pass
            raise LiveTransportBlocked(
                f"OPENAI_HTTP_{exc.code}_CODE_{provider_code}_NO_AUTOMATIC_RETRY"
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise LiveTransportBlocked("OPENAI_TRANSPORT_FAILED_NO_AUTOMATIC_RETRY") from None


def _parse_api_json(raw: bytes) -> dict:
    try:
        obj = json.loads(raw.decode("utf-8"),
                         object_pairs_hook=_no_duplicate_keys, parse_constant=_bad_float)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise LiveTransportBlocked("OPENAI_RESPONSE_JSON_INVALID") from exc
    if not isinstance(obj, dict):
        raise LiveTransportBlocked("OPENAI_RESPONSE_NOT_OBJECT")
    return obj


def run_authorized_shadow_once(*, context: ReportContext,
                               snapshot: MarketDataSnapshot,
                               instructions: str,
                               private_store: LocalPrivateEvidenceStore,
                               client: FixedOpenAIHTTPS,
                               external_authorizer: ExternalAuthorizationVerifier,
                               max_input_tokens: int = 12000,
                               max_output_tokens: int = 4000,
                               max_run_usd: str = "0.03") -> LiveShadowReceipt:
    """Count actual API tokens first; call the model only after external approval.

    This runner cannot mint a billing or owner authorization. The external
    verifier must be separately implemented using independently authenticated
    receipts. Only one attempt per immutable local claim is allowed.
    """
    if type(private_store) is not LocalPrivateEvidenceStore:
        raise LiveTransportBlocked("PRIVATE_IMMUTABLE_STORE_REQUIRED")
    if type(client) is not FixedOpenAIHTTPS:
        raise LiveTransportBlocked("FIXED_OPENAI_HTTPS_CLIENT_REQUIRED")
    if not callable(external_authorizer):
        raise LiveTransportBlocked("INDEPENDENT_APPROVER_REQUIRED")
    request = build_request(context, snapshot, model=MODEL,
                            instructions=instructions,
                            max_output_tokens=max_output_tokens)
    plan = build_count_plan(request, max_input_tokens=max_input_tokens,
                            max_run_usd=max_run_usd)
    # Token counting is not permission to generate. The exact count response
    # bytes must be supplied to the external billing/approval checker.
    raw_count = client.post(plan.count_endpoint, plan.payload)
    review = review_count_fixture(plan, request, raw_count)
    attempt = external_authorizer(
        context=context, snapshot=snapshot, plan=plan, raw_count=raw_count)
    if type(attempt) is not AuthorizedPaidAttempt:
        raise LiveTransportBlocked("EXTERNAL_APPROVAL_TYPE_INVALID")
    expected = (
        attempt.report_id == context.report_id and
        attempt.snapshot_id == snapshot.snapshot_id and
        attempt.project_id == client.project_id and
        attempt.request_sha256 == plan.create_request_sha256 and
        attempt.count_response_sha256 == review.raw_count_sha256 and
        attempt.sender_allowed is True and
        bool(re.fullmatch(r"[A-Za-z0-9_-]{12,100}", attempt.approval_id)) and
        bool(re.fullmatch(r"[A-Za-z0-9_-]{12,128}", attempt.billing_receipt))
    )
    try:
        allowed_amount = Decimal(attempt.approved_run_usd)
        max_amount = Decimal(max_run_usd)
        estimate = Decimal(review.planned_cost_usd)
    except (InvalidOperation, TypeError):
        raise LiveTransportBlocked("EXTERNAL_APPROVAL_AMOUNT_INVALID")
    if (not expected or not allowed_amount.is_finite() or
            allowed_amount <= 0 or allowed_amount > max_amount or
            estimate > allowed_amount):
        raise LiveTransportBlocked("INDEPENDENT_APPROVAL_MISSING_OR_MISMATCHED")
    # O_EXCL claim is created BEFORE sending the billed request.
    # A crash leaves it permanently claimed (requires forensic resolution).
    safe_id = context.report_id.replace("-", "_")
    claim_id = "shadow/" + safe_id + "/paid_attempt_claim"
    private_store.put_once(claim_id, json_bytes({
        "report_id": context.report_id,
        "snapshot_id": snapshot.snapshot_id,
        "model": MODEL,
        "api_project": client.project_id,
        "request_sha256": plan.create_request_sha256,
        "count_response_sha256": review.raw_count_sha256,
        "billing_receipt": attempt.billing_receipt,
        "approval_id": attempt.approval_id,
        "approved_run_usd": attempt.approved_run_usd,
    }))
    raw_response = client.post("/v1/responses", request)
    # Preserve raw bytes BEFORE semantic review, even when the model response
    # is invalid. Report data is never written into the public repository.
    private_store.put_once("shadow/" + safe_id + "/paid_response_raw", raw_response)
    captured: CapturedResponse = capture_response(
        _parse_api_json(raw_response), context, snapshot,
        raw_response_bytes=raw_response)
    model_cost = estimate_usage_usd(captured.usage)
    if model_cost > allowed_amount:
        raise LiveTransportBlocked("ACTUAL_MODEL_COST_EXCEEDS_APPROVED_AMOUNT")
    result = LiveShadowReceipt(
        context.report_id, plan.create_request_sha256,
        review.raw_count_sha256, sha256_bytes(raw_response),
        captured.body_sha256, str(model_cost), captured.response_id,
    )
    private_store.put_once("shadow/" + safe_id + "/paid_review_receipt",
                           json_bytes(result.__dict__))
    return result
