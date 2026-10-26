"""Deterministic, non-market fixture provider for the isolated P1 cloud trial."""
from __future__ import annotations

import json

from scripts.report_continuity_ingress import SCHEDULER_TRIGGER_BODY
from scripts.report_continuity_shadow import SCHEDULER_ATTEMPTS
from scripts.resolve_market_report_slot import ReportIdentity


def acquire(identity: ReportIdentity, binding, trigger_body: bytes) -> bytes:
    """Return attempt-bound fixture bytes; never represents market data or publication proof."""
    if trigger_body != SCHEDULER_TRIGGER_BODY:
        raise ValueError("INVALID_SCHEDULER_TRIGGER")
    if type(binding.attempt_minutes) is not int or binding.attempt_minutes not in SCHEDULER_ATTEMPTS:
        raise ValueError("INVALID_SCHEDULER_ATTEMPT")
    record = {
        "attemptMinutes": binding.attempt_minutes,
        "kind": "P1_TEST_FIXTURE",
        "reportId": identity.report_id,
        "source": "fixture-not-market-data",
        "targetAt": identity.target.isoformat(),
    }
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
