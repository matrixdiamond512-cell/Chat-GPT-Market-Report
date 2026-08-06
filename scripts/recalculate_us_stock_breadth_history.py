#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data" / "market" / "us-stock-breadth.json"
HISTORY = ROOT / "data" / "market" / "us-stock-breadth-history.json"


def main() -> int:
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    unique = {item.get("marketDate"): item for item in history if item.get("marketDate")}
    ordered = [unique[key] for key in sorted(unique)]
    for index, item in enumerate(ordered):
        for exchange in ("NYSE", "NASDAQ"):
            current = item.get("exchanges", {}).get(exchange, {})
            ratio = current.get("advanceDeclineRatio")
            previous = ordered[index - 1].get("exchanges", {}).get(exchange, {}) if index > 0 else {}
            previous_ratio = previous.get("advanceDeclineRatio")
            current["previousDayChange"] = round(ratio - previous_ratio, 6) if isinstance(ratio, (int, float)) and isinstance(previous_ratio, (int, float)) else None
            prior_ratios = [
                x.get("exchanges", {}).get(exchange, {}).get("advanceDeclineRatio")
                for x in ordered[max(0, index - 20):index]
            ]
            prior_ratios = [x for x in prior_ratios if isinstance(x, (int, float))]
            avg20 = sum(prior_ratios) / len(prior_ratios) if prior_ratios else None
            current["average20Day"] = round(avg20, 6) if avg20 is not None else None
            current["versus20DayAveragePercent"] = round((ratio / avg20 - 1) * 100, 4) if isinstance(ratio, (int, float)) and avg20 not in (None, 0) else None
    HISTORY.write_text(json.dumps(ordered[-400:], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if ordered:
        latest = ordered[-1]
        LATEST.write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Recalculated {len(ordered)} unique US breadth dates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
