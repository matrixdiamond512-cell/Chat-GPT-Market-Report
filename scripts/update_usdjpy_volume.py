"""Update Tokyo USD/JPY spot turnover from the Bank of Japan official API."""
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "usdjpy-volume.json"
JST = ZoneInfo("Asia/Tokyo")
API = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
SOURCE_URL = "https://www.boj.or.jp/statistics/market/forex/fxdaily/fxlist/index.htm"
PDF_BASE = "https://www.boj.or.jp/statistics/market/forex/fxdaily/fxlist/"
SERIES = "FXERD06"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/html"})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read()


def month_shift(value: date, months: int) -> date:
    absolute = value.year * 12 + value.month - 1 + months
    return date(absolute // 12, absolute % 12 + 1, 1)


def api_records(now: datetime) -> tuple[list[dict], str]:
    start = month_shift(now.date().replace(day=1), -13).strftime("%Y%m")
    end = now.strftime("%Y%m")
    query = urllib.parse.urlencode({"format": "json", "lang": "en", "db": "FM08", "startDate": start, "endDate": end, "code": SERIES})
    payload = json.loads(fetch(f"{API}?{query}").decode("utf-8"))
    if payload.get("STATUS") != 200:
        raise RuntimeError(f"BOJ API status={payload.get('STATUS')}: {payload.get('MESSAGE')}")
    series = next((item for item in payload.get("RESULTSET", []) if item.get("SERIES_CODE") == SERIES), None)
    if not series:
        raise RuntimeError(f"BOJ series {SERIES} was not returned")
    values = series.get("VALUES") or {}
    dates = values.get("SURVEY_DATES") or []
    amounts = values.get("VALUES") or []
    rows = []
    for raw_date, raw_value in zip(dates, amounts):
        if raw_value is None:
            continue
        text = str(raw_date)
        if not re.fullmatch(r"\d{8}", text):
            continue
        rows.append({"targetDate": f"{text[:4]}-{text[4:6]}-{text[6:]}", "spotVolume": float(raw_value)})
    if not rows:
        raise RuntimeError("BOJ API returned no USD/JPY spot turnover observations")
    return rows, str(series.get("LAST_UPDATE") or "")


def publications() -> list[dict]:
    html = fetch(SOURCE_URL).decode("utf-8", errors="replace")
    found = {}
    for href, yymmdd in re.findall(r'href=["\']([^"\']*fx(\d{6})\.pdf)["\']', html, flags=re.I):
        publication = f"20{yymmdd[:2]}-{yymmdd[2:4]}-{yymmdd[4:]}"
        url = urllib.parse.urljoin(SOURCE_URL, href)
        found[publication] = {"date": publication, "pdfName": f"fx{yymmdd}.pdf", "url": url}
    return [found[key] for key in sorted(found)]


def next_weekday(value: str) -> str:
    current = date.fromisoformat(value) + timedelta(days=1)
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return current.isoformat()


def publication_for(target: str, items: list[dict]) -> dict:
    match = next((item for item in items if item["date"] > target), None)
    if match:
        return match
    publication = next_weekday(target)
    compact = publication.replace("-", "")[2:]
    return {"date": publication, "pdfName": f"fx{compact}.pdf", "url": f"{PDF_BASE}fx{compact}.pdf"}


def rounded(value: float | None, digits: int = 0):
    return None if value is None else round(value, digits)


def update_derived(records: list[dict]) -> None:
    chronological = sorted(records, key=lambda row: row["targetDate"])
    for index, row in enumerate(chronological):
        previous = chronological[index - 1] if index else None
        change = row["spotVolume"] - previous["spotVolume"] if previous else None
        window = chronological[max(0, index - 19):index + 1]
        average = sum(item["spotVolume"] for item in window) / len(window) if window else None
        row["volumeChange"] = rounded(change)
        row["volumeChangePct"] = rounded(change / previous["spotVolume"] * 100, 2) if previous and previous["spotVolume"] else None
        row["avg20"] = rounded(average)
        row["vs20"] = rounded(row["spotVolume"] - average) if average is not None else None
        row["vs20Pct"] = rounded((row["spotVolume"] - average) / average * 100, 2) if average else None


def build(existing: dict, now: datetime) -> dict:
    observations, last_update = api_records(now)
    publication_files = publications()
    existing_rows = {row.get("targetDate"): dict(row) for row in ((existing.get("data") or {}).get("records") or []) if row.get("targetDate")}
    price_rows = {row.get("date"): row for row in ((existing.get("data") or {}).get("priceRecords") or []) if row.get("date")}
    for observation in observations:
        target = observation["targetDate"]
        row = existing_rows.get(target, {"targetDate": target})
        publication = publication_for(target, publication_files)
        row.update({
            "publicationDate": publication["date"],
            "sourcePdfName": publication["pdfName"],
            "sourcePdfUrl": publication["url"],
            "spotVolume": rounded(observation["spotVolume"]),
        })
        price = price_rows.get(target) or {}
        for key in ("close", "open", "high", "low", "priceChangePct"):
            row.setdefault(key, price.get(key))
        existing_rows[target] = row

    records = sorted(existing_rows.values(), key=lambda row: row["targetDate"], reverse=True)
    update_derived(records)
    latest = records[0]
    generated = now.isoformat(timespec="seconds")
    age_days = (now.date() - date.fromisoformat(latest["targetDate"])).days
    existing.update({
        "reportDateTime": generated,
        "dataAsOf": f"{latest['targetDate']}T15:00:00+09:00",
        "generatedAt": generated,
        "publishedAt": generated,
        "status": "ok",
        "isStale": age_days > 7,
        "staleReason": f"BOJ最新対象日から{age_days}日経過" if age_days > 7 else "",
        "errors": [],
    })
    data = existing.setdefault("data", {})
    data.update({
        "sourceName": "日本銀行 外国為替市況（日次）",
        "sourceUrl": SOURCE_URL,
        "pdfBaseUrl": PDF_BASE,
        "unit": "百万ドル",
        "records": records,
    })
    components = existing.setdefault("components", {})
    components["bojSpotVolume"] = {
        "status": "ok", "sourceId": "BOJ_FX_DAILY", "latestTargetDate": latest["targetDate"],
        "latestPublicationDate": latest["publicationDate"], "rule": "日銀外国為替市況のUSD/JPYスポット出来高のみ。スワップ出来高は使用しない。",
    }
    for source in existing.get("sources", []):
        if source.get("id") == "BOJ_FX_DAILY":
            source["asOf"] = latest["publicationDate"]
            source["status"] = "ok"
    existing.setdefault("diagnostics", {})["bojApi"] = {"series": SERIES, "lastUpdate": last_update, "checkedAt": generated}
    return existing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    existing = json.loads(DEFAULT_OUT.read_text(encoding="utf-8"))
    result = build(existing, datetime.now(JST))
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    latest = result["data"]["records"][0]
    print(json.dumps({"targetDate": latest["targetDate"], "publicationDate": latest["publicationDate"], "spotVolume": latest["spotVolume"], "generatedAt": result["generatedAt"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
