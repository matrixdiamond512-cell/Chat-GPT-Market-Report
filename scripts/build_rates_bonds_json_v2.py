#!/usr/bin/env python3
"""Hardened rates/bonds builder.

Fetches each FRED series individually and prevents analysis from comparing
series as if they were same-day observations when their latest publication
dates differ.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.parse

import build_rates_bonds_json as core


FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def parse_fred_series(text: str, series: str) -> list[tuple[dt.date, float]]:
    points: list[tuple[dt.date, float]] = []
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
    breakeven10 = by_name.get("米10年期待インフレ率") or {}
    term10 = by_name.get("米10年タームプレミアム") or {}
    jp10 = by_name.get("日本10年国債利回り") or {}

    def direction_text(row: dict, missing: str = "取得不能") -> str:
        return str(row.get("direction")) if row.get("status") != "unavailable" and row.get("direction") else missing

    # Never describe an unavailable rate as flat.
    if us2.get("status") == "unavailable" or us10.get("status") == "unavailable":
        payload.setdefault("summary", {})["theme"] = (
            f"米2年は{direction_text(us2)}、米10年は{direction_text(us10)}、"
            f"日本10年は{direction_text(jp10)}。取得できた公式データだけで分析する。"
        )

    # Do not call asynchronous FRED observations a same-day decomposition.
    decomposition = payload.get("decomposition") or {}
    factor_rows = decomposition.get("factors") or []
    factor_date_map = {
        "実質金利": real10.get("asOf"),
        "期待インフレ": breakeven10.get("asOf"),
        "タームプレミアム": term10.get("asOf"),
    }
    for factor in factor_rows:
        factor_date = factor_date_map.get(factor.get("name"))
        if factor_date:
            factor["interpretation"] = f"前日比 / 基準日 {factor_date}。{factor.get('interpretation', '')}"

    decomposition_dates = [
        row.get("asOf") for row in (us10, real10, breakeven10)
        if row.get("status") != "unavailable" and row.get("asOf")
    ]
    if decomposition_dates and len(set(decomposition_dates)) > 1:
        decomposition["formula"] = "米10年金利の構成要因（公表日をそろえた場合のみ同日分解）"
        decomposition["point"] = (
            f"公表日が異なるため同日分解は行わない。"
            f"米10年={us10.get('asOf') or '取得不能'}、"
            f"実質金利={real10.get('asOf') or '取得不能'}、"
            f"期待インフレ={breakeven10.get('asOf') or '取得不能'}、"
            f"タームプレミアム={term10.get('asOf') or '取得不能'}。"
            "各系列の方向は確認するが、差分を一つの要因として断定しない。"
        )
        payload.setdefault("summary", {})["consistency"] = (
            "米10年・実質金利・期待インフレは最新公表日が一致していないため、"
            "同日内訳としては扱わない。各系列の基準日を確認しながら株・為替・金との反応を見る。"
        )

    # Cross-asset notes should state when rate and market timestamps differ.
    market_asof = ((core.load_json(core.MARKET_LATEST, {}).get("markets") or {}))
    market_rate_map = {
        "日経225先物": ("nikkei225_futures_ose", us10),
        "USD/JPY": ("usdjpy", us2),
        "EUR/USD": ("eurusd", us10),
        "金": ("gold", real10),
        "BTCUSD": ("btcusd", real10),
    }
    for item in payload.get("crossAssetImpact") or []:
        market_name = item.get("market")
        market_key, rate_row = market_rate_map.get(market_name, (None, {}))
        if rate_row.get("status") == "unavailable":
            item["note"] = f"対応する金利データは取得不能。{market_name}の価格方向のみ表示し、金利との整合性は断定しない。"
            continue
        market_stamp = ((market_asof.get(market_key) or {}).get("asOf")) if market_key else None
        rate_date = rate_row.get("asOf")
        if market_stamp and rate_date and not str(market_stamp).startswith(str(rate_date)):
            item["note"] = (
                f"金利基準日 {rate_date}、{market_name}基準時刻 {market_stamp}。"
                "同時刻比較ではないため、因果を断定せず方向確認として扱う。"
            )

    # Auction rows with no actual metric are not confirmed values.
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
