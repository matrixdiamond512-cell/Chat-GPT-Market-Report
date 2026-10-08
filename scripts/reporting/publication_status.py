"""Independent report and infographic publication status contract."""

from dataclasses import dataclass
from enum import Enum


class ReportStatus(str, Enum):
    PUBLISHED = "PUBLISHED"
    BLOCKED = "BLOCKED"


class InfographicStatus(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    FAILED_VALIDATION = "FAILED_VALIDATION"


@dataclass(frozen=True)
class PublicationStatus:
    report_status: ReportStatus
    infographic_status: InfographicStatus


def publication_status(*, report_validation_passed: bool, infographic_result: str | None = None) -> PublicationStatus:
    """Resolve each lane independently; infographic errors cannot block a valid report."""
    if not report_validation_passed:
        return PublicationStatus(ReportStatus.BLOCKED, InfographicStatus.NOT_READY)
    infographic = infographic_result or InfographicStatus.NOT_READY.value
    return PublicationStatus(ReportStatus.PUBLISHED, InfographicStatus(infographic))
