"""Evidence-complete, fail-closed readiness boundary for AI market reports.

The Google/ChatGPT publisher must not treat successful model generation as
permission to publish. All evidence is frozen *before* the provider request.
Every entry requires a trustworthy document URL and a time that makes sense
for the report slot. Missing source families are never manufactured.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from urllib.parse import urlsplit
import json
import re

from .context import ReportContext, aware, JST
from .snapshot import MarketDataSnapshot
from .shadow_worker import freeze_shadow_input, json_bytes, REQUIRED_SIX

REQUIRED_CATEGORIES = ("news", "rates", "positioning", "events")
MORNING_EXTRA = ("valuation", "breadth", "us_equities", "cme_futures")
MAX_STALENESS = {
    "news": timedelta(hours=36),
    "rates": timedelta(days=5),
    "positioning": timedelta(days=14),
    "events": timedelta(days=7),
    "valuation": timedelta(days=5),
    "breadth": timedelta(days=5),
    "us_equities": timedelta(days=5),
    "cme_futures": timedelta(days=5),
}
SOURCE_URL_RE = re.compile(r"^https://", re.I)


@dataclass(frozen=True)
class ReleaseReadiness:
    state: str
    report_id: str
    snapshot_id: str | None
    evidence_sha256: str | None
    rejection_reasons: tuple[str, ...]

    @property
    def ready(self):
        return self.state == "READY_FOR_SEPARATE_MODEL_AUTHORIZATION"

    @property
    def publishable(self):
        # A generation-readiness assessment NEVER grants publish permission.
        return False


def _valid_https_url(value):
    if not isinstance(value, str) or not SOURCE_URL_RE.match(value):
        return False
    parts = urlsplit(value)
    return bool(parts.hostname and not parts.username and not parts.password and not parts.fragment)


def validate_release_evidence(context: ReportContext, snapshot: MarketDataSnapshot,
                              evidence: dict | None) -> ReleaseReadiness:
    """Validate source inclusion, as-of cutoff, and freshness; never call AI."""
    issues = []
    try:
        freeze_shadow_input(context, snapshot)
    except (ValueError, KeyError, TypeError) as exc:
        issues.append("MARKET_SNAPSHOT_INVALID:" + type(exc).__name__)

    if not isinstance(evidence, dict):
        return ReleaseReadiness("BLOCKED", context.report_id, snapshot.snapshot_id,
                                None, tuple(issues + ["EVIDENCE_MANIFEST_MISSING"]))
    if evidence.get("report_id") != context.report_id:
        issues.append("EVIDENCE_REPORT_ID_MISMATCH")
    if evidence.get("schema") != "market-report-evidence/v1":
        issues.append("EVIDENCE_SCHEMA_INVALID")
    if evidence.get("snapshot_id") != snapshot.snapshot_id:
        issues.append("EVIDENCE_SNAPSHOT_ID_MISMATCH")

    categories = list(REQUIRED_CATEGORIES)
    if context.report_time == "08:00":
        categories.extend(MORNING_EXTRA)
    cutoff = aware(context.data_cutoff)
    seen_ids = set()
    sources = evidence.get("sources")
    if not isinstance(sources, dict):
        sources = {}
        issues.append("SOURCES_OBJECT_REQUIRED")
    for category in categories:
        items = sources.get(category)
        if not isinstance(items, list) or not items:
            issues.append(f"REQUIRED_SOURCE_MISSING:{category}")
            continue
        for index, item in enumerate(items):
            prefix = f"{category}[{index}]"
            if not isinstance(item, dict):
                issues.append(f"SOURCE_NOT_OBJECT:{prefix}")
                continue
            document_id = item.get("id")
            headline = item.get("text")
            url = item.get("url")
            published = item.get("published_at")
            observed = item.get("as_of")
            if not isinstance(document_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{6,150}", document_id):
                issues.append(f"SOURCE_ID_INVALID:{prefix}")
            elif document_id in seen_ids:
                issues.append(f"SOURCE_ID_DUPLICATE:{prefix}")
            else:
                seen_ids.add(document_id)
            if not isinstance(headline, str) or not 8 <= len(headline.strip()) <= 1800:
                issues.append(f"SOURCE_TEXT_MISSING_OR_INVALID:{prefix}")
            if not _valid_https_url(url):
                issues.append(f"SOURCE_URL_INVALID:{prefix}")
            try:
                published_dt = aware(published)
                as_of_dt = aware(observed)
            except (TypeError, ValueError):
                issues.append(f"SOURCE_TIME_INVALID:{prefix}")
                continue
            # For future calendar items 'as_of' represents the verification
            # timestamp, not the future event start. Store event time separately.
            if published_dt > cutoff or as_of_dt > cutoff:
                issues.append(f"SOURCE_AFTER_REPORT_CUTOFF:{prefix}")
            if as_of_dt < cutoff - MAX_STALENESS[category]:
                issues.append(f"SOURCE_STALE:{prefix}")
            if published_dt > as_of_dt:
                issues.append(f"SOURCE_PUBLISHED_AFTER_OBSERVATION:{prefix}")
            if category == "events":
                event_time = item.get("event_at")
                try:
                    if not event_time or aware(event_time) <= cutoff:
                        issues.append(f"FUTURE_EVENT_TIME_INVALID:{prefix}")
                except (TypeError, ValueError):
                    issues.append(f"FUTURE_EVENT_TIME_INVALID:{prefix}")
    # All included source families are checked, even if they are not a
    # required category, so a hidden stale/news entry cannot be laundered.
    for category, records in sources.items():
        if category not in MAX_STALENESS:
            issues.append(f"UNKNOWN_EVIDENCE_CATEGORY:{category}")
        elif category not in categories and records:
            issues.append(f"UNEXPECTED_EVIDENCE_CATEGORY:{category}")
    digest = sha256(json_bytes(evidence)).hexdigest() if not issues else None
    return ReleaseReadiness(
        "READY_FOR_SEPARATE_MODEL_AUTHORIZATION" if not issues else "BLOCKED",
        context.report_id, snapshot.snapshot_id, digest, tuple(issues)
    )


def prepare_evidence_bound_request(context: ReportContext,
                                   snapshot: MarketDataSnapshot, evidence: dict,
                                   *, instructions: str, max_output_tokens=4000):
    """Build signed-by-content input; never generate, save, or grant consent."""
    readiness = validate_release_evidence(context, snapshot, evidence)
    if not readiness.ready:
        raise ValueError("EVIDENCE_PREFLIGHT_BLOCKED:" + "|".join(readiness.rejection_reasons))
    from .d2_responses_contract import build_request
    request = build_request(context, snapshot, instructions=instructions,
                            max_output_tokens=max_output_tokens)
    input_data = json.loads(request["input"])
    input_data["independently_sourced_context"] = evidence
    input_data["independent_evidence_sha256"] = readiness.evidence_sha256
    request["input"] = json.dumps(input_data, sort_keys=True,
                                   ensure_ascii=False, separators=(",", ":"),
                                   allow_nan=False)
    request["instructions"] += (
        "\n根拠資料と保存時刻が入力に含まれる範囲だけで分析すること。"
        "価格、ニュース、金利、需給、経済イベントは各々の根拠資料に結び付けること。"
        "情報源の文面から引用していない主張を検証済み事実と書かないこと。"
        "ソース公開時刻がレポート時刻より後の材料を絶対に利用しないこと。"
    )
    return request


def inspect_saved_input(*, context: ReportContext, payload: dict,
                        evidence: dict | None) -> ReleaseReadiness:
    """Include malformed acquisition failures as explicit blockers."""
    try:
        snapshot = MarketDataSnapshot.from_acquisition(context, payload)
        return validate_release_evidence(context, snapshot, evidence)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        return ReleaseReadiness("BLOCKED", context.report_id, None, None,
                                ("MARKET_INPUT_INVALID:" + str(exc),))
