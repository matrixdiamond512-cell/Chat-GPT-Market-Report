#!/usr/bin/env python3
"""Hardened rates/bonds builder.

This wrapper keeps the existing page schema while fetching each FRED series
individually. FRED's combined graph CSV can contain formatting that Python's
CSV reader rejects; individual two-column series are simpler and more robust.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.parse
from pathlib import Path

import build_rates_bonds_json as core


FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def parse_fred_series(text: str, series: str) -> list[tuple[dt.date, float]]:
    points: list[tuple[dt.date, float]] = []
    # Normalize all newline conventions and avoid csv.Sniffer/quoted-field issues.
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for raw_line in normalized.split("\n"):
        line = raw_line.strip().lstrip("\ufeff")
        if not line or line.lower().startswith("observation_date") or line.lower().startswith("date"):
            continue
        parts = [part.strip().strip('"') for part in line.split(",")]
        if len(parts) < 2:
            continue
        date = core.parse_date(parts[0])
        value = core.safe_float(parts[-1])
        if date and value is not None:
            points.append((date, value))
    return points


def fetch_fred_fixed():
    result: dict[str, dict] = {}
    failures: list[str] = []
    for series in core.FRED_SERIES:
        url = FRED_BASE + "?" + urllib.parse.urlencode({"id": series})
        try:
            text = core.http_text(url)
            points = parse_fred_series(text, series)
            stats = core.point_stats(points)
            if stats:
                result[series] = stats
            else:
                failures.append(f"{series}: no observations")
        except Exception as exc:
            failures.append(f"{series}: {exc}")
    if not result:
        raise RuntimeError(" / ".join(failures) or "FRED returned no usable observations")
    latest = max(stats["date"] for stats in result.values())
    return result, latest.isoformat()


def patch_payload(payload: dict) -> dict:
    rates = payload.get("rates") or []
    by_name = {row.get("name"): row for row in rates}

    us2 = by_name.get("米2年債利回り") or {}
    us10 = by_name.get("米10年債利回り") or {}
    real10 = by_name.get("米10年実質金利") or {}
    jp10 = by_name.get("日本10年国債利回り") or {}

    # Never describe an unavailable rate as "横ばい".
    def direction_text(row: dict, missing: str = "取得不能") -> str:
        return str(row.get("direction")) if row.get("status") != "unavailable" and row.get("direction") else missing

    if us2.get("status") == "unavailable" or us10.get("status") == "unavailable":
        payload.setdefault("summary", {})["theme"] = (
            f"米2年は{direction_text(us2)}、米10年は{direction_text(us10)}、"
            f"日本10年は{direction_text(jp10)}。取得できた公式データだけで分析する。"
        )

    # Cross-asset notes must not imply a missing U.S. rate was flat.
    for item in payload.get("crossAssetImpact") or []:
        market = item.get("market")
        if market in {"日経225先物", "EUR/USD"} and us10.get("status") == "unavailable":
            item["note"] = "米10年金利は取得不能。取得済みの他市場データだけで方向を表示し、金利との整合性は断定しない。"
        if market == "USD/JPY" and us2.get("status") == "unavailable":
            item["note"] = "米2年金利は取得不能。日本金利とUSD/JPYの値動きのみ確認し、日米金利差の整合性は断定しない。"
        if market in {"金", "BTCUSD"} and real10.get("status") == "unavailable":
            item["note"] = "米10年実質金利は取得不能。価格方向のみ表示し、実質金利との整合性は断定しない。"

    # Auction rows with no metric are not confirmed values.
    supply = payload.get("supplyDemand") or {}
    for item in supply.get("items") or []:
        if item.get("value") is None:
            item["status"] = "unavailable"

    source_rows = payload.get("sources") or []
    treasury_source = next((s for s in source_rows if s.get("name") == "U.S. Treasury FiscalData"), None)
    if treasury_source:
        usable = any(item.get("status") != "unavailable" and item.get("value") is not None for item in supply.get("items") or [])
        treasury_source["status"] = "confirmed" if usable else "partial"

    return payload


def main() -> int:
    core.fetch_fred = fetch_fred_fixed
    payload = patch_payload(core.build_payload())
    core.write_json(core.OUTPUT, payload)
    core.update_history(payload)
    print(json.dumps({
        "status": payload.get("meta", {}).get("status"),
        "asOfDate": payload.get("meta", {}).get("asOfDate"),
        "confirmedRates": sum(1 for item in payload.get("rates", []) if item.get("status") == "confirmed"),
        "missing": payload.get("meta", {}).get("missingData"),
        "errors": payload.get("errors"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
