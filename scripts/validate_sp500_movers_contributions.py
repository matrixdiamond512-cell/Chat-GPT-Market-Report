#!/usr/bin/env python3
"""Cross-check estimated S&P contribution data against the verified index return."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks.json"
MOVERS_PATH = ROOT / "data" / "market" / "us-stock-movers.json"
CONTRIB_PATH = ROOT / "data" / "market" / "sp500-contributions.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verified_return(stocks) -> float:
    rows = (((stocks.get("marketInternals") or {}).get("us") or {}).get("rows") or [])
    for row in rows:
        if not isinstance(row, list) or len(row) < 3 or str(row[0]).strip() != "S&P500":
            continue
        matches = re.findall(r"[-+−＋]?\d+(?:\.\d+)?%", str(row[2]))
        if not matches:
            break
        return float(matches[-1].replace("%", "").replace("−", "-").replace("＋", "+"))
    raise RuntimeError("verified S&P500 daily return was not found in stocks.json")


def main() -> int:
    stocks = load(STOCKS_PATH)
    movers = load(MOVERS_PATH)
    contrib = load(CONTRIB_PATH)
    market_date = str((stocks.get("marketDates") or {}).get("us") or "")[:10]
    if movers.get("dataDate") != market_date or contrib.get("dataDate") != market_date:
        raise SystemExit("mover/contribution basis date does not match verified U.S. market date")

    estimated = float((contrib.get("validation") or {}).get("estimatedWeightedReturnPct"))
    actual = verified_return(stocks)
    diff = estimated - actual
    if abs(diff) > 0.20:
        raise SystemExit(
            f"estimated weighted return mismatch: estimated={estimated:.4f}% actual={actual:.4f}% diff={diff:.4f}pt"
        )

    validation = {
        "estimatedWeightedReturnPct": round(estimated, 4),
        "verifiedSP500ReturnPct": round(actual, 4),
        "differencePt": round(diff, 4),
        "tolerancePt": 0.20,
        "status": "passed",
    }
    movers["validation"] = validation
    contrib["validation"] = validation
    ((stocks.setdefault("movers", {})).setdefault("us", {}))["validation"] = validation
    ((stocks.setdefault("contributions", {})).setdefault("us", {}))["validation"] = validation

    save(MOVERS_PATH, movers)
    save(CONTRIB_PATH, contrib)
    save(STOCKS_PATH, stocks)
    print(json.dumps({"status": "passed", "marketDate": market_date, **validation}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
