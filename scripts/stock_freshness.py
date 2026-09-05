"""Shared freshness helpers for stock-analysis collectors.

The public page must distinguish the market session represented by a value from
the time the collector wrote the file.  These helpers also make the
``current``/``lastGood`` boundary explicit so a failed fetch cannot relabel an
old observation as today's value.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

JST = timezone(timedelta(hours=9))
SCHEMA_VERSION = "1.0.0"
VALID_STATUSES = {"ok", "partial", "unavailable", "verified", "verified-estimate"}
VALID_FRESHNESS = {"fresh", "stale", "unavailable"}


def now_jst() -> str:
    return datetime.now(JST).replace(microsecond=0).isoformat()


def normal_date(value: Any) -> str | None:
    text = str(value or "")[:10]
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None
    return parsed.date().isoformat()


def current_block(
    *,
    status: str,
    data_date: str | None,
    as_of: str | None,
    updated_at: str | None,
    source: Any = None,
    error: str | None = None,
    **data: Any,
) -> dict[str, Any]:
    """Build a self-contained current component block.

    ``fresh`` is only emitted for an explicitly available, dated observation.
    A collector that has no current observation must pass ``status=unavailable``
    and leave ``data_date`` unset.
    """
    available = status not in {"unavailable", "error"} and bool(normal_date(data_date))
    freshness = "fresh" if available else "unavailable"
    block: dict[str, Any] = {
        "status": status if status in VALID_STATUSES else "unavailable",
        "freshness": freshness,
        "dataDate": normal_date(data_date) if available else None,
        "asOf": as_of if available else None,
        "updatedAt": updated_at or now_jst(),
        "source": source or {},
        "error": error,
    }
    block.update(data)
    return block


def last_good_from(payload: Any) -> dict[str, Any] | None:
    """Return the previous good observation without exposing it as current."""
    if not isinstance(payload, dict):
        return None
    candidate = payload.get("current")
    if isinstance(candidate, dict) and candidate.get("status") == "unavailable":
        candidate = payload.get("lastGood")
    if not isinstance(candidate, dict):
        candidate = payload
    # Legacy flat payloads predate the freshness field.  Their verified status
    # and dated observation are still safe to retain, but only as stale
    # lastGood data after the next write.
    legacy_good = candidate.get("freshness") is None and candidate.get("status") in {"ok", "verified", "verified-estimate"}
    if candidate.get("freshness") not in {"fresh", "stale"} and not legacy_good:
        return None
    if candidate.get("status") not in {"ok", "partial", "verified", "verified-estimate"}:
        return None
    candidate_date = candidate.get("dataDate") or candidate.get("marketDate") or candidate.get("asOf")
    if not normal_date(candidate_date):
        return None
    result = dict(candidate)
    result["dataDate"] = normal_date(candidate_date)
    result["freshness"] = "stale"
    return result


def envelope(current: dict[str, Any], previous: Any = None) -> dict[str, Any]:
    """Wrap a current block and retain a clearly labelled last-good block."""
    last_good = last_good_from(previous)
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "status": current.get("status", "unavailable"),
        "freshness": current.get("freshness", "unavailable"),
        "dataDate": current.get("dataDate"),
        "asOf": current.get("asOf"),
        "updatedAt": current.get("updatedAt") or now_jst(),
        "source": current.get("source") or {},
        "error": current.get("error"),
        "current": current,
        "lastGood": last_good,
    }
    # Backward-compatible fields are copied only from a valid current block.
    # In particular, an unavailable response never receives yesterday's rows.
    for key, value in current.items():
        if key not in {"status", "freshness", "dataDate", "asOf", "updatedAt", "source", "error"}:
            payload[key] = value
    return payload


def current_of(payload: Any) -> dict[str, Any]:
    """Read a v1 payload, while tolerating the older flat shape."""
    if not isinstance(payload, dict):
        return current_block(status="unavailable", data_date=None, as_of=None, updated_at=None, error="invalid payload")
    candidate = payload.get("current")
    if isinstance(candidate, dict):
        return candidate
    return payload


def is_current(payload: Any, expected_date: str | None) -> bool:
    current = current_of(payload)
    return (
        current.get("status") in {"ok", "verified", "verified-estimate"}
        and current.get("freshness") == "fresh"
        and normal_date(current.get("dataDate")) == normal_date(expected_date)
    )

