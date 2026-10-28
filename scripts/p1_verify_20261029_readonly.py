#!/usr/bin/env python3
"""Read-only evidence check for 2026-10-29 P1 shadow one-shot (JST).

Does not invoke, resume, pause, deploy, build, or modify cloud resources.
"""
import datetime as dt
import json
import subprocess
import sys
from zoneinfo import ZoneInfo

PROJECT = "market-report-p1-shadow"
REGION = "asia-northeast1"
TARGET = "slot-0800-t13"
WATCHDOG = "p1-one-shot-verification-stop"
WORKFLOW = "p1-one-shot-verification"
SERVICE = "p1-report-shadow-ingress"
DAY = dt.date(2026, 10, 28)
JST = ZoneInfo("Asia/Tokyo")
UTC = dt.timezone.utc


def cloud(*args):
    command = ["gcloud", *args, f"--project={PROJECT}", "--format=json"]
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    if proc.returncode:
        raise RuntimeError(f"Cloud read failed: {' '.join(args)}\n{proc.stderr.strip()}")
    return json.loads(proc.stdout)


def timestamp(raw):
    if not raw:
        return None
    return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))


def expected_window(value, start_hour, start_minute, end_hour, end_minute):
    if value is None:
        return False
    local = value.astimezone(JST)
    return (dt.datetime.combine(DAY, dt.time(start_hour, start_minute), JST)
            <= local <= dt.datetime.combine(DAY, dt.time(end_hour, end_minute), JST))


def main():
    now = dt.datetime.now(JST)
    print("P1 SHADOW — 2026-10-29 07:47/07:50 JST read-only verification")
    if now.date() == DAY and now.time() < dt.time(7, 55):
        print("NOT READY: 07:55 JST以降に確認してください。")
        return 2

    target = cloud("scheduler", "jobs", "describe", TARGET, f"--location={REGION}")
    watchdog = cloud("scheduler", "jobs", "describe", WATCHDOG, f"--location={REGION}")
    for name, record in ((TARGET, target), (WATCHDOG, watchdog)):
        print(f"Scheduler {name}: state={record.get('state')} "
              f"lastAttemptTime={record.get('lastAttemptTime', 'ABSENT')} "
              f"lastStatus={record.get('status', {}).get('code', 'ABSENT')}")

    records = cloud("workflows", "executions", "list", WORKFLOW,
                    f"--location={REGION}", "--limit=60")
    begin = dt.datetime(2026, 10, 28, 22, 49, tzinfo=UTC)
    end = dt.datetime(2026, 10, 28, 23, 20, tzinfo=UTC)
    candidates = [r for r in records if r.get("startTime")
                  and begin <= timestamp(r["startTime"]) <= end]
    latest = max(candidates, key=lambda r: r["startTime"], default=None)
    if latest:
        exec_id = latest["name"].rsplit("/", 1)[-1]
        execution = cloud("workflows", "executions", "describe", exec_id,
                          f"--workflow={WORKFLOW}", f"--location={REGION}")
        result = execution.get("result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                result = None
        print(f"Workflow: {execution.get('state')} id={exec_id} "
              f"error={execution.get('error')}")
        if isinstance(result, dict):
            print("Workflow result:", result.get("result"),
                  "httpStatus:", result.get("httpStatus"),
                  "matchedIngressCount:", result.get("matchedIngressCount"))
            print("Workflow checks:", json.dumps(result.get("checks"), ensure_ascii=False))
    else:
        execution, result = None, None
        print("Workflow: NOT FOUND for 2026-10-29 07:49–08:20 JST")

    start_iso = "2026-10-28T22:45:00Z"
    end_iso = "2026-10-28T23:20:00Z"
    query = (
        'resource.type="cloud_run_revision" AND '
        f'resource.labels.service_name="{SERVICE}" AND '
        'jsonPayload.event="P1_INGRESS_RESULT" AND '
        f'timestamp>="{start_iso}" AND timestamp<="{end_iso}"'
    )
    logs = cloud("logging", "read", query, "--limit=200")
    scheduler_query = (
        'resource.type="cloud_scheduler_job" AND '
        f'resource.labels.job_id="{TARGET}" AND '
        f'timestamp>="{start_iso}" AND timestamp<="{end_iso}"'
    )
    scheduler_logs = cloud("logging", "read", scheduler_query, "--limit=100")
    scheduler_finishes = [
        entry for entry in scheduler_logs
        if (entry.get("jsonPayload") or {}).get("@type", "").endswith(".AttemptFinished")
        and expected_window(timestamp(entry.get("timestamp")), 7, 46, 7, 50)
    ]
    print("Target Scheduler AttemptFinished count:", len(scheduler_finishes))
    for entry in scheduler_finishes:
        payload = entry.get("jsonPayload") or {}
        print("  finished:", entry.get("timestamp"),
              "status:", payload.get("status"),
              "debugInfo:", payload.get("debugInfo"))
    matching = []
    for entry in logs:
        payload = entry.get("jsonPayload") or {}
        if (payload.get("jobId") == TARGET
                and payload.get("schedulerDateJst") == DAY.isoformat()
                and payload.get("schedulerTimeJst") == "07:47"
                and payload.get("reportId") == "2026-10-29_08-00"):
            matching.append(payload)
    print("Cloud Run exact matching app logs:", len(matching))
    for value in matching[:3]:
        print("  httpStatus:", value.get("httpStatus"),
              "oidc:", value.get("oidcResult"),
              "jobName:", value.get("jobNameResult"),
              "scheduleTime:", value.get("scheduleTimeResult"))

    checks = result.get("checks") if isinstance(result, dict) else {}
    checks = checks if isinstance(checks, dict) else {}
    critical = ("http", "oidc", "jobName", "scheduleTime", "schedulerAttempt",
                "targetPauseReadback", "watchdogPauseReadback", "logs", "logCorrelation")
    reasons = []
    if target.get("state") != "PAUSED":
        reasons.append("07:47 scheduler not PAUSED")
    if watchdog.get("state") != "PAUSED":
        reasons.append("07:50 watchdog not PAUSED")
    # lastAttemptTime may be absent once a job has been paused; use durable
    # Cloud Scheduler AttemptFinished logs rather than inferring no invocation.
    if len(scheduler_finishes) != 1:
        reasons.append("not exactly one Scheduler AttemptFinished at 07:47")
    elif (scheduler_finishes[0].get("jsonPayload") or {}).get("status"):
        reasons.append("Scheduler AttemptFinished reported a failed HTTP call")
    if not expected_window(timestamp(watchdog.get("lastAttemptTime")), 7, 49, 7, 56):
        reasons.append("watchdog lastAttemptTime outside today's 07:49–07:56")
    if not execution or execution.get("state") != "SUCCEEDED":
        reasons.append("no successful Workflow execution at expected time")
    if not isinstance(result, dict) or result.get("result") != "PASS":
        reasons.append("Workflow verdict is not PASS")
    for key in critical:
        if checks.get(key) != "PASS":
            reasons.append(f"Workflow {key}: {checks.get(key, 'MISSING')}")
    if len(matching) != 1 or matching[0].get("httpStatus") != 200:
        reasons.append("no unique Cloud Run matching HTTP 200 app log")
    if reasons:
        print("\nVERDICT: NOT VERIFIED — do not declare the one-shot PASS.")
        for reason in reasons:
            print(" -", reason)
        if target.get("state") != "PAUSED" or watchdog.get("state") != "PAUSED":
            print("WARNING: unexpected ACTIVE Scheduler; stop it promptly via Cloud Shell.")
        return 1
    print("\nVERDICT: PASS — one-shot HTTP200, logging correlation and both PAUSED.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
        print(f"VERDICT: INCOMPLETE — {exc}", file=sys.stderr)
        sys.exit(3)
