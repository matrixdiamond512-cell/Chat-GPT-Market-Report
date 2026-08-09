#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Update Nikkei 225 options strike OI data from JPX Daily Report.

This script intentionally uses OSE/JPX Japan data only.  It extracts the nearest
monthly Nikkei 225 Options contract from the latest JPX index-options daily
report, compares it with the previous report, and writes strike-level Put/Call
open interest and daily OI changes into data/nikkei225-supply-demand.json.

The dashboard uses this data for price-band / hedge-pressure analysis, not as a
mechanical directional signal.
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import pdfplumber
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "nikkei225-supply-demand.json"
JPX_DAILY_JA = "https://www.jpx.co.jp/markets/statistics-derivatives/daily/index.html"
JPX_DAILY_EN = "https://www.jpx.co.jp/english/markets/statistics-derivatives/daily/"
UA = "Mozilla/5.0 (compatible; MarketReportBot/1.0; +https://www.jpx.co.jp/)"
JST = timezone(timedelta(hours=9))


def log(msg: str) -> None:
    print(f"[nikkei225-options] {msg}")


def clean_int(token: str | None) -> int | None:
    if token is None:
        return None
    s = str(token).strip().replace(",", "").replace("−", "-").replace("△", "-")
    if not s or s in {"…", "...", "-", "—", "－"}:
        return 0
    m = re.fullmatch(r"[+-]?\d+(?:\.0+)?", s)
    if not m:
        return None
    return int(float(s))


def clean_num(token: str | None) -> float | None:
    if token is None:
        return None
    s = str(token).strip().replace(",", "").replace("−", "-").replace("△", "-")
    if not s or s in {"…", "...", "-", "—", "－"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def second_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    offset = (4 - d.weekday()) % 7  # Friday = 4
    return d + timedelta(days=offset + 7)


def calc_next_sq(today: date) -> date:
    y, m = today.year, today.month
    sq = second_friday(y, m)
    if today <= sq:
        return sq
    if m == 12:
        y, m = y + 1, 1
    else:
        m += 1
    return second_friday(y, m)


def fetch(session: requests.Session, url: str, timeout: int = 40) -> bytes:
    r = session.get(url, timeout=timeout, headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"})
    r.raise_for_status()
    return r.content


def discover_reports(session: requests.Session) -> list[tuple[str, str, str]]:
    """Return [(yyyymmdd, kind, url)] sorted newest first.

    kind is 'pdf' for a combined OSE report or 'zip' for Daily_Report_OSE.
    JPX page markup changes periodically, so scan all attributes and raw HTML,
    not only visible anchor text.
    """
    found: dict[tuple[str, str], tuple[str, str, str]] = {}
    for index_url in (JPX_DAILY_JA, JPX_DAILY_EN):
        try:
            raw = fetch(session, index_url).decode("utf-8", errors="ignore")
        except Exception as exc:
            log(f"daily page fetch failed: {index_url}: {exc}")
            continue
        soup = BeautifulSoup(raw, "html.parser")
        candidates: set[str] = set()
        for tag in soup.find_all(True):
            for value in tag.attrs.values():
                vals = value if isinstance(value, list) else [value]
                for v in vals:
                    if isinstance(v, str) and (".pdf" in v.lower() or ".zip" in v.lower()):
                        candidates.add(urljoin(index_url, v))
        for m in re.finditer(r'''["']([^"']+(?:\.pdf|\.zip)(?:\?[^"']*)?)["']''', raw, flags=re.I):
            candidates.add(urljoin(index_url, m.group(1)))

        for url in candidates:
            u = url.lower()
            dm = re.search(r"(20\d{6})", url)
            if not dm:
                continue
            ds = dm.group(1)
            kind = None
            if "ose_all" in u and u.endswith(".pdf"):
                kind = "pdf"
            elif "daily_report_ose" in u and ".zip" in u:
                kind = "zip"
            elif "siop_dyr_" in u and u.endswith(".pdf"):
                kind = "pdf"
            if kind:
                found[(ds, url)] = (ds, kind, url)

    reports = sorted(found.values(), key=lambda x: (x[0], 1 if x[1] == "pdf" else 0), reverse=True)
    # Keep only one preferred report per date (combined PDF first, otherwise ZIP).
    by_date: dict[str, tuple[str, str, str]] = {}
    for item in reports:
        ds, kind, _ = item
        if ds not in by_date or (kind == "pdf" and by_date[ds][1] != "pdf"):
            by_date[ds] = item
    return sorted(by_date.values(), key=lambda x: x[0], reverse=True)


def report_pdf_bytes(session: requests.Session, report: tuple[str, str, str]) -> tuple[bytes, str]:
    ds, kind, url = report
    content = fetch(session, url)
    if kind == "pdf":
        return content, url
    zf = zipfile.ZipFile(io.BytesIO(content))
    names = zf.namelist()
    preferred = [n for n in names if re.search(rf"(?:^|/)siop_dyr_{ds}\.pdf$", n, flags=re.I)]
    if not preferred:
        preferred = [n for n in names if "siop_dyr" in n.lower() and n.lower().endswith(".pdf")]
    if not preferred:
        preferred = [n for n in names if "ose_all" in n.lower() and n.lower().endswith(".pdf")]
    if not preferred:
        raise RuntimeError(f"index options PDF not found in {url}; files={names[:20]}")
    name = preferred[0]
    return zf.read(name), f"{url}#{name}"


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\u3000", " ").strip())


def parse_rows(pdf_bytes: bytes) -> list[dict]:
    rows: list[dict] = []
    in_nikkei = False
    side: str | None = None
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=1.2, y_tolerance=2.0, layout=True) or ""
            for raw_line in text.splitlines():
                line = normalize_line(raw_line)
                if not line:
                    continue
                # Product heading: keep exact Nikkei 225 Options but exclude mini options.
                if ("Nikkei 225 mini Options" in line) or ("日経225ミニオプション" in line):
                    in_nikkei = False
                    side = None
                    continue
                if ("Nikkei 225 Options" in line) or ("日経225オプション" in line):
                    in_nikkei = True
                    continue
                if in_nikkei and (("Put Options" in line) or ("プットオプション" in line)):
                    side = "put"
                    continue
                if in_nikkei and (("Call Options" in line) or ("コールオプション" in line)):
                    side = "call"
                    continue
                if not in_nikkei or side is None:
                    continue

                # Data row example (layout text):
                # 202405 05.09 38,000 189058018 ... 72 20,390,000 295.00 … 3,182
                m = re.match(r"^(20\d{4})\s+(\d{2}\.\d{2})\s+([\d,]+(?:\.\d+)?)\s+(\d{7,10})\s+(.*)$", line)
                if not m:
                    continue
                contract_month, last_day, strike_s, code, rest = m.groups()
                strike = clean_num(strike_s)
                if strike is None:
                    continue
                tokens = rest.split()
                # The published table ends with Volume, Trading Value, Settlement,
                # Contracts Exercised, Open Interest.  Net Change can be two tokens,
                # which is why parsing from the end is more stable.
                oi = clean_int(tokens[-1]) if len(tokens) >= 1 else None
                exercised = clean_int(tokens[-2]) if len(tokens) >= 2 else None
                settlement = clean_num(tokens[-3]) if len(tokens) >= 3 else None
                trading_value = clean_num(tokens[-4]) if len(tokens) >= 4 else None
                volume = clean_int(tokens[-5]) if len(tokens) >= 5 else None
                if oi is None:
                    continue
                rows.append({
                    "contractMonth": contract_month,
                    "lastTradingDay": last_day,
                    "strike": int(round(strike)),
                    "code": code,
                    "side": side,
                    "volume": volume if volume is not None else 0,
                    "openInterest": oi,
                    "settlement": settlement,
                    "contractsExercised": exercised,
                    "tradingValue": trading_value,
                })
    return rows


def choose_contract_month(rows: list[dict], preferred: str | None, report_date: str) -> str:
    months = sorted({r["contractMonth"] for r in rows})
    if preferred and preferred in months:
        return preferred
    if not months:
        raise RuntimeError("no Nikkei 225 Options rows parsed from JPX report")
    threshold = report_date[:6]
    future = [m for m in months if m >= threshold]
    return future[0] if future else months[-1]


def aggregate(rows: list[dict], contract_month: str) -> tuple[dict[int, dict], int, int]:
    strikes: dict[int, dict] = defaultdict(lambda: {"putOi": None, "callOi": None, "putVolume": 0, "callVolume": 0})
    put_volume = 0
    call_volume = 0
    for r in rows:
        if r["contractMonth"] != contract_month:
            continue
        strike = r["strike"]
        if r["side"] == "put":
            strikes[strike]["putOi"] = (strikes[strike]["putOi"] or 0) + int(r["openInterest"])
            strikes[strike]["putVolume"] += int(r.get("volume") or 0)
            put_volume += int(r.get("volume") or 0)
        elif r["side"] == "call":
            strikes[strike]["callOi"] = (strikes[strike]["callOi"] or 0) + int(r["openInterest"])
            strikes[strike]["callVolume"] += int(r.get("volume") or 0)
            call_volume += int(r.get("volume") or 0)
    return dict(strikes), put_volume, call_volume


def ratio(a: int, b: int) -> float | None:
    return (a / b) if b else None


def load_json() -> dict:
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> int:
    data = load_json()
    options = data.setdefault("options", {})
    now = datetime.now(JST)
    today = now.date()

    # Keep an existing future SQ date; otherwise calculate the ordinary second Friday.
    existing_sq = options.get("nextSqDate")
    try:
        sq = date.fromisoformat(existing_sq) if existing_sq else calc_next_sq(today)
        if sq < today:
            sq = calc_next_sq(today)
    except Exception:
        sq = calc_next_sq(today)
    options["nextSqDate"] = sq.isoformat()
    preferred_month = sq.strftime("%Y%m")

    session = requests.Session()
    reports = discover_reports(session)
    if len(reports) < 1:
        raise RuntimeError("JPX daily report links could not be discovered")

    latest = reports[0]
    previous = reports[1] if len(reports) > 1 else None
    log(f"latest report: {latest}")
    latest_pdf, latest_source = report_pdf_bytes(session, latest)
    latest_rows = parse_rows(latest_pdf)
    contract_month = choose_contract_month(latest_rows, preferred_month, latest[0])
    latest_agg, put_volume, call_volume = aggregate(latest_rows, contract_month)
    if not latest_agg:
        raise RuntimeError(f"no strike OI rows for contract month {contract_month}")

    prev_agg: dict[int, dict] = {}
    prev_date = None
    prev_source = None
    if previous:
        try:
            prev_pdf, prev_source = report_pdf_bytes(session, previous)
            prev_rows = parse_rows(prev_pdf)
            prev_agg, _, _ = aggregate(prev_rows, contract_month)
            prev_date = previous[0]
        except Exception as exc:
            log(f"previous report parse failed; OI changes left null: {exc}")

    strike_rows = []
    total_put_oi = 0
    total_call_oi = 0
    for strike in sorted(latest_agg):
        cur = latest_agg[strike]
        prv = prev_agg.get(strike, {})
        put_oi = cur.get("putOi")
        call_oi = cur.get("callOi")
        total_put_oi += int(put_oi or 0)
        total_call_oi += int(call_oi or 0)
        put_prev = prv.get("putOi")
        call_prev = prv.get("callOi")
        strike_rows.append({
            "strike": strike,
            "putOi": put_oi,
            "callOi": call_oi,
            "putOiChange": (int(put_oi or 0) - int(put_prev or 0)) if put_oi is not None and put_prev is not None else None,
            "callOiChange": (int(call_oi or 0) - int(call_prev or 0)) if call_oi is not None and call_prev is not None else None,
            "putVolume": int(cur.get("putVolume") or 0),
            "callVolume": int(cur.get("callVolume") or 0),
        })

    options.update({
        "sourceName": "JPX 大阪取引所日報・指数オプション相場表",
        "sourceUrl": JPX_DAILY_JA,
        "optionDailyReportUrl": latest_source,
        "previousOptionDailyReportUrl": prev_source,
        "optionContractMonth": contract_month,
        "strikeOpenInterest": strike_rows,
        "strikeOiAsOfDate": f"{latest[0][:4]}-{latest[0][4:6]}-{latest[0][6:]}",
        "previousStrikeOiAsOfDate": (f"{prev_date[:4]}-{prev_date[4:6]}-{prev_date[6:]}" if prev_date else None),
        "putOpenInterest": total_put_oi,
        "callOpenInterest": total_call_oi,
        "putVolume": put_volume,
        "callVolume": call_volume,
        "putCallRatio": ratio(total_put_oi, total_call_oi),
        "putCallDefinition": "建玉残高ベース（Put OI / Call OI）",
        "putCallStatus": "verified",
        "strikeOiStatus": "verified",
        "optionChainStatus": "verified",
        "asOfDate": f"{latest[0][:4]}-{latest[0][4:6]}-{latest[0][6:]}",
        "fetchedAt": now.isoformat(timespec="seconds"),
        "comment": "JPX大阪取引所日報の指数オプション相場表から、直近月限の日経225オプションを権利行使価格別に集計。方向予想ではなく、建玉集中帯・OI増減・IV・PCR・SQ接近からヘッジ圧力が変わりやすい価格帯を分析する。",
    })

    # Update page-level generation time without changing other market data timestamps.
    data["generatedAt"] = now.isoformat(timespec="seconds")
    save_json(data)
    log(f"updated {DATA_PATH}: {contract_month}, strikes={len(strike_rows)}, putOI={total_put_oi}, callOI={total_call_oi}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"ERROR: {exc}")
        raise
