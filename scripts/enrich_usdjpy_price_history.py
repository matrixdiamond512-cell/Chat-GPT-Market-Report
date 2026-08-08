from __future__ import annotations

import html
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "usdjpy-supply-demand.json"
JST = ZoneInfo("Asia/Tokyo")
URL_TEMPLATE = "https://www.exchange-rates.org/exchange-rate-history/usd-jpy-{year}"


def now_jst() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def load_json() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def fetch_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        raw = res.read()
        charset = res.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def text_only(raw: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_rates(raw: str) -> dict[str, float]:
    text = text_only(raw)
    rates: dict[str, float] = {}
    pattern = re.compile(
        r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b.{0,120}?"
        r"1\s*USD\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*JPY",
        flags=re.I,
    )
    for year, month, day, value in pattern.findall(text):
        key = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        rates[key] = float(value)
    return rates


def main() -> None:
    data = load_json()
    cftc = data.get("cftc") or {}
    series = cftc.get("series") or []
    if not series:
        raise SystemExit("CFTC series is empty")

    current_count = sum(isinstance(item.get("price"), (int, float)) for item in series)
    needs_fallback = (
        current_count < len(series)
        or cftc.get("priceStatus") != "available"
        or bool(cftc.get("priceError"))
    )
    if not needs_fallback:
        print(json.dumps({"status": "unchanged", "pricePoints": current_count}, ensure_ascii=False))
        return

    years = sorted({int(str(item.get("date"))[:4]) for item in series if item.get("date")})
    all_rates: dict[str, float] = {}
    errors: list[str] = []
    for year in years:
        try:
            url = URL_TEMPLATE.format(year=year)
            rates = parse_rates(fetch_text(url))
            if not rates:
                raise ValueError("価格行を抽出できませんでした")
            all_rates.update(rates)
        except Exception as exc:
            errors.append(f"{year}:{exc}")

    filled = 0
    for item in series:
        date = str(item.get("date") or "")
        if date in all_rates:
            item["price"] = all_rates[date]
            filled += 1

    price_count = sum(isinstance(item.get("price"), (int, float)) for item in series)
    cftc["priceVerifiedPoints"] = price_count
    cftc["priceCheckedAt"] = now_jst()
    cftc["priceStatus"] = "available" if price_count >= 2 else "unavailable"

    if filled:
        cftc["priceSourceName"] = "Exchange-Rates.org USD/JPY historical rates"
        cftc["priceSourceUrl"] = URL_TEMPLATE.format(year=years[-1])
        cftc["priceSourceMode"] = "fallback-after-yahoo"
        cftc.pop("priceError", None)
    elif errors:
        cftc["priceFallbackError"] = "; ".join(errors)

    data["cftc"] = cftc
    data["generatedAt"] = now_jst()
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": cftc.get("priceStatus"),
                "pricePoints": price_count,
                "filledFromFallback": filled,
                "errors": errors,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
