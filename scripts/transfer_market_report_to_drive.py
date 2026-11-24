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
    from reporting.google_drive_writer import GoogleDriveReportWriter
except ModuleNotFoundError:
    from scripts.reporting.delivery_spool import DeliverySpool
    from scripts.reporting.google_drive_writer import GoogleDriveReportWriter


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


def _load_optional(path: str | None) -> bytes | None:
    return Path(path).read_bytes() if path else None


def run(args) -> tuple[dict, int]:
    spool = DeliverySpool(local_spool_path(args.spool))
    writer = GoogleDriveReportWriter.from_environment(args.folder_id)
    identity = (args.report_id, args.revision)

    outcomes = {}
    for kind, source_path, write in (("DOCS", args.body_file, writer.write_docs),
                                     ("PNG", args.png_file, writer.write_png)):
        try:
            payload = _load_optional(source_path)
            if payload is not None:
                spool.persist(*identity, kind, payload)
        except Exception as exc:
            outcomes[kind] = "PERSIST_FAILED:" + type(exc).__name__
            continue
        try:
            artifact = spool.inspect(*identity, kind)
        except ValueError:
            outcomes[kind] = "NOT_PROVIDED"
            continue
        try:
            spool.transfer(*identity, kind, write=write, readback=writer.readback, reconcile=writer.reconcile)
            outcomes[kind] = "WRITE_READBACK_VERIFIED"
        except Exception as exc:
            # Do not expose body, image, destination URL, or credential details.
            outcomes[kind] = "FAILED:" + type(exc).__name__

    status = spool.delivery_status(*identity)
    result = {**status, "attemptOutcomes": outcomes,
              "hashes": {kind: spool.inspect(*identity, kind)["sha256"]
                         for kind in ("DOCS", "PNG") if kind in status["lanes"]}}
    exit_code = 0 if status["status"] == "COMPLETE" else (2 if status["status"] == "PARTIAL" else 1)
    return result, exit_code


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--revision", required=True, type=int)
    parser.add_argument("--spool", default=os.environ.get("MARKET_REPORT_SPOOL_PATH", ""))
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
