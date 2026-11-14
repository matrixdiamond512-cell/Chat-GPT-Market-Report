"""Fail-closed, side-effect-free contract for an external 07:48 JST close-sync trigger.

This module does NOT authenticate a caller, invoke GitHub, acquire data, or write
Sheets. A future runtime must first verify the Cloud Scheduler signed OIDC token,
pin a dedicated caller and exact job resource, and use a durable create-only
idempotency claim before considering workflow_dispatch. This pure contract is
intentionally not a production entry point.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json

JST = timezone(timedelta(hours=9))
INTENDED_HOUR = 7
INTENDED_MINUTE = 48
ACQUISITION_LABEL = "07:50"
REPORT_SLOT = "08:00"
WORKFLOW = "market-data-08-anchor.yml"
REPOSITORY = "matrixdiamond512-cell/Chat-GPT-Market-Report"


class TriggerContractError(ValueError):
    """Fail closed when the claimed external trigger is not an allowed slot."""


@dataclass(frozen=True)
class TriggerIntent:
    report_id: str
    service_date: str
    requested_at_jst: str
    deadline_jst: str
    claim_key: str
    workflow: str
    repository: str
    ref: str
    inputs: dict[str, str]

    def public_diagnostic(self) -> dict[str, str]:
        return {
            "reportId": self.report_id,
            "serviceDate": self.service_date,
            "claimKey": self.claim_key,
            "workflow": self.workflow,
            "state": "CONTRACT_ONLY_NOT_DISPATCHED",
        }


def _instant(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise TriggerContractError("SCHEDULE_TIME_REQUIRED")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TriggerContractError("SCHEDULE_TIME_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TriggerContractError("SCHEDULE_TIME_TZ_REQUIRED")
    return parsed.astimezone(JST)


def resolve_trigger_intent(
    *,
    job_header: str,
    expected_job_resource: str,
    schedule_time_header: str,
    started_at: datetime,
) -> TriggerIntent:
    """Accept only one weekday 07:48 Scheduler attempt for the 07:50 label.

    Caller identity and cryptographic OIDC verification are required upstream:
    a job-name HTTP header alone is never an authentication credential.
    """
    parts = expected_job_resource.split("/") if isinstance(expected_job_resource, str) else []
    if (len(parts) != 6 or parts[0] != "projects"
            or parts[2] != "locations" or parts[4] != "jobs"
            or not parts[1] or not parts[3] or not parts[5]):
        raise TriggerContractError("EXPECTED_JOB_RESOURCE_INVALID")
    if job_header != parts[-1]:
        raise TriggerContractError("SCHEDULER_JOB_MISMATCH")
    scheduled = _instant(schedule_time_header)
    if scheduled.weekday() >= 5:
        raise TriggerContractError("NON_BUSINESS_WEEKDAY")
    if (scheduled.hour, scheduled.minute, scheduled.second) != (
            INTENDED_HOUR, INTENDED_MINUTE, 0):
        raise TriggerContractError("SCHEDULE_TIME_MISMATCH")
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise TriggerContractError("START_TIME_TZ_REQUIRED")
    current = started_at.astimezone(JST)
    nominal = scheduled.replace(second=0, microsecond=0)
    cutoff = nominal.replace(hour=7, minute=50)
    if current < nominal:
        raise TriggerContractError("START_BEFORE_SCHEDULE")
    if current >= cutoff:
        raise TriggerContractError("CLOSE_TRIGGER_AFTER_CUTOFF")
    if current.date() != scheduled.date():
        raise TriggerContractError("SCHEDULER_START_DATE_MISMATCH")
    report_id = f"{scheduled.date().isoformat()}_08-00"
    day = scheduled.date().isoformat()
    # Deterministic across retries, independent of arbitrary HTTP body content.
    claim_key = f"test-only/close-dispatch/{day}_07-50/claim.json"
    return TriggerIntent(
        report_id=report_id,
        service_date=day,
        requested_at_jst=nominal.isoformat(),
        deadline_jst=cutoff.isoformat(),
        claim_key=claim_key,
        workflow=WORKFLOW,
        repository=REPOSITORY,
        ref="main",
        inputs={"permission_probe": "false", "scheduled_time": ACQUISITION_LABEL},
    )


def claim_body(intent: TriggerIntent) -> bytes:
    """Deterministic draft claim bytes; not a dispatch receipt or success proof."""
    content = {
        "schemaVersion": "close-sync-trigger-claim/v1",
        "reportId": intent.report_id,
        "serviceDate": intent.service_date,
        "scheduledAt": intent.requested_at_jst,
        "workflow": intent.workflow,
        "inputs": intent.inputs,
    }
    return (json.dumps(content, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")


def claim_digest(intent: TriggerIntent) -> str:
    return hashlib.sha256(claim_body(intent)).hexdigest()
