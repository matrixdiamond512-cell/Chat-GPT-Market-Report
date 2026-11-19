"""Price backfill entry point for BOTH Tokyo spot-volume update workflows.

The global Yahoo chart JSON endpoint is rate-limited (HTTP 429) on GitHub
Actions. Yahoo Japan's public USDJPY=X historical HTML returned HTTP 200 in
our runner's source probe. Use it first; never invent daily close prices.
"""
from __future__ import annotations

import json
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import update_usdjpy_volume_prices as core
from yahoo_jp_usdjpy_ohlc import SOURCE_URL as YAHOO_JP_URL, fetch_history
from stooq_usdjpy_ohlc import SOURCE_URL as STOOQ_URL, fetch_history as fetch_stooq


def main() -> None:
    payload = json.loads(core.PATH.read_text(encoding="utf-8"))
    data = payload.setdefault("data", {})
    rows = data.get("records") or []
    if not rows:
        raise SystemExit("BOJ spot volume records missing; cannot align dates")
    # Repair a second updater that may have overwritten the published JSON.
    # Recover only the seven historically verified sessions, never future prices.
    recovery_path = core.PATH.with_name("usdjpy-volume-price-recovery.json")
    if recovery_path.exists():
        snapshot = json.loads(recovery_path.read_text(encoding="utf-8"))
        recovered = {r["targetDate"]: r for r in snapshot.get("records", [])}
        by_date = {r.get("targetDate"): r for r in rows}
        price_records = {r["date"]: r for r in data.get("priceRecords", []) if r.get("date")}
        for day, candle in recovered.items():
            row = by_date.get(day)
            if row is None:
                continue
            if any(row.get(field) is None for field in (*core.FIELDS, "priceChangePct")):
                for field in (*core.FIELDS, "priceChangePct", "priceSourceId"):
                    if row.get(field) is None and candle.get(field) is not None:
                        row[field] = candle[field]
                price_records[day] = {"date": day, **{field: row.get(field) for field in (*core.FIELDS, "priceChangePct", "priceSourceId")}}
        data["priceRecords"] = sorted(price_records.values(), key=lambda r: r["date"], reverse=True)
        good = sorted(r["targetDate"] for r in rows if r.get("close") is not None)
        data["priceRange"] = {"startDate": good[0] if good else None, "endDate": good[-1] if good else None, "count": len(good)}
        if all(all(r.get(k) is not None for k in (*core.FIELDS, "priceChangePct")) for r in rows[:20]):
            payload.setdefault("components", {})["usdjpyOhlc"] = {"status": "ok", "sourceId": "YAHOO_GLOBAL_USDJPY", "latestDate": good[-1], "missingLast20Dates": []}
        core.PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    # Audit EVERY BOJ-volume date. The old latest-20 shortcut left 130 gaps.
    def open_gaps():
        return {r["targetDate"] for r in rows if any(r.get(k) is None for k in core.FIELDS)}

    missing_dates = open_gaps()
    if not missing_dates:
        print("USDJPY historical OHLC coverage: all BOJ dates complete; no fetch needed.")
        return

    start = (date.fromisoformat(min(missing_dates)) - timedelta(days=14)).isoformat()
    end = (date.fromisoformat(max(missing_dates)) + timedelta(days=7)).isoformat()
    now = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")
    print(f"USDJPY historical price backfill: {len(missing_dates)} missing dates / {start}..{end}")

    attempted = []
    completed_by_provider: dict[str, int] = {}
    yahoo_global_url = core.SOURCE_URL
    providers = [
        ("YAHOO_JP_USDJPY", YAHOO_JP_URL,
         lambda: fetch_history(missing_dates, start_date=start, end_date=end)),
        ("YAHOO_GLOBAL_USDJPY", yahoo_global_url, core.fetch_yahoo),
        ("STOOQ_USDJPY", STOOQ_URL,
         lambda: fetch_stooq(start_date=start, end_date=end)),
    ]
    for provider, url, acquire in providers:
        gaps_before = open_gaps()
        if not gaps_before:
            break
        try:
            candles = acquire()
            # Never stitch fields from DIFFERENT vendors into a partial candle.
            existing = {r["targetDate"]: r for r in rows}
            candles = {
                day: candle for day, candle in candles.items()
                if day not in existing or all(existing[day].get(k) is None for k in core.FIELDS)
            }
            matched = gaps_before.intersection(candles)
            if not matched:
                attempted.append(f"{provider}: no matching missing dates")
                continue
            core.SOURCE_URL = url
            core.backfill(payload, candles, now)
            by_day = {r["targetDate"]: r for r in data.get("records", [])}
            newly_complete = {day for day in matched
                              if all(by_day[day].get(k) is not None for k in core.FIELDS)}
            for day in newly_complete:
                by_day[day]["priceSourceId"] = provider
            for item in data.get("priceRecords", []):
                if item.get("date") in newly_complete:
                    item["priceSourceId"] = provider
            completed_by_provider[provider] = len(newly_complete)
            attempted.append(f"{provider}: restored {len(newly_complete)}")
        except Exception as exc:
            attempted.append(f"{provider}: {type(exc).__name__}: {str(exc)[:220]}")
            print("::warning::" + attempted[-1])

    remaining = sorted(open_gaps())
    pct_missing = sorted(r["targetDate"] for r in rows if r.get("priceChangePct") is None)
    complete = sorted(r["targetDate"] for r in rows
                      if all(r.get(k) is not None for k in core.FIELDS))
    data["priceRange"] = {
        "startDate": complete[0] if complete else None,
        "endDate": complete[-1] if complete else None,
        "count": len(complete),
    }
    price_items = {r["date"]: r for r in data.get("priceRecords", []) if r.get("date")}
    for row in rows:
        if row["targetDate"] in complete:
            d = row["targetDate"]
            price_items[d] = {"date": d, **{
                k: row.get(k) for k in (*core.FIELDS, "priceChangePct", "priceSourceId")
            }}
    data["priceRecords"] = sorted(price_items.values(), key=lambda r: r["date"], reverse=True)

    names = {
        "YAHOO_JP_USDJPY": ("Yahoo!ファイナンス日本版 USDJPY=X 日足OHLC", YAHOO_JP_URL),
        "YAHOO_GLOBAL_USDJPY": ("Yahoo Finance JPY=X daily OHLC", yahoo_global_url),
        "STOOQ_USDJPY": ("Stooq USDJPY daily OHLC", STOOQ_URL),
    }
    used = {r.get("priceSourceId") for r in rows}
    data["priceSourceName"] = "Investing.com（既存分）" + "".join(
        "／" + names[k][0] + "（欠損補完）" for k in names if k in used
    )
    # One unique source declaration per provider, with the actual date range.
    sources = payload.setdefault("sources", [])
    sources[:] = [s for i, s in enumerate(sources)
                  if s.get("id") not in (*names, "YAHOO_USDJPY")
                  and s.get("id") not in {x.get("id") for x in sources[:i]}]
    for provider, (name, url) in names.items():
        provider_days = sorted(r["targetDate"] for r in rows
                               if r.get("priceSourceId") == provider)
        if provider_days:
            sources.append({
                "id": provider, "name": name, "url": url,
                "asOf": provider_days[-1], "status": "ok",
                "fields": [*core.FIELDS, "priceChangePct"],
                "note": "既存の価格と日銀スポット出来高は維持。日足OHLCは日銀東京集計時間と異なる。"
            })

    latest20 = [r["targetDate"] for r in rows[:20]
                if any(r.get(k) is None for k in (*core.FIELDS, "priceChangePct"))]
    data["priceAcquisition"] = {
        "checkedAt": now,
        "latestTargetDate": rows[0]["targetDate"],
        "filledMissingDates": sum(completed_by_provider.values()),
        "filledByProvider": completed_by_provider,
        "missingAllDates": remaining,
        "missingPriceChangePctDates": pct_missing,
        "missingLast20Dates": latest20,
        "attemptedProviders": attempted,
        "note": "取引時間帯の異なる複数の検証済み日足データを日付ごとに識別。補間値は不使用。"
    }
    status = "ok" if not remaining and not pct_missing else "partial"
    component = payload.setdefault("components", {}).setdefault("usdjpyOhlc", {})
    component.update({
        "status": status,
        "latestDate": complete[-1] if complete else None,
        "sourceId": rows[0].get("priceSourceId") or component.get("sourceId"),
        "missingLast20Dates": latest20,
        "missingHistoricalDates": remaining,
    })
    core.PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({
        "totalVolumeDays": len(rows), "fullOHLC": len(complete),
        "restored": sum(completed_by_provider.values()),
        "stillMissing": len(remaining), "missingPercentChange": len(pct_missing),
        "providers": completed_by_provider,
    }, ensure_ascii=False))
    if remaining or pct_missing:
        print("::warning::USDJPY historical OHLC incomplete; missing dates must remain visible.")


if __name__ == "__main__":
    main()
