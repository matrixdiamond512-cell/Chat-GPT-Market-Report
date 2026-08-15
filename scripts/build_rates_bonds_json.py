#!/usr/bin/env python3
"""Build the rates & bonds page JSON from reliable public data sources.

Core sources:
- FRED: U.S. Treasury yields, real yield, breakeven inflation, term premium
- Japan MOF: JGB constant-maturity yields
- Deutsche Bundesbank: German 10-year federal bond yield
- U.S. Fiscal Data: recent Treasury auction results (best effort)

The script intentionally keeps unavailable optional fields out of the main analysis
rather than inventing values. It is designed to run with Python stdlib only.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "rates-bonds.json"
HISTORY = ROOT / "data" / "rates-bonds-history.json"
MARKET_LATEST = ROOT / "data" / "market" / "latest.json"
EVENTS_LATEST = ROOT / "data" / "events.json"
JST = dt.timezone(dt.timedelta(hours=9))
USER_AGENT = (
    "Mozilla/5.0 (compatible; MarketReportBot/1.0; "
    "+https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/)"
)

FRED_SERIES = {
    "DGS2": "米2年債利回り",
    "DGS5": "米5年債利回り",
    "DGS10": "米10年債利回り",
    "DGS30": "米30年債利回り",
    "DFII10": "米10年実質金利",
    "T10YIE": "米10年期待インフレ率",
    "THREEFYTP10": "米10年タームプレミアム",
    "DFEDTARL": "FF金利目標下限",
    "DFEDTARU": "FF金利目標上限",
}

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + ",".join(FRED_SERIES)
MOF_JGB_URL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"
MOF_JGB_HISTORY_URL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv"
TRADINGVIEW_SCANNER_URL = "https://scanner.tradingview.com/global/scan"
TRADINGVIEW_JGB_SYMBOLS = {2: "TVC:JP02Y", 5: "TVC:JP05Y", 10: "TVC:JP10Y", 30: "TVC:JP30Y"}
BUND10_URL = (
    "https://api.statistiken.bundesbank.de/rest/data/BBSSY/"
    "D.REN.EUR.A630.000000WT1010.A?format=csv&lang=en"
)
TREASURY_AUCTION_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
    "v1/accounting/od/auctions_query"
)
CME_FEDWATCH_PAGE = "https://www.cmegroup.com/ja/markets/interest-rates/cme-fedwatch-tool.html"


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST).replace(microsecond=0)


def iso_now() -> str:
    return now_jst().isoformat()


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def http_text(url: str, timeout: int = 25) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc
    for encoding in (charset, "utf-8-sig", "utf-8", "cp932", "latin-1"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def http_json_post(url: str, payload: dict[str, Any], timeout: int = 25) -> Any:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc


def fedwatch_unavailable(reason: str = "CME FedWatch公式API未設定") -> dict[str, Any]:
    return {"status": "unavailable", "source": "CME FedWatch", "sourceUrl": CME_FEDWATCH_PAGE,
            "asOf": None, "dataMode": "eod", "currentTargetRange": None, "summary": None,
            "meetings": [], "twoYearConsistency": {"status": "unavailable", "us2yChangeBp": None,
            "interpretation": reason}, "unavailableReason": reason}


def stance_shift(change: float | None) -> str:
    if change is None: return "判定不能"
    if change >= 10: return "利下げ織り込みが大きく強まる"
    if change >= 3: return "利下げ織り込みが強まる"
    if change > -3: return "利下げ織り込みは横ばい"
    if change > -10: return "利下げ織り込みが弱まる"
    return "利下げ織り込みが大きく弱まる"


def validate_fedwatch(payload: dict[str, Any]) -> tuple[bool, str | None]:
    summary = payload.get("summary") or {}
    required_summary = ("nextMeetingDate", "dominantAction", "dominantTargetRange", "probabilityPct",
                        "oneDayAgoPct", "oneWeekAgoPct", "oneMonthAgoPct")
    if not payload.get("asOf") or not payload.get("currentTargetRange") or any(summary.get(key) is None for key in required_summary):
        return False, "必須メタ情報または比較確率が不足しています"
    meetings = payload.get("meetings") or []
    if not meetings: return False, "会合別確率がありません"
    for meeting in meetings:
        outcomes = meeting.get("outcomes") or []
        current = [safe_float(row.get("currentProbabilityPct")) for row in outcomes]
        if not current or any(value is None or not 0 <= value <= 100 for value in current):
            return False, "確率が0～100の範囲外です"
        total = sum(value for value in current if value is not None)
        if not 99.5 <= total <= 100.5:
            return False, f"{meeting.get('meetingDate', '会合')}の確率合計が{total:.1f}%です"
        for row in outcomes:
            for key in ("oneDayAgoPct", "oneWeekAgoPct", "oneMonthAgoPct"):
                value = safe_float(row.get(key))
                if value is None or not 0 <= value <= 100:
                    return False, f"{key}が未取得または0～100の範囲外です"
    return True, None


def fetch_fedwatch(us2y: dict[str, Any] | None) -> dict[str, Any]:
    """Use only a contract-confirmed CME JSON endpoint; never guess or scrape."""
    endpoint = os.environ.get("CME_FEDWATCH_API_URL", "").strip()
    api_key = os.environ.get("CME_FEDWATCH_API_KEY", "").strip()
    if not endpoint or not api_key: return fedwatch_unavailable()
    request = urllib.request.Request(endpoint, headers={"User-Agent": USER_AGENT, "Accept": "application/json",
        "Authorization": f"Bearer {api_key}", "X-API-Key": api_key})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return fedwatch_unavailable(f"CME FedWatch公式API取得失敗：{type(exc).__name__}")
    payload = raw.get("fedWatch", raw) if isinstance(raw, dict) else {}
    if not isinstance(payload, dict): return fedwatch_unavailable("CME FedWatch公式APIの応答形式が不正です")
    payload = dict(payload)
    payload.update({"source": "CME FedWatch", "sourceUrl": CME_FEDWATCH_PAGE})
    payload.setdefault("dataMode", "eod")
    summary = payload.get("summary") or {}
    if summary:
        current, previous = safe_float(summary.get("probabilityPct")), safe_float(summary.get("oneDayAgoPct"))
        change = round(current - previous, 1) if current is not None and previous is not None else None
        summary.update({"change1dPt": change, "stanceShift": stance_shift(change)})
        payload["summary"] = summary
    valid, reason = validate_fedwatch(payload)
    payload["status"] = "confirmed" if valid else "unavailable"
    if not valid: payload["unavailableReason"] = reason
    us2_change = safe_float((us2y or {}).get("changeBp"))
    if valid and summary.get("change1dPt") is not None and us2_change is not None:
        shift = float(summary["change1dPt"])
        if abs(shift) < 3 or abs(us2_change) < 0.05:
            status, interpretation = "neutral", "変化が小さく、明確な方向判定はしない"
        else:
            consistent = (shift > 0 and us2_change < 0) or (shift < 0 and us2_change > 0)
            status = "consistent" if consistent else "divergent"
            interpretation = "利下げ織り込み変化と米2年債利回りが整合" if consistent else "FedWatchと米2年債が逆方向。需給・インフレ・基準時刻差を確認"
        payload["twoYearConsistency"] = {"status": status, "us2yChangeBp": us2_change, "interpretation": interpretation}
    else:
        payload["twoYearConsistency"] = {"status": "unavailable", "us2yChangeBp": us2_change,
            "interpretation": reason or "比較に必要な確率または米2年債前日比がありません"}
    return payload


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text in {".", "-", "--", "N/A", "NA", "null", "None"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def fmt_number(value: float | None, digits: int = 3, signed: bool = False) -> str | None:
    if value is None:
        return None
    prefix = "+" if signed and value > 0 else ""
    return f"{prefix}{value:.{digits}f}"


def direction(change_bp: float | None, deadband: float = 0.05) -> str:
    if change_bp is None:
        return "横ばい"
    if change_bp > deadband:
        return "上昇"
    if change_bp < -deadband:
        return "低下"
    return "横ばい"


def parse_date(value: str) -> dt.date | None:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return dt.datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def point_stats(points: list[tuple[dt.date, float]]) -> dict[str, Any] | None:
    if not points:
        return None
    points = sorted({d: v for d, v in points}.items())
    latest_date, latest_value = points[-1]
    previous_value = points[-2][1] if len(points) >= 2 else None
    previous_date = points[-2][0] if len(points) >= 2 else None
    week_target = latest_date - dt.timedelta(days=7)
    week_candidates = [(d, v) for d, v in points[:-1] if d <= week_target]
    if week_candidates:
        week_date, week_value = week_candidates[-1]
    elif len(points) >= 6:
        week_date, week_value = points[-6]
    else:
        week_date, week_value = (None, None)
    change_bp = (latest_value - previous_value) * 100 if previous_value is not None else None
    week_change_bp = (latest_value - week_value) * 100 if week_value is not None else None
    return {
        "date": latest_date,
        "value": latest_value,
        "previousDate": previous_date,
        "previous": previous_value,
        "weekDate": week_date,
        "week": week_value,
        "changeBp": change_bp,
        "weekChangeBp": week_change_bp,
    }


def fetch_fred() -> tuple[dict[str, dict[str, Any]], str]:
    text = http_text(FRED_URL)
    reader = csv.DictReader(io.StringIO(text))
    series_points: dict[str, list[tuple[dt.date, float]]] = {key: [] for key in FRED_SERIES}
    for row in reader:
        date = parse_date(row.get("observation_date") or row.get("DATE") or "")
        if not date:
            continue
        for series in FRED_SERIES:
            value = safe_float(row.get(series))
            if value is not None:
                series_points[series].append((date, value))
    result: dict[str, dict[str, Any]] = {}
    for series, points in series_points.items():
        stats = point_stats(points)
        if stats:
            result[series] = stats
    if not result:
        raise RuntimeError("FRED returned no usable observations")
    latest = max(stats["date"] for stats in result.values())
    return result, latest.isoformat()


def detect_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:30])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        return ","


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def find_tenor_index(headers: list[str], tenor: int) -> int | None:
    candidates = {
        2: {"2y", "2year", "2years", "2yr", "2"},
        5: {"5y", "5year", "5years", "5yr", "5"},
        10: {"10y", "10year", "10years", "10yr", "10"},
        30: {"30y", "30year", "30years", "30yr", "30"},
    }[tenor]
    normalized = [normalize_header(h) for h in headers]
    for idx, header in enumerate(normalized):
        if header in candidates:
            return idx
        if any(token in header for token in candidates if len(token) > 1):
            return idx
    return None


def parse_jgb_rows(text: str) -> dict[int, list[tuple[dt.date, float]]]:
    delimiter = detect_delimiter(text)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    header_idx = None
    date_idx = 0
    tenor_indexes: dict[int, int] = {}
    for idx, row in enumerate(rows[:40]):
        joined = " ".join(row).lower()
        if "date" in joined and ("10" in joined or "year" in joined):
            header_idx = idx
            headers = row
            for i, header in enumerate(headers):
                if "date" in normalize_header(header):
                    date_idx = i
                    break
            for tenor in (2, 5, 10, 30):
                found = find_tenor_index(headers, tenor)
                if found is not None:
                    tenor_indexes[tenor] = found
            break
    if header_idx is None:
        # MOF files normally use Date,1Y,2Y,...; support that fixed layout as fallback.
        for idx, row in enumerate(rows[:20]):
            if row and parse_date(row[0]):
                header_idx = idx - 1
                tenor_indexes = {2: 2, 5: 5, 10: 10, 30: 14}
                break
    points: dict[int, list[tuple[dt.date, float]]] = {2: [], 5: [], 10: [], 30: []}
    start = max((header_idx or 0) + 1, 0)
    for row in rows[start:]:
        if not row or date_idx >= len(row):
            continue
        date = parse_date(row[date_idx])
        if not date:
            continue
        for tenor, col_idx in tenor_indexes.items():
            if col_idx < len(row):
                value = safe_float(row[col_idx])
                if value is not None:
                    points[tenor].append((date, value))
    return points


def latest_japan_market_date() -> dt.date:
    """Infer the date represented by a current JGB market snapshot.

    Before the Tokyo cash-market close, the latest complete observation is the
    preceding market day.  Holiday events already maintained by this portal are
    used so a national holiday is not incorrectly labelled as a trading day.
    """
    current = now_jst()
    candidate = current.date() if current.hour >= 18 else current.date() - dt.timedelta(days=1)
    events = load_json(EVENTS_LATEST, {})
    holiday_dates = {
        parse_date(item.get("date"))
        for item in (events.get("events") or [])
        if item.get("currency") == "JPY" and item.get("category") == "holiday"
    }
    holiday_dates.discard(None)
    while candidate.weekday() >= 5 or candidate in holiday_dates:
        candidate -= dt.timedelta(days=1)
    return candidate


def fetch_tradingview_jgb() -> tuple[dict[int, float], dt.date]:
    payload = {
        "symbols": {"tickers": list(TRADINGVIEW_JGB_SYMBOLS.values()), "query": {"types": []}},
        "columns": ["name", "close"],
    }
    response = http_json_post(TRADINGVIEW_SCANNER_URL, payload)
    by_symbol = {row.get("s"): row.get("d", []) for row in response.get("data", [])}
    values: dict[int, float] = {}
    for tenor, symbol in TRADINGVIEW_JGB_SYMBOLS.items():
        cells = by_symbol.get(symbol) or []
        value = safe_float(cells[1] if len(cells) > 1 else None)
        if value is not None:
            values[tenor] = value
    if not values:
        raise RuntimeError("TradingView JGB scanner returned no usable observations")
    return values, latest_japan_market_date()


def fetch_jgb() -> tuple[dict[int, dict[str, Any]], str]:
    combined: dict[int, list[tuple[dt.date, float]]] = {2: [], 5: [], 10: [], 30: []}
    errors: list[str] = []
    for url in (MOF_JGB_HISTORY_URL, MOF_JGB_URL):
        try:
            parsed = parse_jgb_rows(http_text(url))
            for tenor, points in parsed.items():
                combined[tenor].extend(points)
        except Exception as exc:  # best-effort source chain
            errors.append(f"{url}: {exc}")
    market_source_used = False
    try:
        market_values, market_date = fetch_tradingview_jgb()
        official_latest = max((d for points in combined.values() for d, _ in points), default=None)
        if official_latest is None or market_date > official_latest:
            for tenor, value in market_values.items():
                combined[tenor].append((market_date, value))
            market_source_used = True
    except Exception as exc:
        errors.append(f"{TRADINGVIEW_SCANNER_URL}: {exc}")
    result: dict[int, dict[str, Any]] = {}
    for tenor, points in combined.items():
        stats = point_stats(points)
        if stats:
            if market_source_used and stats["date"] == market_date:
                stats["source"] = "TradingView JGB market snapshot (LSEG)"
            result[tenor] = stats
    if not result:
        raise RuntimeError(" / ".join(errors) or "MOF JGB returned no usable observations")
    latest = max(stats["date"] for stats in result.values())
    return result, latest.isoformat()


def fetch_bund10() -> tuple[dict[str, Any], str]:
    text = http_text(BUND10_URL)
    delimiter = detect_delimiter(text)
    points: list[tuple[dt.date, float]] = []
    for row in csv.reader(io.StringIO(text), delimiter=delimiter):
        if len(row) < 2:
            continue
        date = None
        for cell in row[:3]:
            date = parse_date(cell)
            if date:
                break
        if not date:
            continue
        numeric = [safe_float(cell) for cell in row[1:]]
        numeric = [value for value in numeric if value is not None]
        if numeric:
            points.append((date, numeric[-1]))
    stats = point_stats(points)
    if not stats:
        raise RuntimeError("Bundesbank returned no usable observations")
    return stats, stats["date"].isoformat()


def fetch_treasury_auctions() -> list[dict[str, Any]]:
    start = (dt.date.today() - dt.timedelta(days=120)).isoformat()
    params = urllib.parse.urlencode({
        "filter": f"auction_date:gte:{start}",
        "page[size]": "250",
        "sort": "-auction_date",
    })
    url = f"{TREASURY_AUCTION_URL}?{params}"
    payload = json.loads(http_text(url))
    rows = payload.get("data") or []
    wanted = {"2-Year", "5-Year", "10-Year", "30-Year"}
    normalized_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        term = str(row.get("security_term") or row.get("original_security_term") or "").strip()
        if term not in wanted or term in seen:
            continue
        seen.add(term)
        high_yield = safe_float(row.get("high_yield") or row.get("high_investment_rate"))
        bid_cover = safe_float(row.get("bid_to_cover_ratio"))
        total_accepted = safe_float(row.get("total_accepted"))
        indirect = safe_float(row.get("indirect_bidder_accepted"))
        dealer = safe_float(row.get("primary_dealer_accepted"))
        indirect_pct = (indirect / total_accepted * 100) if indirect is not None and total_accepted else None
        dealer_pct = (dealer / total_accepted * 100) if dealer is not None and total_accepted else None
        normalized_rows.append({
            "term": term,
            "auctionDate": row.get("auction_date"),
            "highYield": high_yield,
            "bidToCover": bid_cover,
            "indirectPct": indirect_pct,
            "dealerPct": dealer_pct,
        })
    return normalized_rows


def rate_item(name: str, stats: dict[str, Any] | None, source: str, meaning: str) -> dict[str, Any]:
    if not stats:
        return {
            "name": name,
            "value": None,
            "unit": "%",
            "changeBp": None,
            "weekChangeBp": None,
            "direction": None,
            "asOf": None,
            "status": "unavailable",
            "source": source,
            "meaning": meaning,
            "missingReason": "今回の自動取得で取得できず",
        }
    return {
        "name": name,
        "value": round(stats["value"], 3),
        "unit": "%",
        "changeBp": round(stats["changeBp"], 1) if stats.get("changeBp") is not None else None,
        "weekChangeBp": round(stats["weekChangeBp"], 1) if stats.get("weekChangeBp") is not None else None,
        "direction": direction(stats.get("changeBp")),
        "asOf": stats["date"].isoformat(),
        "status": "confirmed",
        "source": stats.get("source", source),
        "meaning": meaning,
        "missingReason": None,
    }


def spread_row(label: str, long_stats: dict[str, Any] | None, short_stats: dict[str, Any] | None) -> dict[str, Any]:
    if not long_stats or not short_stats:
        return {"spread": label, "status": "unavailable"}
    current = (long_stats["value"] - short_stats["value"]) * 100
    previous = None
    week = None
    if long_stats.get("previous") is not None and short_stats.get("previous") is not None:
        previous = (long_stats["previous"] - short_stats["previous"]) * 100
    if long_stats.get("week") is not None and short_stats.get("week") is not None:
        week = (long_stats["week"] - short_stats["week"]) * 100
    change = current - previous if previous is not None else None
    week_change = current - week if week is not None else None
    if current < 0:
        shape = "逆イールド"
    elif current < 25:
        shape = "ほぼフラット"
    else:
        shape = "順イールド"
    if change is None:
        reading = "カーブ変化は比較データ不足"
    elif change > 1:
        reading = "スティープ化"
    elif change < -1:
        reading = "フラット化"
    else:
        reading = "形状は概ね不変"
    return {
        "spread": label,
        "value": round(current, 1),
        "unit": "bp",
        "changeBp": round(change, 1) if change is not None else None,
        "weekChangeBp": round(week_change, 1) if week_change is not None else None,
        "shape": shape,
        "reading": reading,
        "status": "calculated",
    }


def market_change(market: dict[str, Any], key: str) -> float | None:
    value = ((market.get("markets") or {}).get(key) or {}).get("changePercent")
    return safe_float(value)


def cross_asset_note(rate_dir: str, asset_change: float | None, asset_name: str, rate_label: str) -> tuple[str, str]:
    if asset_change is None:
        return "取得不能", f"{asset_name}の同時刻データを取得できず"
    asset_dir = "上昇" if asset_change > 0.05 else "下落" if asset_change < -0.05 else "横ばい"
    if rate_dir == "上昇" and asset_dir == "上昇":
        consistency = "逆行"
        note = f"{rate_label}上昇でも{asset_name}は上昇。金利以外の材料・モメンタムが優勢。"
    elif rate_dir == "低下" and asset_dir == "下落":
        consistency = "逆行"
        note = f"{rate_label}低下でも{asset_name}は下落。金利低下だけでは買い材料になっていない。"
    else:
        consistency = "概ね整合"
        note = f"{rate_label}{rate_dir}と{asset_name}{asset_dir}を併せて確認。"
    return f"{asset_dir}（{asset_change:+.2f}%）／{consistency}", note


def build_payload() -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    fred: dict[str, dict[str, Any]] = {}
    jgb: dict[int, dict[str, Any]] = {}
    bund10: dict[str, Any] | None = None
    auctions: list[dict[str, Any]] = []

    try:
        fred, _ = fetch_fred()
    except Exception as exc:
        errors.append({"level": "warning", "message": f"FRED取得失敗: {exc}"})
    try:
        jgb, _ = fetch_jgb()
    except Exception as exc:
        errors.append({"level": "warning", "message": f"財務省JGB取得失敗: {exc}"})
    try:
        bund10, _ = fetch_bund10()
    except Exception as exc:
        errors.append({"level": "warning", "message": f"Bundesbank取得失敗: {exc}"})
    try:
        auctions = fetch_treasury_auctions()
    except Exception as exc:
        errors.append({"level": "info", "message": f"米国債入札取得失敗: {exc}"})

    market = load_json(MARKET_LATEST, {})
    generated = iso_now()

    us2, us5, us10, us30 = fred.get("DGS2"), fred.get("DGS5"), fred.get("DGS10"), fred.get("DGS30")
    real10, breakeven10, term10 = fred.get("DFII10"), fred.get("T10YIE"), fred.get("THREEFYTP10")
    jp2, jp5, jp10, jp30 = jgb.get(2), jgb.get(5), jgb.get(10), jgb.get(30)

    rates = [
        rate_item("米2年債利回り", us2, "FRED DGS2", "金融政策・FF金利見通しを最も反映しやすい年限"),
        rate_item("米5年債利回り", us5, "FRED DGS5", "中期の政策・景気・インフレ期待を確認"),
        rate_item("米10年債利回り", us10, "FRED DGS10", "株式・為替・金の基準となる長期金利"),
        rate_item("米30年債利回り", us30, "FRED DGS30", "財政・国債供給・長期インフレリスクを確認"),
        rate_item("米10年実質金利", real10, "FRED DFII10", "金・高PER株・BTCへの割引率/保有コストを確認"),
        rate_item("米10年期待インフレ率", breakeven10, "FRED T10YIE", "市場のインフレ期待を確認"),
        rate_item("米10年タームプレミアム", term10, "FRED THREEFYTP10", "長期保有リスクに対する上乗せ金利を確認"),
        rate_item("日本2年国債利回り", jp2, "財務省 国債金利情報", "日銀の政策正常化・短期金利期待を確認"),
        rate_item("日本5年国債利回り", jp5, "財務省 国債金利情報", "日本の中期金利とカーブ形状を確認"),
        rate_item("日本10年国債利回り", jp10, "財務省 国債金利情報", "円・銀行株・日経225・円キャリーへの影響を確認"),
        rate_item("日本30年国債利回り", jp30, "財務省 国債金利情報", "日本の財政・超長期債需給を確認"),
        rate_item("ドイツ10年国債利回り", bund10, "Deutsche Bundesbank", "EUR/USDとユーロ圏長期金利の基準"),
    ]

    confirmed_rates = [r for r in rates if r["status"] in {"confirmed", "calculated"} and r["value"] is not None]
    as_of_dates = [r["asOf"] for r in confirmed_rates if r.get("asOf")]
    as_of_date = max(as_of_dates) if as_of_dates else None

    us10_dir = direction(us10.get("changeBp") if us10 else None)
    us2_dir = direction(us2.get("changeBp") if us2 else None)
    jp10_dir = direction(jp10.get("changeBp") if jp10 else None)
    real10_dir = direction(real10.get("changeBp") if real10 else None)

    curve_rows = [
        spread_row("米10年－2年", us10, us2),
        spread_row("米30年－5年", us30, us5),
        spread_row("米30年－10年", us30, us10),
        spread_row("日本10年－2年", jp10, jp2),
        spread_row("日本30年－10年", jp30, jp10),
    ]
    valid_curve_rows = [row for row in curve_rows if row.get("status") != "unavailable"]

    us2s10s = valid_curve_rows[0] if valid_curve_rows else {}
    curve_change = us2s10s.get("changeBp")
    if curve_change is None:
        curve_summary = "米国カーブの前日変化は比較データ不足。"
    elif curve_change > 1:
        curve_summary = f"米2年－10年は前日比{curve_change:+.1f}bpスティープ化。長短金利差が拡大。"
    elif curve_change < -1:
        curve_summary = f"米2年－10年は前日比{curve_change:+.1f}bpフラット化。長短金利差が縮小。"
    else:
        curve_summary = "米2年－10年カーブは前日から大きな形状変化なし。"

    factors = []
    for label, stats, source_note in (
        ("実質金利", real10, "DFII10"),
        ("期待インフレ", breakeven10, "T10YIE"),
        ("タームプレミアム", term10, "THREEFYTP10"),
    ):
        if stats:
            factors.append({
                "name": label,
                "value": round(stats.get("changeBp") or 0.0, 1),
                "unit": "bp",
                "direction": direction(stats.get("changeBp")),
                "status": "confirmed",
                "interpretation": f"前日比。出所: FRED {source_note}",
            })
    if us10 and real10 and breakeven10:
        residual = (us10.get("changeBp") or 0) - (real10.get("changeBp") or 0) - (breakeven10.get("changeBp") or 0)
        decomposition_point = (
            f"米10年は前日比{us10.get('changeBp', 0):+.1f}bp。"
            f"実質金利{real10.get('changeBp', 0):+.1f}bp、期待インフレ{breakeven10.get('changeBp', 0):+.1f}bp。"
            f"単純差分は{residual:+.1f}bpだが、これをタームプレミアムと断定しない。"
        )
    else:
        decomposition_point = "米10年の変化要因は取得済み系列のみで判定。未取得部分は推測しない。"

    latest_auction = auctions[0] if auctions else None
    supply_items: list[dict[str, Any]] = []
    if latest_auction:
        supply_items.append({
            "name": f"直近米国債入札（{latest_auction['term']}）",
            "value": latest_auction.get("bidToCover"),
            "unit": "倍",
            "status": "confirmed",
            "source": "U.S. Treasury FiscalData",
            "note": (
                f"入札日 {latest_auction.get('auctionDate') or '取得不能'} / "
                f"最高落札利回り {fmt_number(latest_auction.get('highYield'), 3) or '取得不能'}%"
            ),
        })
        if latest_auction.get("indirectPct") is not None:
            supply_items.append({
                "name": "間接入札者比率",
                "value": round(latest_auction["indirectPct"], 1),
                "unit": "%",
                "status": "calculated",
                "source": "U.S. Treasury FiscalData",
                "note": "海外需要と完全には同義ではないため、需要の一指標として扱う。",
            })
        if latest_auction.get("dealerPct") is not None:
            supply_items.append({
                "name": "プライマリーディーラー引受比率",
                "value": round(latest_auction["dealerPct"], 1),
                "unit": "%",
                "status": "calculated",
                "source": "U.S. Treasury FiscalData",
                "note": "高止まり時は最終投資家需要の弱さを示す可能性に注意。",
            })

    target_low = fred.get("DFEDTARL")
    target_high = fred.get("DFEDTARU")
    policy_rows: list[dict[str, Any]] = []
    if target_low and target_high:
        policy_rows.append({
            "policy": "FF金利目標レンジ",
            "value": f"{target_low['value']:.2f}－{target_high['value']:.2f}%",
            "change": "政策金利の現行レンジ",
            "status": "confirmed",
            "source": "FRED DFEDTARL / DFEDTARU",
            "note": "次回会合の確率ではなく、現在の公式目標レンジ。米2年債の動きと併せて市場期待を読む。",
        })
    if us2:
        policy_rows.append({
            "policy": "米2年債が示す政策期待",
            "value": f"{us2['value']:.3f}%",
            "change": f"前日比 {us2.get('changeBp', 0):+.1f}bp",
            "status": "confirmed",
            "source": "FRED DGS2",
            "note": "FedWatchの確率値ではない。短期金利期待の方向確認用。",
        })
    if jp2:
        policy_rows.append({
            "policy": "日本2年債が示す政策期待",
            "value": f"{jp2['value']:.3f}%",
            "change": f"前日比 {jp2.get('changeBp', 0):+.1f}bp" if jp2.get("changeBp") is not None else "比較データ不足",
            "status": "confirmed",
            "source": "財務省 国債金利情報",
            "note": "日銀会合の確率値ではなく、日本の短期金利期待の方向確認用。",
        })

    nikkei_change = market_change(market, "nikkei225_futures_ose")
    usdjpy_change = market_change(market, "usdjpy")
    eurusd_change = market_change(market, "eurusd")
    gold_change = market_change(market, "gold")
    btc_change = market_change(market, "btcusd")

    stock_status, stock_note = cross_asset_note(us10_dir, nikkei_change, "日経225先物", "米10年金利")
    gold_status, gold_note = cross_asset_note(real10_dir, gold_change, "金", "米10年実質金利")
    btc_status, btc_note = cross_asset_note(real10_dir, btc_change, "BTCUSD", "米10年実質金利")

    if usdjpy_change is not None:
        fx_status = f"{'上昇' if usdjpy_change > 0.05 else '下落' if usdjpy_change < -0.05 else '横ばい'}（{usdjpy_change:+.2f}%）"
        fx_note = f"米2年{us2_dir}・日本10年{jp10_dir}とUSD/JPYの反応を併せて確認。"
    else:
        fx_status, fx_note = "取得不能", "USD/JPYの同時刻データを取得できず"

    if eurusd_change is not None:
        eur_status = f"{'上昇' if eurusd_change > 0.05 else '下落' if eurusd_change < -0.05 else '横ばい'}（{eurusd_change:+.2f}%）"
        eur_note = "米10年と独10年の相対方向がEUR/USDの金利差材料。"
    else:
        eur_status, eur_note = "取得不能", "EUR/USDの同時刻データを取得できず"

    cross_asset = [
        {"market": "日経225先物", "driver": "米10年債・日本10年国債", "path": ["割引率", "円相場", "日本株バリュエーション"], "actualStatus": stock_status, "status": "confirmed" if nikkei_change is not None else "unavailable", "note": stock_note},
        {"market": "USD/JPY", "driver": "米2年債・日本2年/10年国債", "path": ["政策期待", "日米金利差", "円キャリー/実需"], "actualStatus": fx_status, "status": "confirmed" if usdjpy_change is not None else "unavailable", "note": fx_note},
        {"market": "EUR/USD", "driver": "米10年債・独10年国債", "path": ["米欧金利差", "ドル需要", "ユーロ評価"], "actualStatus": eur_status, "status": "confirmed" if eurusd_change is not None else "unavailable", "note": eur_note},
        {"market": "金", "driver": "米10年実質金利", "path": ["保有コスト", "ドル", "安全資産需要"], "actualStatus": gold_status, "status": "confirmed" if gold_change is not None else "unavailable", "note": gold_note},
        {"market": "BTCUSD", "driver": "米実質金利・流動性", "path": ["流動性期待", "リスク選好", "暗号資産フロー"], "actualStatus": btc_status, "status": "confirmed" if btc_change is not None else "unavailable", "note": btc_note},
    ]

    # Determine the leading rate from absolute daily bp movement among core yields.
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    for name, stats in (("米2年債", us2), ("米10年債", us10), ("米30年債", us30), ("日本10年国債", jp10), ("米10年実質金利", real10)):
        if stats and stats.get("changeBp") is not None:
            candidates.append((abs(stats["changeBp"]), name, stats))
    candidates.sort(reverse=True, key=lambda item: item[0])
    if candidates:
        _, leading_name, leading_stats = candidates[0]
        leading = {
            "name": leading_name,
            "status": "calculated",
            "reason": f"主要金利の中で前日比変化が最大（{leading_stats['changeBp']:+.1f}bp）。",
            "changeFromPrevious": f"{direction(leading_stats['changeBp'])} {leading_stats['changeBp']:+.1f}bp",
            "switchCondition": "別年限の変化幅が上回る、または株・為替・商品への波及が別の金利に連動し始めた場合。",
        }
    else:
        leading = {"name": "取得不能", "status": "unavailable", "reason": "比較可能な主要金利が不足", "changeFromPrevious": "未判定", "switchCondition": "データ取得後に再判定"}

    if us10 and us2:
        headline = f"米2年 {us2['value']:.3f}%（{us2.get('changeBp', 0):+.1f}bp）、米10年 {us10['value']:.3f}%（{us10.get('changeBp', 0):+.1f}bp）"
        theme = f"短期金利は{us2_dir}、長期金利は{us10_dir}。{curve_summary}"
    else:
        headline = "主要金利データを一部取得"
        theme = "取得できた公式データだけで分析し、欠損値は推測しません。"

    if us10 and real10 and breakeven10:
        consistency = (
            f"米10年{us10_dir}の内訳確認：実質金利{real10_dir}、期待インフレ{direction(breakeven10.get('changeBp'))}。"
            "金・株・為替の反応がこの方向と一致するかを下段で確認。"
        )
    else:
        consistency = "材料と値動きの整合性は取得済み系列の範囲で判定。"

    cards = []
    if us10:
        cards.append({"label": "米金利", "direction": us10_dir, "status": "confirmed", "reason": f"米10年 {us10['value']:.3f}% / 前日比 {us10.get('changeBp', 0):+.1f}bp", "asOf": us10["date"].isoformat()})
    if jp10:
        cards.append({"label": "日本金利", "direction": jp10_dir, "status": "confirmed", "reason": f"日本10年 {jp10['value']:.3f}% / 前日比 {jp10.get('changeBp', 0):+.1f}bp" if jp10.get("changeBp") is not None else f"日本10年 {jp10['value']:.3f}%", "asOf": jp10["date"].isoformat()})
    if us2s10s:
        cards.append({"label": "米イールドカーブ", "direction": us2s10s.get("reading", "未判定"), "status": "calculated", "reason": f"10年－2年 {us2s10s.get('value')}bp / {us2s10s.get('shape')}", "asOf": us10["date"].isoformat() if us10 else None})
    if real10:
        cards.append({"label": "実質金利", "direction": real10_dir, "status": "confirmed", "reason": f"米10年実質 {real10['value']:.3f}% / 前日比 {real10.get('changeBp', 0):+.1f}bp", "asOf": real10["date"].isoformat()})

    missing_data = [r["name"] for r in rates if r["status"] == "unavailable"]
    status = "confirmed" if len(confirmed_rates) >= 8 else "partial" if confirmed_rates else "unavailable"

    scenario_main_body = (
        f"米2年は{us2_dir}、米10年は{us10_dir}、実質金利は{real10_dir}。"
        f"現時点では{leading.get('name')}の動きを主導シグナルとして、USD/JPY・金・日経225先物の追随を確認する。"
    )
    scenario_alt_body = (
        "雇用・物価・原油・国債入札・財政材料で長短金利の方向が入れ替わる場合、"
        "カーブ形状とドル・金・株の反応を再判定する。"
    )

    fedwatch = fetch_fedwatch(us2)
    sources = [
        {"name": "CME FedWatch", "status": fedwatch.get("status", "unavailable"), "note": "公式FedWatch API（EOD）。未設定時は確率を推定しない。"},
        {"name": "FRED / Federal Reserve", "status": "confirmed" if fred else "unavailable", "note": "米2・5・10・30年、10年実質金利、10年期待インフレ、10年タームプレミアム、FF目標レンジ"},
        {"name": "財務省 国債金利情報", "status": "confirmed" if jgb else "unavailable", "note": "JGBコンスタントマチュリティ金利。市場終値ベース、翌営業日公表。"},
        {"name": "TradingView / LSEG JGB", "status": "confirmed" if any(x.get("source", "").startswith("TradingView") for x in jgb.values()) else "standby", "note": "財務省の翌営業日公表が遅れている場合のみ、直近市場スナップショットで補完。"},
        {"name": "Deutsche Bundesbank", "status": "confirmed" if bund10 else "unavailable", "note": "ドイツ10年連邦債利回り"},
        {"name": "U.S. Treasury FiscalData", "status": "confirmed" if auctions else "unavailable", "note": "米国債入札結果。取得できた場合のみ需給欄へ表示。"},
        {"name": "WEBマーケットレポート 独立市場データ", "status": "confirmed" if market else "unavailable", "note": "USD/JPY、EUR/USD、金、BTCUSD、日経225先物との整合性判定に使用。"},
    ]

    payload = {
        "schemaVersion": "2.0.0",
        "pageId": "rates-bonds",
        "pageTitle": "金利・債券市場分析",
        "subtitle": "米・日・欧の金利、イールドカーブ、実質金利、入札需給、他市場への波及を一画面で確認",
        "generatedAt": generated,
        "meta": {
            "page": "rates-bonds",
            "asOfDate": as_of_date,
            "asOfTime": "各市場の公表時点",
            "updatedAt": generated,
            "status": status,
            "sourceStatus": "自動取得",
            "isStale": False,
            "staleReason": None,
            "missingData": missing_data,
        },
        "summary": {
            "headline": headline,
            "theme": theme,
            "conclusion": scenario_main_body,
            "consistency": consistency,
        },
        "cards": cards,
        "rates": rates,
        "decomposition": {
            "formula": "米10年債利回りを、実質金利・期待インフレ・タームプレミアムなどの動きに分けて確認",
            "point": decomposition_point,
            "status": "confirmed" if factors else "partial",
            "factors": factors,
        },
        "curve": {
            "summary": curve_summary,
            "status": "calculated" if valid_curve_rows else "unavailable",
            "rows": curve_rows,
            "usCurve": [
                {"tenor": "2年", "value": us2["value"] if us2 else None, "status": "confirmed" if us2 else "unavailable"},
                {"tenor": "5年", "value": us5["value"] if us5 else None, "status": "confirmed" if us5 else "unavailable"},
                {"tenor": "10年", "value": us10["value"] if us10 else None, "status": "confirmed" if us10 else "unavailable"},
                {"tenor": "30年", "value": us30["value"] if us30 else None, "status": "confirmed" if us30 else "unavailable"},
            ],
            "jpCurve": [
                {"tenor": "2年", "value": jp2["value"] if jp2 else None, "status": "confirmed" if jp2 else "unavailable"},
                {"tenor": "5年", "value": jp5["value"] if jp5 else None, "status": "confirmed" if jp5 else "unavailable"},
                {"tenor": "10年", "value": jp10["value"] if jp10 else None, "status": "confirmed" if jp10 else "unavailable"},
                {"tenor": "30年", "value": jp30["value"] if jp30 else None, "status": "confirmed" if jp30 else "unavailable"},
            ],
        },
        "supplyDemand": {
            "summary": "米国債入札は公式FiscalDataから取得できた場合のみ表示。ETFフローやCFTCは未取得値を推測しない。",
            "items": supply_items,
        },
        "policyExpectations": {
            "summary": "確率推定を無理に表示せず、公式政策金利と短期国債利回りから市場期待の方向を確認。",
            "rows": policy_rows,
        },
        "fedWatch": fedwatch,
        "crossAssetImpact": cross_asset,
        "leadingRate": leading,
        "scenarios": {
            "main": {"title": "メインシナリオ", "body": scenario_main_body, "status": "calculated" if candidates else "unavailable"},
            "alternative": {"title": "代替シナリオ", "body": scenario_alt_body, "status": "calculated" if candidates else "unavailable"},
            "breakConditions": [
                "米2年債と米10年債の方向が反転し、カーブ変化の主因が変わる",
                "米10年実質金利と金・BTCの連動が明確に崩れる",
                "日本10年国債が急変し、USD/JPYが米金利より日本金利主導へ移る",
                "30年債主導の急なスティープ化で財政・供給懸念が前面に出る",
            ],
            "watchPoints": [
                "米雇用・CPI/PCEなど次の重要指標",
                "米国債2年・5年・10年・30年入札",
                "米10年実質金利と期待インフレ率",
                "日本2年・10年・30年国債とUSD/JPY",
                "米独10年金利差とEUR/USD",
            ],
        },
        "sources": sources,
        "errors": errors,
    }

    return payload


def update_history(payload: dict[str, Any]) -> None:
    history = load_json(HISTORY, {"schemaVersion": "1.0.0", "snapshots": []})
    snapshots = history.get("snapshots") or []
    stamp = payload.get("meta", {}).get("asOfDate") or payload.get("generatedAt")
    snapshot = {
        "asOf": stamp,
        "generatedAt": payload.get("generatedAt"),
        "rates": {item["name"]: item.get("value") for item in payload.get("rates", []) if item.get("value") is not None},
        "fedWatch": payload.get("fedWatch"),
    }
    if not snapshots or snapshots[-1].get("asOf") != snapshot["asOf"]:
        snapshots.append(snapshot)
    else:
        snapshots[-1] = snapshot
    history["snapshots"] = snapshots[-400:]
    write_json(HISTORY, history)


def main() -> int:
    payload = build_payload()
    write_json(OUTPUT, payload)
    update_history(payload)
    print(json.dumps({
        "status": payload["meta"]["status"],
        "asOfDate": payload["meta"]["asOfDate"],
        "confirmedRates": sum(1 for item in payload["rates"] if item.get("status") == "confirmed"),
        "missing": payload["meta"]["missingData"],
        "errors": payload["errors"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
