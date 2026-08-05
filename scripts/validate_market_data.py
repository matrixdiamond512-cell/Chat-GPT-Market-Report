#!/usr/bin/env python3
"""Validate dashboard market data JSON before publishing."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def validate(path: Path, require_publishable: bool = False) -> list[str]:
    data = load_json(path)
    errors: list[str] = []
    markets = data.get("markets") or {}
    config = load_json(ROOT / "config" / "market_data_sources.json")
    required = [
        key
        for key, value in (config.get("symbols") or {}).items()
        if value.get("required", False)
    ]
    for key in required:
        market = markets.get(key)
        if not market:
            errors.append(f"{key}: market object missing")
            continue
        if not is_number(market.get("value")):
            errors.append(f"{key}: numeric value missing")
        if not market.get("unit"):
            errors.append(f"{key}: unit missing")
        if not market.get("marketType"):
            errors.append(f"{key}: marketType missing")
        if market.get("verificationStatus") not in {"verified", "fallback"}:
            errors.append(f"{key}: verificationStatus is {market.get('verificationStatus')}")
        if not market.get("sourceId") and market.get("verificationStatus") == "verified":
            errors.append(f"{key}: sourceId missing")
        if not market.get("asOf"):
            errors.append(f"{key}: asOf missing")

    if require_publishable and data.get("overallStatus") == "blocked":
        errors.append("overallStatus is blocked")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=str(ROOT / "data" / "market" / "latest.json"))
    parser.add_argument("--require-publishable", action="store_true")
    args = parser.parse_args()
    path = Path(args.file)
    if not path.is_absolute():
        path = ROOT / path
    errors = validate(path, args.require_publishable)
    if errors:
        print("Market data validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Market data validation passed: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
