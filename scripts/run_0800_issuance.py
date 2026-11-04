#!/usr/bin/env python3
"""Explicit entry point for the existing protected 08:00 issuance task.

The scheduled producer supplies a G2 bundle and exact GCS evidence generation.
This program never selects the latest evidence object and fails closed outside
the report date's 08:00 issuance window. Production writes remain protected by
the publisher's main-branch/Environment gates.
"""
from __future__ import annotations

import argparse
from datetime import datetime, time, timedelta
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.reporting.issuance_pipeline import (
    GcsCreateOnlyClaimStore, GoogleDocsApiWriter, IssuanceBlocked,
    load_pinned_production_evidence, run_issuance,
)
from scripts.reporting.issuance_portal import (
    GitHubPortalPublisher, StrictGoogleDocsImporter,
)

JST = ZoneInfo("Asia/Tokyo")


def require_08_issuance_owner(config_path: Path | None = None) -> str:
    """Require the one shared owner recorded in the checked-out main config."""
    path = config_path or Path(__file__).resolve().parents[1] / "config" / "issuance_ownership.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IssuanceBlocked("ISSUANCE_OWNER_CONFIG_UNAVAILABLE") from exc
    owners = config.get("slotOwners") if isinstance(config, dict) else None
    owner = owners.get("08:00") if isinstance(owners, dict) else None
    if config.get("schemaVersion") != 1 or not isinstance(owner, str):
        raise IssuanceBlocked("ISSUANCE_OWNER_CONFIG_INVALID")
    if owner != "g2_issuance_cli":
        raise IssuanceBlocked("ISSUANCE_OWNER_CONFLICT:08:00:" + owner)
    return owner


def validate_bundle_input(path: Path, *, now: datetime | None = None) -> dict:
    """Validate the local G2/evidence references without creating cloud clients."""
    try:
        supplied = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IssuanceBlocked("ISSUANCE_BUNDLE_UNREADABLE") from exc
    if not isinstance(supplied, dict) or not isinstance(supplied.get("g2"), dict):
        raise IssuanceBlocked("BLOCKED_G2_PRODUCER_MISSING")
    ref = supplied.get("evidence_ref")
    if not isinstance(ref, dict):
        raise IssuanceBlocked("BLOCKED_G2_PRODUCER_MISSING")
    object_name = ref.get("object")
    generation = ref.get("generation")
    if (not isinstance(object_name, str) or not object_name or
            type(generation) is not int or generation <= 0):
        raise IssuanceBlocked("ISSUANCE_EVIDENCE_REF_INVALID")
    report = supplied["g2"].get("report") or {}
    now = (now or datetime.now(JST)).astimezone(JST)
    try:
        report_date = datetime.strptime(report["date"], "%Y-%m-%d").date()
        report_time = report["time"]
    except (KeyError, TypeError, ValueError) as exc:
        raise IssuanceBlocked("ISSUANCE_REPORT_SLOT_INVALID") from exc
    if report_time != "08:00" or report_date != now.date() or now.weekday() >= 5:
        raise IssuanceBlocked("ISSUANCE_ENTRYPOINT_REQUIRES_TODAY_WEEKDAY_0800")
    slot_start = datetime.combine(report_date, time(8, 0), tzinfo=JST)
    if now < slot_start or now > slot_start + timedelta(minutes=40):
        raise IssuanceBlocked("ISSUANCE_ENTRYPOINT_OUTSIDE_SLOT_WINDOW")
    return supplied


def load_bundle(path: Path, *, now: datetime | None = None) -> dict:
    """Bind a scheduled G2 bundle to one explicit immutable evidence object."""
    supplied = validate_bundle_input(path, now=now)
    ref = supplied["evidence_ref"]
    project_id = os.environ.get("REPORT_EVIDENCE_PROJECT_ID", "")
    bucket = os.environ.get("REPORT_EVIDENCE_BUCKET", "")
    object_name = ref["object"]
    generation = ref["generation"]
    envelope = load_pinned_production_evidence(
        project_id=project_id, bucket_name=bucket, object_name=object_name,
        generation=generation,
    )
    return {"environment": "PRODUCTION", "g2": supplied["g2"],
            "evidence_object": envelope["evidence_object"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", nargs="?", type=Path,
                        help="G2 JSON containing evidence_ref.object and generation")
    args = parser.parse_args(argv)
    try:
        if args.bundle is None:
            raise IssuanceBlocked("BLOCKED_G2_PRODUCER_MISSING")
        validate_bundle_input(args.bundle)
        require_08_issuance_owner()
        required_env = ("REPORT_EVIDENCE_PROJECT_ID", "REPORT_EVIDENCE_BUCKET",
                       "REPORT_ISSUANCE_CLAIM_BUCKET", "REPORT_ISSUANCE_DOCS_FOLDER_ID",
                       "REPORT_ISSUANCE_ROOT_FOLDER_ID", "GITHUB_SHA")
        missing = [key for key in required_env if not os.environ.get(key)]
        if missing:
            raise IssuanceBlocked("ISSUANCE_CONFIG_MISSING:" + ",".join(missing))
        bundle = load_bundle(args.bundle)
        project_id = os.environ["REPORT_EVIDENCE_PROJECT_ID"]
        bucket = os.environ["REPORT_EVIDENCE_BUCKET"]
        claim_bucket = os.environ["REPORT_ISSUANCE_CLAIM_BUCKET"]
        root = Path(__file__).resolve().parents[1]
        head = os.environ.get("GITHUB_SHA", "")
        if not head:
            raise IssuanceBlocked("ISSUANCE_GITHUB_SHA_REQUIRED")
        docs_writer = GoogleDocsApiWriter(
            folder_id=os.environ.get("REPORT_ISSUANCE_DOCS_FOLDER_ID", ""),
            root_folder_id=os.environ.get("REPORT_ISSUANCE_ROOT_FOLDER_ID", ""),
        )
        importer = StrictGoogleDocsImporter(root=root, docs_session=docs_writer._session)
        portal = GitHubPortalPublisher.from_environment(importer=importer, expected_head=head)
        result = run_issuance(
            bundle, expected_project_id=project_id, expected_evidence_bucket=bucket,
            docs_writer=docs_writer, portal=portal,
            claim_store=GcsCreateOnlyClaimStore(claim_bucket),
        )
        print(json.dumps({"status": result["status"], "environment": result["environment"],
                          "report_id": result["report_id"], "revision": result["revision"],
                          "body_hash": result["body_hash"],
                          "completed_stages": result["completed_stages"]},
                         ensure_ascii=False))
        return 0
    except IssuanceBlocked as exc:
        print(json.dumps({"status": "BLOCKED", "stage": exc.stage,
                          "completed_stages": list(exc.completed_stages),
                          "retryable": exc.retryable, "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

