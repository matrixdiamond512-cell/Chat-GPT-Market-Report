#!/usr/bin/env python3
"""Fail closed on scheduled delivery, verified receipt and infographic readiness.

A saved Google Doc, GitHub Actions success, or archive display alone is not
proof of formal publication. Historical reports before the strict receipt
epoch keep the legacy behavior unless infographic validation is requested.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re

from report_identity import canonical_path, internal_report_key
from reporting.publication_eligibility import is_publication_eligible
from reporting.publication_evidence import validate_receipt
from verify_publication_consistency import STRICT_RECEIPT_POLICY_FROM, dashboard_latest_is_consistent

JST = timezone(timedelta(hours=9))
SLOTS = ("08:00", "12:00", "16:00", "21:00")
HEX256 = re.compile(r"[0-9a-fA-F]{64}")


def verify_image_manifest(canonical: dict, report_id: str) -> dict:
    """Validate pinned image identity without pretending to re-read Drive bytes.

    The source image bytes must be independently read back in the publication
    pipeline. This check rejects missing, unvalidated or wrong-body manifests
    in the *scheduled delivery health* check.
    """
    if canonical.get("infographic_status") != "READY":
        raise ValueError(
            f"Infographic missing or unverified for {report_id}: "
            f"{canonical.get('infographic_status') or 'NOT_REPORTED'}"
        )
    info = canonical.get("infographic")
    if not isinstance(info, dict):
        raise ValueError(f"Infographic READY without a bound manifest for {report_id}")
    body = str(canonical.get("fullText") or "")
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if info.get("artifact_type") != "FORMAL_INFOGRAPHIC":
        raise ValueError("Infographic is not a formal artifact")
    if info.get("report_id") != report_id or info.get("revision") != canonical.get("revision"):
        raise ValueError("Infographic report identity/revision mismatch")
    if info.get("body_hash") != body_hash:
        raise ValueError("Infographic body hash mismatch")
    published_evidence = canonical.get("publicationEvidence")
    if isinstance(published_evidence, dict):
        if info.get("snapshot_id") != published_evidence.get("snapshotId"):
            raise ValueError("Infographic snapshot mismatch")
    elif not str(info.get("snapshot_id") or "").strip():
        raise ValueError("Infographic snapshot ID missing")
    for field in ("manifest_id", "drive_file_id"):
        if not str(info.get(field) or "").strip():
            raise ValueError(f"Infographic {field} missing")
    for field in ("manifest_hash", "sha256"):
        if not HEX256.fullmatch(str(info.get(field) or "")):
            raise ValueError(f"Infographic {field} is not a SHA-256 digest")
    if info.get("numeric_validation") != "PASS" or info.get("renderer_status") != "PASS":
        raise ValueError("Infographic numeric/renderer validation missing")
    return {"status": "MANIFEST_IDENTITY_PASS", "driveImageFileId": info["drive_file_id"]}


def verify(root: Path, date: str, slot: str, *, require_infographic: bool = False) -> dict:
    if slot not in SLOTS:
        raise ValueError("Unknown market report slot")
    report_path = canonical_path({"date": date, "time": slot}, root / "reports")
    if not report_path.is_file():
        raise ValueError("Missing published canonical " + report_path.name)
    canonical = json.loads(report_path.read_text(encoding="utf-8"))
    key = (date, slot)
    if not is_publication_eligible(canonical):
        raise ValueError(
            f"Report is archived but not publication-eligible: "
            f"{date} {slot} ({canonical.get('report_status')})"
        )
    if (canonical.get("date"), canonical.get("time")) != key or not str(canonical.get("fullText") or "").strip():
        raise ValueError("Incomplete or wrong-slot canonical report")

    # After this policy date, do not accept status-less/legacy public entries,
    # bare source archives, or reports missing exact Docs readback receipts.
    if date >= STRICT_RECEIPT_POLICY_FROM:
        if canonical.get("report_status") not in ("DOC_READBACK_PASS", "PUBLISHED"):
            raise ValueError("New scheduled report lacks verified publication status")
        receipt_path = root / "publication-receipts" / f"{date}_{slot.replace(':', '-')}.json"
        if not receipt_path.is_file():
            raise ValueError("Missing publication receipt " + receipt_path.name)
        try:
            validate_receipt(json.loads(receipt_path.read_text(encoding="utf-8")), canonical)
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("Publication receipt failed readback/identity validation") from exc

    index = json.loads((root / "reports.json").read_text(encoding="utf-8"))
    entries = index if isinstance(index, list) else (index.get("reports") or index.get("items") or [])
    matches = [x for x in entries if isinstance(x, dict) and (x.get("date"), x.get("time")) == key]
    if len(matches) != 1 or matches[0] != canonical:
        raise ValueError("Canonical and history index are not identical")
    latest_data = json.loads((root / "data" / "latest-report.json").read_text(encoding="utf-8"))
    latest = latest_data.get("latestReport", latest_data)
    if (latest.get("date"), latest.get("time")) < key:
        raise ValueError("Latest report pointer is behind required slot")
    dashboard = json.loads((root / "data" / "dashboard.json").read_text(encoding="utf-8"))
    if not dashboard_latest_is_consistent(latest, dashboard):
        raise ValueError("Dashboard and latest report pointer disagree")
    if dashboard.get("currentReportKey") != internal_report_key(latest):
        raise ValueError("Dashboard currentReportKey disagrees with latest report")

    result = {"status": "PASS", "date": date, "slot": slot, "canonical": str(report_path),
              "bodyPublication": "PASS", "infographic": "NOT_CHECKED"}
    if require_infographic:
        # Separate lane: failure must be visible but never rewrite body status.
        result["infographic"] = verify_image_manifest(canonical, f"{date}_{slot.replace(':', '-')}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=SLOTS, required=True)
    parser.add_argument("--date")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--require-infographic", action="store_true",
                        help="Fail health check if the formal image manifest is not READY and bound to the body")
    args = parser.parse_args()
    date = args.date or datetime.now(JST).date().isoformat()
    print(json.dumps(verify(args.root, date, args.slot, require_infographic=args.require_infographic),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
