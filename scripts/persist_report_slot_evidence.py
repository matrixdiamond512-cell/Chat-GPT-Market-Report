#!/usr/bin/env python3
"""Persist immutable, pre-draft evidence for one real report slot.

This artifact only establishes the frozen acquisition and report context. It is
not a publication receipt and never makes a report eligible for publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

if __package__:
    from .reporting.context import ReportContext, aware
    from .reporting.snapshot import MarketDataSnapshot, digest
    from .run_market_data_window import snapshot_is_current
else:
    from reporting.context import ReportContext, aware
    from reporting.snapshot import MarketDataSnapshot, digest
    from run_market_data_window import snapshot_is_current

ROOT = Path(__file__).resolve().parents[1]


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def build_slot_evidence(report_date: str, report_time: str, market_payload: dict, raw_market_bytes: bytes, *, max_age_minutes: int = 15) -> dict:
    day = date.fromisoformat(report_date)
    if max_age_minutes < 0:
        raise ValueError("max_age_minutes must be nonnegative")
    if not snapshot_is_current(market_payload, report_time, day):
        raise ValueError("acquisition is not verified for the requested report date/slot/cutoff")

    cutoff = aware(f"{report_date}T{report_time}:00+09:00")
    generated_at = aware(market_payload["generatedAt"])
    age_seconds = (cutoff - generated_at).total_seconds()
    if age_seconds < 0 or age_seconds > max_age_minutes * 60:
        raise ValueError("acquisition is outside the allowed pre-draft cutoff window")
    context = ReportContext.create(report_date, report_time, generated_at.isoformat(), revision=1, mode="new")
    snapshot = MarketDataSnapshot.from_acquisition(context, market_payload)
    context_data = context.to_dict()
    snapshot_data = snapshot.to_dict()
    source_hash = hashlib.sha256(raw_market_bytes).hexdigest()
    context_hash = digest(context_data)
    snapshot_hash = digest(snapshot_data)
    evidence_id = hashlib.sha256(f"{context_hash}:{snapshot_hash}:{source_hash}".encode("ascii")).hexdigest()
    return {
        "schemaVersion": 1,
        "evidenceStatus": "READY_FOR_DRAFT",
        "evidenceId": evidence_id,
        "reportId": context.report_id,
        "revision": context.revision,
        "context": context_data,
        "contextHash": context_hash,
        "snapshot": snapshot_data,
        "snapshotHash": snapshot_hash,
        "acquisitionSource": {
            "path": "data/market/latest.json",
            "contentHash": source_hash,
            "generatedAt": market_payload["generatedAt"],
            "reportSlot": report_time,
            "overallStatus": market_payload.get("overallStatus"),
        },
    }


def require_before_slot(report_date: str, report_time: str, *, now: datetime | None = None) -> None:
    """Fail closed if the live producer tries to backfill after the slot cutoff."""
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("BLOCKED_LIVE_EVIDENCE_NAIVE_CLOCK")
    target = aware(f"{report_date}T{report_time}:00+09:00")
    if current >= target:
        raise ValueError("BLOCKED_LIVE_EVIDENCE_AFTER_SLOT")


def persist_slot_evidence(report_date: str, report_time: str, market_data_path: Path, output_dir: Path, *, max_age_minutes: int = 15, require_live_before_slot: bool = False, now: datetime | None = None) -> tuple[Path, bool]:
    if require_live_before_slot:
        require_before_slot(report_date, report_time, now=now)
    raw = market_data_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("market acquisition must be a JSON object")
    evidence = build_slot_evidence(report_date, report_time, payload, raw, max_age_minutes=max_age_minutes)
    out_path = output_dir / f"{evidence['reportId']}-r{evidence['revision']}.json"
    encoded = canonical_bytes(evidence)
    if out_path.exists():
        if out_path.read_bytes() == encoded:
            return out_path, False
        raise FileExistsError(f"immutable report evidence already exists with different content: {out_path}")
    if require_live_before_slot:
        require_before_slot(report_date, report_time, now=now)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Exclusive creation prevents two independent workflows from silently
        # replacing one another's evidence between the existence check and write.
        with out_path.open("xb") as handle:
            handle.write(encoded)
    except FileExistsError:
        existing = out_path.read_bytes()
        if existing == encoded:
            return out_path, False
        raise FileExistsError(f"immutable report evidence already exists with different content: {out_path}")
    if require_live_before_slot:
        try:
            require_before_slot(report_date, report_time, now=now)
        except ValueError:
            out_path.unlink(missing_ok=True)
            raise
    # Read back and verify both exact bytes and calculated identity before success.
    readback = out_path.read_bytes()
    if readback != encoded:
        out_path.unlink(missing_ok=True)
        raise OSError("report evidence readback differs from persisted bytes")
    restored = json.loads(readback.decode("utf-8"))
    if restored.get("evidenceId") != evidence["evidenceId"] or digest(restored["snapshot"]) != evidence["snapshotHash"] or digest(restored["context"]) != evidence["contextHash"]:
        out_path.unlink(missing_ok=True)
        raise OSError("report evidence identity readback failed")
    return out_path, True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="explicit report date YYYY-MM-DD; never inferred from runner time")
    parser.add_argument("--slot", required=True, choices=("08:00", "12:00", "16:00", "21:00"))
    parser.add_argument("--market-data", default="data/market/latest.json")
    parser.add_argument("--output-dir", default="data/report-evidence")
    parser.add_argument("--max-age-minutes", type=int, default=15)
    parser.add_argument("--require-live-before-slot", action="store_true", help="never create a live report-slot evidence after its cutoff")
    args = parser.parse_args()
    path, created = persist_slot_evidence(args.date, args.slot, Path(args.market_data), Path(args.output_dir), max_age_minutes=args.max_age_minutes, require_live_before_slot=args.require_live_before_slot)
    print(f"{'CREATED' if created else 'NO_OP'} pre-draft evidence: {path.as_posix()}")


if __name__ == "__main__":
    main()
