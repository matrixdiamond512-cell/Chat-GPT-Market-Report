#!/usr/bin/env python3
"""Reconcile verified intraday market data into an incomplete latest report.

The market-data workflows can finish a staged retry after the report body was
created. When that happens, the verified snapshot is authoritative for rows
that still say "取得不能", while existing report values are intentionally
preserved to avoid rewriting a valid report with a later quote.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LATEST_REPORT = ROOT / "data" / "latest-report.json"
MARKET_SNAPSHOT = ROOT / "data" / "market" / "latest.json"
JST = dt.timezone(dt.timedelta(hours=9))
RECONCILE_SLOTS = {"12:00", "16:00", "21:00"}

SYMBOL_ALIASES: dict[str, set[str]] = {
    "gold": {"金", "COMEX金先物", "COMEX金", "金先物"},
    "wti": {"WTI原油", "WTI", "原油"},
    "nikkei225_futures_ose": {
        "日経225先物（大阪取引所）",
        "日経225先物(大阪取引所)",
        "日経225先物・大阪取引所",
    },
    "usdjpy": {"USD/JPY", "ドル円", "USDJPY"},
    "eurusd": {"EUR/USD", "ユーロドル", "EURUSD"},
    "btcusd": {"BTCUSD", "BTC/USD", "ビットコイン"},
}

VALUE_UNAVAILABLE_MARKERS = ("取得不能", "取得不可", "確定できず", "unavailable", "not available", "n/a", "—")
DISPLAY_UNITS = {
    "gold": "ドル/oz",
    "wti": "ドル/bbl",
    "nikkei225_futures_ose": "円",
    "usdjpy": "円前後",
    "eurusd": "",
    "btcusd": "ドル",
}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_label(value: Any) -> str:
    return " ".join(str(value or "").replace("　", " ").split()).strip()


def symbol_for_label(value: Any) -> str | None:
    label = normalize_label(value)
    for symbol, aliases in SYMBOL_ALIASES.items():
        if label in aliases:
            return symbol
    return None


def parse_jst(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    return parsed.astimezone(JST)


def is_verified_market(market: Any) -> bool:
    if not isinstance(market, dict):
        return False
    if market.get("verificationStatus") != "verified":
        return False
    try:
        return float(market.get("value"))
    except (TypeError, ValueError):
        return False


def is_unavailable(value: Any) -> bool:
    text = normalize_label(value).lower()
    return not text or any(marker in text for marker in VALUE_UNAVAILABLE_MARKERS)


def format_number(value: Any, decimals: int) -> str:
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value or "").strip()


def display_number(market: dict[str, Any], symbol: str) -> str:
    display = normalize_label(market.get("displayValue"))
    if display:
        return display
    decimals = {
        "gold": 2,
        "wti": 2,
        "nikkei225_futures_ose": 0,
        "usdjpy": 2,
        "eurusd": 5,
        "btcusd": 0,
    }.get(symbol, 2)
    return format_number(market.get("value"), decimals)


def format_rate(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(number) < 0.0000001:
        return "0.00%"
    return f"{number:+.2f}%"


def format_change(market: dict[str, Any]) -> str:
    text = normalize_label(market.get("changeText"))
    if text:
        return text
    try:
        change = float(market.get("change"))
    except (TypeError, ValueError):
        return "—"
    return f"{change:+,.2f}"


def formatted_value(market: dict[str, Any], symbol: str, report_time: str) -> str:
    value = display_number(market, symbol)
    unit = DISPLAY_UNITS.get(symbol, "")
    timestamp = parse_jst(market.get("asOf")) or parse_jst(market.get("fetchedAt"))
    suffix = ""
    if timestamp:
        observed = timestamp.strftime("%H:%M")
        status = "確認" if observed == report_time else "再取得"
        suffix = f"（{observed} JST{status}）"
    return f"{value}{unit}{suffix}"


def reconcile_report_market_data(
    report: dict[str, Any],
    snapshot: dict[str, Any],
) -> list[str]:
    """Fill only unavailable report fields from a matching verified snapshot."""
    report_date = normalize_label(report.get("date"))
    report_time = normalize_label(report.get("time"))
    if report_time not in RECONCILE_SLOTS:
        return []

    if normalize_label(snapshot.get("reportSlot")) != report_time:
        return []

    generated = parse_jst(snapshot.get("generatedAt"))
    if not generated or generated.date().isoformat() != report_date:
        return []

    if snapshot.get("overallStatus") not in {"verified", "degraded"}:
        return []

    markets = snapshot.get("markets")
    if not isinstance(markets, dict):
        return []

    changed: list[str] = []
    for symbol, market in markets.items():
        if symbol not in SYMBOL_ALIASES or not is_verified_market(market):
            continue

        value = formatted_value(market, symbol, report_time)
        change = format_change(market)
        rate = format_rate(market.get("changePercent"))

        table = report.get("marketDataTable")
        rows = table.get("rows") if isinstance(table, dict) else []
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if symbol_for_label(row.get("label") or row.get("item") or row.get("name")) != symbol:
                    continue
                if not is_unavailable(row.get("value")):
                    continue
                row["value"] = value
                row["change"] = change
                row["rate"] = rate
                changed.append(symbol)
                break

        report_markets = report.get("markets")
        if isinstance(report_markets, list):
            for item in report_markets:
                if not isinstance(item, dict):
                    continue
                if symbol_for_label(item.get("name")) != symbol:
                    continue
                if not is_unavailable(item.get("price")):
                    continue
                item["price"] = value
                item["change"] = change
                changed.append(symbol)
                break

    changed = sorted(set(changed))
    if changed:
        provenance = report.setdefault("dataProvenance", {})
        provenance["marketDataReconciliation"] = {
            "rule": "verified snapshot values fill only report fields still marked unavailable",
            "source": "data/market/latest.json",
            "sourceGeneratedAt": snapshot.get("generatedAt", ""),
            "reportSlot": f"{report_date} {report_time}",
            "updatedAt": dt.datetime.now(JST).replace(microsecond=0).isoformat(),
            "updatedSymbols": changed,
        }
    return changed


def update_latest_report(snapshot: dict[str, Any]) -> list[str]:
    payload = load_json(LATEST_REPORT, {})
    if not isinstance(payload, dict):
        raise SystemExit("data/latest-report.json must be a JSON object")

    source_report = payload.get("latestReport") or payload.get("report") or payload
    if not isinstance(source_report, dict):
        raise SystemExit("data/latest-report.json does not contain a report object")

    report = copy.deepcopy(source_report)
    changed = reconcile_report_market_data(report, snapshot)
    if not changed:
        return []

    if isinstance(payload.get("latestReport"), dict):
        payload["latestReport"] = report
    elif isinstance(payload.get("report"), dict):
        payload["report"] = report
    else:
        payload = report
    dump_json(LATEST_REPORT, payload)
    return changed


def main() -> None:
    snapshot = load_json(MARKET_SNAPSHOT, {})
    if not isinstance(snapshot, dict):
        raise SystemExit("data/market/latest.json must be a JSON object")
    changed = update_latest_report(snapshot)
    if changed:
        print(
            "Reconciled verified market data into latest report: "
            + ", ".join(changed)
        )
    else:
        print("No unavailable latest-report market fields matched a verified snapshot.")


if __name__ == "__main__":
    main()
