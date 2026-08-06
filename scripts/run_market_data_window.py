#!/usr/bin/env python3
"""Run a resilient multi-attempt market-data acquisition window.

This script is used by the 07:00 primary and fallback workflows.  A single
runner stays alive across the requested Japan-time schedule, records every
attempt in a committed daily audit log, writes the best staged data to Google
Sheets when configured, and commits each attempt before waiting for the next
one.  Separate primary/fallback workflows share a concurrency group, so a
fallback run waits for the primary and then exits after confirming the audit.
"""

from __future__ import annotations

import argparse
import datetime as dt
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
        if item.get("reportSlot") == slot and item.get("outcome") in {"verified", "degraded", "blocked"}
    }


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


def git_commit_push(message: str) -> bool:
    run(["git", "add", "data/market", "data/dashboard.json"], check=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=ROOT,
        text=True,
        env=os.environ.copy(),
    )
    if staged.returncode == 0:
        print("No staged market-data changes to commit.", flush=True)
        return False
    run(["git", "commit", "-m", message], check=True)
    run(["git", "pull", "--rebase"], check=True)
    run(["git", "push"], check=True)
    return True


def sync_sheets(status: str) -> tuple[str, str]:
    if status == "blocked":
        return "skipped_blocked", "Blocked staged data was not written to Google Sheets."
    if not os.environ.get("MARKET_DATA_SPREADSHEET_ID") or not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        return "skipped_unconfigured", "Google Sheets credentials are not configured."
    completed = run([sys.executable, "scripts/write_market_data_to_sheets.py"], check=False, capture=True)
    output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    if completed.returncode == 0:
        return "success", output[-2000:]
    return "failed", output[-2000:]


def perform_attempt(slot: str, scheduled_time: str, trigger_source: str, audit: Path) -> dict[str, Any]:
    started = now_jst()
    os.environ["ACQUISITION_TRIGGER_SOURCE"] = trigger_source
    os.environ["ACQUISITION_SCHEDULED_TIME"] = scheduled_time

    run([
        sys.executable,
        "scripts/run_market_data_acquisition.py",
        "--slot",
        slot,
        "--mode",
        "auto",
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
    sheets_outcome, sheets_message = sync_sheets(status)
    completed = now_jst()
    acquisition = payload.get("acquisition") or {}
    record = {
        "scheduledDate": started.date().isoformat(),
        "scheduledTime": scheduled_time,
        "reportSlot": slot,
        "triggerSource": trigger_source,
        "workflowRunId": os.environ.get("GITHUB_RUN_ID", ""),
        "workflowRunAttempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "startedAt": iso(started),
        "completedAt": iso(completed),
        "outcome": status,
        "missingRequired": payload.get("missingRequired") or [],
        "fallbackCount": payload.get("fallbackCount", 0),
        "runCount": acquisition.get("runCount", 0),
        "targetedSymbols": acquisition.get("targetedSymbols") or [],
        "recoveredSymbols": acquisition.get("recoveredSymbols") or [],
        "remainingUnavailable": acquisition.get("remainingUnavailable") or [],
        "sheetsOutcome": sheets_outcome,
        "sheetsMessage": sheets_message,
    }
    append_audit(audit, record)
    git_commit_push(f"Record {slot} market data attempt {scheduled_time}")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", required=True, choices=("07:00", "12:00", "16:00", "21:00"))
    parser.add_argument("--times", required=True, type=parse_times)
    parser.add_argument("--trigger-source", default=os.environ.get("ACQUISITION_TRIGGER_SOURCE", "window"))
    parser.add_argument("--max-catchup-minutes", type=int, default=90)
    args = parser.parse_args()

    run(["git", "config", "user.name", "github-actions[bot]"])
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])

    day = now_jst().date()
    audit = audit_path(day, args.slot)
    failures: list[str] = []

    for scheduled_time in args.times:
        git_sync()
        done = completed_times(audit, args.slot)
        if scheduled_time in done:
            print(f"Already recorded: {args.slot} {scheduled_time}", flush=True)
            continue

        target = target_datetime(day, scheduled_time)
        age_minutes = (now_jst() - target).total_seconds() / 60.0
        if age_minutes < 0:
            wait_until(target)
        elif age_minutes > args.max_catchup_minutes:
            print(f"Skipping expired attempt {scheduled_time}: {age_minutes:.1f} minutes late", flush=True)
            failures.append(scheduled_time)
            continue
        else:
            print(f"Catching up {scheduled_time}: {age_minutes:.1f} minutes late", flush=True)

        try:
            perform_attempt(args.slot, scheduled_time, args.trigger_source, audit)
        except Exception as exc:
            print(f"Attempt {scheduled_time} failed: {exc}", file=sys.stderr, flush=True)
            failures.append(scheduled_time)
            # Keep the window alive so later attempts can still recover data.
            time.sleep(30)

    git_sync()
    final_done = completed_times(audit, args.slot)
    missing = [item for item in args.times if item not in final_done]
    summary = {
        "date": day.isoformat(),
        "reportSlot": args.slot,
        "expectedTimes": args.times,
        "completedTimes": sorted(final_done),
        "missingTimes": missing,
        "triggerSource": args.trigger_source,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
