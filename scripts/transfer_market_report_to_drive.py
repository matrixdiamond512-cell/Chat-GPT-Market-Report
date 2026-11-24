#!/usr/bin/env python3
"""Transfer already-created report text/PNG to an explicit TEST_ONLY Drive folder.

This command never generates report content or marks a report publication/PNG QA
ready. The SQLite spool must be inside the operating-system temporary directory
so source bytes are not placed in a cloud-synced workspace.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

try:
    from reporting.delivery_spool import DeliverySpool
    from reporting.google_drive_writer import DriveLockReleaseError, GoogleDriveReportWriter
except ModuleNotFoundError:
    from scripts.reporting.delivery_spool import DeliverySpool
    from scripts.reporting.google_drive_writer import DriveLockReleaseError, GoogleDriveReportWriter


def local_spool_path(value: str) -> Path:
    if not value:
        raise ValueError("--spool is required")
    path = Path(value).expanduser().resolve()
    roots = [Path(tempfile.gettempdir()).resolve()]
    for name in ("LOCALAPPDATA", "RUNNER_TEMP", "TMPDIR"):
        value = os.environ.get(name)
        if value:
            roots.append(Path(value).expanduser().resolve())
    for root in roots:
        try:
            path.relative_to(root)
            return path
        except ValueError:
            continue
    raise ValueError("spool must be stored under a local non-synced app-data or temp directory")


def default_spool_path() -> str:
    configured = os.environ.get("MARKET_REPORT_SPOOL_PATH", "").strip()
    if configured:
        return configured
    app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if not app_data:
        return ""
    # LocalAppData survives process/OS restarts and is not a cloud-synced path.
    return str(Path(app_data) / "MarketReportDelivery" / "delivery-spool.sqlite3")


def _load_optional(path: str | None) -> bytes | None:
    return Path(path).read_bytes() if path else None


def run(args) -> tuple[dict, int]:
    spool = DeliverySpool(local_spool_path(args.spool))
    identity = (args.report_id, args.revision)

    outcomes = {}
    lock_release = {}
    available = []
    persist_failed = False
    # Read and commit every supplied source before authenticating or making
    # any network request. Both lanes survive a stop during the first transfer.
    for kind, source_path in (("DOCS", args.body_file), ("PNG", args.png_file)):
        try:
            payload = _load_optional(source_path)
            if payload is not None:
                spool.persist(*identity, kind, payload)
        except Exception as exc:
            outcomes[kind] = "PERSIST_FAILED:" + type(exc).__name__
            persist_failed = True
            continue
        try:
            spool.inspect(*identity, kind)
            available.append(kind)
        except ValueError:
            outcomes[kind] = "NOT_PROVIDED"
    if persist_failed or not available:
        return _result(spool, identity, outcomes, lock_release)

    try:
        writer = GoogleDriveReportWriter.from_environment(args.folder_id)
    except Exception as exc:
        # Leave all source bytes intact when auth/configuration is unavailable.
        for kind in available:
            outcomes[kind] = "BLOCKED:" + type(exc).__name__
        result, exit_code = _result(spool, identity, outcomes, lock_release)
        return result, 1 if exit_code == 0 else exit_code

    for kind, write in (("DOCS", writer.write_docs), ("PNG", writer.write_png)):
        if kind not in available:
            continue
        try:
            spool.transfer(*identity, kind, write=write, readback=writer.readback,
                           reconcile=writer.reconcile, guard=writer.transfer_guard)
            outcomes[kind] = "WRITE_READBACK_VERIFIED"
            lock_release[kind] = "RELEASED"
        except DriveLockReleaseError as exc:
            # Keep verified Drive readback and lock cleanup as separate facts.
            if exc.operation_succeeded:
                outcomes[kind] = "WRITE_READBACK_VERIFIED"
            elif exc.operation_error is not None:
                outcomes[kind] = "FAILED:" + type(exc.operation_error).__name__
            else:
                outcomes[kind] = "FAILED:DriveLockReleaseError"
            lock_release[kind] = "FAILED"
        except Exception as exc:
            # Do not expose body, image, destination URL, or credential details.
            outcomes[kind] = "FAILED:" + type(exc).__name__
            lock_release[kind] = "NOT_CONFIRMED"

    return _result(spool, identity, outcomes, lock_release)


def _result(spool, identity, outcomes, lock_release=None):
    status = spool.delivery_status(*identity)
    lock_release = lock_release or {}
    release_failed = any(value == "FAILED" for value in lock_release.values())
    result = {**status, "attemptOutcomes": outcomes, "lockRelease": lock_release,
              "resultStatus": "LOCK_RELEASE_FAILED" if release_failed else status["status"],
              "hashes": {kind: spool.inspect(*identity, kind)["sha256"]
                         for kind in ("DOCS", "PNG") if kind in status["lanes"]}}
    exit_code = (3 if release_failed else 0 if status["status"] == "COMPLETE" else
                 2 if status["status"] == "PARTIAL" else 1)
    return result, exit_code


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--revision", required=True, type=int)
    parser.add_argument("--spool", default=default_spool_path())
    parser.add_argument("--folder-id", default=None, help="TEST_ONLY folder; otherwise GOOGLE_REPORT_WRITER_FOLDER_ID")
    parser.add_argument("--body-file", help="Path to an already-generated UTF-8 body")
    parser.add_argument("--png-file", help="Path to an already-generated PNG")
    args = parser.parse_args(argv)
    try:
        result, exit_code = run(args)
    except Exception as exc:
        # Keep diagnostics bounded and exclude exception messages that might
        # contain paths, request payloads, or authentication material.
        print(json.dumps({"status": "BLOCKED", "error": type(exc).__name__}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
