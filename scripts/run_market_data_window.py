#!/usr/bin/env python3
"""Run resilient scheduled market-data acquisition attempts.

The script can run one or several Japan-time attempts, records every real
attempt in a committed audit log, and keeps the committed GitHub market-data
layer usable as the canonical source for the Google Sheets pull/import layer.

Important operational rules:
- only verified/degraded attempts count as completed;
- blocked attempts do not satisfy the schedule;
- excessively late attempts are recorded as expired instead of being replayed
  minutes or hours later and falsely appearing on-time;
- final health checks may use --mode full to force a fresh snapshot;
- Google Sheets reads data/market/chatgpt_input.csv through IMPORTDATA, so
  service-account credentials are not required by this workflow.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
JST = dt.timezone(dt.timedelta(hours=9))


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST).replace(microsecond=0)


def iso(value: dt.datetime | None = None) -> str:
    return (value or now_jst()).astimezone(JST).isoformat()


def iso_utc(value: dt.datetime | None = None) -> str:
    return (value or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def workflow_run_url() -> str | None:
    run_id = os.environ.get("GITHUB_RUN_ID")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not run_id or not repository:
        return None
    return f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com').rstrip('/')}/{repository}/actions/runs/{run_id}"


def run(command: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), flush=True)
    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=capture,
        env=os.environ.copy(),
    )


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def parse_times(value: str) -> list[str]:
    result: list[str] = []
    for item in value.split(","):
        item = item.strip()
        try:
            dt.datetime.strptime(item, "%H:%M")
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid HH:MM time: {item}") from exc
        if item not in result:
            result.append(item)
    return sorted(result)


def target_datetime(day: dt.date, hhmm: str) -> dt.datetime:
    hour, minute = (int(part) for part in hhmm.split(":"))
    return dt.datetime.combine(day, dt.time(hour, minute), tzinfo=JST)


def audit_path(day: dt.date, slot: str) -> Path:
    return ROOT / "data" / "market" / "acquisition_runs" / f"{day.isoformat()}_{slot.replace(':', '-')}.jsonl"


def read_audit(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def completed_times(path: Path, slot: str) -> set[str]:
    return {
        str(item.get("scheduledTime"))
        for item in read_audit(path)
        if item.get("reportSlot") == slot and item.get("outcome") in {"verified", "degraded"}
        and not item.get("recoveryAfterExpiry")
    }


def snapshot_is_current(payload: dict[str, Any], slot: str, day: dt.date) -> bool:
    """Return whether GitHub already exposes a usable snapshot for this slot/day."""
    generated = str(payload.get("generatedAt") or "")
    try:
        produced_at = dt.datetime.fromisoformat(generated.replace("Z", "+00:00"))
        if produced_at.tzinfo is None:
            return False
        produced_at = produced_at.astimezone(JST)
        report_cutoff = target_datetime(day, slot)
    except (ValueError, TypeError):
        return False
    if not (
        payload.get("reportSlot") == slot
        and produced_at.date() == day
        and produced_at <= report_cutoff
        and payload.get("overallStatus") in {"verified", "degraded"}
    ):
        return False
    for market in (payload.get("markets") or {}).values():
        if not isinstance(market, dict):
            return False
        if market.get("asOf"):
            try:
                observed_at = dt.datetime.fromisoformat(str(market["asOf"]).replace("Z", "+00:00"))
                if observed_at.tzinfo is None or observed_at.astimezone(JST) > report_cutoff:
                    return False
            except (ValueError, TypeError):
                return False
    return True


def report_ready(snapshot_ready: bool, evidence_main_ready: bool) -> bool:
    """The report gate requires both current acquisition and immutable main evidence."""
    return snapshot_ready and evidence_main_ready


def append_audit(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")


def wait_until(target: dt.datetime) -> None:
    while True:
        remaining = (target - now_jst()).total_seconds()
        if remaining <= 0:
            return
        sleep_seconds = min(60.0, remaining)
        print(f"Waiting {sleep_seconds:.0f}s for {target.strftime('%Y-%m-%d %H:%M JST')}", flush=True)
        time.sleep(sleep_seconds)


def git_sync() -> None:
    run(["git", "pull", "--rebase"], check=True)


def git_commit_push(message: str, *, evidence_path: Path | None = None) -> bool:
    paths = ["data/market", "data/dashboard.json"]
    if evidence_path is not None and evidence_path.is_file():
        paths.append(evidence_path.relative_to(ROOT).as_posix())
    run(["git", "add", *paths], check=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=ROOT,
        text=True,
        env=os.environ.copy(),
    )
    if staged.returncode == 0:
        print("No staged market-data changes to commit.", flush=True)
        run(["git", "push"], check=True)
        return False
    run(["git", "commit", "-m", message], check=True)
    run(["git", "pull", "--rebase"], check=True)
    run(["git", "push"], check=True)
    return True


def freeze_slot_evidence(day: dt.date, slot: str) -> Path:
    """Freeze the just-acquired slot while still before its publication cutoff."""
    if __package__:
        from .persist_report_slot_evidence import persist_slot_evidence
    else:
        from persist_report_slot_evidence import persist_slot_evidence

    path, created = persist_slot_evidence(
        day.isoformat(),
        slot,
        ROOT / "data" / "market" / "latest.json",
        ROOT / "data" / "report-evidence",
        max_age_minutes=15,
        require_live_before_slot=True,
    )
    print(f"PRE_DRAFT_EVIDENCE_{'CREATED' if created else 'NO_OP'}={path.as_posix()}", flush=True)
    return path


def verify_main_file(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    run(["git", "fetch", "origin", "main"], check=True)
    result = subprocess.run(
        ["git", "show", f"origin/main:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    return result.stdout


def verify_main_evidence(
    path: Path,
    day: dt.date | None = None,
    slot: str | None = None,
) -> bool:
    """Verify the exact evidence bytes through a fresh read of origin/main."""
    relative = path.relative_to(ROOT).as_posix()
    if day is not None and slot is not None:
        if __package__:
            from .persist_report_slot_evidence import require_before_slot, validate_stored_slot_evidence
        else:
            from persist_report_slot_evidence import require_before_slot, validate_stored_slot_evidence
        require_before_slot(day.isoformat(), slot)
    remote_bytes = verify_main_file(path)
    if day is not None and slot is not None:
        require_before_slot(day.isoformat(), slot)
    local_bytes = path.read_bytes()
    if remote_bytes != local_bytes:
        raise RuntimeError(f"BLOCKED_MAIN_EVIDENCE_READBACK_MISMATCH: {relative}")
    if day is not None and slot is not None:
        validate_stored_slot_evidence(local_bytes, day.isoformat(), slot)
        require_before_slot(day.isoformat(), slot)
    print(f"PRE_DRAFT_EVIDENCE_MAIN_READBACK=PASS sha256={hashlib.sha256(local_bytes).hexdigest()}", flush=True)
    return True


def verify_main_audit_record(
    audit: Path,
    record: dict[str, Any],
    day: dt.date | None = None,
    slot: str | None = None,
) -> bool:
    if day is not None and slot is not None:
        if __package__:
            from .persist_report_slot_evidence import require_before_slot
        else:
            from persist_report_slot_evidence import require_before_slot
        require_before_slot(day.isoformat(), slot)
    expected_line = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    remote_lines = verify_main_file(audit).splitlines()
    if day is not None and slot is not None:
        require_before_slot(day.isoformat(), slot)
    if expected_line not in remote_lines:
        raise RuntimeError("BLOCKED_MAIN_AUDIT_READBACK_MISMATCH")
    return True


def record_evidence_readback(audit: Path, day: dt.date, slot: str, path: Path, status: str, reason: str | None = None) -> bool:
    data = path.read_bytes() if path.is_file() else b""
    evidence_hash = hashlib.sha256(data).hexdigest() if data else None
    prior = [
        item
        for item in read_audit(audit)
        if item.get("auditEvent") == "pre_draft_evidence_main_readback"
        and item.get("evidenceHash") == evidence_hash
    ]
    if prior and prior[-1].get("evidenceStatus") == status:
        record = prior[-1]
        print(f"PRE_DRAFT_EVIDENCE_READBACK_AUDIT_NO_OP={status}", flush=True)
    else:
        record = {
            "auditEvent": "pre_draft_evidence_main_readback",
            "scheduledDate": day.isoformat(),
            "reportSlot": slot,
            "recordedAtJST": iso(),
            "recordedAtUTC": iso_utc(),
            "workflowRunId": os.environ.get("GITHUB_RUN_ID", ""),
            "actionsUrl": workflow_run_url(),
            "evidencePath": path.relative_to(ROOT).as_posix(),
            "evidenceHash": evidence_hash,
            "evidenceStatus": status,
            "reason": reason,
        }
        append_audit(audit, record)
    git_commit_push(f"Record pre-draft evidence readback {day.isoformat()} {slot}")
    if status == "VERIFIED_ON_MAIN":
        verify_main_audit_record(audit, record, day, slot)
    else:
        verify_main_audit_record(audit, record)
    return True


def sheets_pull_status(status: str) -> tuple[str, str]:
    """Describe the Google Sheets handoff used by the current architecture.

    GitHub Actions no longer writes to Google Sheets with a service account.
    Verified CSV is committed to GitHub and the spreadsheet imports it from
    the hidden GitHub_Market_Import sheet.
    """
    if status == "blocked":
        return (
            "skipped_blocked",
            "Blocked staged data is not exposed as usable data to the Google Sheets pull layer.",
        )
    return (
        "pull_importdata",
        "Google Sheets pulls data/market/chatgpt_input.csv through GitHub_Market_Import/IMPORTDATA; no service-account credentials are required.",
    )


def perform_attempt(
    slot: str,
    scheduled_day: dt.date,
    scheduled_time: str,
    trigger_source: str,
    audit: Path,
    mode: str,
    late_minutes: float,
    recovery_after_expiry: bool = False,
    freeze_evidence: bool = False,
) -> dict[str, Any]:
    started = now_jst()
    os.environ["ACQUISITION_TRIGGER_SOURCE"] = trigger_source
    os.environ["ACQUISITION_SCHEDULED_TIME"] = scheduled_time

    run([
        sys.executable,
        "scripts/run_market_data_acquisition.py",
        "--slot",
        slot,
        "--mode",
        mode,
        "--print-summary",
    ])
    run([sys.executable, "scripts/build_market_sheet_exports.py"])
    run([
        sys.executable,
        "scripts/build_market_json.py",
        "--market-data",
        "data/market/latest.json",
        "--dashboard",
        "data/dashboard.json",
    ])

    payload = load_json(ROOT / "data" / "market" / "latest.json", {})
    status = str(payload.get("overallStatus") or "blocked")
    sheets_outcome, sheets_message = sheets_pull_status(status)
    evidence_path: Path | None = None
    evidence_error: str | None = None
    evidence_status = "NOT_ATTEMPTED"
    if freeze_evidence and status in {"verified", "degraded"}:
        try:
            expected_evidence = ROOT / "data" / "report-evidence" / f"{scheduled_day.isoformat()}_{slot.replace(':', '-')}-r1.json"
            if expected_evidence.is_file():
                # Retry the exact immutable candidate after a prior push/readback
                # failure. Never rebuild this report ID from newer market data.
                evidence_path = expected_evidence
                evidence_status = "LOCAL_EXISTING"
            else:
                evidence_path = freeze_slot_evidence(scheduled_day, slot)
                evidence_status = "LOCAL_FROZEN"
        except Exception as exc:
            evidence_error = f"{type(exc).__name__}: {exc}"
            evidence_status = "BLOCKED_FREEZE"
            print(f"PRE_DRAFT_EVIDENCE_BLOCKED={evidence_error}", file=sys.stderr, flush=True)
    elif not freeze_evidence and status in {"verified", "degraded"}:
        evidence_status = "ALREADY_VERIFIED_ON_MAIN"
    completed = now_jst()
    acquisition = payload.get("acquisition") or {}
    targeted = acquisition.get("targetedSymbols") or []
    record = {
        "scheduledDate": scheduled_day.isoformat(),
        "scheduledTime": scheduled_time,
        "reportSlot": slot,
        "triggerSource": trigger_source,
        "workflowRunId": os.environ.get("GITHUB_RUN_ID", ""),
        "workflowRunAttempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "actionsUrl": workflow_run_url(),
        "startedAt": iso(started),
        "completedAt": iso(completed),
        "durationSeconds": round((completed - started).total_seconds(), 1),
        "startedAtUTC": iso_utc(started),
        "completedAtUTC": iso_utc(completed),
        "scheduledAtJST": target_datetime(scheduled_day, scheduled_time).isoformat(),
        "scheduledAtUTC": target_datetime(scheduled_day, scheduled_time).astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "lateMinutes": round(max(0.0, late_minutes), 1),
        "recoveryAfterExpiry": recovery_after_expiry,
        "outcome": status,
        "acquisitionStatus": status,
        "missingRequired": payload.get("missingRequired") or [],
        "fallbackCount": payload.get("fallbackCount", 0),
        "runCount": acquisition.get("runCount", 0),
        "mode": acquisition.get("mode") or mode,
        "targetedSymbols": targeted,
        "effectiveFetch": bool(targeted),
        "recoveredSymbols": acquisition.get("recoveredSymbols") or [],
        "remainingUnavailable": acquisition.get("remainingUnavailable") or [],
        "sheetsSyncMode": "pull_importdata",
        "sheetsOutcome": sheets_outcome,
        "sheetsMessage": sheets_message,
        "reportDataSource": "ChatGPT_Market_Input via GitHub_Market_Import/IMPORTDATA",
        "reportDataFallback": "data/market/latest.json",
        "evidenceStatus": evidence_status,
        "evidenceFailure": evidence_error,
    }
    append_audit(audit, record)
    try:
        git_commit_push(
            f"Record {slot} market data attempt {scheduled_time}",
            evidence_path=evidence_path,
        )
    except Exception as exc:
        persistence_failure = f"{type(exc).__name__}: {exc}"
        if evidence_path is not None:
            record["evidenceStatus"] = "BLOCKED_GIT_PUSH"
            record["evidenceFailure"] = persistence_failure
            record["evidenceReadback"] = "BLOCKED"
        else:
            # The immutable evidence may already have been verified on main;
            # a later acquisition-audit push failure must not rewrite that fact.
            record["auditStatus"] = "BLOCKED_GIT_PUSH"
        append_audit(audit, {
            "auditEvent": "market_attempt_persistence_failure",
            "scheduledDate": scheduled_day.isoformat(),
            "scheduledTime": scheduled_time,
            "reportSlot": slot,
            "recordedAtJST": iso(),
            "recordedAtUTC": iso_utc(),
            "workflowRunId": os.environ.get("GITHUB_RUN_ID", ""),
            "actionsUrl": workflow_run_url(),
            "acquisitionStatus": status,
            "evidenceStatus": record["evidenceStatus"],
            "auditStatus": "BLOCKED_GIT_PUSH",
            "reason": persistence_failure,
        })
        print(f"ACQUISITION_AUDIT_PUSH_BLOCKED={persistence_failure}", file=sys.stderr, flush=True)
        return record
    if evidence_path is not None:
        try:
            verify_main_evidence(evidence_path, scheduled_day, slot)
            record_evidence_readback(audit, scheduled_day, slot, evidence_path, "VERIFIED_ON_MAIN")
        except Exception as exc:
            evidence_error = f"{type(exc).__name__}: {exc}"
            record["evidenceStatus"] = "BLOCKED_MAIN_READBACK"
            record["evidenceFailure"] = evidence_error
            record["evidenceReadback"] = "BLOCKED"
            print(f"PRE_DRAFT_EVIDENCE_READBACK_BLOCKED={evidence_error}", file=sys.stderr, flush=True)
            try:
                record_evidence_readback(audit, scheduled_day, slot, evidence_path, "BLOCKED", evidence_error)
            except Exception as audit_exc:
                print(f"PRE_DRAFT_EVIDENCE_BLOCK_AUDIT_PUSH_BLOCKED={audit_exc}", file=sys.stderr, flush=True)
            return record
        record["evidenceStatus"] = "VERIFIED_ON_MAIN"
        record["evidenceReadback"] = "PASS"
    elif evidence_error:
        record["evidenceReadback"] = "BLOCKED"
    return record


def record_expired(
    audit: Path,
    slot: str,
    day: dt.date,
    scheduled_time: str,
    trigger_source: str,
    late_minutes: float,
) -> None:
    record = {
        "scheduledDate": day.isoformat(),
        "scheduledTime": scheduled_time,
        "reportSlot": slot,
        "triggerSource": trigger_source,
        "workflowRunId": os.environ.get("GITHUB_RUN_ID", ""),
        "workflowRunAttempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "actionsUrl": workflow_run_url(),
        "startedAt": iso(),
        "completedAt": iso(),
        "startedAtUTC": iso_utc(),
        "completedAtUTC": iso_utc(),
        "scheduledAtJST": target_datetime(day, scheduled_time).isoformat(),
        "scheduledAtUTC": target_datetime(day, scheduled_time).astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "lateMinutes": round(max(0.0, late_minutes), 1),
        "outcome": "expired",
        "effectiveFetch": False,
        "reason": "scheduled attempt started after the allowed catch-up window",
    }
    append_audit(audit, record)
    git_commit_push(f"Record expired {slot} market data attempt {scheduled_time}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", required=True, choices=("08:00", "12:00", "16:00", "21:00"))
    parser.add_argument("--times", required=True, type=parse_times)
    parser.add_argument("--trigger-source", default=os.environ.get("ACQUISITION_TRIGGER_SOURCE", "window"))
    parser.add_argument("--max-catchup-minutes", type=int, default=30)
    parser.add_argument("--mode", choices=("auto", "full"), default="auto")
    parser.add_argument(
        "--recover-expired",
        action="store_true",
        help=(
            "After recording expired scheduled attempts, fetch one explicitly late "
            "recovery snapshot when this slot/day still has no usable data."
        ),
    )
    args = parser.parse_args()

    run(["git", "config", "user.name", "github-actions[bot]"])
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])

    day = now_jst().date()
    audit = audit_path(day, args.slot)
    failures: list[str] = []
    evidence_path = ROOT / "data" / "report-evidence" / f"{day.isoformat()}_{args.slot.replace(':', '-')}-r1.json"
    evidence_main_ready = False
    if evidence_path.is_file():
        try:
            if verify_main_evidence(evidence_path, day, args.slot):
                record_evidence_readback(audit, day, args.slot, evidence_path, "VERIFIED_ON_MAIN")
                evidence_main_ready = True
        except Exception as exc:
            print(f"EXISTING_EVIDENCE_READBACK_BLOCKED={exc}", file=sys.stderr, flush=True)
            evidence_main_ready = False

    for scheduled_time in args.times:
        git_sync()
        done = completed_times(audit, args.slot)
        if scheduled_time in done:
            print(f"Already recorded: {args.slot} {scheduled_time}", flush=True)
            continue

        target = target_datetime(day, scheduled_time)
        age_minutes = (now_jst() - target).total_seconds() / 60.0
        # A Github runner can start an intended 15:50 acquisition at 21:13.
        # Do not relabel 21h prices as the 16h report even during recovery.
        if now_jst() >= target_datetime(day, args.slot):
            print(f"Past report cutoff for {args.slot}: no source acquisition", flush=True)
            record_expired(audit, args.slot, day, scheduled_time,
                           args.trigger_source, age_minutes)
            failures.append(scheduled_time)
            continue
        if age_minutes < 0:
            wait_until(target)
            age_minutes = max(0.0, (now_jst() - target).total_seconds() / 60.0)
        elif age_minutes > args.max_catchup_minutes:
            print(f"Skipping expired attempt {scheduled_time}: {age_minutes:.1f} minutes late", flush=True)
            record_expired(audit, args.slot, day, scheduled_time, args.trigger_source, age_minutes)
            failures.append(scheduled_time)
            continue
        else:
            print(f"Catching up {scheduled_time}: {age_minutes:.1f} minutes late", flush=True)

        try:
            record = perform_attempt(
                args.slot,
                day,
                scheduled_time,
                args.trigger_source,
                audit,
                args.mode,
                age_minutes,
                freeze_evidence=not evidence_main_ready,
            )
            if record.get("evidenceStatus") == "VERIFIED_ON_MAIN" and record.get("evidenceReadback") == "PASS":
                evidence_main_ready = True
            if record.get("outcome") not in {"verified", "degraded"}:
                failures.append(scheduled_time)
        except Exception as exc:
            print(f"Attempt {scheduled_time} failed: {exc}", file=sys.stderr, flush=True)
            failures.append(scheduled_time)
            # A multi-time manual/recovery window may continue to a later attempt.
            time.sleep(10)

    recovery_record: dict[str, Any] | None = None
    current_payload = load_json(ROOT / "data" / "market" / "latest.json", {})
    if (args.recover_expired and now_jst() <= target_datetime(day, args.slot)
            and not snapshot_is_current(current_payload, args.slot, day)):
        recovery_time = args.times[-1]
        recovery_lateness = max(
            0.0,
            (now_jst() - target_datetime(day, recovery_time)).total_seconds() / 60.0,
        )
        print(
            f"Running explicit late recovery for {args.slot}; "
            f"scheduled attempts remain expired ({recovery_lateness:.1f} minutes late).",
            flush=True,
        )
        try:
            recovery_record = perform_attempt(
                args.slot,
                day,
                recovery_time,
                args.trigger_source,
                audit,
                "full",
                recovery_lateness,
                recovery_after_expiry=True,
                freeze_evidence=not evidence_main_ready,
            )
            if recovery_record.get("evidenceStatus") == "VERIFIED_ON_MAIN" and recovery_record.get("evidenceReadback") == "PASS":
                evidence_main_ready = True
        except Exception as exc:
            print(f"Late recovery failed: {exc}", file=sys.stderr, flush=True)

    git_sync()
    # If the window was already acquired by a sibling attempt, let this run
    # freeze that verified input itself instead of waiting for the freeze cron.
    if (not evidence_main_ready and now_jst() < target_datetime(day, args.slot)
            and snapshot_is_current(load_json(ROOT / "data" / "market" / "latest.json", {}), args.slot, day)):
        try:
            candidate = ROOT / "data" / "report-evidence" / f"{day.isoformat()}_{args.slot.replace(':', '-')}-r1.json"
            evidence_path = candidate if candidate.is_file() else freeze_slot_evidence(day, args.slot)
            git_commit_push(f"Freeze pre-draft evidence for {day.isoformat()} {args.slot}", evidence_path=evidence_path)
            if verify_main_evidence(evidence_path, day, args.slot):
                record_evidence_readback(audit, day, args.slot, evidence_path, "VERIFIED_ON_MAIN")
                evidence_main_ready = True
        except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError, RuntimeError) as exc:
            print(f"PRE_DRAFT_EVIDENCE_BLOCKED={type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    final_done = completed_times(audit, args.slot)
    missing = [item for item in args.times if item not in final_done]
    final_payload = load_json(ROOT / "data" / "market" / "latest.json", {})
    current_snapshot_ready = snapshot_is_current(final_payload, args.slot, day)
    report_is_ready = report_ready(current_snapshot_ready, evidence_main_ready)
    evidence_failure_stage: str | None = None
    evidence_status = "VERIFIED_ON_MAIN" if evidence_main_ready else "BLOCKED"
    if not evidence_main_ready:
        evidence_failure_stage = "pre_draft_evidence"
        relevant_audit = [
            item for item in read_audit(audit)
            if item.get("evidenceStatus") in {
                "BLOCKED_FREEZE", "BLOCKED_GIT_PUSH", "BLOCKED_MAIN_READBACK",
                "BLOCKED_MAIN_EVIDENCE_READBACK", "BLOCKED_PRE_DRAFT_EVIDENCE_MISSING",
            }
        ]
        evidence_status = (
            str(relevant_audit[-1]["evidenceStatus"])
            if relevant_audit
            else ("BLOCKED_MAIN_EVIDENCE_READBACK" if evidence_path.is_file() else "BLOCKED_PRE_DRAFT_EVIDENCE_MISSING")
        )
        try:
            record_evidence_readback(
                audit,
                day,
                args.slot,
                evidence_path,
                evidence_status,
                "No immutable pre-draft evidence was verified on GitHub main before the report cutoff.",
            )
        except Exception as exc:
            print(f"PRE_DRAFT_EVIDENCE_BLOCK_AUDIT_PERSISTENCE_FAILED={exc}", file=sys.stderr, flush=True)
    summary = {
        "date": day.isoformat(),
        "reportSlot": args.slot,
        "expectedTimes": args.times,
        "completedTimes": sorted(final_done),
        "missingTimes": missing,
        "triggerSource": args.trigger_source,
        "mode": args.mode,
        "recoveryAfterExpiry": recovery_record,
        "currentSnapshotReady": current_snapshot_ready,
        "acquisitionStatus": "READY" if current_snapshot_ready else "BLOCKED",
        "preDraftEvidenceOnMain": evidence_main_ready,
        "evidenceStatus": evidence_status,
        "reportReady": report_is_ready,
        "reportStatus": "READY" if report_is_ready else "BLOCKED",
        "evidenceFailureStage": evidence_failure_stage,
        "actionsUrl": workflow_run_url(),
        "sheetsSyncMode": "pull_importdata",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if report_is_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
