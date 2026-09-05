#!/usr/bin/env python3
"""Cross-check stock-analysis dates, freshness, and current/lastGood isolation."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any

JST = timezone(timedelta(hours=9))


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: cannot read JSON: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def date_text(value: Any) -> str | None:
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def current_of(payload: dict[str, Any]) -> dict[str, Any]:
    current = payload.get("current")
    return current if isinstance(current, dict) else payload


def rows_in(block: dict[str, Any]) -> list[Any]:
    for key in ("gainers", "losers", "top", "bottom", "topGainers", "topLosers", "topVolume", "items", "rows"):
        value = block.get(key)
        if isinstance(value, list) and value:
            return value
    return []


def check_component(name: str, payload: dict[str, Any], expected: str | None, errors: list[str], *, reference_date: str, allow_partial: bool = False) -> None:
    current = current_of(payload)
    status = current.get("status")
    freshness = current.get("freshness")
    data_date = date_text(current.get("dataDate") or current.get("marketDate") or current.get("asOf"))
    if status == "unavailable":
        if rows_in(current):
            errors.append(f"{name}: unavailable current contains data rows")
    elif status not in {"ok", "verified", "verified-estimate"} and not (allow_partial and status == "partial"):
        errors.append(f"{name}: unsupported status {status!r}")
    if status != "unavailable" and freshness != "fresh":
        errors.append(f"{name}: usable current is not fresh ({freshness!r})")
    if expected and status != "unavailable" and data_date != expected:
        errors.append(f"{name}: dataDate {data_date!r} != expected {expected!r}")
    # GitHub Actions runs in UTC.  A Tokyo morning run is still on the
    # previous UTC date, so future-data validation must use the caller's
    # market-local reference date rather than date.today().
    if data_date and data_date > reference_date:
        errors.append(f"{name}: future dataDate {data_date}")
    last_good = payload.get("lastGood")
    if isinstance(last_good, dict) and last_good.get("freshness") != "stale":
        errors.append(f"{name}: lastGood must be marked stale")
    if status == "unavailable" and current.get("updatedAt") and payload.get("updatedAt") == current.get("updatedAt"):
        # This equality is fine: it proves the unavailable attempt was written.
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--today", default=datetime.now(JST).date().isoformat())
    args = parser.parse_args()
    reference_date = date_text(args.today)
    if not reference_date:
        parser.error(f"--today must be YYYY-MM-DD: {args.today!r}")
    root = args.root
    errors: list[str] = []
    warnings: list[str] = []
    try:
        stocks = load(root / "data" / "stocks.json")
    except ValueError as error:
        errors.append(str(error))
        stocks = {}
    dates = stocks.get("marketDates") or {}
    japan_date = date_text(dates.get("japan"))
    us_date = date_text(dates.get("us"))
    if japan_date and date.fromisoformat(japan_date).weekday() >= 5:
        errors.append(f"marketDates.japan is not a weekday session: {japan_date}")
    if us_date and date.fromisoformat(us_date).weekday() >= 5:
        errors.append(f"marketDates.us is not a weekday session: {us_date}")

    paths = {
        "tokyo-preopen": root / "data" / "market" / "tokyo-preopen.json",
        "us-premarket": root / "data" / "market" / "us-premarket.json",
        "japan-movers": root / "data" / "market" / "japan-stock-movers.json",
        "sectors": root / "data" / "market" / "sector-performance.json",
        "us-breadth": root / "data" / "market" / "us-stock-breadth.json",
        "us-movers": root / "data" / "market" / "us-stock-movers.json",
        "sp500-contributions": root / "data" / "market" / "sp500-contributions.json",
        "nikkei-contributions": root / "data" / "nikkei-contributions.json",
    }
    payloads: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        if not path.exists():
            warnings.append(f"{name}: dedicated JSON is not present")
            continue
        try:
            payloads[name] = load(path)
        except ValueError as error:
            errors.append(str(error))

    check_component("japan-movers", payloads.get("japan-movers", {}), japan_date, errors, reference_date=reference_date)
    check_component("us-breadth", payloads.get("us-breadth", {}), us_date, errors, reference_date=reference_date)
    check_component("us-movers", payloads.get("us-movers", {}), us_date, errors, reference_date=reference_date)
    check_component("sp500-contributions", payloads.get("sp500-contributions", {}), us_date, errors, reference_date=reference_date)
    check_component("nikkei-contributions", payloads.get("nikkei-contributions", {}), japan_date, errors, reference_date=reference_date)
    check_component("tokyo-preopen", payloads.get("tokyo-preopen", {}), reference_date, errors, reference_date=reference_date)
    check_component("us-premarket", payloads.get("us-premarket", {}), None, errors, reference_date=reference_date, allow_partial=True)

    sectors = payloads.get("sectors") or {}
    for key, expected in (("japan", japan_date), ("us", us_date)):
        market = (sectors.get("markets") or {}).get(key)
        if isinstance(market, dict):
            check_component(f"sectors.{key}", market, expected, errors, reference_date=reference_date)
            if market.get("status") in {"ok", "verified"}:
                if len(market.get("gainers") or []) < 5 or len(market.get("losers") or []) < 5:
                    errors.append(f"sectors.{key}: fewer than five gainers/losers")

    # Compatibility aggregate must not surface an old row as a fresh current.
    for group, expected in (("movers", japan_date), ("sectors", japan_date), ("contributions", japan_date)):
        block = ((stocks.get(group) or {}).get("japan") or {})
        if block and block.get("status") not in {"unavailable", "verified", "ok", "verified-estimate"}:
            errors.append(f"stocks.{group}.japan: unsupported status {block.get('status')!r}")
        if block and block.get("dataDate") and block.get("dataDate") != expected:
            warnings.append(f"stocks.{group}.japan: compatibility value is dated {block.get('dataDate')}; dedicated current is authoritative")

    result = {"status": "error" if errors else "ok", "errors": errors, "warnings": warnings, "marketDates": {"japan": japan_date, "us": us_date}}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if args.report_only or not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

