from __future__ import annotations

import json
from pathlib import Path

import build_usdjpy_supply_demand as base

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "usdjpy-supply-demand.json"
TARGET_WEEKS = 52


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    previous = data.get("cftc") or {}

    # Reuse the existing official CFTC/Yahoo acquisition logic, but widen the
    # requested history from 26 to 52 weeks before the fallback price enricher.
    base.LOOKBACK_WEEKS = TARGET_WEEKS
    cftc = base.fetch_cftc(previous)
    series = cftc.get("series") or []

    if len(series) < TARGET_WEEKS:
        raise SystemExit(
            f"CFTC 52-week expansion failed: expected {TARGET_WEEKS}, got {len(series)}"
        )

    price_points = sum(isinstance(item.get("price"), (int, float)) for item in series)
    cftc["lookbackWeeks"] = len(series)
    cftc["verifiedPoints"] = len(series)
    cftc["priceVerifiedPoints"] = price_points
    cftc["note"] = (
        "CFTC公式のJapanese Yen・Non-Commercial Long/Shortを使用。"
        "直近52週を年次履歴から取得し、各CFTC基準日のUSD/JPY価格を重ねる。"
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
                "status": "expanded",
                "weeks": len(series),
                "pricePointsBeforeFallback": price_points,
                "asOf": cftc.get("asOf"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
