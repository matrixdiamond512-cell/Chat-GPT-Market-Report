#!/usr/bin/env python3
"""Preserve one complete Gold supply/demand page snapshot per report date."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = ROOT / "data" / "gold-supply-demand.json"
MARKET_PATH = ROOT / "data" / "market" / "latest.json"
ETF_HISTORY_PATH = ROOT / "data" / "gold-etf-flow-history.json"
ARCHIVE_DIR = ROOT / "data" / "gold-supply-demand-archive"
ARCHIVE_INDEX = ARCHIVE_DIR / "index.json"
MIN_REPORT_DATE = "2026-08-08"
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


def report_date(gold: dict[str, Any]) -> str | None:
    generated = str(gold.get("generatedAt") or "")
    if len(generated) >= 10 and generated[4:5] == "-" and generated[7:8] == "-":
        return generated[:10]
    return None


def is_usable_gold_snapshot(gold: dict[str, Any]) -> bool:
    date = report_date(gold)
    if not date or date < MIN_REPORT_DATE:
        return False
    if gold.get("pageTitle") != "ゴールド需給分析":
        return False
    return all(isinstance(gold.get(key), dict) for key in ("comex", "cftc", "etf", "assessment"))


def first_date(value: Any) -> str | None:
    text = str(value or "")
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return None


def latest_etf_date(gold: dict[str, Any]) -> str | None:
    etf = gold.get("etf") or {}
    dates: list[str] = []
    for key in ("gld", "iau", "global"):
        row = etf.get(key) or {}
        d = first_date(row.get("asOfDate") or row.get("period"))
        if d:
            dates.append(d)
    return max(dates) if dates else None


def market_gold_date(market: dict[str, Any]) -> str | None:
    gold = ((market.get("markets") or {}).get("gold") or {})
    return first_date(gold.get("asOf"))


def make_entry(date: str, bundle: dict[str, Any]) -> dict[str, Any]:
    gold = bundle.get("gold") or {}
    return {
        "date": date,
        "generatedAt": gold.get("generatedAt"),
        "marketDataDate": market_gold_date(bundle.get("market") or {}),
        "comexDate": first_date((gold.get("comex") or {}).get("asOfDate")),
        "cftcDate": first_date((gold.get("cftc") or {}).get("asOfDate")),
        "etfDate": latest_etf_date(gold),
        "file": f"{date}.json",
    }


def current_bundle() -> dict[str, Any]:
    gold = load_json(GOLD_PATH, {})
    market = load_json(MARKET_PATH, {})
    etf_history = load_json(ETF_HISTORY_PATH, {}) if ETF_HISTORY_PATH.exists() else {}
    return {
        "schemaVersion": "1.0.0",
        "pageId": "gold-supply-demand",
        "reportDate": report_date(gold),
        "generatedAt": gold.get("generatedAt"),
        "gold": gold,
        "market": market,
        "etfHistory": etf_history,
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


def git_bundle(commit: str) -> dict[str, Any] | None:
    gold = git_json(commit, "data/gold-supply-demand.json")
    if not is_usable_gold_snapshot(gold):
        return None
    market = git_json(commit, "data/market/latest.json")
    etf_history = git_json(commit, "data/gold-etf-flow-history.json")
    date = report_date(gold)
    return {
        "schemaVersion": "1.0.0",
        "pageId": "gold-supply-demand",
        "reportDate": date,
        "generatedAt": gold.get("generatedAt"),
        "gold": gold,
        "market": market,
        "etfHistory": etf_history,
        "sourceCommit": commit,
    }


def backfill(entries: dict[str, dict[str, Any]]) -> None:
    """Backfill the latest complete snapshot per JST report date from repository history."""
    try:
        proc = subprocess.run(
            [
                "git",
                "log",
                "--since=2026-08-07",
                "--format=%H",
                "--",
                "data/gold-supply-demand.json",
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
    for commit in [line.strip() for line in proc.stdout.splitlines() if line.strip()]:
        bundle = git_bundle(commit)
        if not bundle:
            continue
        date = str(bundle.get("reportDate") or "")
        if not date:
            continue
        # git log is newest first, so preserve the latest complete snapshot for each date.
        snapshots.setdefault(date, bundle)

    for date, bundle in snapshots.items():
        path = ARCHIVE_DIR / f"{date}.json"
        if not path.exists():
            write_json(path, bundle)
        entries.setdefault(date, make_entry(date, bundle))


def update_archive(bundle: dict[str, Any]) -> dict[str, Any]:
    gold = bundle.get("gold") or {}
    if not is_usable_gold_snapshot(gold):
        raise RuntimeError("Current gold supply-demand snapshot is incomplete")
    date = report_date(gold)
    if not date:
        raise RuntimeError("Could not determine gold report date")

    existing = load_json(
        ARCHIVE_INDEX,
        {
            "schemaVersion": "1.0.0",
            "pageId": "gold-supply-demand",
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
        "pageId": "gold-supply-demand",
        "updatedAt": gold.get("generatedAt"),
        "backfillComplete": True,
        "reports": [entries[key] for key in ordered_dates],
    }
    write_json(ARCHIVE_INDEX, index)
    return index


def main() -> int:
    bundle = current_bundle()
    index = update_archive(bundle)
    print(
        json.dumps(
            {
                "reportDate": bundle.get("reportDate"),
                "archiveCount": len(index.get("reports") or []),
                "archiveIndex": str(ARCHIVE_INDEX.relative_to(ROOT)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
