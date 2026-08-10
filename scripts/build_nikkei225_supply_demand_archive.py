#!/usr/bin/env python3
"""Preserve one complete Nikkei 225 supply/demand page snapshot per report date."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NIKKEI_PATH = ROOT / "data" / "nikkei225-supply-demand.json"
MARKET_PATH = ROOT / "data" / "market" / "latest.json"
STOCKS_PATH = ROOT / "data" / "stocks.json"
OPTIONS_LATEST_PATH = ROOT / "data" / "nikkei225-options-latest.json"
ARCHIVE_DIR = ROOT / "data" / "nikkei225-supply-demand-archive"
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


def first_date(value: Any) -> str | None:
    text = str(value or "")
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return None


def report_date(nikkei: dict[str, Any]) -> str | None:
    return first_date(nikkei.get("generatedAt"))


def is_usable_nikkei_snapshot(nikkei: dict[str, Any]) -> bool:
    date = report_date(nikkei)
    if not date or date < MIN_REPORT_DATE:
        return False
    if nikkei.get("pageTitle") != "日経225需給分析":
        return False
    return all(isinstance(nikkei.get(key), dict) for key in ("futures", "arbitrage", "options"))


def market_nikkei_date(market: dict[str, Any]) -> str | None:
    fut = ((market.get("markets") or {}).get("nikkei225_futures_ose") or {})
    return first_date(fut.get("asOf"))


def cftc_date(nikkei: dict[str, Any]) -> str | None:
    sp = nikkei.get("speculativePositioning") or {}
    direct = first_date(sp.get("asOfDate"))
    if direct:
        return direct
    series = sp.get("series") or []
    dates = [first_date(row.get("date") or row.get("asOfDate")) for row in series if isinstance(row, dict)]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def make_entry(date: str, bundle: dict[str, Any]) -> dict[str, Any]:
    nikkei = bundle.get("nikkei") or {}
    return {
        "date": date,
        "generatedAt": nikkei.get("generatedAt"),
        "marketDataDate": market_nikkei_date(bundle.get("market") or {}),
        "spotDate": first_date((nikkei.get("spot") or {}).get("asOfDate")),
        "futuresDate": first_date((nikkei.get("futures") or {}).get("asOfDate")),
        "sessionsDate": first_date((nikkei.get("sessions") or {}).get("asOfDate")),
        "arbitrageDate": first_date((nikkei.get("arbitrage") or {}).get("asOfDate")),
        "optionsDate": first_date((nikkei.get("options") or {}).get("ivAsOfDate") or (nikkei.get("options") or {}).get("asOfDate")),
        "foreignDate": first_date((nikkei.get("foreignInvestors") or {}).get("asOfDate")),
        "cftcDate": cftc_date(nikkei),
        "file": f"{date}.json",
    }


def current_bundle() -> dict[str, Any]:
    nikkei = load_json(NIKKEI_PATH, {})
    market = load_json(MARKET_PATH, {})
    stocks = load_json(STOCKS_PATH, {})
    options_latest = load_json(OPTIONS_LATEST_PATH, {}) if OPTIONS_LATEST_PATH.exists() else {}
    return {
        "schemaVersion": "1.0.0",
        "pageId": "nikkei225-supply-demand",
        "reportDate": report_date(nikkei),
        "generatedAt": nikkei.get("generatedAt"),
        "nikkei": nikkei,
        "market": market,
        "stocks": stocks,
        "optionsLatest": options_latest,
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
    nikkei = git_json(commit, "data/nikkei225-supply-demand.json")
    if not is_usable_nikkei_snapshot(nikkei):
        return None
    date = report_date(nikkei)
    return {
        "schemaVersion": "1.0.0",
        "pageId": "nikkei225-supply-demand",
        "reportDate": date,
        "generatedAt": nikkei.get("generatedAt"),
        "nikkei": nikkei,
        "market": git_json(commit, "data/market/latest.json"),
        "stocks": git_json(commit, "data/stocks.json"),
        "optionsLatest": git_json(commit, "data/nikkei225-options-latest.json"),
        "sourceCommit": commit,
    }


def backfill(entries: dict[str, dict[str, Any]]) -> None:
    """Backfill the latest complete snapshot per report date from repository history."""
    try:
        proc = subprocess.run(
            [
                "git",
                "log",
                "--since=2026-08-07",
                "--format=%H",
                "--",
                "data/nikkei225-supply-demand.json",
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
        snapshots.setdefault(date, bundle)

    for date, bundle in snapshots.items():
        path = ARCHIVE_DIR / f"{date}.json"
        if not path.exists():
            write_json(path, bundle)
        entries.setdefault(date, make_entry(date, bundle))


def update_archive(bundle: dict[str, Any]) -> dict[str, Any]:
    nikkei = bundle.get("nikkei") or {}
    if not is_usable_nikkei_snapshot(nikkei):
        raise RuntimeError("Current Nikkei 225 supply-demand snapshot is incomplete")
    date = report_date(nikkei)
    if not date:
        raise RuntimeError("Could not determine Nikkei 225 report date")

    existing = load_json(
        ARCHIVE_INDEX,
        {
            "schemaVersion": "1.0.0",
            "pageId": "nikkei225-supply-demand",
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
        "pageId": "nikkei225-supply-demand",
        "updatedAt": nikkei.get("generatedAt"),
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
