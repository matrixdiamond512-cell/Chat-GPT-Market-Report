#!/usr/bin/env python3
"""Run a single TEST_ONLY pre-slot capture from explicit fixture/input files."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys

from scripts.reporting.pre_slot_execution import PrivateFileEvidenceStore, execute_test_only_capture
from scripts.reporting.slot_recovery_contract import ContractError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True, help="signed TEST_ONLY request JSON with signature field")
    parser.add_argument("--acquisition-input", type=Path, required=True, help="acquired market JSON bytes; never a live-source selector")
    parser.add_argument("--private-root", type=Path, required=True, help="isolated private evidence/ledger directory outside repository")
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--now", required=True, help="explicit aware ISO timestamp for deterministic TEST_ONLY execution")
    args = parser.parse_args()
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        signature = request.pop("signature")
        secret = os.environ.get("PRE_SLOT_TRIGGER_HMAC_KEY", "").encode("utf-8")
        store = PrivateFileEvidenceStore(args.private_root / "evidence", repository_root=args.repository_root)
        result = execute_test_only_capture(
            payload=request,
            signature=signature,
            secret=secret,
            acquisition=lambda _trigger: args.acquisition_input.read_bytes(),
            store=store,
            attempt_ledger=args.private_root / "ledger" / f"{request.get('attemptId', 'missing')}.json",
            repository_root=args.repository_root,
            now=datetime.fromisoformat(args.now.replace("Z", "+00:00")),
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (ContractError, ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
