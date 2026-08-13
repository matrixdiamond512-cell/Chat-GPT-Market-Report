#!/usr/bin/env python3
"""Build the report-time ChatGPT market input from the published report contract.

For the 08:00 report, the user-facing contract is exactly 28 rows / 5 columns.
This script converts that structured table into the same market-data schema used by
ChatGPT_Market_Input, without relabeling late quotes as 08:00 values.  Rows whose
published value is explicitly unavailable remain unavailable with the reason intact.

For intraday slots, the independently acquired data/market/latest.json remains the
input source when its reportSlot matches the published report slot.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST_REPORT = ROOT / "data" / "latest-report.json"
RAW_MARKET = ROOT / "data" / "market" / "latest.json"
OUT = ROOT / "data" / "market" / "chatgpt-input.json"
JST = dt.timezone(dt.timedelta(hours=9))

ITEMS: list[tuple[str, str, str, str, str]] = [
    ("NYダウ", "dow", "pt", "index", "daily"),
    ("NASDAQ総合", "nasdaq", "pt", "index", "daily"),
    ("S&P500", "sp500", "pt", "index", "daily"),
    ("Russell 2000", "russell2000", "pt", "index", "daily"),
    ("日経225現物", "nikkei225_cash", "円", "index", "daily"),
    ("CME日経225先物・円建て", "nikkei225_futures_cme_yen", "円", "futures_cme", "overnight"),
    ("CME日経225先物・ドル建て", "nikkei225_futures_cme_usd", "円", "futures_cme", "overnight"),
    ("日経225先物（大阪取引所）", "nikkei225_futures_ose", "円", "futures_ose", "day_through"),
    ("USD/JPY", "usdjpy", "円", "spot", "continuous"),
    ("EUR/USD", "eurusd", "USD", "spot", "continuous"),
    ("COMEX金先物", "gold", "USD/oz", "continuous_futures", "global"),
    ("WTI原油", "wti", "USD/bbl", "continuous_futures", "global"),
    ("BTCUSD", "btcusd", "USD", "spot_crypto", "continuous"),
    ("VIX", "vix", "pt", "index", "daily"),
    ("日経VI", "nikkei_vi", "pt", "index", "daily"),
    ("Fear & Greed Index", "fear_greed", "score", "sentiment", "daily"),
    ("米10年債利回り", "us10y", "%", "yield", "daily"),
    ("日本10年国債利回り", "jp10y", "%", "yield", "daily"),
    ("日経225予想PER", "nikkei225_per", "倍", "valuation", "daily"),
    ("日経225 PBR", "nikkei225_pbr", "倍", "valuation", "daily"),
    ("日経225予想EPS", "nikkei225_eps", "円", "valuation", "daily"),
    ("日経225 25日移動平均乖離率", "nikkei225_dev25", "%", "technical", "daily"),
    ("日経225 200日移動平均乖離率", "nikkei225_dev200", "%", "technical", "daily"),
    ("東証プライム売買代金", "tse_prime_turnover", "兆円", "breadth", "daily"),
    ("東証プライム売買高", "tse_prime_volume", "百万株", "breadth", "daily"),
    ("東証プライム値上がり銘柄数", "tse_prime_advancers", "銘柄", "breadth", "daily"),
    ("東証プライム値下がり銘柄数", "tse_prime_decliners", "銘柄", "breadth", "daily"),
    ("東証プライム25日騰落レシオ", "tse_prime_ad_ratio25", "%", "breadth", "daily"),
]

UNAVAILABLE_RE = re.compile(r"取得不能|未公表|未取得|取得継続")
NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def numeric(text: Any) -> float | None:
    m = NUM_RE.search(str(text or ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def report_object(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("latestReport") or payload.get("report") or payload
    return value if isinstance(value, dict) else {}


def publication_asof(report: dict[str, Any]) -> str:
    date = str(report.get("date") or "")
    slot = str(report.get("time") or "")
    return f"{date}T{slot}:00+09:00" if date and slot else ""


def source_document(report: dict[str, Any]) -> tuple[str, str]:
    source = report.get("sourceDocument") or {}
    if not isinstance(source, dict):
        return "構造化マーケットレポート", ""
    return str(source.get("name") or "構造化マーケットレポート"), str(source.get("url") or "")


def row_market(
    report: dict[str, Any],
    row: dict[str, Any],
    *,
    symbol_id: str,
    label: str,
    unit: str,
    market_type: str,
    session: str,
) -> dict[str, Any]:
    value_text = str(row.get("value") or "").strip()
    change_text = str(row.get("change") or "—").strip() or "—"
    rate_text = str(row.get("rate") or row.get("changePercent") or "—").strip() or "—"
    direction = str(row.get("direction") or "—").strip() or "—"
    unavailable = bool(UNAVAILABLE_RE.search(value_text))
    source_name, source_url = source_document(report)
    as_of = publication_asof(report)
    value = None if unavailable else numeric(value_text)
    change = None if unavailable else numeric(change_text)
    rate = None if unavailable else numeric(rate_text)
    reason = value_text if unavailable else ""
    return {
        "id": symbol_id,
        "displayName": label,
        "value": value,
        "displayValue": value_text,
        "previousClose": None,
        "change": change,
        "changePercent": rate,
        "changeText": f"{change_text} / {rate_text}" if change_text != "—" or rate_text != "—" else "—",
        "unit": unit,
        "marketType": market_type,
        "session": session,
        "asOf": as_of,
        "fetchedAt": dt.datetime.now(JST).replace(microsecond=0).isoformat(),
        "sourceId": "published_report_market_table",
        "sourceName": source_name,
        "sourceUrl": source_url,
        "rawReference": f"marketDataTable:{label}",
        "classification": direction,
        "verificationStatus": "unavailable" if unavailable else "verified",
        "freshnessStatus": "report_time",
        "fallbackUsed": False,
        "lastVerifiedAt": as_of if not unavailable else "",
        "error": reason or None,
        "note": "08:00公開時点の構造化28項目表。後刻取得値で遡及上書きしない。",
    }


def build_morning(report: dict[str, Any]) -> dict[str, Any]:
    table = report.get("marketDataTable") or {}
    rows = table.get("rows") if isinstance(table, dict) else None
    if not isinstance(rows, list) or len(rows) != 28:
        raise SystemExit(f"08:00 report requires 28 structured rows; got {len(rows) if isinstance(rows, list) else 'invalid'}")
    by_label = {str(row.get("label") or "").strip(): row for row in rows if isinstance(row, dict)}
    expected = [item[0] for item in ITEMS]
    if list(by_label) != expected:
        missing = [label for label in expected if label not in by_label]
        extra = [label for label in by_label if label not in expected]
        if missing or extra:
            raise SystemExit(f"08:00 market labels mismatch. missing={missing}, extra={extra}")

    markets: dict[str, Any] = {}
    unavailable: list[str] = []
    for label, symbol_id, unit, market_type, session in ITEMS:
        market = row_market(report, by_label[label], symbol_id=symbol_id, label=label, unit=unit, market_type=market_type, session=session)
        markets[symbol_id] = market
        if market["verificationStatus"] != "verified":
            unavailable.append(label)

    required_six = {"gold", "wti", "nikkei225_futures_ose", "usdjpy", "eurusd", "btcusd"}
    missing_required = [markets[key]["displayName"] for key in required_six if markets[key]["verificationStatus"] != "verified"]
    return {
        "schemaVersion": "2.0.0",
        "pageId": "chatgpt-report-input",
        "generatedAt": dt.datetime.now(JST).replace(microsecond=0).isoformat(),
        "reportDate": report.get("date"),
        "reportSlot": report.get("time"),
        "reportTitle": report.get("title"),
        "overallStatus": "verified" if not unavailable else "degraded",
        "dataComplete": not unavailable,
        "availableCount": 28 - len(unavailable),
        "expectedCount": 28,
        "unavailableLabels": unavailable,
        "missingRequired": missing_required,
        "markets": markets,
        "contract": {
            "rowCount": 28,
            "source": "data/latest-report.json marketDataTable",
            "lateBackfillAllowed": False,
        },
    }


def main() -> int:
    report = report_object(load_json(LATEST_REPORT, {}))
    if not report:
        raise SystemExit("data/latest-report.json has no report")
    slot = str(report.get("time") or "")
    if slot == "08:00":
        payload = build_morning(report)
    else:
        raw = load_json(RAW_MARKET, {})
        if str(raw.get("reportSlot") or "") != slot:
            print(f"ChatGPT report input unchanged: raw market slot {raw.get('reportSlot')} != report slot {slot}")
            return 0
        payload = dict(raw)
        payload["pageId"] = "chatgpt-report-input"
        payload["reportDate"] = report.get("date")
        payload["reportTitle"] = report.get("title")
    dump_json(OUT, payload)
    print(json.dumps({
        "reportDate": payload.get("reportDate"),
        "reportSlot": payload.get("reportSlot"),
        "marketCount": len(payload.get("markets") or {}),
        "dataComplete": payload.get("dataComplete"),
        "unavailableLabels": payload.get("unavailableLabels") or [],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
