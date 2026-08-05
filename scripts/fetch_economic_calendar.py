#!/usr/bin/env python3
"""Build the normalized economic-event calendar used by GitHub Pages.

Only normalized, selected events are committed. The provider's raw weekly
payload is deliberately not stored in the public repository.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")
MARKET_ORDER = [
    "米2年債",
    "米10年債",
    "ダウ先物",
    "ナスダック先物",
    "日経225先物",
    "USD/JPY",
    "EUR/USD",
    "金",
    "原油",
]
COUNTRY_LABELS = {
    "USD": "米国",
    "JPY": "日本",
    "EUR": "欧州",
    "CNY": "中国",
    "GBP": "英国",
    "AUD": "豪州",
    "CAD": "カナダ",
    "CHF": "スイス",
    "NZD": "ニュージーランド",
    "All": "複数",
}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iso_jst(value: dt.datetime) -> str:
    return value.astimezone(JST).isoformat(timespec="seconds")


def parse_datetime(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timezone is missing: {value}")
    return parsed


def clean(value: Any, limit: int = 200) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def fetch_weekly(url: str, timeout: int = 20, retries: int = 3) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Chat-GPT-Market-Report/1.0 (+GitHub Pages calendar updater)",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8-sig"))
            if not isinstance(payload, list):
                raise ValueError("weekly calendar response is not an array")
            return [item for item in payload if isinstance(item, dict)]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            last_error = error
            if attempt + 1 < retries:
                time.sleep(1.2 * (2**attempt))
    raise RuntimeError(f"calendar fetch failed after {retries} attempts: {last_error}")


def fetch_results(config: dict[str, Any], now: dt.datetime, timeout: int = 20) -> list[dict[str, Any]]:
    provider = config.get("resultProvider", {})
    if not provider.get("url"):
        return []
    start = (now.astimezone(dt.timezone.utc) - dt.timedelta(days=7)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    end = (now.astimezone(dt.timezone.utc) + dt.timedelta(days=8)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    query = urllib.parse.urlencode(
        {
            "from": start,
            "to": end,
            "countries": ",".join(provider.get("countries", [])),
        }
    )
    request = urllib.request.Request(
        f"{provider['url']}?{query}",
        headers={
            "Accept": "application/json",
            "Origin": "https://www.tradingview.com",
            "Referer": "https://www.tradingview.com/",
            "User-Agent": "WEB-Market-Report/1.0 (+GitHub Actions)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    rows = payload.get("result", []) if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def compile_dictionary(payload: dict[str, Any]) -> list[tuple[re.Pattern[str], dict[str, Any]]]:
    rules: list[tuple[re.Pattern[str], dict[str, Any]]] = []
    for rule in payload.get("rules", []):
        try:
            rules.append((re.compile(rule["pattern"], re.I), rule))
        except (KeyError, re.error):
            continue
    return rules


def dictionary_match(title: str, rules: list[tuple[re.Pattern[str], dict[str, Any]]]) -> dict[str, Any]:
    for pattern, rule in rules:
        if pattern.search(title):
            return rule
    return {}


def category_for(title: str, rule: dict[str, Any]) -> str:
    if rule.get("category"):
        return str(rule["category"])
    patterns = [
        (r"Interest Rate|Monetary Policy|FOMC|Central Bank", "central_bank"),
        (r"Employment|Unemployment|Job|Earnings|Labor", "employment"),
        (r"CPI|PPI|PCE|Inflation|Price", "inflation"),
        (r"GDP|PMI|Production|Retail Sales|Confidence|Orders", "growth"),
        (r"Trade Balance|Current Account|Export|Import", "trade"),
        (r"Oil|Gas|OPEC|Petroleum", "energy"),
        (r"Bond Auction|Bill Auction|Note Auction", "bond_auction"),
        (r"Speaks|Speech|Testifies", "speech"),
        (r"Holiday", "holiday"),
    ]
    for pattern, category in patterns:
        if re.search(pattern, title, re.I):
            return category
    return "other"


def source_importance(impact: str) -> int:
    return {"High": 3, "Medium": 2, "Low": 1, "Holiday": 0}.get(impact, 0)


def market_importance(impact: str, rule: dict[str, Any], title: str) -> int:
    importance = source_importance(impact)
    if rule.get("importance") is not None:
        importance = max(importance, int(rule["importance"]))
    if re.search(r"Interest Rate Decision|FOMC Statement|Fed Chair|BOJ Gov|Non-Farm Employment|CPI|PCE|GDP", title, re.I):
        importance = max(importance, 3)
    return max(0, min(3, importance))


def should_include(raw: dict[str, Any], config: dict[str, Any]) -> bool:
    country = clean(raw.get("country"), 8)
    impact = clean(raw.get("impact"), 16)
    title = clean(raw.get("title"), 160)
    if country not in set(config.get("currencies", [])):
        return False
    if impact in set(config.get("includedImpacts", [])):
        return True
    if impact == "Low" and re.search(r"Trade Balance", title, re.I):
        return country == "CNY"
    return any(re.search(pattern, title, re.I) for pattern in config.get("curatedLowImpactPatterns", []))


def stable_id(source_date: str, currency: str, title: str) -> str:
    key = f"{source_date}|{currency}|{title.lower()}"
    return "event-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:14]


def official_source_id(category: str, currency: str, rule: dict[str, Any], title: str) -> str:
    if rule.get("officialSourceId"):
        return str(rule["officialSourceId"])
    if category == "central_bank":
        return {"USD": "federal_reserve", "JPY": "boj", "EUR": "ecb"}.get(currency, "forex_factory")
    if category in {"employment", "inflation"} and currency == "USD":
        return "bls" if not re.search(r"PCE", title, re.I) else "bea"
    if category == "growth" and currency == "USD" and re.search(r"GDP", title, re.I):
        return "bea"
    if category == "energy" and re.search(r"Crude Oil|Petroleum", title, re.I):
        return "eia"
    if category == "bond_auction":
        return "japan_mof" if currency == "JPY" else "us_treasury" if currency == "USD" else "forex_factory"
    if re.search(r"OPEC", title, re.I):
        return "opec"
    return "forex_factory"


def localized_title(original: str, currency: str, rule: dict[str, Any]) -> str:
    name = clean(rule.get("nameJa"), 100)
    if not name:
        return original
    if name == "国債入札":
        auction = re.sub(r"\s*Bond Auction\s*$", " 国債入札", original, flags=re.I)
        return f"{COUNTRY_LABELS.get(currency, currency)} {auction}"
    if name in {"失業率", "消費者物価指数（CPI）", "生産者物価指数（PPI）", "製造業PMI", "サービス業PMI", "政策金利発表", "貿易収支", "小売売上高", "鉱工業生産"}:
        return f"{COUNTRY_LABELS.get(currency, currency)} {name}"
    if name == "FOMCメンバー発言":
        speaker = re.sub(r"^FOMC Member\s+|\s+Speaks$", "", original, flags=re.I)
        return f"FOMCメンバー {speaker} 発言" if speaker else name
    return name


def affected_markets(category: str, currency: str) -> list[str]:
    if category == "energy":
        return ["原油", "米10年債", "ダウ先物", "USD/JPY", "金"]
    if category == "bond_auction":
        return (["日本金利", "USD/JPY", "日経225先物"] if currency == "JPY" else ["米2年債", "米10年債", "USD/JPY", "ダウ先物", "ナスダック先物", "金"])
    if currency == "JPY" or category == "central_bank" and currency == "JPY":
        return ["USD/JPY", "日本金利", "日経225先物", "米10年債", "金"]
    if currency == "EUR":
        return ["EUR/USD", "欧州金利", "米10年債", "金", "株価指数先物"]
    if currency == "CNY":
        return ["日経225先物", "原油", "金", "USD/JPY", "豪ドル"]
    return ["米2年債", "米10年債", "USD/JPY", "ダウ先物", "ナスダック先物", "日経225先物", "金"]


def parse_number(value: str) -> float | None:
    text = clean(value, 48).replace(",", "")
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([KMBT%]?)", text, re.I)
    if not match:
        return None
    number = float(match.group(1))
    multiplier = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}.get(match.group(2).upper(), 1.0)
    return number * multiplier


def normalized_match_title(value: Any) -> str:
    text = clean(value, 180).lower()
    text = re.sub(r"\b(?:prelim|final|revised|flash|s\.a\.|n\.s\.a\.)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def result_value(row: dict[str, Any], key: str, hint: str = "") -> str:
    value = row.get(f"{key}Raw", row.get(key))
    if value in (None, ""):
        return ""
    hint_match = re.search(r"([KMBT])\s*$", clean(hint, 48), re.I)
    if hint_match and isinstance(value, (int, float)):
        suffix = hint_match.group(1).upper()
        divisor = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[suffix]
        scaled = float(value) / divisor
        formatted = f"{scaled:.3f}".rstrip("0").rstrip(".")
        return f"{formatted}{suffix}"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    unit = clean(row.get("unit"), 12)
    return f"{value}{unit}" if unit and unit not in {"Index", "Points", "Units"} else str(value)


def result_country(currency: str) -> str:
    return {
        "USD": "US",
        "JPY": "JP",
        "EUR": "EU",
        "CNY": "CN",
        "GBP": "GB",
        "AUD": "AU",
        "CAD": "CA",
        "CHF": "CH",
        "NZD": "NZ",
    }.get(currency, "")


def match_result(event: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    target_country = result_country(str(event.get("currency", "")))
    target_title = normalized_match_title(event.get("eventNameOriginal") or event.get("title"))
    try:
        target_time = parse_datetime(str(event.get("datetimeJst", ""))).astimezone(dt.timezone.utc)
    except ValueError:
        return None
    best: tuple[float, dict[str, Any]] | None = None
    for row in rows:
        if target_country and clean(row.get("country"), 8) != target_country:
            continue
        try:
            row_time = parse_datetime(str(row.get("date", ""))).astimezone(dt.timezone.utc)
        except ValueError:
            continue
        time_distance = abs((row_time - target_time).total_seconds())
        if time_distance > 45 * 60:
            continue
        row_title = normalized_match_title(row.get("title") or row.get("indicator"))
        similarity = SequenceMatcher(None, target_title, row_title).ratio()
        target_tokens = set(target_title.split())
        row_tokens = set(row_title.split())
        overlap = len(target_tokens & row_tokens) / max(1, len(target_tokens | row_tokens))
        score = max(similarity, overlap) - time_distance / (45 * 60) * 0.08
        if score >= 0.48 and (best is None or score > best[0]):
            best = (score, row)
    return best[1] if best else None


def enrich_results(events: list[dict[str, Any]], rows: list[dict[str, Any]], now: dt.datetime) -> int:
    saved = 0
    for event in events:
        row = match_result(event, rows)
        if not row:
            continue
        actual = result_value(row, "actual", str(event.get("forecast") or event.get("previous") or ""))
        if not actual:
            continue
        forecast = event.get("forecast") or result_value(row, "forecast")
        previous = event.get("previous") or result_value(row, "previous")
        comparison = result_comparison(actual, str(forecast or ""))
        event.update(
            {
                "actual": actual,
                "forecast": forecast,
                "previous": previous,
                "resultComparison": comparison,
                "resultExplanation": f"実績 {actual} は予想 {forecast or 'なし'} に対して{comparison or '比較保留'}。発表後の市場反応は検証済み価格データで確認します。",
                "status": "released",
                "resultSource": {
                    "id": "tradingview_economic_calendar",
                    "name": clean(row.get("source"), 100) or "TradingView Economic Calendar",
                    "url": clean(row.get("source_url"), 300) or "https://www.tradingview.com/economic-calendar/",
                },
                "resultSavedAt": iso_jst(now),
                "updatedAt": iso_jst(now),
            }
        )
        event["conclusion"] = {
            **event.get("conclusion", {}),
            "narrative": "結果確認済み",
            "reaction": comparison or "市場反応を確認",
        }
        saved += 1
    return saved


def result_comparison(actual: str, forecast: str) -> str:
    actual_value = parse_number(actual)
    forecast_value = parse_number(forecast)
    if actual_value is None or forecast_value is None:
        return ""
    tolerance = max(abs(forecast_value) * 0.0001, 1e-9)
    if actual_value > forecast_value + tolerance:
        return "市場予想を上回る"
    if actual_value < forecast_value - tolerance:
        return "市場予想を下回る"
    return "市場予想と一致"


def scenario_rows(category: str, currency: str) -> list[list[str]]:
    rows = {
        "米2年債": ["上昇しやすい", "小動き", "低下しやすい"],
        "米10年債": ["上昇しやすい", "小動き", "低下しやすい"],
        "ダウ先物": ["金利上昇なら重い", "小動き", "金利低下なら支え"],
        "ナスダック先物": ["高金利なら重い", "小動き", "金利低下なら支え"],
        "日経225先物": ["米株安・円高なら重い", "小動き", "米株高・円安なら支え"],
        "USD/JPY": ["ドル高で上昇しやすい", "小動き", "ドル安で下落しやすい"],
        "EUR/USD": ["ドル高で下落しやすい", "小動き", "ドル安で上昇しやすい"],
        "金": ["実質金利上昇なら重い", "小動き", "実質金利低下なら支え"],
        "原油": ["景気上振れなら支え", "小動き", "景気減速なら重い"],
    }
    if currency == "JPY":
        rows["USD/JPY"] = ["円高で下落しやすい", "小動き", "円安で上昇しやすい"]
        rows["日経225先物"] = ["円高なら重い", "小動き", "円安なら支え"]
    elif currency == "EUR":
        rows["EUR/USD"] = ["ユーロ高になりやすい", "小動き", "ユーロ安になりやすい"]
    elif currency == "CNY":
        rows["日経225先物"] = ["中国需要期待で支え", "小動き", "中国減速懸念で重い"]
        rows["原油"] = ["需要期待で上昇しやすい", "小動き", "需要懸念で下落しやすい"]
    if category == "energy":
        rows["原油"] = ["在庫減・供給不安なら上昇", "予想通りなら限定的", "在庫増・供給懸念後退なら下落"]
        rows["米2年債"] = ["反応は限定的", "小動き", "反応は限定的"]
    return [[market, *rows[market]] for market in MARKET_ORDER]


def outlook_rows(category: str, currency: str) -> list[list[str]]:
    base = {
        "米2年債": ["政策金利見通しに反応", "初動と翌営業日の持続性を確認", "利下げ期待後退", "利下げ期待拡大"],
        "米10年債": ["成長・インフレ・国債需給に反応", "2年債との方向差を確認", "インフレ再燃・需給悪化", "成長鈍化・利下げ期待"],
        "ダウ先物": ["景気敏感株の反応を確認", "金利と業績期待の綱引きを確認", "景気悪化・金利上昇", "景気底堅さ・金利低下"],
        "ナスダック先物": ["高PER株の金利感応度を確認", "実質金利への耐性を見る", "実質金利上昇", "金利低下・買い戻し"],
        "日経225先物": ["米株と円相場に反応", "USD/JPYとの組み合わせを見る", "米株安・円高", "米株高・円安"],
        "USD/JPY": ["米金利差とドルに反応", "米2年・10年債との連動を確認", "米金利上昇・ドル高", "米金利低下・ドル安"],
        "EUR/USD": ["ドルと欧州固有材料に反応", "ドル全面高かを確認", "米金利上昇・ドル高", "米金利低下・ドル安"],
        "金": ["実質金利とドルに反応", "安全資産需要との整合性を確認", "実質金利上昇・ドル高", "実質金利低下・ドル安"],
        "原油": ["需要見通しと供給材料に反応", "景気と在庫のどちらが主導か確認", "需要上振れ・供給不安", "需要鈍化・供給懸念後退"],
    }
    if category == "holiday":
        for market in base:
            base[market] = ["流動性低下に注意", "スプレッド拡大と値飛びを確認", "薄商いの急変", "通常取引再開"]
    return [[market, *base[market]] for market in MARKET_ORDER]


def build_event(raw: dict[str, Any], config: dict[str, Any], rules: list[tuple[re.Pattern[str], dict[str, Any]]], now: dt.datetime) -> dict[str, Any]:
    original = clean(raw.get("title"), 160)
    currency = clean(raw.get("country"), 8)
    source_time = parse_datetime(clean(raw.get("date"), 48))
    scheduled = source_time.astimezone(JST)
    rule = dictionary_match(original, rules)
    category = category_for(original, rule)
    impact = clean(raw.get("impact"), 16)
    importance = market_importance(impact, rule, original)
    title = localized_title(original, currency, rule)
    actual = clean(raw.get("actual"), 48)
    forecast = clean(raw.get("forecast"), 48)
    previous = clean(raw.get("previous"), 48)
    comparison = result_comparison(actual, forecast)
    official_id = official_source_id(category, currency, rule, original)
    official = config.get("officialSources", {}).get(official_id, config.get("officialSources", {}).get("forex_factory", {}))
    source_key = f"{scheduled.date().isoformat()}|{scheduled:%H:%M}|{currency}|{original.lower()}"
    released = bool(actual)
    past = scheduled <= now
    status = "released" if released else "result_pending" if past and category != "holiday" else "scheduled"
    explanation = (
        f"実績 {actual} は予想 {forecast or 'なし'} に対して{comparison or '比較保留'}。"
        if released
        else "実績値の更新を確認中。公式発表元と取得元の更新後に自動反映します。"
        if past and category != "holiday"
        else "発表後に実績値と市場反応を更新します。"
    )
    return {
        "id": stable_id(clean(raw.get("date"), 48), currency, original),
        "sourceKey": source_key,
        "date": scheduled.date().isoformat(),
        "time": scheduled.strftime("%H:%M"),
        "datetimeJst": iso_jst(scheduled),
        "scheduledAtSource": source_time.isoformat(timespec="seconds"),
        "scheduledAtUtc": source_time.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "country": COUNTRY_LABELS.get(currency, currency),
        "currency": currency,
        "title": title,
        "eventNameOriginal": original,
        "category": category,
        "impactOriginal": impact,
        "ffImportance": source_importance(impact),
        "importance": importance,
        "importanceLabel": {0: "休場", 1: "低", 2: "中", 3: "高"}[importance],
        "forecast": forecast,
        "previous": previous,
        "actual": actual,
        "revised": clean(raw.get("revised"), 48),
        "resultComparison": comparison,
        "resultExplanation": explanation,
        "status": status,
        "isTimed": True,
        "isImportantEvent": importance >= 2 or category in {"holiday", "bond_auction", "speech", "energy"},
        "affectedMarkets": affected_markets(category, currency),
        "focusMarkets": affected_markets(category, currency)[:5],
        "pricedIn": [
            f"市場予想：{forecast or '予想なし'}",
            f"前回値：{previous or '前回値なし'}",
            "発表直後は米2年債、米10年債、株価指数先物、為替の順に確認",
        ],
        "scenarios": scenario_rows(category, currency),
        "outlook": outlook_rows(category, currency),
        "postReleaseReactions": [],
        "comparison": [[market, "データ次第", "未計測", "確認中"] for market in MARKET_ORDER],
        "conclusion": {
            "narrative": "結果確認済み" if released else "発表前" if not past else "結果確認中",
            "reaction": comparison or ("市場反応を確認" if released else "結果待ち"),
            "watch": ["米2年債の初動", "米10年債への波及", "ダウ・ナスダック先物", "USD/JPYとEUR/USD", "日経225先物・金・原油"],
        },
        "officialSource": {"id": official_id, "name": official.get("name", ""), "url": official.get("url", "")},
        "sourceType": "forex_factory_weekly",
        "sourceUrl": config["provider"]["url"],
        "sourceNote": "週間カレンダーをJST変換し、WEBマーケットレポート独自の重要度と市場対応を付与",
        "createdAt": iso_jst(now),
        "updatedAt": iso_jst(now),
    }


PRESERVED_FIELDS = {
    "actual",
    "revised",
    "resultComparison",
    "resultExplanation",
    "postReleaseReactions",
    "comparison",
    "conclusion",
    "resultSource",
    "resultSavedAt",
    "resultUpdatedAt",
}


def merge_preserved(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    keep_previous_result = not current.get("actual") and bool(previous.get("actual"))
    for field in PRESERVED_FIELDS:
        value = previous.get(field)
        if keep_previous_result or field not in merged or merged.get(field) in (None, "", [], {}):
            if value not in (None, "", [], {}):
                merged[field] = value
    merged["createdAt"] = previous.get("createdAt") or current.get("createdAt")
    if merged.get("actual"):
        merged["status"] = "released"
    return merged


def event_sort_key(event: dict[str, Any]) -> tuple[str, str, str]:
    return (str(event.get("date", "")), str(event.get("time", "")), str(event.get("title", "")))


def previous_events(root: Path) -> list[dict[str, Any]]:
    latest = load_json(root / "data/events/latest.json", {})
    if latest.get("events"):
        return [item for item in latest["events"] if isinstance(item, dict)]
    legacy = load_json(root / "data/events.json", {})
    return [item for item in legacy.get("events", []) if isinstance(item, dict)]


def build_payload(
    root: Path,
    config: dict[str, Any],
    raw_rows: list[dict[str, Any]],
    now: dt.datetime,
    result_rows: list[dict[str, Any]] | None = None,
    result_error: str = "",
) -> dict[str, Any]:
    dictionary = load_json(root / "data/events/event_dictionary.json", {})
    rules = compile_dictionary(dictionary)
    previous = previous_events(root)
    previous_by_key = {str(item.get("sourceKey") or item.get("id")): item for item in previous}
    current: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not should_include(raw, config):
            continue
        event = build_event(raw, config, rules, now)
        old = previous_by_key.get(event["sourceKey"]) or previous_by_key.get(event["id"])
        current.append(merge_preserved(event, old) if old else event)
    result_count = enrich_results(current, result_rows or [], now)

    retention_cutoff = (now.date() - dt.timedelta(days=int(config.get("retentionDays", 365)))).isoformat()
    current_keys = {item["sourceKey"] for item in current}
    retained: list[dict[str, Any]] = []
    for item in previous:
        if str(item.get("date", "")) < retention_cutoff:
            continue
        if item.get("category") == "monitoring_headline":
            continue
        key = str(item.get("sourceKey") or item.get("id"))
        if key in current_keys or not item.get("time"):
            continue
        item_date = str(item.get("date", ""))
        has_saved_result = any(item.get(field) not in (None, "", [], {}) for field in PRESERVED_FIELDS)
        if item_date >= now.date().isoformat() and not has_saved_result:
            continue
        retained.append(item)

    events = sorted(current + retained, key=event_sort_key, reverse=True)[: int(config.get("maxEvents", 2500))]
    day_rows: list[dict[str, Any]] = []
    for date in sorted({str(item.get("date")) for item in events if item.get("date")}, reverse=True):
        rows = [item for item in events if item.get("date") == date]
        day_rows.append(
            {
                "date": date,
                "eventCount": len(rows),
                "releasedCount": sum(item.get("status") == "released" for item in rows),
                "resultPendingCount": sum(item.get("status") == "result_pending" for item in rows),
            }
        )

    generated_at = iso_jst(now)
    return {
        "schemaVersion": "2.0.0",
        "pageId": "events",
        "generatedAt": generated_at,
        "publishedAt": generated_at,
        "dataAsOf": generated_at,
        "timezone": "Asia/Tokyo",
        "status": "ok",
        "isStale": False,
        "mode": "normalized_calendar_history",
        "retention": {"days": int(config.get("retentionDays", 365)), "preserveResultFields": True, "rawProviderDataStored": False},
        "days": day_rows,
        "events": events,
        "sources": [
            {
                "id": config["provider"]["id"],
                "name": config["provider"]["name"],
                "url": config["provider"]["calendarUrl"],
                "status": "ok",
                "note": "時刻・通貨・重要度・予想・前回値を取得。元JSONは公開保存しません。",
            },
            {
                "id": config.get("resultProvider", {}).get("id", "result_provider"),
                "name": config.get("resultProvider", {}).get("name", "実績値補完"),
                "url": config.get("resultProvider", {}).get("calendarUrl", ""),
                "status": "warning" if result_error else "ok",
                "note": f"実績値を{result_count}件照合。生データは公開保存しません。" if not result_error else f"実績値の取得に失敗。前回保存値を維持: {result_error}",
            },
            {"id": "official_source_map", "name": "主要イベント公式照合先", "status": "available"},
        ],
        "errors": [result_error] if result_error else [],
    }


def stale_payload(root: Path, error: Exception, now: dt.datetime) -> dict[str, Any]:
    previous = load_json(root / "data/events/latest.json", {})
    if not previous.get("events"):
        previous = load_json(root / "data/events.json", {})
    if not previous.get("events"):
        raise error
    payload = dict(previous)
    payload["generatedAt"] = iso_jst(now)
    payload["status"] = "stale"
    payload["isStale"] = True
    payload["errors"] = [{"code": "SOURCE_FETCH_FAILED", "message": clean(error, 300), "at": iso_jst(now)}]
    return payload


def write_outputs(root: Path, payload: dict[str, Any], config: dict[str, Any], now: dt.datetime, write_history: bool = True) -> None:
    events = payload.get("events", [])
    upcoming_end = now + dt.timedelta(days=int(config.get("upcomingDays", 7)))

    def event_time(item: dict[str, Any]) -> dt.datetime | None:
        try:
            return parse_datetime(str(item.get("datetimeJst", "")))
        except (ValueError, TypeError):
            return None

    upcoming = [item for item in events if (stamp := event_time(item)) and now <= stamp <= upcoming_end]
    completed = [item for item in events if item.get("status") == "released"]
    base_meta = {key: payload.get(key) for key in ("schemaVersion", "pageId", "generatedAt", "dataAsOf", "timezone", "status", "isStale", "sources", "errors")}
    write_json(root / "data/events/latest.json", payload)
    write_json(root / "data/events/upcoming.json", {**base_meta, "rangeDays": int(config.get("upcomingDays", 7)), "events": sorted(upcoming, key=event_sort_key)})
    write_json(root / "data/events/completed.json", {**base_meta, "events": completed})
    write_json(root / "data/events.json", payload)
    write_json(
        root / "economic-calendar.json",
        {
            "schemaVersion": "2.0.0",
            "status": payload.get("status"),
            "updatedAt": payload.get("generatedAt"),
            "timezone": "Asia/Tokyo",
            "provider": config["provider"]["id"],
            "range": {"days": int(config.get("upcomingDays", 7))},
            "events": sorted(upcoming, key=event_sort_key),
            "errors": payload.get("errors", []),
        },
    )
    if write_history:
        by_date: dict[str, list[dict[str, Any]]] = {}
        for item in events:
            if item.get("date"):
                by_date.setdefault(str(item["date"]), []).append(item)
        for date, rows in by_date.items():
            if date >= (now.date() - dt.timedelta(days=int(config.get("retentionDays", 365)))).isoformat():
                write_json(root / f"data/events/history/{date}.json", {**base_meta, "date": date, "events": sorted(rows, key=event_sort_key)})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--config", type=Path)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--now", help="ISO 8601 test time")
    parser.add_argument("--no-history", action="store_true")
    parser.add_argument("--print-summary", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    config_path = args.config or root / "config/economic_calendar.json"
    config = load_json(config_path, {})
    if not config.get("provider", {}).get("url"):
        raise SystemExit("economic calendar provider is not configured")
    now = parse_datetime(args.now).astimezone(JST) if args.now else dt.datetime.now(JST)
    try:
        raw = load_json(args.fixture, []) if args.fixture else fetch_weekly(config["provider"]["url"])
        result_rows: list[dict[str, Any]] = []
        result_error = ""
        if not args.fixture:
            try:
                result_rows = fetch_results(config, now)
            except Exception as error:
                result_error = clean(error, 300)
        payload = build_payload(root, config, raw, now, result_rows, result_error)
    except Exception as error:  # Keep the last valid calendar instead of publishing an empty one.
        payload = stale_payload(root, error, now)
    write_outputs(root, payload, config, now, write_history=not args.no_history)
    if args.print_summary:
        print(
            json.dumps(
                {
                    "generatedAt": payload.get("generatedAt"),
                    "status": payload.get("status"),
                    "events": len(payload.get("events", [])),
                    "upcoming": len(load_json(root / "data/events/upcoming.json", {}).get("events", [])),
                    "resultsSaved": sum(item.get("status") == "released" for item in payload.get("events", [])),
                    "rawProviderDataStored": False,
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
