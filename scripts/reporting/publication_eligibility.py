"""Single fail-closed rule for market-report public projections."""
from __future__ import annotations


_PUBLIC_STATUSES = {"PUBLISHED", "DOC_READBACK_PASS"}


def is_publication_eligible(report: object) -> bool:
    """Return whether a canonical report may enter public projections.

    Status-less entries predate the status contract and remain public history
    for compatibility. Once a status is explicit, only verified publication
    states are public. Source archives and unknown states fail closed.
    """
    if not isinstance(report, dict):
        return False
    status = str(report.get("report_status") or "").strip().upper()
    return not status or status in _PUBLIC_STATUSES
