"""Offline result contract for one-shot P1 Scheduler verification.

The deployed safety workflow uses the same status vocabulary and acceptance
rules. This module is dependency-free so CI can exercise outcomes without GCP.
"""
from __future__ import annotations

from datetime import datetime, time
from typing import Any, Iterable
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
RESULTS = {"PASS", "FAIL", "BLOCKED", "INCOMPLETE"}


def _status_for_stage(events: Iterable[dict[str, Any]], stage: str) -> str:
    matches = [event for event in events
               if event.get("event") == "P1_AUTO_VERIFY_STAGE"
               and event.get("stage") == stage]
    if any(event.get("result") == "FAIL" for event in matches):
        return "FAIL"
    if any(event.get("result") == "PASS" for event in matches):
        return "PASS"
    return "INCOMPLETE"


def _is_expected_schedule_event(event: dict[str, Any], *, date_jst: str,
                                expected_job_id: str) -> bool:
    return (
        event.get("jobId") == expected_job_id
        and event.get("schedulerDateJst") == date_jst
        and event.get("schedulerTimeJst") == "07:47"
    )


def _last_attempt_matches(value: str | None, *, date_jst: str) -> bool | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return False
        local = parsed.astimezone(JST)
        if local.date().isoformat() != date_jst or local.weekday() >= 5:
            return False
        # Scheduler may dispatch slightly after its Cron minute. Keep a bounded
        # 4-minute window so a stale/manual execution cannot count as the run.
        start = datetime.combine(local.date(), time(7, 46), tzinfo=JST)
        end = datetime.combine(local.date(), time(7, 50), tzinfo=JST)
        return start <= local <= end
    except (TypeError, ValueError, OverflowError):
        return False


def evaluate_one_shot(*, expected_date_jst: str, expected_job_id: str,
                      events: Iterable[dict[str, Any]],
                      http_status: int | None,
                      scheduler_status_code: int | None,
                      scheduler_last_attempt_time: str | None,
                      target_state_after_pause: str | None,
                      watchdog_state_after_pause: str | None,
                      logs_read: bool) -> dict[str, Any]:
    """Classify one normal 07:47 JST run and independently observed stop state."""
    event_list = list(events)
    job_events = [event for event in event_list
                  if event.get("event") == "P1_AUTO_VERIFY_STAGE"
                  and event.get("jobId") == expected_job_id]

    http_result = ("INCOMPLETE" if http_status is None else
                   "PASS" if http_status == 200 else "FAIL")
    oidc_result = _status_for_stage(job_events, "OIDC")
    if oidc_result == "INCOMPLETE" and http_status in (401, 403):
        oidc_result = "FAIL"
    job_result = _status_for_stage(job_events, "JOB_NAME")
    if not any(event.get("stage") == "JOB_NAME" for event in job_events):
        # An unlisted job is explicitly a failed job check, never a passing run.
        if any(event.get("event") == "P1_AUTO_VERIFY_STAGE"
               and event.get("stage") == "JOB_NAME"
               and event.get("result") == "FAIL" for event in event_list):
            job_result = "FAIL"

    time_events = [event for event in job_events
                   if event.get("stage") == "SCHEDULE_TIME"]
    if any(event.get("result") == "FAIL" for event in time_events):
        time_result = "FAIL"
    elif any(event.get("result") == "PASS"
             and _is_expected_schedule_event(
                 event, date_jst=expected_date_jst,
                 expected_job_id=expected_job_id,
             ) for event in time_events):
        time_result = "PASS"
    elif any(event.get("result") == "PASS" for event in time_events):
        time_result = "FAIL"
    else:
        time_result = "INCOMPLETE"

    if not logs_read:
        log_result = "INCOMPLETE"
    else:
        log_result = "PASS" if job_events else "INCOMPLETE"

    if scheduler_status_code is None:
        scheduler_result = "INCOMPLETE"
    elif scheduler_status_code != 0:
        scheduler_result = "FAIL"
    else:
        attempt = _last_attempt_matches(
            scheduler_last_attempt_time, date_jst=expected_date_jst
        )
        scheduler_result = ("INCOMPLETE" if attempt is None else
                            "PASS" if attempt else "FAIL")

    target_stop = ("PASS" if target_state_after_pause == "PAUSED"
                   else "BLOCKED")
    watchdog_stop = ("PASS" if watchdog_state_after_pause == "PAUSED"
                     else "BLOCKED")
    stop_result = ("PASS" if target_stop == watchdog_stop == "PASS"
                   else "BLOCKED")

    checks = {
        "http": http_result,
        "oidc": oidc_result,
        "jobName": job_result,
        "scheduleTime": time_result,
        "schedulerAttempt": scheduler_result,
        "targetPauseReadback": target_stop,
        "watchdogPauseReadback": watchdog_stop,
        "logs": log_result,
    }
    if stop_result == "BLOCKED":
        overall = "BLOCKED"
    elif "FAIL" in checks.values():
        overall = "FAIL"
    elif all(value == "PASS" for value in checks.values()):
        overall = "PASS"
    else:
        overall = "INCOMPLETE"

    return {
        "schemaVersion": 1,
        "dateJst": expected_date_jst,
        "expectedJobId": expected_job_id,
        "expectedSchedulerTimeJst": "07:47",
        "checks": checks,
        "overall": overall,
    }
