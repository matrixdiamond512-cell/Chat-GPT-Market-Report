"""Price backfill entry point for BOTH Tokyo spot-volume update workflows.

The global Yahoo chart JSON endpoint is rate-limited (HTTP 429) on GitHub
Actions. Yahoo Japan's public USDJPY=X historical HTML returned HTTP 200 in
our runner's source probe. Use it first; never invent daily close prices.
"""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import update_usdjpy_volume_prices as core
from yahoo_jp_usdjpy_ohlc import SOURCE_URL as YAHOO_JP_URL, fetch_history


def main() -> None:
    payload = json.loads(core.PATH.read_text(encoding="utf-8"))
    data = payload.setdefault("data", {})
    rows = data.get("records") or []
    if not rows:
        raise SystemExit("BOJ spot volume records missing; cannot align dates")
    missing_dates = {r["targetDate"] for r in rows if any(r.get(k) is None for k in core.FIELDS)}
    # Ask for one earlier reference close to compute first backfilled date's
    # day-over-day change using the SAME Yahoo JP series, not Investing.com.
    if missing_dates:
        from datetime import date, timedelta
        first = date.fromisoformat(min(missing_dates))
        missing_dates.add((first - timedelta(days=7)).isoformat())
    provider = "YAHOO_JP_USDJPY"
    url = YAHOO_JP_URL
    now = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")
    try:
        try:
            candles = fetch_history(missing_dates)
            if not any(d in candles for d in missing_dates):
                raise RuntimeError("Yahoo Japan pages contained no matching BOJ dates")
        except Exception as first_error:
            print(f"::warning::Yahoo Japan history unavailable: {first_error}; trying global chart API")
            candles = core.fetch_yahoo()
            provider = "YAHOO_GLOBAL_USDJPY"
            url = core.SOURCE_URL
        core.SOURCE_URL = url
        filled, missing = core.backfill(payload, candles, now)
        for row in rows:
            if row.get("priceSourceId") == "YAHOO_USDJPY":
                row["priceSourceId"] = provider
        for price in data.get("priceRecords", []):
            if price.get("priceSourceId") == "YAHOO_USDJPY":
                price["priceSourceId"] = provider
        data["priceSourceName"] = (
            "Investing.com（2026/08/26以前の既存分）／"
            + ("Yahoo!ファイナンス日本版 USDJPY=X（日足OHLC補完分）" if provider == "YAHOO_JP_USDJPY" else "Yahoo Finance JPY=X（日足OHLC補完分）")
        )
        data["priceAcquisition"].update({
            "provider": provider, "source": url,
            "note": "日足OHLCと日銀東京スポット出来高は取引時間帯が異なる。価格ソースの異なる日付がある。",
        })
        component = payload.setdefault("components", {}).setdefault("usdjpyOhlc", {})
        component["sourceId"] = provider
        sources = payload.setdefault("sources", [])
        for source in sources:
            if source.get("id") == "YAHOO_USDJPY":
                source.update({"id": provider, "url": url,
                               "name": ("Yahoo!ファイナンス日本版 USDJPY=X 日足OHLC" if provider == "YAHOO_JP_USDJPY" else "Yahoo Finance JPY=X 日足OHLC")})
            elif source.get("id") == "INV_USDJPY":
                source["note"] = "既存の2026年8月26日以前の日足OHLC。以降は別ソースで補完。"
        if missing:
            print("::warning::OHLC incomplete after backfill:", ", ".join(missing))
        print(json.dumps({"provider": provider, "filledDates": filled,
                          "missingRecentDates": missing,
                          "latestPriceDate": data["priceRange"]["endDate"]}, ensure_ascii=False))
    except Exception as error:
        msg = f"All verified USDJPY OHLC sources failed: {type(error).__name__}: {error}"
        print("::warning::" + msg)
        payload.setdefault("components", {})["usdjpyOhlc"] = {"status": "error", "checkedAt": now, "note": msg}
        data["priceAcquisition"] = {"checkedAt": now, "error": msg}
    core.PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
