from __future__ import annotations

import html
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "usdjpy-supply-demand.json"
URL = "https://www.traderswebfx.jp/order/currency/USDJPY"
JST = ZoneInfo("Asia/Tokyo")


def now_jst() -> datetime:
    return datetime.now(JST)


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as res:
        raw = res.read()
        charset = res.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def html_to_text(raw: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def price_range(label: str) -> tuple[float, float]:
    if "-" not in label:
        v = float(label)
        return v, v
    left, right = label.split("-", 1)
    low = float(left)
    if "." in right:
        high = float(right)
    else:
        high = float(f"{int(low)}.{right}")
    return min(low, high), max(low, high)


def parse_rows(text: str) -> list[dict]:
    # The source used to expose a literal ``|`` between the price and the
    # description.  It is now only a visual separator in the HTML, so use the
    # next price (or the members-only notice) as the row boundary instead.
    pattern = re.compile(
        r"(\d{3}\.\d{2}(?:-\d{2})?)円\s*(?:\|\s*)?(.*?)"
        r"(?=\s+\d{3}\.\d{2}(?:-\d{2})?円(?:\s|\|)|\s+プレミアム会員サービス|$)",
        re.S,
    )
    rows = []
    for price, desc in pattern.findall(text):
        desc = re.sub(r"\s+", " ", desc).strip()
        if not desc or not any(word in desc for word in ("売り", "買い", "現在", "OP", "ストップ")):
            continue
        low, high = price_range(price)
        rows.append({
            "price": price,
            "low": low,
            "high": high,
            "mid": round((low + high) / 2, 3),
            "description": desc,
            "isCurrent": "現在" in desc,
            "sell": "売り" in desc and "ストップロス売り" not in desc,
            "buy": "買い" in desc and "ストップロス買い" not in desc,
            "stopSell": "ストップロス売り" in desc,
            "stopBuy": "ストップロス買い" in desc,
            "option": "OP" in desc,
        })
    return rows


def compact(r: dict) -> dict:
    return {"price": r["price"], "description": r["description"]}


def analyze_options(rows: list[dict], spot: float | None) -> dict:
    options = [r for r in rows if r["option"]]
    if not options or spot is None:
        return {"status": "unavailable", "headline": "分析対象のNYカット情報なし", "summary": "現在値と比較できるオプション水準を取得できませんでした。", "points": []}

    options.sort(key=lambda r: abs(r["mid"] - spot))
    nearest = options[0]
    distance = round(nearest["mid"] - spot, 2)
    pips = round(abs(distance) * 100)
    size = "大きめ" if "大きめ" in nearest["description"] else "通常規模"
    side = "上" if distance > 0 else "下" if distance < 0 else "同水準"
    clustered = any("・" in r["description"] and "日NYカット" in r["description"] for r in options)

    overlaps = []
    for r in options:
        tags = []
        if r["sell"]: tags.append("売り注文")
        if r["buy"]: tags.append("買い注文")
        if r["stopSell"]: tags.append("売りストップ")
        if r["stopBuy"]: tags.append("買いストップ")
        if tags: overlaps.append((r, "・".join(tags)))

    points = [f"最接近は{nearest['price']}円（現在値から{side}へ約{pips}pips、{size}）。NYカット接近時は同水準へ値が寄る動きと、通過後の反動に注意。"]
    if overlaps:
        r, tags = min(overlaps, key=lambda x: abs(x[0]["mid"] - spot))
        if r["sell"]: reading = "上値を抑えやすい"
        elif r["buy"] and r["stopSell"]: reading = "いったん支えになりやすい一方、割れると下落が加速しやすい"
        elif r["buy"]: reading = "下値を支えやすい"
        else: reading = "通過時に値動きが加速しやすい"
        points.append(f"{r['price']}円はNYカットと{tags}が重複。カット前後は{reading}水準。")
    if clustered:
        points.append("複数期日のNYカットが同一水準に重なるため、単一期日より意識されやすい価格帯があります。")

    above = [r for r in options if r["mid"] > spot]
    below = [r for r in options if r["mid"] < spot]
    headline = "上下のNYカットに挟まれ、カット前はレンジ化しやすい" if above and below else "上側NYカットが短期的な吸着・上値抑制候補" if above else "下側NYカットが短期的な吸着・下値支持候補"
    return {"status": "calculated", "headline": headline, "summary": "NYカットは方向を保証せず、カット時刻までは吸着、その後は反動が出る可能性を注文・ストップとの重複で評価します。", "nearestPrice": nearest["price"], "nearestDistancePips": pips, "points": points}


def select_levels(rows: list[dict]) -> dict:
    current = next((r for r in rows if r["isCurrent"]), None)
    spot = current["mid"] if current else None

    def dist(r: dict) -> float:
        return abs(r["mid"] - spot) if spot is not None else r["mid"]

    sells = [r for r in rows if r["sell"] and not r["isCurrent"]]
    buys = [r for r in rows if r["buy"] and not r["isCurrent"]]
    stops = [r for r in rows if r["stopSell"] or r["stopBuy"]]
    options = [r for r in rows if r["option"]]

    if spot is not None:
        sells = [r for r in sells if r["high"] >= spot]
        buys = [r for r in buys if r["low"] <= spot]
    sells.sort(key=dist)
    buys.sort(key=dist)
    stops.sort(key=dist)
    options.sort(key=dist)

    return {
        "referenceSpot": current["price"] if current else None,
        "referenceSpotDescription": current["description"] if current else None,
        "sellOrders": [compact(r) for r in sells[:2]],
        "buyOrders": [compact(r) for r in buys[:2]],
        "stops": [compact(r) for r in stops[:2]],
        "nyCutOptions": [compact(r) for r in options[:3]],
        "optionAnalysis": analyze_options(rows, spot),
        "extractedRowCount": len(rows),
        "displayMode": "key-levels-excerpt",
    }


def main() -> None:
    data = json.loads(OUT.read_text(encoding="utf-8"))
    tw = data.setdefault("tradersWebFx", {})
    raw = fetch_text(URL)
    text = html_to_text(raw)

    m = re.search(r"(20\d{2})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})\s*更新", text)
    if not m:
        raise RuntimeError("Traders Web FX update timestamp not found")
    dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), tzinfo=JST)

    rows = parse_rows(text)
    if not rows:
        raise RuntimeError("Traders Web FX order rows not found")

    now = now_jst()
    age_hours = max(0.0, (now - dt).total_seconds() / 3600)
    freshness = "today" if dt.date() == now.date() else "previous-session"
    if age_hours >= 48:
        freshness = "stale"

    tw.update({
        "sourceUpdatedAt": dt.isoformat(timespec="seconds"),
        "sourceDate": dt.strftime("%Y-%m-%d"),
        "sourceTime": dt.strftime("%H:%M"),
        "checkedAt": now.isoformat(timespec="seconds"),
        "status": "confirmed",
        "pageConfirmed": True,
        "freshness": freshness,
        "ageHours": round(age_hours, 1),
        "keyLevels": select_levels(rows),
        "redistributionMode": "key-levels-excerpt-with-attribution",
        "note": "無料公開データから需給判断に必要な主要水準のみ抜粋し、基準日時と出典を明示する。",
    })
    data["schemaVersion"] = "3.2.0"
    data.setdefault("rules", {})["tradersWebFx"] = "無料ページから主要な売り・買い・ストップ・NYカット水準を抜粋し、基準日時・鮮度・出典を明示する。"
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sourceUpdatedAt": tw["sourceUpdatedAt"], "rows": tw["keyLevels"]["extractedRowCount"], "freshness": freshness}, ensure_ascii=False))


def safe_main() -> None:
    try:
        main()
    except Exception as exc:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        now = now_jst().isoformat(timespec="seconds")
        tw = data.setdefault("tradersWebFx", {})
        has_previous = bool((tw.get("keyLevels") or {}).get("extractedRowCount"))
        tw.update({
            "checkedAt": now,
            "lastAttemptAt": now,
            "status": "preserved_after_fetch_error" if has_previous else "unavailable",
            "pageConfirmed": bool(has_previous),
            "error": f"{type(exc).__name__}: {exc}",
        })
        data.setdefault("sourceStatus", {})["tradersWebFx"] = tw["status"]
        data["generatedAt"] = now
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": tw["status"], "checkedAt": now, "error": tw["error"]}, ensure_ascii=False))


if __name__ == "__main__":
    safe_main()
