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
import hashlib
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.reporting.context import aware
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
    if not isinstance(config, dict):
        raise IssuanceBlocked("ISSUANCE_OWNER_CONFIG_INVALID")
    owners = config.get("slotOwners")
    owner = owners.get("08:00") if isinstance(owners, dict) else None
    if config.get("schemaVersion") != 1 or not isinstance(owner, str):
        raise IssuanceBlocked("ISSUANCE_OWNER_CONFIG_INVALID")
    if owner != "g2_issuance_cli":
        raise IssuanceBlocked("ISSUANCE_OWNER_CONFLICT:08:00:" + owner)
    return owner


def validate_bundle_payload(supplied: dict, *, now: datetime | None = None) -> dict:
    """Validate a G2/evidence bundle before creating any cloud clients."""
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


def validate_bundle_input(path: Path, *, now: datetime | None = None) -> dict:
    """Read and validate a local G2 bundle without creating cloud clients."""
    try:
        supplied = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IssuanceBlocked("ISSUANCE_BUNDLE_UNREADABLE") from exc
    return validate_bundle_payload(supplied, now=now)


def load_pinned_g2_bundle(*, project_id: str, bucket_name: str,
                          object_name: str, generation: int, client=None) -> dict:
    """Read a trusted producer's exact G2 object generation; never read latest."""
    if (not project_id or not bucket_name or "test" in project_id.lower() or
            "test" in bucket_name.lower()):
        raise IssuanceBlocked("PRODUCTION_G2_TARGET_NOT_CONFIGURED")
    if not object_name or type(generation) is not int or generation <= 0:
        raise IssuanceBlocked("G2_BUNDLE_GENERATION_REQUIRED")
    if client is None:
        from google.cloud import storage
        client = storage.Client(project=project_id)
    blob = client.bucket(bucket_name).blob(object_name, generation=generation)
    try:
        payload = blob.download_as_bytes(if_generation_match=generation)
        blob.reload()
    except Exception as exc:
        raise IssuanceBlocked("PINNED_G2_BUNDLE_READBACK_FAILED") from exc
    if int(blob.generation) != generation:
        raise IssuanceBlocked("PINNED_G2_BUNDLE_GENERATION_MISMATCH")
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IssuanceBlocked("PINNED_G2_BUNDLE_JSON_INVALID") from exc
    if not isinstance(data, dict):
        raise IssuanceBlocked("PINNED_G2_BUNDLE_NOT_OBJECT")
    return {"data": data, "generation": generation,
            "object": object_name, "bucket": bucket_name,
            "created_at": (blob.time_created.isoformat()
                           if getattr(blob, "time_created", None) else None),
            "sha256": hashlib.sha256(payload).hexdigest()}


def load_bundle(path: Path | None, *, now: datetime | None = None,
                g2_object_name: str = "", g2_generation: int | None = None,
                g2_bucket: str = "", expected_report_id: str = "",
                expected_revision: int | None = None,
                expected_evidence_object: str = "",
                expected_evidence_generation: int | None = None) -> dict:
    """Bind one local or exact-generation G2 bundle to pinned production Evidence."""
    project_id = os.environ.get("REPORT_EVIDENCE_PROJECT_ID", "")
    evidence_bucket = os.environ.get("REPORT_EVIDENCE_BUCKET", "")
    pinned_g2 = None
    if path is not None:
        if g2_object_name or g2_generation is not None:
            raise IssuanceBlocked("G2_BUNDLE_INPUTS_ARE_MUTUALLY_EXCLUSIVE")
        supplied = validate_bundle_input(path, now=now)
    else:
        if not g2_object_name or type(g2_generation) is not int or g2_generation <= 0:
            raise IssuanceBlocked("BLOCKED_G2_PRODUCER_MISSING")
        pinned_g2 = load_pinned_g2_bundle(
            project_id=project_id, bucket_name=g2_bucket or evidence_bucket,
            object_name=g2_object_name, generation=g2_generation)
        supplied = validate_bundle_payload(pinned_g2["data"], now=now)
        if not pinned_g2.get("created_at"):
            raise IssuanceBlocked("G2_BUNDLE_CREATION_TIME_UNKNOWN")
        report = supplied["g2"]["report"]
        slot_start = datetime.combine(
            datetime.strptime(report["date"], "%Y-%m-%d").date(), time(8, 0), tzinfo=JST)
        if aware(pinned_g2["created_at"]) > slot_start:
            raise IssuanceBlocked("G2_BUNDLE_CREATED_AFTER_REPORT_SLOT")
        if not expected_report_id or expected_revision is None:
            raise IssuanceBlocked("G2_BUNDLE_TARGET_IDENTITY_REQUIRED")
        ref = supplied["evidence_ref"]
        if (supplied["g2"].get("report_id") != expected_report_id or
                supplied["g2"].get("revision") != expected_revision or
                supplied["g2"]["report"].get("report_id") != expected_report_id or
                supplied["g2"]["report"].get("revision") != expected_revision):
            raise IssuanceBlocked("G2_BUNDLE_TARGET_IDENTITY_MISMATCH")
        if (not expected_evidence_object or expected_evidence_generation is None or
                ref.get("object") != expected_evidence_object or
                ref.get("generation") != expected_evidence_generation):
            raise IssuanceBlocked("G2_BUNDLE_EVIDENCE_TARGET_MISMATCH")
    ref = supplied["evidence_ref"]
    envelope = load_pinned_production_evidence(
        project_id=project_id, bucket_name=evidence_bucket,
        object_name=ref["object"], generation=ref["generation"])
    result = {"environment": "PRODUCTION", "g2": supplied["g2"],
              "evidence_object": envelope["evidence_object"]}
    if pinned_g2:
        result["g2_bundle"] = {key: pinned_g2[key] for key in
                               ("object", "bucket", "generation", "created_at", "sha256")}
    return result

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", nargs="?", type=Path,
                        help="Local G2 JSON (use pinned GCS flags for producer handoff)")
    parser.add_argument("--g2-bundle-object", default="")
    parser.add_argument("--g2-bundle-generation", type=int)
    parser.add_argument("--g2-bundle-bucket", default="")
    parser.add_argument("--report-id", default="")
    parser.add_argument("--revision", type=int)
    parser.add_argument("--evidence-object", default="")
    parser.add_argument("--evidence-generation", type=int)
    args = parser.parse_args(argv)
    try:
        gcs_bundle = args.g2_bundle_object or args.g2_bundle_generation is not None
        if args.bundle is None and not gcs_bundle:
            raise IssuanceBlocked("BLOCKED_G2_PRODUCER_MISSING")
        if args.bundle is not None:
            validate_bundle_input(args.bundle)
        elif not all((args.report_id, args.revision and args.revision > 0,
                      args.evidence_object, args.evidence_generation and args.evidence_generation > 0)):
            raise IssuanceBlocked("G2_BUNDLE_TARGET_INPUT_REQUIRED")
        require_08_issuance_owner()
        required_env = ("REPORT_EVIDENCE_PROJECT_ID", "REPORT_EVIDENCE_BUCKET",
                       "REPORT_ISSUANCE_CLAIM_BUCKET", "REPORT_ISSUANCE_DOCS_FOLDER_ID",
                       "REPORT_ISSUANCE_ROOT_FOLDER_ID", "GITHUB_SHA")
        missing = [key for key in required_env if not os.environ.get(key)]
        if missing:
            raise IssuanceBlocked("ISSUANCE_CONFIG_MISSING:" + ",".join(missing))
        bundle = load_bundle(
            args.bundle, g2_object_name=args.g2_bundle_object,
            g2_generation=args.g2_bundle_generation, g2_bucket=args.g2_bundle_bucket,
            expected_report_id=args.report_id, expected_revision=args.revision,
            expected_evidence_object=args.evidence_object,
            expected_evidence_generation=args.evidence_generation)
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

