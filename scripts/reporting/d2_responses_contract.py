"""Responses API D2 boundary: construction and inspection only.

No SDK, network, secrets, system clock, filesystem writes or publisher.
External caller MUST independently authorize a paid request. This module
does not expose an HTTP request sender and cannot grant that authorization.
The model's JSON schema is never treated as factual validation of markets.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import json
import re
from typing import Any
from .context import ReportContext
from .snapshot import MarketDataSnapshot
from .shadow_worker import freeze_shadow_input, REQUIRED_SIX, sha256_bytes, json_bytes
from .d2_numeric_claims import audit_numeric_claims, verified_source_bundle, NumericClaimBlocked, CLAIM_KEYS

# Verified against official model page on 2026-10-15; eligibility and availability
# on a particular API project must still be checked independently.
MODEL = "gpt-5.4-mini-2026-03-17"
STRUCTURED_SCHEMA_VERSION = "shadow-responses-json/v2"
# Static offline planning reference only; independently re-verify prices before paid use.
INPUT_RATE_USD_PER_MILLION = Decimal("0.75")
OUTPUT_RATE_USD_PER_MILLION = Decimal("4.50")


class ResponsesContractError(ValueError):
    pass


def _fail(msg: str):
    raise ResponsesContractError(msg)


def response_format() -> dict:
    """A narrow strict Responses API JSON schema; no optional fields or tools."""
    item = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "series": {"type": "string"},
            "value": {"type": "number"},
            "unit": {"type": "string"},
        },
        "required": ["series", "value", "unit"]
    }
    numeric_item = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "start": {"type": "integer"},
            "literal": {"type": "string"},
            "series": {"type": "string"},
            "field": {"type": "string"},
            "source_id": {"type": "string"},
            "as_of": {"type": "string"},
        },
        "required": list(CLAIM_KEYS),
    }
    return {
        "type": "json_schema",
        "name": "market_report_shadow_v2",
        "strict": True,
        "schema": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "report_id": {"type": "string"},
                "title": {"type": "string"},
                "full_text": {"type": "string"},
                "observations_used": {"type": "array", "items": item},
                "numeric_claims": {"type": "array", "items": numeric_item},
            },
            "required": ["report_id", "title", "full_text", "observations_used", "numeric_claims"]
        },
    }


def build_request(context: ReportContext, snapshot: MarketDataSnapshot, *,
                  model: str = MODEL, instructions: str,
                  max_output_tokens: int = 4000) -> dict:
    """Freeze once; reject unverified source before constructing provider payload."""
    if model != MODEL:
        _fail("MODEL_NOT_APPROVED_FOR_OFFLINE_CONTRACT")
    if not instructions or not isinstance(instructions, str):
        _fail("INSTRUCTIONS_REQUIRED")
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 4000:
        _fail("OUTPUT_TOKEN_BUDGET_UNSAFE")
    context_data, snapshot_data = freeze_shadow_input(context, snapshot)
    # The report identity is deterministic; the model must never infer the
    # Japanese weekday or reinterpret directional observations.
    report_day = date.fromisoformat(context.report_date)
    expected_title = (
        f"マーケットレポート｜{report_day:%Y/%m/%d}"
        f"（{'月火水木金土日'[report_day.weekday()]}）{context.report_time}"
    )
    observed_directions = [
        {"series": market.instrument, "direction": market.direction,
         "change": market.changeValue, "change_pct": market.changePct}
        for market in snapshot.markets
    ]
    anchored_instructions = (
        instructions
        + "\n[検証可能な出力制約] title と full_text の第1行は次の文字列に完全一致させる: "
        + expected_title
        + "。曜日を再計算しない。価格変化の方向を推定せず、"
          "下記の観測方向と矛盾する上昇・下落の断定を書かない。"
          "市場ニュースや需給の裏付けがない場合は、原因や資金フローを事実として書かない。"
    )
    # All information goes in a fixed request. No latest/latest.json fallback.
    input_data = {
        "report_id": context.report_id,
        "expected_title": expected_title,
        "observed_directions": observed_directions,
        "context": context_data,
        "snapshot": snapshot_data,
        "approved_market_series": list(REQUIRED_SIX),
        "verified_numeric_source_bundle": verified_source_bundle(context, snapshot),
    }
    return {
        "model": model,
        "instructions": anchored_instructions,
        "input": json.dumps(input_data, ensure_ascii=False, allow_nan=False,
                            sort_keys=True, separators=(",", ":")),
        "max_output_tokens": max_output_tokens,
        "store": False,  # no server-side retention assumption in offline design
        "tools": [],
        "tool_choice": "none",
        "text": {"format": response_format()},
    }


def _no_duplicate_keys(items):
    result = {}
    for key, value in items:
        if key in result:
            _fail("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _bad_float(value: str):
    _fail("NONFINITE_JSON_CONSTANT")


@dataclass(frozen=True)
class CapturedResponse:
    response_id: str
    response_status: str
    model: str
    usage: dict
    full_text: str
    title: str
    report_id: str
    observations_used: tuple[dict, ...]
    raw_response_sha256: str | None
    normalized_response_sha256: str
    body_sha256: str
    numeric_audit_bundle_sha256: str
    numeric_claims_checked: int
    # Never equate model emission with verified market truth or ChatGPT task output.
    publishable: bool = False


def capture_response(raw: dict, context: ReportContext, snapshot: MarketDataSnapshot,
                     *, expected_model: str = MODEL,
                     raw_response_bytes: bytes | None = None) -> CapturedResponse:
    """Parse actual Responses API shape received by an external authenticated caller.

    fail closed on tool calls, refusal, duplicates, incomplete, bogus IDs or usage.
    full_text still needs the separately tested SOP, claim-level data validation.
    """
    if not isinstance(raw, dict):
        _fail("RESPONSE_NOT_OBJECT")
    status = raw.get("status")
    if status != "completed":
        _fail("PROVIDER_RESPONSE_NOT_COMPLETED")
    response_id = raw.get("id")
    if not isinstance(response_id, str) or not re.fullmatch(r"resp_[A-Za-z0-9_-]{5,256}", response_id):
        _fail("PROVIDER_RESPONSE_ID_INVALID")
    if raw.get("model") != expected_model:
        _fail("RESPONSE_MODEL_MISMATCH")
    if raw.get("error") or raw.get("incomplete_details"):
        _fail("RESPONSE_ERROR_OR_INCOMPLETE")
    usage = raw.get("usage")
    if not isinstance(usage, dict) or any(
        type(usage.get(k)) is not int or usage[k] < 0
        for k in ("input_tokens", "output_tokens", "total_tokens")
    ) or usage["total_tokens"] < usage["input_tokens"] + usage["output_tokens"]:
        _fail("RESPONSE_USAGE_INVALID")
    output = raw.get("output")
    if not isinstance(output, list) or len(output) != 1:
        _fail("OUTPUT_COUNT_OR_TOOL_CALL_FORBIDDEN")
    message = output[0]
    if not isinstance(message, dict) or message.get("type") != "message" or (
        message.get("role") != "assistant" or message.get("status") != "completed"
    ):
        _fail("OUTPUT_NOT_COMPLETED_ASSISTANT_MESSAGE")
    content = message.get("content")
    if not isinstance(content, list) or len(content) != 1:
        _fail("OUTPUT_TEXT_CONTENT_MISSING_OR_AMBIGUOUS")
    item = content[0]
    if not isinstance(item, dict) or item.get("type") != "output_text" or (
        not isinstance(item.get("text"), str) or not item["text"]
    ):
        _fail("MODEL_REFUSAL_OR_TEXT_MISSING")
    try:
        parsed = json.loads(item["text"], object_pairs_hook=_no_duplicate_keys,
                            parse_constant=_bad_float)
    except (ValueError, TypeError) as exc:
        raise ResponsesContractError("OUTPUT_JSON_INVALID") from exc
    if not isinstance(parsed, dict) or set(parsed) != {
        "report_id", "title", "full_text", "observations_used", "numeric_claims"
    }:
        _fail("OUTPUT_SCHEMA_VIOLATION")
    if parsed["report_id"] != context.report_id:
        _fail("OUTPUT_REPORT_ID_MISMATCH")
    # The final semantic checker is the existing D1 model-output validator.
    # Use its mock contract with the real response_id/usage; no model data fixing.
    from .shadow_worker import validate_mock_response, ShadowBlocked
    try:
        full_text = validate_mock_response({
            "response_id": response_id,
            "status": "completed",
            "report_id": parsed["report_id"],
            "title": parsed["title"],
            "full_text": parsed["full_text"],
            "observations_used": parsed["observations_used"],
            "usage": {
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"]
            },
            "refusal": None
        }, context, snapshot)
    except (ShadowBlocked, ValueError, KeyError, TypeError) as exc:
        raise ResponsesContractError("OUTPUT_SHADOW_VALIDATION_BLOCKED") from exc
    # The model's numerical claims and its natural-language summary can
    # contradict one another. Reject objectively detectable contradictions
    # before accepting the private draft; complete evidence and extended SOP
    # checks are handled by the separate production release preflight.
    from .d3_narrative_quality import check_narrative_quality
    narrative = check_narrative_quality(
        context, snapshot, parsed["title"], full_text, require_full_sop=False
    )
    if narrative.status != "PASS":
        raise ResponsesContractError("NARRATIVE_FACT_CONTRADICTION:" + "|".join(narrative.issues))
    # The model-supplied spans are audited against independently frozen
    # source data. A JSON schema or self-declared citation grants no authority.
    try:
        audit = audit_numeric_claims(context, snapshot, full_text, parsed["numeric_claims"])
    except NumericClaimBlocked as exc:
        raise ResponsesContractError("NUMERIC_CLAIM_AUDIT_BLOCKED:" + str(exc)) from exc
    # The parsed response-object hash is NOT a hash of the original HTTP bytes.
    # Only record a raw-byte digest when exact original bytes are independently
    # supplied and verified against the parsed object. A digest alone does not
    # establish API/provider authenticity.
    normalized_sha = sha256_bytes(json_bytes(raw))
    raw_sha = None
    if raw_response_bytes is not None:
        if type(raw_response_bytes) is not bytes:
            _fail("RAW_RESPONSE_BYTES_NOT_BYTES")
        try:
            original_object = json.loads(
                raw_response_bytes.decode("utf-8"),
                object_pairs_hook=_no_duplicate_keys, parse_constant=_bad_float
            )
            original_canonical = json_bytes(original_object)
        except (UnicodeError, ValueError, TypeError) as exc:
            raise ResponsesContractError("RAW_RESPONSE_BYTES_INVALID") from exc
        if original_canonical != json_bytes(raw):
            _fail("RAW_RESPONSE_OBJECT_MISMATCH")
        raw_sha = sha256_bytes(raw_response_bytes)
    return CapturedResponse(
        response_id, status, expected_model,
        {"input_tokens": usage["input_tokens"],
         "output_tokens": usage["output_tokens"],
         "total_tokens": usage["total_tokens"]},
        full_text, parsed["title"], parsed["report_id"],
        tuple(parsed["observations_used"]),
        raw_sha,
        normalized_sha,
        sha256_bytes(full_text.encode("utf8")),
        audit.source_bundle_sha256,
        audit.checked_claims
    )


def estimate_usage_usd(usage: dict) -> Decimal:
    """Official standard text-token rates on 2026-10-15; excludes storage etc."""
    if not isinstance(usage, dict) or any(
        type(usage.get(k)) is not int or usage[k] < 0
        for k in ("input_tokens", "output_tokens")
    ):
        _fail("USAGE_INVALID")
    return (Decimal(usage["input_tokens"]) * INPUT_RATE_USD_PER_MILLION +
            Decimal(usage["output_tokens"]) * OUTPUT_RATE_USD_PER_MILLION) / Decimal(1000000)
