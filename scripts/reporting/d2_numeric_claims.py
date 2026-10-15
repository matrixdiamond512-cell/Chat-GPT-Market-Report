"""D2 offline numeric-claim audit against already frozen acquisition data.

Conservative lexical coverage only: unknown numbers, units, dates, benchmarks,
option strikes, EPS/PER and news statistics MUST be blocked until backed by a
separate independently verified source adapter. A model's own claim list or
alleged citation is never sufficient evidence. No network, secrets or writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
import unicodedata

from .context import ReportContext
from .snapshot import MarketDataSnapshot
from .shadow_worker import REGISTRY, freeze_shadow_input, json_bytes, sha256_bytes

SCHEMA = "d2-numeric-claims/v1"
FIELDS = ("priceValue", "changeValue", "changePct")
CLAIM_KEYS = ("start", "literal", "series", "field", "source_id", "as_of")
# The text must use plain decimal numbers, not exponential form or estimated
# prose ("about 100"). The lexer still detects exponents as unmatched tokens.
NUMBER_RE = re.compile(
    r"(?<![0-9０-９.,．])(?:[+\-−＋－]?[0-9０-９]+"
    r"(?:[,，][0-9０-９]{3})*(?:[.．][0-9０-９]+)?)(?![0-9０-９.,．])"
)


class NumericClaimBlocked(ValueError):
    pass


@dataclass(frozen=True)
class NumericAudit:
    schema_version: str
    source_bundle_sha256: str
    checked_claims: int
    scanned_numbers: int
    status: str = "OFFLINE_LEXICAL_PASS"
    # This status is never publish permission or semantic truth attestation.
    publication_allowed: bool = False


def verified_source_bundle(context: ReportContext, snapshot: MarketDataSnapshot) -> dict:
    """Independently derive allowed fields from the frozen verified snapshot.

    No model-supplied citation/source URL, self-declared price or invented
    bundle may enlarge this set. Requires trusted upstream acquisition rights.
    """
    freeze_shadow_input(context, snapshot)
    return {
        "schema_version": "d2-verified-market-bundle/v1",
        "report_id": context.report_id,
        "revision": context.revision,
        "snapshot_id": snapshot.snapshot_id,
        "cutoff": context.data_cutoff,
        "observations": [
            {
                "series": m.instrument,
                "market_type": m.marketType,
                "as_of": m.asOf,
                "source": [{"id": s["id"], "url": s["url"]} for s in m.source],
                "unit": m.priceUnit,
                "priceValue": m.priceValue,
                "changeValue": m.changeValue,
                "changePct": m.changePct,
            }
            for m in snapshot.markets
        ],
    }


def _decimal(raw: str) -> Decimal:
    text = unicodedata.normalize("NFKC", raw).replace("−", "-")
    text = text.replace(",", "")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise NumericClaimBlocked("NUMERIC_LITERAL_NOT_DECIMAL") from exc
    if not number.is_finite():
        raise NumericClaimBlocked("NUMERIC_LITERAL_NONFINITE")
    return number


def _reserved_ranges(body: str, context: ReportContext, snapshot: MarketDataSnapshot):
    """Only the EXACT title line and fixed instrument labels are non-price metadata."""
    title_end = body.find("\n")
    if title_end < 0:
        raise NumericClaimBlocked("TITLE_LINE_MISSING")
    metadata = [(0, title_end)]
    # A literal instrument label (not an arbitrary prose number) can contain
    # digits, e.g. 日経225先物 or nikkei225_futures_ose.
    labels = {m.instrument for m in snapshot.markets}
    labels |= {REGISTRY[m.instrument]["displayName"] for m in snapshot.markets}
    for label in labels:
        if not any(c.isdigit() for c in label):
            continue
        for hit in re.finditer(re.escape(label), body[title_end+1:]):
            left = title_end + 1 + hit.start()
            right = title_end + 1 + hit.end()
            # Avoid allowing "225" at the start of a different larger number.
            if left and body[left-1].isdigit():
                continue
            if right < len(body) and body[right].isdigit():
                continue
            metadata.append((left, right))
    return metadata


def _non_claim_tokens(body: str, context: ReportContext, snapshot: MarketDataSnapshot):
    ranges = _reserved_ranges(body, context, snapshot)
    return [
        match for match in NUMBER_RE.finditer(body)
        if not any(a <= match.start() and match.end() <= b for a, b in ranges)
    ]


def audit_numeric_claims(context: ReportContext, snapshot: MarketDataSnapshot,
                         body: str, claims: list[dict]) -> NumericAudit:
    """Require 1:1 full-text lexical coverage with source-bound numeric spans.

    This is deliberately NOT a complete financial semantic validator. Numbers
    in news and tables without frozen source facts are rejected, not guessed.
    Source/timestamp affiliation is checked against the immutable snapshot;
    relatedness in surrounding natural-language prose is not yet guaranteed.
    """
    bundle = verified_source_bundle(context, snapshot)
    if not isinstance(body, str) or not body or not isinstance(claims, list):
        raise NumericClaimBlocked("NUMERIC_CLAIMS_MISSING")
    candidates = _non_claim_tokens(body, context, snapshot)
    spans = {(m.start(), m.group(0)): m for m in candidates}
    if len(spans) != len(candidates):
        raise NumericClaimBlocked("NUMERIC_TOKEN_AMBIGUOUS")
    if len(claims) != len(candidates):
        raise NumericClaimBlocked("NUMERIC_COVERAGE_INCOMPLETE")
    markets = {m.instrument: m for m in snapshot.markets}
    used = set()
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != set(CLAIM_KEYS):
            raise NumericClaimBlocked("NUMERIC_CLAIM_SCHEMA_INVALID")
        start, literal = claim["start"], claim["literal"]
        if type(start) is not int or not isinstance(literal, str):
            raise NumericClaimBlocked("NUMERIC_CLAIM_POSITION_INVALID")
        if (start, literal) not in spans or start in used:
            raise NumericClaimBlocked("NUMERIC_SPAN_UNKNOWN_OR_DUPLICATED")
        used.add(start)
        field, series = claim["field"], claim["series"]
        if field not in FIELDS or type(series) is not str or series not in markets:
            raise NumericClaimBlocked("NUMERIC_SOURCE_FIELD_UNVERIFIED")
        market = markets[series]
        if (claim["as_of"] != market.asOf or
                not any(claim["source_id"] == s["id"] for s in market.source)):
            raise NumericClaimBlocked("NUMERIC_SOURCE_TIME_OR_ID_MISMATCH")
        expected = getattr(market, field)
        if expected is None:
            raise NumericClaimBlocked("NUMERIC_SOURCE_VALUE_MISSING")
        actual = _decimal(literal)
        if actual != Decimal(str(expected)):
            raise NumericClaimBlocked("NUMERIC_VALUE_MISMATCH")
        if actual.is_zero() and actual.is_signed() != Decimal(str(expected)).is_signed():
            raise NumericClaimBlocked("NUMERIC_SIGNED_ZERO_MISMATCH")
        end = start + len(literal)
        suffix = body[end:end+1]
        if field == "changePct":
            if suffix not in ("%", "％"):
                raise NumericClaimBlocked("NUMERIC_PERCENT_UNIT_MISSING")
        elif suffix in ("%", "％"):
            raise NumericClaimBlocked("NUMERIC_UNIT_CONFLICT")
        # Disallow scientific notation, date fragments and mismatched extra
        # digits being disguised as independently claimed decimal numbers.
        if end < len(body) and (body[end] in "eE" and
                end+1 < len(body) and (body[end+1].isdigit() or body[end+1] in "+-")):
            raise NumericClaimBlocked("NUMERIC_UNSUPPORTED_EXPONENT")
    return NumericAudit(
        SCHEMA, sha256_bytes(json_bytes(bundle)), len(claims), len(candidates)
    )
