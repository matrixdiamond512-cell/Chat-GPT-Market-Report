"""One canonical inspection path for an actual paid AI response.

A valid OpenAI response alone does NOT make a report publishable.
This boundary requires independent source completeness, strict structured
response/number auditing, exact title and full user SOP coverage. It never
modifies a source or writes to Drive/GitHub.
"""
from dataclasses import dataclass
from .context import ReportContext
from .snapshot import MarketDataSnapshot
from .d2_responses_contract import capture_response
from .d3_release_evidence import validate_release_evidence
from .d3_narrative_quality import check_narrative_quality


@dataclass(frozen=True)
class ReportCandidateReview:
    status: str
    report_id: str
    source_snapshot_id: str
    reasons: tuple[str, ...]
    evidence_sha256: str | None = None
    body_sha256: str | None = None
    model_response_id: str | None = None
    eligible_for_publication: bool = False


def review_model_candidate(*, context: ReportContext,
                           snapshot: MarketDataSnapshot,
                           evidence: dict | None, raw_response: dict,
                           raw_response_bytes: bytes | None = None) -> ReportCandidateReview:
    """No fixing or regenerating bad output, no public artifact mutation."""
    verified=validate_release_evidence(context,snapshot,evidence)
    if not verified.ready:
        return ReportCandidateReview(
            "BLOCKED_EVIDENCE",context.report_id,snapshot.snapshot_id,
            verified.rejection_reasons,
        )
    try:
        captured=capture_response(raw_response,context,snapshot,
                                  raw_response_bytes=raw_response_bytes)
    except (ValueError,TypeError,KeyError) as exc:
        return ReportCandidateReview(
            "BLOCKED_MODEL_RESPONSE",context.report_id,snapshot.snapshot_id,
            (str(exc),),evidence_sha256=verified.evidence_sha256
        )
    narrative=check_narrative_quality(
        context,snapshot,captured.title,captured.full_text,require_full_sop=True
    )
    if narrative.status!="PASS":
        return ReportCandidateReview(
            "BLOCKED_NARRATIVE",context.report_id,snapshot.snapshot_id,
            narrative.issues,evidence_sha256=verified.evidence_sha256,
            body_sha256=captured.body_sha256,model_response_id=captured.response_id,
        )
    # This is a PRIVATE generated draft only. Independently authenticated
    # producer provenance, Google Docs readback, and Pages readback are later
    # mandatory gates; a draft MUST NOT publish itself.
    return ReportCandidateReview(
        "PRIVATE_DRAFT_VALIDATED",context.report_id,snapshot.snapshot_id,(),
        evidence_sha256=verified.evidence_sha256,
        body_sha256=captured.body_sha256,model_response_id=captured.response_id,
    )
