from __future__ import annotations

import csv
import html
import io
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "usdjpy-supply-demand.json"
JST = ZoneInfo("Asia/Tokyo")
TRADERS_WEB_URL = "https://www.traderswebfx.jp/order/currency/USDJPY"
CFTC_URL = "https://www.cftc.gov/dea/newcot/deafut.txt"


def now_jst() -> datetime:
    return datetime.now(JST)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def fetch_text(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        raw = res.read()
        charset = res.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


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
        "publicScope": "一般公開はUSD/JPYの直近6時台情報",
        "redistributionMode": "source-metadata-and-link",
        "note": (
            "無料ページの公開状況・基準日時を取得して表示する。"
            "注文水準本文は提供元の利用条件を尊重し、このページには転載しない。"
        ),
    }
    try:
        raw = fetch_text(TRADERS_WEB_URL)
        text = html_to_text(raw)
        page_confirmed = "ドル円" in text and "USD/JPY" in text and "FXオーダー" in text
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
        result.update(
            {
                "sourceUpdatedAt": dt.isoformat(timespec="seconds"),
                "sourceDate": dt.strftime("%Y-%m-%d"),
                "sourceTime": dt.strftime("%H:%M"),
                "status": "confirmed",
                "pageConfirmed": True,
                "checkedAt": now_jst().isoformat(timespec="seconds"),
            }
        )
        result.pop("error", None)
    except Exception as exc:
        result["checkedAt"] = now_jst().isoformat(timespec="seconds")
        result["error"] = str(exc)
    return result


def to_int(value: str) -> int:
    return int(str(value).strip().replace(",", ""))


def fetch_cftc(previous: dict) -> dict:
    base = {
        "name": "CFTC Commitments of Traders - Japanese Yen",
        "url": CFTC_URL,
        "status": "stale",
        "asOf": previous.get("asOf"),
        "long": previous.get("long"),
        "short": previous.get("short"),
        "net": previous.get("net"),
        "previousNet": previous.get("previousNet"),
        "note": "CFTC公式のJapanese Yen・Non-Commercial Long/Shortを使用。",
    }
    try:
        raw = fetch_text(CFTC_URL)
        found = None
        for row in csv.reader(io.StringIO(raw)):
            if not row:
                continue
            if str(row[0]).strip().upper().startswith("JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"):
                found = row
                break
        if not found or len(found) < 17:
            raise ValueError("CFTC Japanese Yen行を取得できませんでした")

        as_of = str(found[2]).strip()
        long_pos = to_int(found[8])
        short_pos = to_int(found[9])
        net_pos = long_pos - short_pos

        old_as_of = str(previous.get("asOf") or "")
        old_net = previous.get("net")
        old_previous_net = previous.get("previousNet")
        if as_of and old_as_of and as_of > old_as_of and old_net is not None:
            previous_net = old_net
        elif as_of == old_as_of:
            previous_net = old_previous_net
        else:
            previous_net = old_previous_net

        base.update(
            {
                "status": "confirmed",
                "asOf": as_of,
                "long": long_pos,
                "short": short_pos,
                "net": net_pos,
                "previousNet": previous_net,
                "checkedAt": now_jst().isoformat(timespec="seconds"),
            }
        )
    except Exception as exc:
        base["checkedAt"] = now_jst().isoformat(timespec="seconds")
        base["error"] = str(exc)
    return base


def core_snapshot() -> dict:
    market = load_json(ROOT / "data" / "market" / "latest.json")
    rates = load_json(ROOT / "data" / "rates-bonds.json")
    volume = load_json(ROOT / "data" / "usdjpy-volume.json")
    events = load_json(ROOT / "data" / "events.json")

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
        "events": {
            "generatedAt": events.get("generatedAt"),
            "dataAsOf": events.get("dataAsOf"),
            "status": events.get("status"),
        },
    }


def main() -> None:
    old = load_json(OUT)
    generated = now_jst().isoformat(timespec="seconds")
    traders = fetch_traders_web(old.get("tradersWebFx") or {})
    cftc = fetch_cftc(old.get("cftc") or {})
    snapshot = core_snapshot()

    data = {
        "schemaVersion": "3.1.1",
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
                "data/events.json",
            ],
            "assessment": (
                "価格方向、日米10年金利差の変化、東京スポット出来高の強弱を中核とし、"
                "CFTCは鮮度が十分な場合のみ方向判定へ加える。"
            ),
            "tradersWebFx": (
                "無料ページの取得確認、基準日・時刻、最終確認時刻を表示する。"
                "注文水準本文は転載せず参照リンクを表示する。"
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
                "tradersWebPageConfirmed": traders.get("pageConfirmed"),
                "cftcAsOf": cftc.get("asOf"),
                "cftcStatus": cftc.get("status"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
