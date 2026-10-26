"""Offline result contract for one-shot P1 Scheduler verification.

The deployed safety workflow uses the same status vocabulary and acceptance
rules. This module is dependency-free so CI can exercise outcomes without GCP.
"""
from __future__ import annotations

from datetime import datetime, time
from typing import Any, Iterable
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


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
    """Classify today's normal 07:47 JST run and independent stop readbacks."""
    records = [event for event in events
               if event.get("event") == "P1_INGRESS_RESULT"]
    expected = [event for event in records
                if event.get("jobId") == expected_job_id]
    unlisted = [event for event in records
                if event.get("jobId") == "UNLISTED"]
    record = expected[-1] if expected else (unlisted[-1] if unlisted else {})

    http_result = ("INCOMPLETE" if http_status is None else
                   "PASS" if http_status == 200 else "FAIL")
    oidc_result = record.get("oidcResult", "INCOMPLETE")
    job_result = record.get("jobNameResult", "INCOMPLETE")
    time_result = record.get("scheduleTimeResult", "INCOMPLETE")
    if (time_result == "PASS"
            and (record.get("schedulerDateJst") != expected_date_jst
                 or record.get("schedulerTimeJst") != "07:47")):
        time_result = "FAIL"
    if oidc_result == "INCOMPLETE" and http_status in (401, 403):
        oidc_result = "FAIL"
    if not logs_read or not record:
        log_result = "INCOMPLETE"
    else:
        log_result = "PASS"

    if scheduler_status_code is None or scheduler_last_attempt_time is None:
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
