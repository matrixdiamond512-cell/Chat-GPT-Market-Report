"""Read-only 08:00 source-to-render staging bridge.

Consumes the canonical Docs-derived report, its immutable slot evidence and
the receipt issued after the canonical importer read the actual Google Doc.
It does not call Google Docs itself and never writes to Drive or publication
paths. A successful local render is still a DRAFT candidate.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from bind_morning_report_evidence import assemble
from persist_report_slot_evidence import validate_stored_slot_evidence
from preflight_morning_infographic import check as preflight_check
from reporting.infographic import ValidationFailure
from reporting.infographic_summary import validate_summary
from reporting.morning_layout import validate_projection
from reporting.publication_evidence import validate_receipt


def canonical_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def docs_readback_from_verified_import(report: dict, receipt: dict) -> dict:
    """Expose the importer-observed Docs body after its receipt is validated.

    sync_reports_from_drive parses the Google Docs API response into canonical
    fullText; publication_evidence validates its exact SHA-256 and revision.
    The independent pre-save body is checked separately by
    ``validate_original_body_evidence``; canonical/receipt agreement alone is
    never treated as proof that the original ChatGPT body was preserved.
    """
    body = report.get("fullText")
    if not isinstance(body, str):
        raise ValidationFailure("STAGING_DOCS_BODY_MISSING")
    return {
        "document_id": report.get("sourceDocument", {}).get("id"),
        "document_revision_id": receipt.get("documentRevisionId"),
        "report_id": receipt.get("reportId"),
        "revision": receipt.get("revision"),
        "fullText": body,
        "bodyHash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "readback_source": "Google Docs API body read by canonical importer",
        "receipt_status": receipt.get("readback", {}).get("status"),
        "receipt_exact_match": receipt.get("readback", {}).get("exactMatch"),
    }


def validate_original_body_evidence(original: dict, report: dict, evidence: dict,
                                   receipt: dict) -> str:
    """Compare the frozen pre-save source with the importer's actual Docs readback."""
    source_body = original.get("fullText")
    if (original.get("evidence_stage") != "G2_DRAFT_NOT_SAVED"
            or original.get("validated_gates") != ["G0", "G1", "G2"]
            or not isinstance(source_body, str) or not source_body.strip()):
        raise ValidationFailure("STAGING_PRE_SAVE_BODY_EVIDENCE_MISSING")
    source_hash = hashlib.sha256(source_body.encode("utf-8")).hexdigest()
    if original.get("bodyHash") != source_hash:
        raise ValidationFailure("STAGING_PRE_SAVE_BODY_HASH_INVALID")
    try:
        captured_at = datetime.fromisoformat(str(original.get("capturedAt", "")).replace("Z", "+00:00"))
        saved_at = datetime.fromisoformat(str(receipt.get("savedAt", "")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationFailure("STAGING_PRE_SAVE_CAPTURE_TIME_INVALID") from exc
    if (captured_at.tzinfo is None or saved_at.tzinfo is None
            or captured_at > saved_at):
        raise ValidationFailure("STAGING_PRE_SAVE_CAPTURE_ORDER_INVALID")
    expected = {
        "date": report.get("date"), "time": "08:00", "title": report.get("title"),
        "report_id": f"{report.get('date')}_08-00", "revision": report.get("revision"),
        "snapshot_id": (evidence.get("snapshot") or {}).get("snapshot_id"),
    }
    if any(original.get(key) != value for key, value in expected.items()):
        raise ValidationFailure("STAGING_PRE_SAVE_BODY_IDENTITY_MISMATCH")
    if (original.get("fullText") != report.get("fullText")
            or source_hash != report.get("bodyHash")):
        raise ValidationFailure("STAGING_ORIGINAL_BODY_DIFFERS_FROM_DOCS_READBACK")
    if (original.get("context") != evidence.get("context")
            or original.get("snapshot") != evidence.get("snapshot")):
        raise ValidationFailure("STAGING_PRE_SAVE_SNAPSHOT_CONTEXT_MISMATCH")
    return source_hash


def validate_transaction(*, report: dict, evidence_bytes: bytes, receipt: dict,
                         docs_readback: dict, summary: dict, view: dict,
                         spec: dict, scenario_review: dict,
                         original_body_evidence: dict, report_date: str) -> tuple[dict, dict]:
    """Fail closed unless one immutable report/evidence/Docs/render transaction agrees."""
    if report.get("date") != report_date or report.get("time") != "08:00":
        raise ValidationFailure("STAGING_TARGET_SLOT_MISMATCH")
    report_id = f"{report_date}_08-00"
    if report.get("report_id") not in (None, report_id):
        raise ValidationFailure("STAGING_REPORT_ID_MISMATCH")
    if report.get("report_status") != "DOC_READBACK_PASS":
        raise ValidationFailure("STAGING_CANONICAL_REPORT_NOT_READBACK_VERIFIED")
    try:
        evidence = validate_stored_slot_evidence(evidence_bytes, report_date, "08:00")
        validate_receipt(receipt, report)
    except (ValueError, KeyError, TypeError) as exc:
        raise ValidationFailure("STAGING_PUBLICATION_EVIDENCE_INVALID", str(exc)) from exc
    original_body_hash = validate_original_body_evidence(
        original_body_evidence, report, evidence, receipt)

    publication = report.get("publicationEvidence") or {}
    evidence_links = {
        "evidenceId": evidence.get("evidenceId"),
        "snapshotId": (evidence.get("snapshot") or {}).get("snapshot_id"),
        "contextHash": evidence.get("contextHash"),
        "snapshotHash": evidence.get("snapshotHash"),
    }
    for key, evidence_value in evidence_links.items():
        if receipt.get(key) != evidence_value:
            raise ValidationFailure("STAGING_RECEIPT_EVIDENCE_MISMATCH", key)
        if publication.get(key) != receipt.get(key):
            raise ValidationFailure("STAGING_CANONICAL_RECEIPT_MISMATCH", key)
    if publication.get("bodyHash") != receipt.get("bodyHash"):
        raise ValidationFailure("STAGING_CANONICAL_RECEIPT_MISMATCH", "bodyHash")

    expected_hash = hashlib.sha256(str(report.get("fullText", "")).encode("utf-8")).hexdigest()
    if (not expected_hash or report.get("bodyHash") != expected_hash
            or docs_readback.get("fullText") != report.get("fullText")
            or docs_readback.get("bodyHash") != expected_hash
            or docs_readback.get("readback_source") != "Google Docs API body read by canonical importer"
            or docs_readback.get("receipt_status") != "PASS"
            or docs_readback.get("receipt_exact_match") is not True
            or docs_readback.get("report_id") != report_id
            or docs_readback.get("revision") != report.get("revision")
            or docs_readback.get("document_id") != receipt.get("driveFileId")
            or docs_readback.get("document_revision_id") != receipt.get("documentRevisionId")):
        raise ValidationFailure("STAGING_DOCS_BODY_OR_IDENTITY_MISMATCH")

    # Bind the unmodified canonical source to the exact frozen context/snapshot.
    # The renderer re-enters this same gate using the bound copy written by this
    # wrapper, so accept that copy only when it is byte-for-byte source-bound.
    if report.get("context") or report.get("snapshot"):
        bound = report
        if (bound.get("context") != evidence.get("context")
                or bound.get("snapshot") != evidence.get("snapshot")
                or bound.get("report_id") != report_id
                or bound.get("snapshot_id") != (evidence.get("snapshot") or {}).get("snapshot_id")):
            raise ValidationFailure("STAGING_BOUND_REPORT_EVIDENCE_MISMATCH")
    else:
        try:
            bound = assemble(report, evidence["context"], evidence["snapshot"])
        except (ValidationFailure, ValueError, KeyError, TypeError) as exc:
            raise ValidationFailure("STAGING_REPORT_EVIDENCE_BIND_FAILED", str(exc)) from exc
    if (bound.get("snapshot_id") != receipt.get("snapshotId")
            or canonical_hash(bound.get("context")) != evidence.get("contextHash")
            or canonical_hash(bound.get("snapshot")) != evidence.get("snapshotHash")):
        raise ValidationFailure("STAGING_BOUND_SNAPSHOT_MISMATCH")

    # The three scenario roles must be source-position validated and separately
    # mapped into the rendered panel 12. A review record is an explicit human gate.
    try:
        summary_result = validate_summary(bound, summary)
    except (ValidationFailure, ValueError, KeyError, TypeError) as exc:
        raise ValidationFailure("STAGING_SUMMARY_OR_SCENARIO_INVALID", str(exc)) from exc
    role_claims = {claim.get("scenario_role"): claim for claim in summary.get("claims", [])
                   if claim.get("panel") == 12}
    expected_roles = {
        "main": "main_scenario",
        "upside": "alternative_scenario",
        "downside": "invalidation_trigger",
    }
    facts = {fact.get("id"): fact for fact in view.get("facts", [])}
    chains = view.get("cards", [{}] * 12)[11].get("chains", []) if len(view.get("cards", [])) > 11 else []
    if len(chains) != 3:
        raise ValidationFailure("STAGING_PANEL12_ROLE_COUNT")
    for chain in chains:
        role = expected_roles.get(chain.get("scenario"))
        if not role or chain.get("scenario_role") != role:
            raise ValidationFailure("STAGING_PANEL12_ROLE_MAPPING_INVALID")
        claim = role_claims.get(role)
        if not claim or chain.get("summary_claim_id") != claim.get("id"):
            raise ValidationFailure("STAGING_PANEL12_SUMMARY_LINK_MISSING", role)
        field_refs = chain.get("field_refs")
        if not isinstance(field_refs, dict):
            raise ValidationFailure("STAGING_PANEL12_FIELD_REFS_MISSING", role)
        node_refs = {node.get("ref") for node in chain.get("nodes", []) if isinstance(node, dict)}
        for field in ("condition", "development", "market_impact"):
            ref = field_refs.get(field, {}).get("ref") if isinstance(field_refs.get(field), dict) else None
            fact = facts.get(ref)
            if not fact or ref not in node_refs:
                raise ValidationFailure("STAGING_PANEL12_FIELD_NOT_RENDERED", {"role": role, "field": field})
            start, end = fact.get("start"), fact.get("end")
            source_refs = claim.get("field_source_refs", {}).get(field, [])
            if not source_refs or any(not (start <= source.get("start", -1) < source.get("end", -1) <= end)
                                      for source in source_refs):
                raise ValidationFailure("STAGING_PANEL12_SOURCE_POSITION_NOT_COVERED", {"role": role, "field": field})

    review_expected = {
        "status": "PASS",
        "report_id": report_id,
        "revision": report.get("revision"),
        "bodyHash": report.get("bodyHash"),
        "snapshot_id": bound.get("snapshot_id"),
        "summary_sha256": canonical_hash(summary),
    }
    if any(scenario_review.get(key) != value for key, value in review_expected.items()):
        raise ValidationFailure("STAGING_HUMAN_SCENARIO_REVIEW_MISSING_OR_STALE")
    if not scenario_review.get("reviewer") or not scenario_review.get("reviewed_at"):
        raise ValidationFailure("STAGING_HUMAN_SCENARIO_REVIEW_IDENTITY_MISSING")
    if scenario_review.get("roles") != {
            role: {"condition": "PASS", "development": "PASS", "market_impact": "PASS"}
            for role in ("main_scenario", "alternative_scenario", "invalidation_trigger")
    }:
        raise ValidationFailure("STAGING_HUMAN_SCENARIO_REVIEW_INCOMPLETE")

    assessment = preflight_check(bound, view, docs_readback=docs_readback,
                                 require_docs_readback=True)
    if assessment["status"] != "READY_FOR_CANONICAL_VALIDATION":
        raise ValidationFailure("STAGING_PREFLIGHT_BLOCKED", assessment["missing_or_unverified"])
    try:
        projection = validate_projection(bound, view, fixture=False, spec=spec)
    except (ValidationFailure, ValueError, KeyError, TypeError) as exc:
        raise ValidationFailure("STAGING_RENDER_CONTRACT_BLOCKED", str(exc)) from exc
    transaction = {
        "report_id": report_id,
        "revision": report.get("revision"),
        "bodyHash": expected_hash,
        "originalBodyHash": original_body_hash,
        "snapshot_id": bound.get("snapshot_id"),
        "contextHash": evidence.get("contextHash"),
        "snapshotHash": evidence.get("snapshotHash"),
        "acquisitionHash": evidence.get("acquisitionSource", {}).get("contentHash"),
        "evidenceId": evidence.get("evidenceId"),
        "cutoff": (evidence.get("context") or {}).get("data_cutoff"),
        "source": (evidence.get("acquisitionSource") or {}).get("path"),
        "document_id": receipt.get("driveFileId"),
        "document_revision_id": receipt.get("documentRevisionId"),
        "viewHash": canonical_hash(view),
        "specHash": canonical_hash(spec),
        "summaryHash": canonical_hash(summary),
        "scenarioReviewHash": canonical_hash(scenario_review),
    }
    transaction["transaction_id"] = canonical_hash(transaction)
    return bound, {"preflight": assessment, "summary": summary_result,
                   "projection": projection, "transaction": transaction}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Explicit target date YYYY-MM-DD")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--original-body-evidence", type=Path, required=True,
                        help="G2_DRAFT_NOT_SAVED artifact captured before the Docs save")
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--view", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--scenario-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node", default="node")
    parser.add_argument("--browser", help="Optional locally installed browser executable")
    args = parser.parse_args()
    try:
        report = _read_json(args.report)
        receipt = _read_json(args.receipt)
        original_body_evidence = _read_json(args.original_body_evidence)
        evidence_bytes = args.evidence.read_bytes()
        summary, view, spec = _read_json(args.summary), _read_json(args.view), _read_json(args.spec)
        scenario_review = _read_json(args.scenario_review)
        docs_readback = docs_readback_from_verified_import(report, receipt)
        bound, result = validate_transaction(
            report=report, evidence_bytes=evidence_bytes, receipt=receipt,
            docs_readback=docs_readback, summary=summary, view=view, spec=spec,
            scenario_review=scenario_review, original_body_evidence=original_body_evidence,
            report_date=args.date)
        if args.output.exists():
            raise ValidationFailure("STAGING_OUTPUT_EXISTS")
        args.output.mkdir(parents=True)
        bound_path = args.output / "bound-report.json"
        readback_path = args.output / "docs-readback.json"
        evidence_path = args.output / "slot-evidence.json"
        receipt_path = args.output / "publication-receipt.json"
        original_body_path = args.output / "pre-save-original-body.json"
        summary_path = args.output / "summary.json"
        scenario_review_path = args.output / "scenario-review.json"
        bound_path.write_text(json.dumps(bound, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        readback_path.write_text(json.dumps(docs_readback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        evidence_path.write_bytes(evidence_bytes)
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        original_body_path.write_text(json.dumps(original_body_evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        view_path = args.output / "view.json"
        spec_path = args.output / "spec.json"
        view_path.write_text(json.dumps(view, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        scenario_review_path.write_text(json.dumps(scenario_review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        render_out = args.output / "render"
        command = [sys.executable, str(Path(__file__).with_name("render_morning_infographic.py")),
                   "render", "--report", str(bound_path), "--view", str(view_path),
                   "--spec", str(spec_path), "--docs-readback", str(readback_path),
                   "--slot-evidence", str(evidence_path), "--publication-receipt", str(receipt_path),
                   "--summary", str(summary_path), "--scenario-review", str(scenario_review_path),
                   "--output", str(render_out), "--node", args.node]
        if args.browser:
            command += ["--browser", args.browser]
        subprocess.run(command, check=True)
        png_files = sorted((render_out / "png").glob("*.png"))
        if not png_files:
            raise ValidationFailure("STAGING_RENDER_PNG_MISSING")
        png_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in png_files}
        manifest = {
            "artifact_type": "LOCAL_DRAFT_INFOGRAPHIC_VALIDATION",
            "status": "PASS_FOR_LOCAL_REVIEW",
            "publish_allowed": False,
            "debug_preview": True,
            "transaction": result["transaction"],
            "scenario_roles": summary.get("critical_roles_required"),
            "scenario_review": {key: scenario_review[key] for key in
                                ("status", "reviewer", "reviewed_at", "summary_sha256")},
            "render": {"png_sha256": png_hashes, "renderer": "existing HTML/SVG + Playwright renderer"},
            "browser": "PASS_CUSTOM_PLAYWRIGHT_CHROMIUM" if args.browser else "PASS_DEFAULT_PLAYWRIGHT_CHROMIUM",
        }
        (args.output / "validation-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": manifest["status"], "publish_allowed": False,
                          "transaction_id": result["transaction"]["transaction_id"],
                          "pngs": png_hashes}, ensure_ascii=False))
        return 0
    except (ValidationFailure, ValueError, KeyError, TypeError, OSError,
            json.JSONDecodeError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": getattr(exc, "reason", str(exc))},
                         ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
