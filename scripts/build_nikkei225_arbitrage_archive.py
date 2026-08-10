#!/usr/bin/env python3
"""Preserve one complete Nikkei 225 arbitrage page snapshot per report date."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
JST = ZoneInfo("Asia/Tokyo")
ARBITRAGE_PATH = ROOT / "data" / "nikkei225-arbitrage.json"
ARCHIVE_DIR = ROOT / "data" / "nikkei225-arbitrage-archive"
ARCHIVE_INDEX = ARCHIVE_DIR / "index.json"
MIN_REPORT_DATE = "2026-08-10"
MAX_REPORTS = 400


def load_json(path: Path, default: Any = None) -> Any:
    if default is None:
        default = {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_date(value: Any) -> str | None:
    text = str(value or "").strip().replace("/", "-")
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return None


def report_date_from_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(JST).date().isoformat()
    except Exception:
        return normalize_date(value)


def is_usable_snapshot(data: dict[str, Any]) -> bool:
    if data.get("pageTitle") != "裁定取引":
        return False
    latest = data.get("latest") or {}
    history = data.get("history") or []
    return isinstance(latest, dict) and isinstance(history, list) and bool(latest)


def latest_history_date(data: dict[str, Any]) -> str | None:
    dates = [normalize_date(row.get("date")) for row in (data.get("history") or []) if isinstance(row, dict)]
    dates = [d for d in dates if d]
    return max(dates) if dates else normalize_date(data.get("asOfDate"))


def make_entry(date: str, bundle: dict[str, Any]) -> dict[str, Any]:
    data = bundle.get("arbitrage") or {}
    return {
        "date": date,
        "generatedAt": bundle.get("generatedAt"),
        "asOfDate": normalize_date(data.get("asOfDate")),
        "latestHistoryDate": latest_history_date(data),
        "sourceStatus": data.get("sourceStatus"),
        "file": f"{date}.json",
    }


def current_bundle() -> dict[str, Any]:
    now = datetime.now(JST).isoformat(timespec="seconds")
    data = load_json(ARBITRAGE_PATH, {})
    return {
        "schemaVersion": "1.0.0",
        "pageId": "nikkei225-arbitrage",
        "reportDate": now[:10],
        "generatedAt": now,
        "arbitrage": data,
    }


def git_json(commit: str, path: str) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", "show", f"{commit}:{path}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        value = json.loads(proc.stdout)
        return value if isinstance(value, dict) else {}
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        return {}


def git_bundle(commit: str, committed_at: str) -> dict[str, Any] | None:
    data = git_json(commit, "data/nikkei225-arbitrage.json")
    if not is_usable_snapshot(data):
        return None
    date = report_date_from_timestamp(committed_at)
    if not date or date < MIN_REPORT_DATE:
        return None
    return {
        "schemaVersion": "1.0.0",
        "pageId": "nikkei225-arbitrage",
        "reportDate": date,
        "generatedAt": committed_at,
        "arbitrage": data,
        "sourceCommit": commit,
    }


def backfill(entries: dict[str, dict[str, Any]]) -> None:
    try:
        proc = subprocess.run(
            [
                "git",
                "log",
                "--since=2026-08-09",
                "--format=%H%x09%cI",
                "--",
                "data/nikkei225-arbitrage.json",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (subprocess.CalledProcessError, OSError):
        return

    snapshots: dict[str, dict[str, Any]] = {}
    for line in proc.stdout.splitlines():
        if not line.strip() or "\t" not in line:
            continue
        commit, committed_at = line.split("\t", 1)
        bundle = git_bundle(commit.strip(), committed_at.strip())
        if not bundle:
            continue
        date = str(bundle.get("reportDate") or "")
        if date:
            snapshots.setdefault(date, bundle)

    for date, bundle in snapshots.items():
        path = ARCHIVE_DIR / f"{date}.json"
        if not path.exists():
            write_json(path, bundle)
        entries.setdefault(date, make_entry(date, bundle))


def update_archive(bundle: dict[str, Any]) -> dict[str, Any]:
    data = bundle.get("arbitrage") or {}
    if not is_usable_snapshot(data):
        raise RuntimeError("Current Nikkei 225 arbitrage snapshot is incomplete")

    date = str(bundle.get("reportDate") or "")
    if not date:
        raise RuntimeError("Could not determine arbitrage report date")

    existing = load_json(
        ARCHIVE_INDEX,
        {
            "schemaVersion": "1.0.0",
            "pageId": "nikkei225-arbitrage",
            "reports": [],
            "backfillComplete": False,
        },
    )
    entries = {
        str(row.get("date")): dict(row)
        for row in (existing.get("reports") or [])
        if isinstance(row, dict) and row.get("date")
    }

    if not existing.get("backfillComplete"):
        backfill(entries)

    write_json(ARCHIVE_DIR / f"{date}.json", bundle)
    entries[date] = make_entry(date, bundle)

    ordered_dates = sorted(entries)[-MAX_REPORTS:]
    index = {
        "schemaVersion": "1.0.0",
        "pageId": "nikkei225-arbitrage",
        "updatedAt": bundle.get("generatedAt"),
        "backfillComplete": True,
        "reports": [entries[key] for key in ordered_dates],
    }
    write_json(ARCHIVE_INDEX, index)
    return index


def main() -> int:
    bundle = current_bundle()
    index = update_archive(bundle)
    print(json.dumps({
        "reportDate": bundle.get("reportDate"),
        "archiveCount": len(index.get("reports") or []),
        "archiveIndex": str(ARCHIVE_INDEX.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
