#!/usr/bin/env python3
"""Build the rates/bonds page and preserve one full report per report date."""

from __future__ import annotations

import json
import subprocess
from typing import Any

import build_rates_bonds_json as core
import build_rates_bonds_json_v2 as hardened


ROOT = core.ROOT
ARCHIVE_DIR = ROOT / "data" / "rates-bonds-archive"
ARCHIVE_INDEX = ARCHIVE_DIR / "index.json"
LATEST_PATH = core.OUTPUT
MAX_REPORTS = 400


def report_date(payload: dict[str, Any]) -> str | None:
    generated = str(payload.get("generatedAt") or "")
    if len(generated) >= 10 and generated[4:5] == "-" and generated[7:8] == "-":
        return generated[:10]
    meta_date = str((payload.get("meta") or {}).get("asOfDate") or "")
    if len(meta_date) >= 10 and meta_date[4:5] == "-" and meta_date[7:8] == "-":
        return meta_date[:10]
    return None


def valid_report_payload(payload: dict[str, Any]) -> bool:
    if payload.get("pageId") != "rates-bonds":
        return False
    if not (payload.get("meta") or {}).get("asOfDate"):
        return False
    return any(
        row.get("status") == "confirmed" and row.get("value") is not None
        for row in (payload.get("rates") or [])
    )


def latest_market_date(payload: dict[str, Any], prefix: str) -> str | None:
    dates = []
    for row in payload.get("rates") or []:
        name = str(row.get("name") or "")
        as_of = str(row.get("asOf") or "")
        if name.startswith(prefix) and len(as_of) >= 10:
            dates.append(as_of[:10])
    return max(dates) if dates else None


def make_entry(date: str, payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("meta") or {}
    return {
        "date": date,
        "generatedAt": payload.get("generatedAt"),
        "asOfDate": meta.get("asOfDate"),
        "usDataDate": latest_market_date(payload, "米"),
        "japanDataDate": latest_market_date(payload, "日本"),
        "file": f"{date}.json",
    }


def read_git_snapshot(commit: str) -> dict[str, Any] | None:
    try:
        proc = subprocess.run(
            ["git", "show", f"{commit}:data/rates-bonds.json"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(proc.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        return None
    return payload if valid_report_payload(payload) else None


def backfill_from_git(entries: dict[str, dict[str, Any]]) -> None:
    """Backfill one latest full snapshot per report date from repository history."""
    try:
        proc = subprocess.run(
            ["git", "log", "--format=%H", "--", "data/rates-bonds.json"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (subprocess.CalledProcessError, OSError):
        return

    # git log is newest first. setdefault therefore preserves the latest commit of each date.
    snapshots: dict[str, dict[str, Any]] = {}
    for commit in [line.strip() for line in proc.stdout.splitlines() if line.strip()][:500]:
        payload = read_git_snapshot(commit)
        if not payload:
            continue
        date = report_date(payload)
        if not date:
            continue
        snapshots.setdefault(date, payload)

    for date, payload in snapshots.items():
        path = ARCHIVE_DIR / f"{date}.json"
        # Do not overwrite a newer archive already created by this mechanism.
        if not path.exists():
            core.write_json(path, payload)
        entries.setdefault(date, make_entry(date, payload))


def update_archive(payload: dict[str, Any]) -> None:
    if not valid_report_payload(payload):
        raise RuntimeError("Current rates/bonds payload is not valid for archive publication")

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    existing = core.load_json(
        ARCHIVE_INDEX,
        {"schemaVersion": "1.0.0", "pageId": "rates-bonds", "reports": []},
    )
    # Old prototypes without a real market as-of date are intentionally omitted from the calendar.
    entries = {
        str(row.get("date")): dict(row)
        for row in (existing.get("reports") or [])
        if isinstance(row, dict) and row.get("date") and row.get("asOfDate")
    }

    if not existing.get("backfillComplete"):
        backfill_from_git(entries)

    date = report_date(payload)
    if not date:
        raise RuntimeError("Could not determine rates/bonds report date")

    core.write_json(ARCHIVE_DIR / f"{date}.json", payload)
    entries[date] = make_entry(date, payload)

    ordered_dates = sorted(entries)[-MAX_REPORTS:]
    reports = [entries[key] for key in ordered_dates]
    index = {
        "schemaVersion": "1.0.0",
        "pageId": "rates-bonds",
        "updatedAt": payload.get("generatedAt"),
        "backfillComplete": True,
        "reports": reports,
    }
    core.write_json(ARCHIVE_INDEX, index)


def main() -> int:
    # Preserve the hardened data-acquisition and same-date validation logic already used by the page.
    core.fetch_fred = hardened.fetch_fred_fixed
    payload = hardened.patch_payload(core.build_payload())
    core.write_json(LATEST_PATH, payload)
    core.update_history(payload)
    update_archive(payload)

    print(json.dumps({
        "status": payload.get("meta", {}).get("status"),
        "asOfDate": payload.get("meta", {}).get("asOfDate"),
        "reportDate": report_date(payload),
        "confirmedRates": sum(
            1 for item in payload.get("rates", [])
            if item.get("status") == "confirmed" and item.get("value") is not None
        ),
        "archiveIndex": str(ARCHIVE_INDEX.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
