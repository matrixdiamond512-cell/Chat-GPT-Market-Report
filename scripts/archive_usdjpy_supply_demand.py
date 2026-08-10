from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "usdjpy-supply-demand.json"
MARKET_PATH = ROOT / "data" / "market" / "latest.json"
RATES_PATH = ROOT / "data" / "rates-bonds.json"
VOLUME_PATH = ROOT / "data" / "usdjpy-volume.json"
EVENTS_PATH = ROOT / "data" / "events.json"
ARCHIVE_DIR = ROOT / "data" / "usdjpy-supply-demand-archive"
INDEX_PATH = ARCHIVE_DIR / "index.json"
MAX_REPORTS = 400


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iso_date(value: Any) -> str | None:
    text = str(value or "")
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return None


def report_date(config: dict[str, Any]) -> str | None:
    return iso_date(config.get("generatedAt"))


def compact_market(payload: dict[str, Any]) -> dict[str, Any]:
    markets = payload.get("markets") or {}
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "generatedAt": payload.get("generatedAt"),
        "status": payload.get("status"),
        "markets": {
            key: markets.get(key)
            for key in ("usdjpy", "vix")
            if markets.get(key) is not None
        },
    }


def compact_rates(payload: dict[str, Any]) -> dict[str, Any]:
    wanted = {"米2年債利回り", "米10年債利回り", "日本10年国債利回り"}
    rows = [row for row in (payload.get("rates") or []) if row.get("name") in wanted]
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "pageId": payload.get("pageId"),
        "generatedAt": payload.get("generatedAt"),
        "meta": payload.get("meta") or {},
        "rates": rows,
    }


def compact_volume(payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload.get("data") or {})
    data["records"] = list(data.get("records") or [])[:40]
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "generatedAt": payload.get("generatedAt"),
        "status": payload.get("status"),
        "data": data,
    }


def compact_events(payload: dict[str, Any], date: str) -> dict[str, Any]:
    selected = []
    for event in payload.get("events") or []:
        if str(event.get("date") or "") != date:
            continue
        focus = event.get("focusMarkets") or []
        affected = event.get("affectedMarkets") or []
        if (
            "USD/JPY" in focus
            or "USD/JPY" in affected
            or event.get("currency") in {"USD", "JPY"}
        ):
            selected.append(event)
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "generatedAt": payload.get("generatedAt"),
        "dataAsOf": payload.get("dataAsOf"),
        "status": payload.get("status"),
        "events": selected,
    }


def latest_rate_date(rates: dict[str, Any], prefix: str) -> str | None:
    dates = [
        iso_date(row.get("asOf"))
        for row in rates.get("rates") or []
        if str(row.get("name") or "").startswith(prefix)
    ]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def market_date(market: dict[str, Any]) -> str | None:
    row = ((market.get("markets") or {}).get("usdjpy") or {})
    return iso_date(row.get("asOf"))


def volume_date(volume: dict[str, Any]) -> str | None:
    records = ((volume.get("data") or {}).get("records") or [])
    return iso_date(records[0].get("targetDate")) if records else None


def build_bundle(
    config: dict[str, Any],
    market: dict[str, Any],
    rates: dict[str, Any],
    volume: dict[str, Any],
    events: dict[str, Any],
) -> dict[str, Any]:
    date = report_date(config)
    if not date:
        raise RuntimeError("USD/JPY需給分析のレポート日を判定できません")
    c_market = compact_market(market)
    c_rates = compact_rates(rates)
    c_volume = compact_volume(volume)
    c_events = compact_events(events, date)
    cftc_date = iso_date((config.get("cftc") or {}).get("asOf"))
    return {
        "schemaVersion": "1.0.0",
        "pageId": "usdjpy-supply-demand-archive",
        "reportDate": date,
        "generatedAt": config.get("generatedAt"),
        "market": c_market,
        "rates": c_rates,
        "volume": c_volume,
        "events": c_events,
        "config": config,
        "meta": {
            "priceDataDate": market_date(c_market),
            "usDataDate": latest_rate_date(c_rates, "米"),
            "japanDataDate": latest_rate_date(c_rates, "日本"),
            "tokyoDataDate": volume_date(c_volume),
            "cftcDate": cftc_date,
        },
    }


def make_entry(bundle: dict[str, Any]) -> dict[str, Any]:
    date = bundle["reportDate"]
    meta = bundle.get("meta") or {}
    return {
        "date": date,
        "generatedAt": bundle.get("generatedAt"),
        "priceDataDate": meta.get("priceDataDate"),
        "usDataDate": meta.get("usDataDate"),
        "japanDataDate": meta.get("japanDataDate"),
        "tokyoDataDate": meta.get("tokyoDataDate"),
        "cftcDate": meta.get("cftcDate"),
        "file": f"{date}.json",
    }


def git_json(commit: str, path: str) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", "show", f"{commit}:{path}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(proc.stdout)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def valid_historical_config(config: dict[str, Any]) -> bool:
    if config.get("pageId") != "usdjpy-supply-demand":
        return False
    version = str(config.get("schemaVersion") or "")
    return version.startswith("3.") and bool(report_date(config))


def backfill(entries: dict[str, dict[str, Any]]) -> None:
    try:
        proc = subprocess.run(
            ["git", "log", "--format=%H", "--", "data/usdjpy-supply-demand.json"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except Exception:
        return

    selected: dict[str, str] = {}
    for commit in [line.strip() for line in proc.stdout.splitlines() if line.strip()][:500]:
        config = git_json(commit, "data/usdjpy-supply-demand.json")
        if not valid_historical_config(config):
            continue
        date = report_date(config)
        if date and date not in selected:
            selected[date] = commit

    for date, commit in selected.items():
        if date in entries and (ARCHIVE_DIR / f"{date}.json").exists():
            continue
        config = git_json(commit, "data/usdjpy-supply-demand.json")
        market = git_json(commit, "data/market/latest.json")
        rates = git_json(commit, "data/rates-bonds.json")
        volume = git_json(commit, "data/usdjpy-volume.json")
        events = git_json(commit, "data/events.json")
        if not (config and market and rates and volume):
            continue
        try:
            bundle = build_bundle(config, market, rates, volume, events)
        except Exception:
            continue
        write_json(ARCHIVE_DIR / f"{date}.json", bundle)
        entries.setdefault(date, make_entry(bundle))


def main() -> int:
    config = load_json(CONFIG_PATH)
    market = load_json(MARKET_PATH)
    rates = load_json(RATES_PATH)
    volume = load_json(VOLUME_PATH)
    events = load_json(EVENTS_PATH)
    if not valid_historical_config(config):
        raise RuntimeError("現在のUSD/JPY需給分析JSONが履歴保存対象の形式ではありません")
    if not (market and rates and volume):
        raise RuntimeError("USD/JPY需給分析の中核データが不足しています")

    bundle = build_bundle(config, market, rates, volume, events)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    write_json(ARCHIVE_DIR / f"{bundle['reportDate']}.json", bundle)

    existing = load_json(INDEX_PATH)
    entries = {
        str(row.get("date")): dict(row)
        for row in (existing.get("reports") or [])
        if isinstance(row, dict) and row.get("date")
    }
    entries[bundle["reportDate"]] = make_entry(bundle)
    if not existing.get("backfillComplete"):
        backfill(entries)

    dates = sorted(entries)[-MAX_REPORTS:]
    index = {
        "schemaVersion": "1.0.0",
        "pageId": "usdjpy-supply-demand",
        "updatedAt": bundle.get("generatedAt"),
        "backfillComplete": True,
        "reports": [entries[d] for d in dates],
    }
    write_json(INDEX_PATH, index)
    print(json.dumps({
        "reportDate": bundle["reportDate"],
        "archiveCount": len(dates),
        "index": str(INDEX_PATH.relative_to(ROOT)),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
