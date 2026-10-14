#!/usr/bin/env python3
"""Build dated private-report observations from already acquired local datasets.

This module does not make network requests. It reuses the repository's confirmed
Japan 10-year record and the previously captured TSE Prime breadth history. The
breadth ratio is emitted only when all 25 expected 2026 TSE sessions are present.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

JST = dt.timezone(dt.timedelta(hours=9))
UTC = dt.timezone.utc
TSE_CLOSED_2026 = {
    dt.date(2026, 1, 1), dt.date(2026, 1, 2), dt.date(2026, 1, 12),
    dt.date(2026, 2, 11), dt.date(2026, 2, 23), dt.date(2026, 3, 20),
    dt.date(2026, 4, 29), dt.date(2026, 5, 4), dt.date(2026, 5, 5),
    dt.date(2026, 5, 6), dt.date(2026, 7, 20), dt.date(2026, 8, 11),
    dt.date(2026, 9, 21),  # Respect for the Aged Day
    dt.date(2026, 9, 22),  # Citizen's holiday
    dt.date(2026, 9, 23),  # Autumnal Equinox Day
    dt.date(2026, 10, 12), dt.date(2026, 11, 3), dt.date(2026, 11, 23),
    dt.date(2026, 12, 31),
}


def parse_date(value: Any) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def parse_time(value: Any) -> str:
    stamp = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("retrieval timestamp must include timezone")
    return stamp.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def expected_tse_sessions(target: dt.date, count: int = 25) -> list[dt.date] | None:
    # Fail closed outside a year with a reviewed TSE holiday set.
    if target.year != 2026:
        return None
    if target.weekday() >= 5 or target in TSE_CLOSED_2026:
        return None
    sessions: list[dt.date] = []
    day = target
    while len(sessions) < count:
        if day.weekday() < 5 and day not in TSE_CLOSED_2026:
            sessions.append(day)
        day -= dt.timedelta(days=1)
    return list(reversed(sessions))


def prime_ratio25(history: Any, target: dt.date) -> tuple[float | None, str]:
    if not isinstance(history, list):
        return None, "Prime breadth history missing"
    expected = expected_tse_sessions(target)
    if expected is None:
        return None, "TSE trading-session calendar is not reviewed for this year"
    rows_by_day: dict[dt.date, dict[str, Any]] = {}
    for row in history:
        if not isinstance(row, dict):
            continue
        day = parse_date(row.get("date"))
        if day is None or day > target:
            continue
        if day in rows_by_day:
            return None, "duplicate date in Prime breadth history"
        rows_by_day[day] = row
    if [day for day in expected if day in rows_by_day] != expected:
        return None, "fewer than 25 complete TSE Prime sessions or a session gap"
    rows = [rows_by_day[day] for day in expected]
    up_total = down_total = 0
    for row in rows:
        try:
            up = int(row["primeAdvancers"])
            down = int(row["primeDecliners"])
        except (KeyError, TypeError, ValueError):
            return None, "invalid Prime breadth count in 25-session window"
        if up < 0 or down < 0:
            return None, "negative Prime breadth count"
        up_total += up
        down_total += down
    if down_total == 0:
        return None, "zero decliners in 25-session window"
    return up_total / down_total * 100, "25-session ratio from same-market TSE Prime advancers/decliners"


def _timestamp(value: Any) -> dt.datetime | None:
    try:
        stamp = dt.datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return None
    return stamp


def build_supplements(
    rates: dict[str, Any],
    japan_close: dict[str, Any],
    market_snapshot: dict[str, Any] | None = None,
    *,
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    supplements: list[dict[str, Any]] = []
    now = _timestamp(generated_at) if generated_at else dt.datetime.now(UTC)
    market_snapshot = market_snapshot or {}
    observed_markets = market_snapshot.get("markets") or {}

    # Promote the official MOF series only when its own configured adapter is
    # the recorded source. A confirmed LSEG snapshot is useful as a reference,
    # but does not become an official MOF observation by inheritance.
    official_jp10 = observed_markets.get("jp10y") or {}
    official_jp10_source = str(official_jp10.get("sourceId") or "") == "mof_jgbcm_10y"
    official_jp10_fetched = _timestamp(official_jp10.get("fetchedAt"))
    official_jp10_date = parse_date(official_jp10.get("asOf"))
    if (official_jp10_source and official_jp10.get("verificationStatus") == "verified"
            and not official_jp10.get("fallbackUsed") and official_jp10_date
            and official_jp10_fetched and official_jp10_fetched <= now
            and official_jp10_date <= official_jp10_fetched.astimezone(JST).date()):
        supplements.append({
            "id": "jp10y", "value": official_jp10.get("value"), "unit": "%",
            "asOf": official_jp10_date.isoformat(), "fetchedAt": official_jp10_fetched.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "sourceId": "mof_jgbcm_10y", "sourceName": official_jp10.get("sourceName") or "日本財務省10年定数年限国債金利",
            "sourceUrl": official_jp10.get("sourceUrl") or "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/",
            "verificationStatus": "verified",
            "verificationBasis": "MOF official 10-year constant-maturity CSV adapter; source ID and market date retained",
            "marketType": "yield", "session": "japan_yield_daily",
        })

    rates_meta = rates.get("meta") or {}
    target = parse_date(rates_meta.get("asOfDate"))
    retrieved = parse_time(rates.get("generatedAt"))
    if (not official_jp10_source and rates_meta.get("status") == "confirmed" and not rates_meta.get("isStale")
            and target and target <= dt.datetime.fromisoformat(retrieved.replace("Z", "+00:00")).astimezone(JST).date()):
        record = next((r for r in rates.get("rates", [])
                       if isinstance(r, dict) and r.get("name") == "日本10年国債利回り"), None)
        if record and record.get("status") == "confirmed" and parse_date(record.get("asOf")) == target:
            supplements.append({
                "id": "jp10y", "value": record.get("value"), "unit": "%",
                "asOf": target.isoformat(), "fetchedAt": retrieved,
                "sourceId": "rates_bonds_jp10y_reference", "sourceName": record.get("source") or "既存確認済み金利系列",
                "sourceUrl": "data/rates-bonds.json", "verificationStatus": "reference_only",
                "verificationBasis": "既存rates-bonds系列の確認済み市場観測。公式MOF系列とは独立した参照値",
                "marketType": "yield", "session": "japan_yield_daily",
            })

    fear_greed = observed_markets.get("fear_greed") or {}
    fear_fetched = _timestamp(fear_greed.get("fetchedAt"))
    fear_asof = _timestamp(fear_greed.get("asOf"))
    fear_value = fear_greed.get("value")
    if (fear_greed.get("verificationStatus") == "verified" and not fear_greed.get("fallbackUsed")
            and fear_greed.get("sourceId") == "cnn_fear_greed_graphdata"
            and fear_fetched and fear_asof and fear_value not in (None, "")
            and fear_fetched <= now and fear_asof <= fear_fetched
            and (now - fear_fetched).total_seconds() <= 72 * 3600):
        try:
            score = float(fear_value)
        except (TypeError, ValueError):
            score = -1
        if 0 <= score <= 100:
            supplements.append({
                "id": "fear_greed", "value": score, "unit": "score",
                "asOf": fear_asof.astimezone(JST).isoformat(),
                "fetchedAt": fear_fetched.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "sourceId": "cnn_fear_greed_graphdata", "sourceName": fear_greed.get("sourceName") or "CNN Fear & Greed Index",
                "sourceUrl": fear_greed.get("sourceUrl") or "https://edition.cnn.com/markets/fear-and-greed",
                "verificationStatus": "verified",
                "verificationBasis": "既存取得スナップショットのCNN source ID、verified状態、非fallback、取得時刻と指数時刻を確認",
                "marketType": "sentiment", "session": "daily",
            })

    close_date = parse_date(japan_close.get("dataDate"))
    generated = japan_close.get("generatedAt")
    if close_date and generated:
        retrieved_close = parse_time(generated)
        if close_date <= dt.datetime.fromisoformat(retrieved_close.replace("Z", "+00:00")).astimezone(JST).date():
            items = japan_close.get("items") or {}
            source_rows = japan_close.get("breadthHistory") or []
            count_sources = {
                "tse_prime_advancers": ("東証プライム値上がり銘柄数", "銘柄", "primeAdvancers"),
                "tse_prime_decliners": ("東証プライム値下がり銘柄数", "銘柄", "primeDecliners"),
            }
            for symbol, (name, unit, key) in count_sources.items():
                item = items.get(name) or {}
                if parse_date(item.get("date")) == close_date and item.get("value") not in (None, ""):
                    supplements.append({
                        "id": symbol, "value": item["value"], "unit": unit,
                        "asOf": close_date.isoformat(), "fetchedAt": retrieved_close,
                        "sourceId": "investforest_prime_breadth_history",
                        "sourceName": item.get("sourceName") or "投資の森 値上がり・値下がり銘柄数",
                        "sourceUrl": item.get("sourceUrl") or "https://nikkeiyosoku.com/jp_index_rate/",
                        "verificationStatus": "reference_only",
                        "verificationBasis": "既存保存履歴の東証プライム区分。公開ページとの独立再照合は未実施",
                        "marketType": "breadth", "session": "tse_prime_close",
                        "marketSegment": "TSE Prime",
                    })
            ratio, reason = prime_ratio25(source_rows, close_date)
            if ratio is not None:
                supplements.append({
                    "id": "tse_prime_ad_ratio25", "value": ratio, "unit": "%",
                    "asOf": close_date.isoformat(), "fetchedAt": retrieved_close,
                    "sourceId": "calculated_investforest_prime_breadth_history",
                    "sourceName": "既存保存済み東証プライム騰落履歴から算出",
                    "sourceUrl": "https://nikkeiyosoku.com/jp_index_rate/",
                    "verificationStatus": "reference_only",
                    "verificationBasis": reason,
                    "marketType": "breadth", "session": "tse_prime_close",
                    "marketSegment": "TSE Prime",
                    "calculation": "100 × 25営業日の値上がり合計 ÷ 同期間の値下がり合計",
                })
    return supplements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rates", type=Path, required=True)
    parser.add_argument("--japan-close", type=Path, required=True)
    parser.add_argument("--market-snapshot", type=Path, help="Optional latest market snapshot containing CNN and official MOF observations")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rates = json.loads(args.rates.read_text(encoding="utf-8"))
    close = json.loads(args.japan_close.read_text(encoding="utf-8"))
    market_snapshot = json.loads(args.market_snapshot.read_text(encoding="utf-8")) if args.market_snapshot else {}
    result = {"supplementalValues": build_supplements(rates, close, market_snapshot)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"supplementCount": len(result["supplementalValues"]),
                      "ids": [row["id"] for row in result["supplementalValues"]]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

