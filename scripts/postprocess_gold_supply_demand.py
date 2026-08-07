#!/usr/bin/env python3
"""Normalize display statuses after gold acquisition without fabricating data."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "gold-supply-demand.json"


def has_number(v):
    try:
        return v is not None and v != "" and float(v) == float(v)
    except Exception:
        return False


def main() -> int:
    d = json.loads(PATH.read_text(encoding="utf-8"))

    physical = d.get("physical") or {}
    valid_physical = False
    for key in ("china", "india"):
        x = physical.get(key)
        if not isinstance(x, dict):
            continue
        if has_number(x.get("premiumUsdOz")):
            valid_physical = True
        else:
            x["status"] = "unavailable"
            x["premiumUsdOz"] = None
            x["change"] = None
    if not valid_physical:
        physical["status"] = "unavailable"

    comex = d.get("comex") or {}
    ai = list(d.get("aiSummary") or [])
    if comex.get("status") == "stale" and has_number(comex.get("volume")) and has_number(comex.get("openInterest")):
        msg = (
            f"COMEXは{comex.get('asOfDate') or '前回'}の前回確認値を保持しています。"
            f"出来高{int(float(comex['volume'])):,}枚、建玉{int(float(comex['openInterest'])):,}枚、"
            f"建玉前日比{int(float(comex.get('openInterestChange') or 0)):+,}枚です。"
            "今回取得に失敗した場合も推測値へ置き換えません。"
        )
        if len(ai) >= 2:
            ai[1] = msg
        else:
            ai.append(msg)
    d["aiSummary"] = ai

    PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Normalized gold supply-demand display statuses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
