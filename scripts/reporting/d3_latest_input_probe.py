"""No-network diagnostic for the saved market data -> OpenAI input boundary.

The command never generates market facts, calls an API, or changes publication.
It reports whether the *saved snapshot* is eligible for its own named slot.
It does not assert a report for today's date is ready.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .context import ReportContext
from .snapshot import MarketDataSnapshot
from .shadow_worker import freeze_shadow_input, REQUIRED_SIX


def probe_latest_market_input(payload: dict) -> dict:
    output = {
        "status": "INPUT_BLOCKED",
        "source_generated_at": payload.get("generatedAt") if isinstance(payload, dict) else None,
        "declared_report_slot": payload.get("reportSlot") if isinstance(payload, dict) else None,
        "publish_allowed": False,
        "model_send_allowed": False,
    }
    try:
        if not isinstance(payload, dict):
            raise ValueError("MARKET_PAYLOAD_NOT_OBJECT")
        when = payload.get("generatedAt")
        slot = payload.get("reportSlot")
        if not isinstance(when, str) or len(when) < 10:
            raise ValueError("ACQUISITION_TIMESTAMP_MISSING")
        if slot not in ("08:00", "12:00", "16:00", "21:00"):
            raise ValueError("REPORT_SLOT_INVALID")
        day = when[:10]
        context = ReportContext.create(day, slot, f"{day}T{slot}:00+09:00")
        snapshot = MarketDataSnapshot.from_acquisition(context, payload)
        freeze_shadow_input(context, snapshot)
        present = {m.instrument for m in snapshot.markets}
        if not set(REQUIRED_SIX).issubset(present):
            raise ValueError("SIX_REQUIRED_MARKETS_MISSING")
        output["status"] = "INPUT_READY_FOR_SAVED_SLOT_ONLY"
        output["reason"] = None
        output["market_count"] = len(snapshot.markets)
        output["frozen_snapshot_id"] = snapshot.snapshot_id
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        output["reason"] = str(exc)
    return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--market-json", default="data/market/latest.json")
    args = p.parse_args()
    data = json.loads(Path(args.market_json).read_text(encoding="utf-8"))
    result = probe_latest_market_input(data)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    # This is a DIAGNOSTIC, not a readiness gate. Blocked input must not
    # make CI misrepresent readiness; inspect its explicit status and reason.


if __name__ == "__main__":
    main()
