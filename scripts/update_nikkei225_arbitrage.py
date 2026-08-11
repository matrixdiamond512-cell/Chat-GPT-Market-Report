#!/usr/bin/env python3
"""Update the dedicated arbitrage JSON and keep it aligned with Nikkei supply-demand."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.jpx_arbitrage import component_from_positions, fetch_latest_positions, now_iso

ROOT = Path(__file__).resolve().parents[1]
ARBITRAGE = ROOT / "data" / "nikkei225-arbitrage.json"
SUPPLY = ROOT / "data" / "nikkei225-supply-demand.json"


def load(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def iso(value) -> str | None:
    text = str(value or "")[:10].replace("/", "-")
    return text if len(text) == 10 else None


def normalize_component(value: dict) -> dict:
    required = ("asOfDate", "buyBalance", "sellBalance")
    if not isinstance(value, dict) or any(value.get(key) is None for key in required):
        raise ValueError("supply-demand arbitrage component is incomplete")
    out = dict(value)
    out["asOfDate"] = iso(out["asOfDate"])
    out.setdefault("frequency", "daily")
    out.setdefault("lastAttemptAt", out.get("fetchedAt") or now_iso())
    out.setdefault("lastSuccessAt", out.get("fetchedAt") or now_iso())
    return out


def update_history(page: dict, component: dict, supply: dict) -> list[dict]:
    rows = [dict(row) for row in page.get("history", []) if isinstance(row, dict)]
    by_date = {iso(row.get("date")): row for row in rows if iso(row.get("date"))}
    as_of = iso(component["asOfDate"])
    spot = supply.get("spot") or {}
    existing = by_date.get(as_of, {})
    by_date[as_of] = {
        **existing,
        "date": as_of,
        "sellBalance": int(component["sellBalance"]),
        "buyBalance": int(component["buyBalance"]),
        "source": "JPX",
        "sourceFileUrl": component.get("sourceFileUrl"),
        "nikkei225Close": spot.get("value") if iso(spot.get("asOfDate")) == as_of else existing.get("nikkei225Close"),
    }
    return [by_date[key] for key in sorted(by_date)]


def validate(page: dict, supply: dict) -> None:
    component = supply.get("arbitrage") or {}
    latest = page.get("latest") or {}
    if iso(page.get("asOfDate")) != iso(component.get("asOfDate")):
        raise ValueError("dedicated and supply-demand arbitrage dates differ")
    for key in ("buyBalance", "sellBalance"):
        if not isinstance(latest.get(key), int) or latest[key] < 0:
            raise ValueError(f"invalid {key}")
        if latest[key] != component.get(key):
            raise ValueError(f"dedicated and supply-demand {key} differ")
    if not page.get("history"):
        raise ValueError("arbitrage history is empty")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-supply", action="store_true", help="sync the standalone JSON from the already verified supply component")
    args = parser.parse_args()
    page = load(ARBITRAGE, {})
    supply = load(SUPPLY, {})
    previous_component = supply.get("arbitrage") or {}
    attempt = now_iso()
    try:
        if args.from_supply:
            component = normalize_component(previous_component)
        else:
            component = component_from_positions(fetch_latest_positions(), previous_component)
            supply["arbitrage"] = component
            supply["generatedAt"] = now_iso()
        page.update({
            "schemaVersion": 2,
            "pageId": "nikkei225-arbitrage",
            "pageTitle": "裁定取引",
            "asOfDate": iso(component["asOfDate"]),
            "generatedAt": now_iso(),
            "lastAttemptAt": attempt,
            "lastSuccessAt": component.get("lastSuccessAt") or component.get("fetchedAt") or now_iso(),
            "status": component.get("status", "verified"),
            "frequency": "daily",
            "sourceStatus": "JPX一次情報で確認" if component.get("status") == "verified" else "前回正常値を保持",
            "sourcePageUrl": component.get("sourceUrl"),
            "sourceFileUrl": component.get("sourceFileUrl"),
            "latest": {key: component.get(key) for key in ("buyBalance", "buyChange", "sellBalance", "sellChange")},
        })
        page["history"] = update_history(page, component, supply)
        validate(page, supply)
        ARBITRAGE.write_text(json.dumps(page, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not args.from_supply:
            SUPPLY.write_text(json.dumps(supply, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": page["status"], "asOfDate": page["asOfDate"], "history": len(page["history"])}, ensure_ascii=False))
        return 0
    except Exception as exc:
        page["lastAttemptAt"] = attempt
        page["status"] = "preserved_after_fetch_error" if page.get("latest") else "unavailable"
        page["error"] = f"{type(exc).__name__}: {exc}"
        page["sourceStatus"] = "JPX取得失敗・前回正常値を保持" if page.get("latest") else "取得不能"
        ARBITRAGE.write_text(json.dumps(page, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": page["status"], "error": page["error"]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
