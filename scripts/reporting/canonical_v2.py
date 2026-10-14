"""Cross-language canonical JSON v2 for *new* producer evidence.

Immutable legacy MarketDataSnapshot.snapshot_id continues to use snapshot.digest
(v1 Python JSON) and MUST NOT be recomputed by this serializer.

v2 evidence is an independently named digest of a typed, JSON-safe payload:
- mapping keys: ASCII identifiers (JSON key ordering independent of UTF-16);
- Python float: tagged object {"decimal_v2": repr(value)} (retains -0.0
  and 100.0, unlike JSON numeric decoding in JavaScript);
- integers: ECMAScript safe integer range; decimals never become raw floats;
- Unicode string values: UTF-8, no lone surrogates, no normalized substitutions;
- arrays: preserve order; no NaN, Infinity or unsupported types.
Uses Python json.dumps(sort_keys=True, ensure_ascii=False, compact separators).
Signer must independently validate data origin; hash equivalence != authenticity.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import math
import re

ASCII_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DECIMAL = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?$")
MAX_SAFE_INTEGER = 2**53 - 1
VERSION = "report-canonical-json/v2"


class CanonicalV2Error(ValueError):
    pass


def _valid_text(value: str):
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise CanonicalV2Error("lone surrogate in Unicode text")


def tagged_v2(value):
    """Convert typed values into a strictly interoperable JSON representation."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        _valid_text(value)
        return value
    if type(value) is int:
        if abs(value) > MAX_SAFE_INTEGER:
            raise CanonicalV2Error("unsafe integer cannot round-trip via JSON")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise CanonicalV2Error("nonfinite float cannot be canonically encoded")
        return {"decimal_v2": repr(value)}
    if isinstance(value, (list, tuple)):
        return [tagged_v2(item) for item in value]
    if isinstance(value, Mapping):
        output = {}
        for k, v in value.items():
            if not isinstance(k, str) or not ASCII_KEY.fullmatch(k):
                raise CanonicalV2Error("canonical object keys must be ASCII identifiers")
            _valid_text(k)
            output[k] = tagged_v2(v)
        if set(output) == {"decimal_v2"}:
            decimal = output["decimal_v2"]
            if not isinstance(decimal, str) or not DECIMAL.fullmatch(decimal):
                raise CanonicalV2Error("invalid tagged decimal")
        return output
    raise CanonicalV2Error("unsupported canonical value type")


def canonical_v2_bytes(value) -> bytes:
    """Accept typed payloads OR the already-tagged JSON representation."""
    result = tagged_v2(value)
    return json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def sha256_v2(value) -> str:
    return hashlib.sha256(canonical_v2_bytes(value)).hexdigest()
