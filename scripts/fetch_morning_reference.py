#!/usr/bin/env python3
"""Fetch source-verified morning reference values that are not in the core quote layer.

This helper captures CME Nikkei 225 futures (yen- and dollar-denominated) plus the
Osaka large Nikkei 225 future from the nikkei225jp summary page. CME rows on the
site may end in either a page date (MM/DD) or a live quote time (HH:MM); both are
accepted. Values are reference quotes, not official CME settlement prices.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JST = dt.timezone(dt.timedelta(hours=9))
SOURCE_URL = "https://nikkei225jp.com/cme/"
OUT = ROOT / "data" / "market" / "morning-reference.json"
USER_AGENT = "Mozilla/5.0 (compatible; ChatGPT-Market-Report/1.0)"


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST).replace(microsecond=0)


def strip_tags(value: str) -> str:
    value = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return html.unescape(re.sub(r"\s+", " ", value)).strip()


def get_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() or "utf-8"
    return strip_tags(raw.decode(encoding, errors="replace"))


def number(value: str) -> float:
    return float(value.replace(",", ""))


def pct_from_change(value: float, change: float) -> str:
    previous = value - change
    if previous == 0:
        return ""
    return f"{(change / previous) * 100:+.2f}%"


def fmt_integer(value: float) -> str:
    return f"{value:,.0f}"


def parse_cme(text: str, currency: str) -> dict[str, str] | None:
    marker = "CME￥" if currency == "yen" else "CME＄"
    pattern = re.compile(
        re.escape(marker)
        + r"\s+26年09月限\s+([0-9,]+)\s+([+\-][0-9,]+)\s+"
          r"([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+(\d{2}:\d{2}|\d{2}/\d{2})"
    )
    match = pattern.search(text)
    if not match:
        return None
    value = number(match.group(1))
    change = number(match.group(2))
    stamp = match.group(6)
    return {
        "value": fmt_integer(value),
        "change": f"{change:+,.0f}",
        "rate": pct_from_change(value, change),
        "direction": "上昇" if change > 0 else "下落" if change < 0 else "横ばい",
        "stamp": stamp,
        "stampType": "time" if ":" in stamp else "date",
    }


def parse_ose(text: str) -> dict[str, str] | None:
    pattern = re.compile(
        r"大証ラージ\s+26年9月限\s+([0-9,]+)\s+([+\-][0-9,]+)\s+"
        r"([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+(\d{2}:\d{2})"
    )
    match = pattern.search(text)
    if not match:
        return None
    value = number(match.group(1))
    change = number(match.group(2))
    return {
        "value": f"{fmt_integer(value)}円",
        "change": f"{change:+,.0f}",
        "rate": pct_from_change(value, change),
        "direction": "上昇" if change > 0 else "下落" if change < 0 else "横ばい",
        "time": match.group(7),
    }


def cme_as_of(report_date: dt.date, parsed: dict[str, str]) -> str:
    if parsed.get("stampType") == "time":
        return f"{report_date.isoformat()}T{parsed['stamp']}:00+09:00"
    month, day = (int(part) for part in parsed["stamp"].split("/"))
    return dt.date(report_date.year, month, day).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-date", default=now_jst().date().isoformat())
    parser.add_argument("--slot", default="08:00")
    args = parser.parse_args()

    report_date = dt.date.fromisoformat(args.report_date)
    text = get_text(SOURCE_URL)
    yen = parse_cme(text, "yen")
    dollar = parse_cme(text, "dollar")
    ose = parse_ose(text)

    items: dict[str, dict[str, object]] = {}
    reference_dates: list[str] = []

    for label, parsed, product in (
        ("CME日経225先物・円建て", yen, "CME NIY"),
        ("CME日経225先物・ドル建て", dollar, "CME NKD"),
    ):
        if not parsed:
            continue
        as_of = cme_as_of(report_date, parsed)
        if parsed.get("stampType") == "date":
            reference_dates.append(as_of[:10])
        items[label] = {
            "value": parsed["value"],
            "change": parsed["change"],
            "rate": parsed["rate"],
            "direction": parsed["direction"],
            "asOf": as_of,
            "sourceName": f"nikkei225jp.com {product}",
            "sourceUrl": SOURCE_URL,
            "status": "verified_reference",
            "note": "26年09月限のページ上最終表示値。CME公式清算値ではないため、その区別を維持する。",
        }

    if ose:
        items["日経225先物（大阪取引所）"] = {
            "value": ose["value"],
            "change": ose["change"],
            "rate": ose["rate"],
            "direction": ose["direction"],
            "asOf": f"{report_date.isoformat()}T{ose['time']}:00+09:00",
            "sourceName": "JPX/OSE mirrored quote on nikkei225jp.com",
            "sourceUrl": SOURCE_URL,
            "status": "verified_reference",
            "note": "大証ラージ26年9月限。JPX/OSEの値とクロスチェックして使用する。",
        }

    if not items:
        raise SystemExit("No morning reference values parsed")

    payload = {
        "schemaVersion": "1.1.0",
        "generatedAt": now_jst().isoformat(),
        "reportDate": report_date.isoformat(),
        "reportSlot": args.slot,
        "referenceDate": max(reference_dates) if reference_dates else report_date.isoformat(),
        "items": items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
