from __future__ import annotations

import csv
import html
import io
import json
import re
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "usdjpy-supply-demand.json"
JST = ZoneInfo("Asia/Tokyo")
TRADERS_WEB_URL = "https://www.traderswebfx.jp/order/currency/USDJPY"
CFTC_URL = "https://www.cftc.gov/dea/newcot/deafut.txt"
CFTC_HISTORY_URL = "https://www.cftc.gov/files/dea/history/deacot{year}.zip"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/USDJPY=X"
YAHOO_HISTORY_URL = "https://finance.yahoo.co.jp/quote/USDJPY=X/history"
CFTC_MARKET_PREFIX = "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"
LOOKBACK_WEEKS = 26


def now_jst() -> datetime:
    return datetime.now(JST)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def request(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read()


def fetch_text(url: str, timeout: int = 30) -> str:
    raw = request(url, timeout=timeout)
    return raw.decode("utf-8", errors="replace")


def html_to_text(raw: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_traders_web(previous: dict) -> dict:
    result = {
        "name": "トレーダーズ・ウェブFX 無料ページ",
        "url": TRADERS_WEB_URL,
        "sourceUpdatedAt": previous.get("sourceUpdatedAt"),
        "checkedAt": previous.get("checkedAt"),
        "status": "stale",
        "pageConfirmed": False,
        "publicScope": "一般公開はUSD/JPYの直近情報",
        "redistributionMode": previous.get("redistributionMode") or "source-metadata-and-link",
        "note": (
            "無料ページの公開状況・基準日時を取得して表示する。"
            "取得済みの主要水準がある場合は前回値を保持し、基準日時を明示する。"
        ),
    }
    for key in (
        "sourceDate",
        "sourceTime",
        "freshness",
        "ageHours",
        "keyLevels",
    ):
        if previous.get(key) is not None:
            result[key] = previous.get(key)
    try:
        raw = fetch_text(TRADERS_WEB_URL)
        text = html_to_text(raw)
        page_confirmed = "ドル円" in text and "USD/JPY" in text
        if not page_confirmed:
            raise ValueError("USD/JPY無料オーダーページ本文を確認できませんでした")

        m = re.search(
            r"(20\d{2})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{1,2})\s+"
            r"(\d{1,2})\s*:\s*(\d{2})\s*更新",
            text,
        )
        if not m:
            raise ValueError("無料ページの更新日時を抽出できませんでした")

        dt = datetime(
            int(m.group(1)),
            int(m.group(2)),
            int(m.group(3)),
            int(m.group(4)),
            int(m.group(5)),
            tzinfo=JST,
        )
        checked = now_jst()
        age_hours = max(0.0, (checked - dt).total_seconds() / 3600)
        result.update(
            {
                "sourceUpdatedAt": dt.isoformat(timespec="seconds"),
                "sourceDate": dt.strftime("%Y-%m-%d"),
                "sourceTime": dt.strftime("%H:%M"),
                "status": "confirmed",
                "pageConfirmed": True,
                "checkedAt": checked.isoformat(timespec="seconds"),
                "freshness": "today" if checked.date() == dt.date() else "previous-session",
                "ageHours": round(age_hours, 1),
            }
        )
        result.pop("error", None)
    except Exception as exc:
        result["checkedAt"] = now_jst().isoformat(timespec="seconds")
        result["error"] = str(exc)
    return result


def to_int(value: str) -> int:
    return int(str(value).strip().replace(",", ""))


def parse_cftc_date(value: str) -> str | None:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_cftc_rows(raw: str) -> list[dict]:
    records: list[dict] = []
    for row in csv.reader(io.StringIO(raw)):
        if not row or len(row) < 10:
            continue
        if not str(row[0]).strip().upper().startswith(CFTC_MARKET_PREFIX):
            continue
        as_of = parse_cftc_date(row[2])
        if not as_of:
            continue
        try:
            long_pos = to_int(row[8])
            short_pos = to_int(row[9])
        except Exception:
            continue
        records.append(
            {
                "date": as_of,
                "long": long_pos,
                "short": short_pos,
                "net": long_pos - short_pos,
            }
        )
    return records


def fetch_cftc_history(previous_series: list[dict]) -> tuple[list[dict], str | None]:
    merged: dict[str, dict] = {}
    for item in previous_series or []:
        d = parse_cftc_date(item.get("date"))
        if d:
            merged[d] = {
                "date": d,
                "long": item.get("long"),
                "short": item.get("short"),
                "net": item.get("net"),
                "price": item.get("price"),
            }

    errors: list[str] = []
    years = sorted({now_jst().year, now_jst().year - 1})
    for year in years:
        url = CFTC_HISTORY_URL.format(year=year)
        try:
            payload = request(url, timeout=35)
            with zipfile.ZipFile(io.BytesIO(payload)) as zf:
                names = [n for n in zf.namelist() if n.lower().endswith((".txt", ".csv"))]
                if not names:
                    raise ValueError("CFTC年次ZIP内にテキストデータがありません")
                raw = zf.read(names[0]).decode("utf-8", errors="replace")
            for item in parse_cftc_rows(raw):
                old = merged.get(item["date"]) or {}
                item["price"] = old.get("price")
                merged[item["date"]] = item
        except Exception as exc:
            errors.append(f"{year}:{exc}")

    series = sorted(merged.values(), key=lambda x: x["date"])[-LOOKBACK_WEEKS:]
    return series, "; ".join(errors) if errors else None


def fetch_usdjpy_prices(series: list[dict]) -> tuple[dict[str, float], str, str | None]:
    previous = {
        str(item.get("date")): float(item["price"])
        for item in series
        if item.get("date") and isinstance(item.get("price"), (int, float))
    }
    if not series:
        return previous, "unavailable", "CFTC系列がありません"
    try:
        start = datetime.fromisoformat(series[0]["date"]).replace(tzinfo=timezone.utc) - timedelta(days=5)
        end = datetime.now(timezone.utc) + timedelta(days=2)
        params = urllib.parse.urlencode(
            {
                "period1": int(start.timestamp()),
                "period2": int(end.timestamp()),
                "interval": "1d",
                "events": "history",
                "includeAdjustedClose": "true",
            }
        )
        raw = fetch_text(f"{YAHOO_CHART_URL}?{params}", timeout=25)
        data = json.loads(raw)
        result = ((data.get("chart") or {}).get("result") or [None])[0] or {}
        timestamps = result.get("timestamp") or []
        closes = ((((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or [])
        daily: dict[str, float] = {}
        for ts, close in zip(timestamps, closes):
            if close is None:
                continue
            d = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
            daily[d] = float(close)
        if not daily:
            raise ValueError("Yahoo価格系列が空です")
        dates = sorted(daily)
        for item in series:
            d = item["date"]
            if d in daily:
                previous[d] = daily[d]
                continue
            target = datetime.fromisoformat(d).date()
            candidates = [x for x in dates if datetime.fromisoformat(x).date() <= target]
            if candidates:
                nearest = candidates[-1]
                gap = (target - datetime.fromisoformat(nearest).date()).days
                if gap <= 3:
                    previous[d] = daily[nearest]
        return previous, "available" if len(previous) >= 2 else "partial", None
    except Exception as exc:
        status = "available" if len(previous) >= 2 else "unavailable"
        return previous, status, str(exc)


def classify_jpy_position(net: int | None, net_change: int | None) -> tuple[str, str]:
    if net is None:
        return "判定待ち", "CFTC系列を確認中"
    if net < 0:
        if net_change is not None and net_change < 0:
            return "円売り越し拡大", "USD/JPYの上昇圧力"
        return "円売り越し縮小", "ドル買い圧力が弱まる方向"
    if net > 0:
        if net_change is not None and net_change > 0:
            return "円買い越し拡大", "USD/JPYの下押し圧力"
        return "円買い越し縮小", "円買い圧力が弱まる方向"
    return "中立", "方向感は中立"


def fetch_cftc(previous: dict) -> dict:
    previous_series = previous.get("series") or []
    history, history_error = fetch_cftc_history(previous_series)
    base = {
        "name": "CFTC Commitments of Traders - Japanese Yen",
        "url": CFTC_URL,
        "historyUrl": CFTC_HISTORY_URL.format(year=now_jst().year),
        "status": "stale",
        "asOf": previous.get("asOf"),
        "long": previous.get("long"),
        "short": previous.get("short"),
        "net": previous.get("net"),
        "previousNet": previous.get("previousNet"),
        "series": history,
        "lookbackWeeks": len(history),
        "note": "CFTC公式のJapanese Yen・Non-Commercial Long/Shortを使用。26週推移を年次履歴から取得する。",
        "priceSourceName": "Yahoo!ファイナンス USD/JPY時系列",
        "priceSourceUrl": YAHOO_HISTORY_URL,
    }
    try:
        current_raw = fetch_text(CFTC_URL)
        current_rows = parse_cftc_rows(current_raw)
        if not current_rows:
            raise ValueError("CFTC Japanese Yen行を取得できませんでした")
        current = current_rows[-1]
        by_date = {item["date"]: item for item in history}
        old_price = by_date.get(current["date"], {}).get("price")
        current["price"] = old_price
        by_date[current["date"]] = current
        history = sorted(by_date.values(), key=lambda x: x["date"])[-LOOKBACK_WEEKS:]

        prices, price_status, price_error = fetch_usdjpy_prices(history)
        for i, item in enumerate(history):
            item["price"] = prices.get(item["date"])
            item["label"] = "今週" if i == len(history) - 1 else f"{len(history)-1-i}週前"

        latest = history[-1]
        prev = history[-2] if len(history) >= 2 else None
        net_change = latest["net"] - prev["net"] if prev else None
        long_change = latest["long"] - prev["long"] if prev else None
        short_change = latest["short"] - prev["short"] if prev else None
        net_change_pct = None
        if prev and prev["net"]:
            net_change_pct = net_change / abs(prev["net"]) * 100
        judge, judge_sub = classify_jpy_position(latest["net"], net_change)

        base.update(
            {
                "status": "confirmed",
                "asOf": latest["date"],
                "long": latest["long"],
                "short": latest["short"],
                "net": latest["net"],
                "previousNet": prev["net"] if prev else previous.get("previousNet"),
                "netChange": net_change,
                "netChangePct": round(net_change_pct, 1) if net_change_pct is not None else None,
                "longChange": long_change,
                "shortChange": short_change,
                "judgement": judge,
                "judgementSub": judge_sub,
                "series": history,
                "lookbackWeeks": len(history),
                "priceStatus": price_status,
                "checkedAt": now_jst().isoformat(timespec="seconds"),
                "comment": (
                    f"{judge}。円先物のNetは{latest['net']:+,}枚、前週比{net_change:+,}枚。"
                    "USD/JPY価格線と合わせ、ポジション変化が価格に追随しているか、先行しているかを確認する。"
                    if net_change is not None
                    else f"{judge}。円先物の偏りを日米金利差・出来高と合わせて確認する。"
                ),
            }
        )
        if history_error:
            base["historyWarning"] = history_error
        if price_error:
            base["priceError"] = price_error
        base.pop("error", None)
    except Exception as exc:
        base["checkedAt"] = now_jst().isoformat(timespec="seconds")
        base["error"] = str(exc)
        if history_error:
            base["historyWarning"] = history_error
    return base


def core_snapshot() -> dict:
    market = load_json(ROOT / "data" / "market" / "latest.json")
    rates = load_json(ROOT / "data" / "rates-bonds.json")
    volume = load_json(ROOT / "data" / "usdjpy-volume.json")

    usdjpy = ((market.get("markets") or {}).get("usdjpy") or {})
    records = (((volume.get("data") or {}).get("records")) or [])
    latest_volume = records[0] if records else {}
    rates_meta = rates.get("meta") or {}

    return {
        "market": {
            "generatedAt": market.get("generatedAt"),
            "asOf": usdjpy.get("asOf"),
            "verificationStatus": usdjpy.get("verificationStatus"),
        },
        "ratesBonds": {
            "generatedAt": rates.get("generatedAt"),
            "asOfDate": rates_meta.get("asOfDate"),
            "status": rates_meta.get("status"),
        },
        "usdJpyVolume": {
            "generatedAt": volume.get("generatedAt"),
            "targetDate": latest_volume.get("targetDate"),
            "publicationDate": latest_volume.get("publicationDate"),
            "status": volume.get("status"),
        },
    }


def main() -> None:
    old = load_json(OUT)
    generated = now_jst().isoformat(timespec="seconds")
    traders = fetch_traders_web(old.get("tradersWebFx") or {})
    cftc = fetch_cftc(old.get("cftc") or {})
    snapshot = core_snapshot()

    data = {
        "schemaVersion": "3.3.0",
        "pageId": "usdjpy-supply-demand",
        "generatedAt": generated,
        "mode": "integrated-realistic",
        "sourceStatus": {
            "tradersWebFx": traders.get("status"),
            "cftc": cftc.get("status"),
            "core": "referenced-existing-json",
        },
        "tradersWebFx": traders,
        "cftc": cftc,
        "coreSnapshot": snapshot,
        "rules": {
            "hideUnavailableOptionalBlocks": True,
            "coreSources": [
                "data/market/latest.json",
                "data/rates-bonds.json",
                "data/usdjpy-volume.json",
                "CFTC Japanese Yen futures",
            ],
            "assessment": (
                "価格方向、日米10年金利差の変化、東京スポット出来高、CFTC円先物の26週ポジション推移を中核とし、"
                "オーダー情報を補助材料として総合判断する。"
            ),
            "cftc": (
                "Japanese Yen / Non-CommercialのLong・Short・Netを26週で表示し、"
                "USD/JPY価格との整合性を確認する。Netプラスは円買い越し、Netマイナスは円売り越しとして読む。"
            ),
            "tradersWebFx": (
                "無料ページの取得確認、基準日・時刻、最終確認時刻を表示する。"
                "取得済みの主要水準は基準日時を明示して利用する。"
            ),
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "generatedAt": generated,
                "tradersWebFx": traders.get("sourceUpdatedAt"),
                "tradersWebStatus": traders.get("status"),
                "cftcAsOf": cftc.get("asOf"),
                "cftcStatus": cftc.get("status"),
                "cftcWeeks": cftc.get("lookbackWeeks"),
                "cftcPriceStatus": cftc.get("priceStatus"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
