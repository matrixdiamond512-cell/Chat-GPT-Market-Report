from __future__ import annotations

import json
from pathlib import Path

import build_usdjpy_supply_demand as base

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "usdjpy-supply-demand.json"
TARGET_WEEKS = 52
MINIMUM_WEEKS = 26


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    previous = data.get("cftc") or {}

    # Reuse the existing official CFTC/Yahoo acquisition logic, but widen the
    # requested history from 26 to 52 weeks before the fallback price enricher.
    base.LOOKBACK_WEEKS = TARGET_WEEKS
    cftc = base.fetch_cftc(previous)
    series = cftc.get("series") or []
    fetched_weeks = len(series)

    previous_series = previous.get("series") or []
    if len(series) < MINIMUM_WEEKS and len(previous_series) >= MINIMUM_WEEKS:
        # A partial CFTC response must not truncate a previously usable history.
        latest_by_date = {str(item.get("date") or item.get("asOf") or item.get("asOfDate")): item for item in previous_series}
        for item in series:
            latest_by_date[str(item.get("date") or item.get("asOf") or item.get("asOfDate"))] = item
        series = sorted(latest_by_date.values(), key=lambda item: str(item.get("date") or item.get("asOf") or item.get("asOfDate")))[-TARGET_WEEKS:]
        cftc["series"] = series
        cftc["status"] = "preserved_after_fetch_error"
        cftc["error"] = f"CFTC履歴不足（取得{fetched_weeks}週）。前回正常履歴を保持"
    elif len(series) < MINIMUM_WEEKS:
        cftc["status"] = "unavailable"
        cftc["error"] = f"CFTC履歴不足: 最低{MINIMUM_WEEKS}週に対して{len(series)}週"
    elif len(series) < TARGET_WEEKS:
        cftc["status"] = "degraded"
        cftc["error"] = f"CFTC 52週拡張は一部取得: {len(series)}週"
    else:
        cftc["status"] = "verified"
        cftc.pop("error", None)

    price_points = sum(isinstance(item.get("price"), (int, float)) for item in series)
    cftc["lookbackWeeks"] = len(series)
    cftc["verifiedPoints"] = len(series)
    cftc["priceVerifiedPoints"] = price_points
    cftc["frequency"] = "weekly"
    cftc["note"] = (
        "CFTC公式のJapanese Yen・Non-Commercial Long/Shortを使用。"
        f"直近{len(series)}週を年次履歴から取得し、各CFTC基準日のUSD/JPY価格を重ねる。"
    )

    data["cftc"] = cftc
    data["schemaVersion"] = "3.3.2"
    data["generatedAt"] = base.now_jst().isoformat(timespec="seconds")

    rules = data.get("rules") or {}
    if isinstance(rules.get("assessment"), str):
        rules["assessment"] = rules["assessment"].replace("26週", "52週")
    if isinstance(rules.get("cftc"), str):
        rules["cftc"] = rules["cftc"].replace("26週", "52週")
    data["rules"] = rules

    DATA_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": cftc.get("status"),
                "weeks": len(series),
                "pricePointsBeforeFallback": price_points,
                "asOf": cftc.get("asOf"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
