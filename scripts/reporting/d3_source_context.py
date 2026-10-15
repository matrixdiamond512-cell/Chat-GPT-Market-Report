"""Non-generative report context adapter: as-of, provenance and stale gating.

All source paths are fixed to repository-managed snapshots. A stored adapter
packet is NOT evidence of live market accuracy, news reporting, or publication.
It must be pinned to the exact repository revision by a future producer.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import hashlib
import json
import re
from typing import Mapping
from urllib.parse import urlparse

from .context import ReportContext, aware, JST

SCHEMA = "supplementary-source-context/v1"
SOURCES = {
    "rates": "data/rates-bonds.json",
    "calendar": "data/events/upcoming.json",
    "usdjpy_position": "data/usdjpy-supply-demand.json",
    "gold_position": "data/gold-supply-demand.json",
    "nikkei_position": "data/nikkei225-supply-demand.json",
}
REQUIRED_10Y = ("米10年債利回り", "日本10年国債利回り")
HOSTS = {
    "fred.stlouisfed.org", "www.traderswebfx.jp", "www.cftc.gov",
    "publicreporting.cftc.gov", "www.jpx.co.jp", "www.forexfactory.com",
    "www.tradingview.com", "www.bundesbank.de", "www.mof.go.jp",
}
MAX_RATES_AGE = 4  # calendar days; no inferred values from old business dates
MAX_WEEKLY_POSITION_AGE = 14
MAX_DAILY_POSITION_AGE = 3


def _sha(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _origin(url):
    if not isinstance(url, str):
        return None
    p = urlparse(url)
    if p.scheme != "https" or p.hostname not in HOSTS or p.username or p.password:
        return None
    return url


def _as_of(day, cutoff: datetime, max_days: int):
    if not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        return False
    try:
        observed = date.fromisoformat(day)
    except ValueError:
        return False
    # Date-only observations have no trusted intraday release time. On their
    # own observation date, never assume they existed before a report cutoff.
    age = (cutoff.date() - observed).days
    return 1 <= age <= max_days


def _ready_timestamp(value, cutoff: datetime):
    try:
        dt = aware(value)
    except (TypeError, ValueError):
        return False
    return dt <= cutoff and dt >= cutoff - timedelta(days=30)


def _finite(value):
    return type(value) in (int, float) and not isinstance(value, bool) and __import__("math").isfinite(value)


def create_source_context(context: ReportContext, snapshots: Mapping) -> dict:
    """Pure function. Never fixes upstream records or guesses missing content."""
    cutoff = aware(context.data_cutoff).astimezone(JST)
    entries = []
    omissions = []
    for category in SOURCES:
        payload = snapshots.get(category)
        if not isinstance(payload, dict):
            omissions.append({"category": category, "reason": "SOURCE_NOT_AVAILABLE"})
            continue
        stamp = payload.get("generatedAt")
        if not _ready_timestamp(stamp, cutoff):
            omissions.append({"category": category, "reason": "SOURCE_GENERATED_AFTER_CUTOFF_OR_TOO_OLD"})
            continue
        if category == "rates":
            for name in REQUIRED_10Y:
                rows = [r for r in payload.get("rates", []) if isinstance(r, dict) and r.get("name") == name]
                if len(rows) != 1:
                    omissions.append({"category": category, "reason": name + "_ROW_NOT_UNIQUE"})
                    continue
                row = rows[0]
                source = (("https://fred.stlouisfed.org/series/DGS10"
                           if name.startswith("米") else
                           "https://www.tradingview.com/markets/bonds/prices-japan/")
                          if name.startswith("米") or "TradingView" in str(row.get("source")) else
                          "https://www.mof.go.jp/jgbs/reference/interest_rate/")
                if (row.get("status") != "confirmed" or not _as_of(row.get("asOf"), cutoff, MAX_RATES_AGE)
                        or not _finite(row.get("value")) or not _origin(source)):
                    omissions.append({"category": category, "reason": name + "_UNVERIFIED_OR_STALE"})
                    continue
                entries.append({
                    "category": "rates", "series": name, "as_of": row["asOf"],
                    "source_generated_at": stamp, "source_url": source,
                    "status": "confirmed_date_only", "value": row["value"],
                    "unit": row.get("unit"), "change_bp": row.get("changeBp")
                    if _finite(row.get("changeBp")) else None,
                })
        elif category == "calendar":
            if payload.get("status") != "ok" or payload.get("isStale") is True:
                omissions.append({"category": category, "reason": "CALENDAR_NOT_CONFIRMED"})
                continue
            feeds = [s.get("url") for s in payload.get("sources", [])
                     if isinstance(s, dict) and s.get("status") == "ok" and _origin(s.get("url"))]
            if not feeds or cutoff - aware(stamp) > timedelta(days=2):
                omissions.append({"category": category, "reason": "CALENDAR_SOURCE_OR_FRESHNESS_INVALID"})
                continue
            upcoming = []
            for row in payload.get("events", []):
                if not isinstance(row, dict) or row.get("status") != "scheduled" or row.get("actual"):
                    continue
                event_at = row.get("datetimeJst")
                if not _ready_timestamp(event_at, cutoff + timedelta(days=7)):
                    continue
                when = aware(event_at).astimezone(JST)
                if when <= cutoff or when > cutoff + timedelta(days=7):
                    continue
                if not isinstance(row.get("title"), str) or not row["title"].strip():
                    continue
                upcoming.append((when.isoformat(), row))
            for _, row in sorted(upcoming, key=lambda x: x[0])[:8]:
                entries.append({
                    "category": "calendar", "series": row.get("id"),
                    "as_of": row["datetimeJst"], "source_generated_at": stamp,
                    "source_url": feeds[0], "status": "scheduled_unconfirmed_outcome",
                    "title": row["title"], "importance": row.get("importance"),
                    "affected_markets": (row.get("affectedMarkets") or [])[:8],
                })
            if not upcoming:
                omissions.append({"category": category, "reason": "NO_CONFIRMED_UPCOMING_EVENT"})
        elif category == "usdjpy_position":
            c = payload.get("cftc", {})
            url = _origin(c.get("url"))
            day = c.get("asOf")
            if c.get("status") == "verified" and url and _as_of(day, cutoff, MAX_WEEKLY_POSITION_AGE) and _finite(c.get("net")):
                entries.append({"category": category, "series": "CFTC_JPY_NET",
                                "as_of": day, "source_generated_at": stamp,
                                "source_url": url, "status": "verified_weekly_lagged",
                                "net": c["net"], "net_change": c.get("netChange")
                                if _finite(c.get("netChange")) else None})
            else:
                omissions.append({"category": category, "reason": "CFTC_NOT_VERIFIED_OR_STALE"})
        elif category == "gold_position":
            c = payload.get("cftc", {})
            url = _origin(c.get("sourceUrl"))
            if (c.get("status") == "verified" and url and _as_of(c.get("asOfDate"), cutoff, MAX_WEEKLY_POSITION_AGE)
                    and _finite(c.get("managedMoneyNet"))):
                entries.append({"category": category, "series": "CFTC_GOLD_MANAGED_MONEY_NET",
                                "as_of": c["asOfDate"], "source_generated_at": stamp,
                                "source_url": url, "status": "verified_weekly_lagged",
                                "net": c["managedMoneyNet"], "net_change": c.get("managedMoneyNetChange")
                                if _finite(c.get("managedMoneyNetChange")) else None})
            else:
                omissions.append({"category": category, "reason": "CFTC_NOT_VERIFIED_OR_STALE"})
        elif category == "nikkei_position":
            c = payload.get("futures", {})
            url = _origin(c.get("oiSourceUrl"))
            if (c.get("status") == "verified" and url and _as_of(c.get("asOfDate"), cutoff, MAX_DAILY_POSITION_AGE)
                    and _finite(c.get("openInterest"))):
                entries.append({"category": category, "series": "JPX_NIKKEI_OI",
                                "as_of": c["asOfDate"], "source_generated_at": stamp,
                                "source_url": url, "status": "verified_daily_lagged",
                                "open_interest": c["openInterest"],
                                "oi_change": c.get("openInterestChange")
                                if _finite(c.get("openInterestChange")) else None})
            else:
                omissions.append({"category": category, "reason": "JPX_OI_NOT_VERIFIED_OR_STALE"})
    # This adapter has no verified timestamped news article feed.
    omissions.append({"category": "news", "reason": "NO_VERIFIED_NEWS_ARTICLE_FEED"})
    bundle = {
        "schema_version": SCHEMA,
        "report_id": context.report_id, "cutoff": context.data_cutoff,
        "data_kind": "historical_repository_snapshots_not_live_feed",
        "entries": entries, "omissions": omissions,
    }
    bundle["sha256"] = _sha(bundle)
    return bundle


def verify_source_context(context: ReportContext, bundle: dict) -> None:
    if not isinstance(bundle, dict) or bundle.get("schema_version") != SCHEMA:
        raise ValueError("SUPPLEMENTARY_CONTEXT_SCHEMA_INVALID")
    if bundle.get("report_id") != context.report_id or bundle.get("cutoff") != context.data_cutoff:
        raise ValueError("SUPPLEMENTARY_CONTEXT_SLOT_MISMATCH")
    copy = {k: v for k, v in bundle.items() if k != "sha256"}
    if bundle.get("sha256") != _sha(copy):
        raise ValueError("SUPPLEMENTARY_CONTEXT_HASH_INVALID")
    cutoff = aware(context.data_cutoff)
    for item in bundle.get("entries", []):
        if not _ready_timestamp(item.get("source_generated_at"), cutoff):
            raise ValueError("SUPPLEMENTARY_SOURCE_AFTER_CUTOFF")
        if not _origin(item.get("source_url")):
            raise ValueError("SUPPLEMENTARY_UNTRUSTED_SOURCE")
    if not any(x.get("category") == "news" for x in bundle.get("omissions", [])):
        raise ValueError("NEWS_AVAILABILITY_STATUS_REQUIRED")


def load_repository_sources(root: Path) -> dict:
    # Explicitly never crawl arbitrary files, URLs, or a different folder.
    results = {}
    for name, relpath in SOURCES.items():
        path = root / relpath
        try:
            results[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            results[name] = None
    return results
