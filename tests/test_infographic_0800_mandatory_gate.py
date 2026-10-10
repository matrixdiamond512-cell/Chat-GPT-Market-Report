from __future__ import annotations

import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from reporting.infographic_0800_fixtures import build_synthetic_0800_source
from reporting.infographic_0800_fixed import render_0800_fixed
from reporting.infographic_0800_generation_contract import (
    FIXED_CONFIG, PRODUCTION_GATES, build_0800_generation_attestation, evaluate_0800_production_candidate,
    provenance_banner, validate_0800_generation_contract, write_0800_qa_evidence,
)
from reporting.infographic_0800_publication_gate import (
    authorize_0800_action, validate_0800_publication_report, verify_changed_0800_reports,
)


def _ready_payload(provenance: str = "LIVE_CAPTURED") -> dict:
    source = build_synthetic_0800_source(snapshot_provenance=provenance)
    source["synthetic_fixture"] = provenance == "SYNTHETIC_FIXTURE"
    source["source_type"] = "SYNTHETIC_FIXTURE" if source["synthetic_fixture"] else "GOOGLE_DOCS"
    return source


def _report_with_receipt() -> dict:
    source = _ready_payload()
    qa = validate_0800_generation_contract(source)
    receipt = build_0800_generation_attestation(source, qa)
    return {"date": source["report_date"], "time": "08:00", "fullText": source["body_text"],
            "infographicGenerationQa": receipt}


class Infographic0800MandatoryGateTests(unittest.TestCase):
    def test_qa_fail_blocks_docs_png_portal_and_production_json(self):
        report = {"date": "2099-01-01", "time": "08:00", "fullText": "missing contract"}
        for action in ("DOCS_SAVE", "PNG_GENERATION", "PORTAL_REFLECTION", "PRODUCTION_JSON_WRITE"):
            with self.subTest(action=action):
                result = authorize_0800_action(report, action)
                self.assertEqual("BLOCKED", result["status"])
                self.assertFalse(result["allowed"])

    def test_synthetic_cannot_pass_production_publication_gate(self):
        source = _ready_payload("SYNTHETIC_FIXTURE")
        qa = validate_0800_generation_contract(source)
        source["synthetic_fixture"] = True
        source["source_type"] = "SYNTHETIC_FIXTURE"
        receipt = build_0800_generation_attestation(source, qa)
        report = {"date": source["report_date"], "time": "08:00", "fullText": source["body_text"],
                  "synthetic_fixture": True, "infographicGenerationQa": receipt}
        self.assertEqual("BLOCKED", validate_0800_publication_report(report)["status"])
        self.assertEqual("SYNTHETIC_FIXTURE", provenance_banner("SYNTHETIC_FIXTURE"))

    def test_provenance_banner_values_are_distinct_and_exact(self):
        self.assertEqual("SOURCE_RECONSTRUCTED", provenance_banner("SOURCE_RECONSTRUCTED"))
        self.assertEqual("LIVE_CAPTURED", provenance_banner("LIVE_CAPTURED"))
        self.assertEqual("SYNTHETIC_FIXTURE", provenance_banner("SYNTHETIC_FIXTURE"))

    def test_renderer_does_not_allow_live_bypass_without_pre_render_qa(self):
        source = _ready_payload("LIVE_CAPTURED")
        result = render_0800_fixed(source, draft_preview=True)
        self.assertEqual("BLOCKED", result["status"])
        self.assertIsNone(result["image_bytes"])
        self.assertIn("PRE_RENDER_0800_QA_REQUIRED_OR_IDENTITY_MISMATCH", result["errors"])

    def test_renderer_attestation_mismatch_blocks_live_output(self):
        source = _ready_payload("LIVE_CAPTURED")
        source["generation_qa_attestation"] = {"status": "PASS", "body_sha256": "0" * 64}
        result = render_0800_fixed(source, draft_preview=True)
        self.assertEqual("BLOCKED", result["status"])
        self.assertIsNone(result["image_bytes"])

    def test_synthetic_banner_matches_snapshot_provenance(self):
        result = render_0800_fixed(_ready_payload("SYNTHETIC_FIXTURE"), draft_preview=True)
        self.assertEqual("SYNTHETIC_FIXTURE", result["provenance_banner"])
        self.assertEqual(result["provenance_banner"], result["snapshot_provenance"])

    def test_reconstructed_banner_matches_snapshot_provenance(self):
        result = render_0800_fixed(_ready_payload("SOURCE_RECONSTRUCTED"), draft_preview=True)
        self.assertEqual("SOURCE_RECONSTRUCTED", result["provenance_banner"])
        self.assertEqual(result["provenance_banner"], result["snapshot_provenance"])

    def test_live_banner_is_rendered_only_through_generation_qa(self):
        source = _ready_payload("LIVE_CAPTURED")
        result = render_0800_fixed(source, draft_preview=True)
        self.assertEqual("BLOCKED", result["status"])
        qa = validate_0800_generation_contract(source)
        source["generation_qa_attestation"] = build_0800_generation_attestation(source, qa)
        result = render_0800_fixed(source, draft_preview=True)
        self.assertEqual("LIVE_CAPTURED", result["provenance_banner"])
        self.assertEqual(result["provenance_banner"], result["snapshot_provenance"])

    def test_all_pass_live_source_can_become_candidate_only_with_bound_review(self):
        source = _ready_payload("LIVE_CAPTURED")
        image_hash = hashlib.sha256(b"test image bytes").hexdigest()
        source["visual_review_attestation"] = {
            "status": "PASS", "verification_status": "VERIFIED", "report_id": source["report_id"],
            "body_sha256": source["body_hash"], "image_sha256": image_hash,
            "template_id": FIXED_CONFIG["template_id"], "review_id": "review-fixture",
            "reviewed_at": "2099-01-01T08:10:00+09:00", "trusted_provider": "trusted-fixture-provider",
        }
        result = evaluate_0800_production_candidate(
            source, {gate: "PASS" for gate in PRODUCTION_GATES}, image_sha256=image_hash,
        )
        self.assertEqual("PASS", result["status"])
        self.assertTrue(result["production_candidate"])

    def test_synthetic_never_becomes_candidate_even_when_every_gate_is_pass(self):
        source = _ready_payload("SYNTHETIC_FIXTURE")
        image_hash = hashlib.sha256(b"fixture image").hexdigest()
        source["visual_review_attestation"] = {"status": "PASS", "verification_status": "VERIFIED",
            "report_id": source["report_id"], "body_sha256": source["body_hash"], "image_sha256": image_hash,
            "template_id": FIXED_CONFIG["template_id"], "review_id": "review-fixture",
            "reviewed_at": "2099-01-01T08:10:00+09:00", "trusted_provider": "trusted-fixture-provider"}
        result = evaluate_0800_production_candidate(source,
            {gate: "PASS" for gate in PRODUCTION_GATES}, image_sha256=image_hash)
        self.assertEqual("BLOCKED", result["status"])
        self.assertFalse(result["production_candidate"])

    def test_reconstructed_source_remains_draft_even_when_other_gates_are_pass(self):
        source = _ready_payload("SOURCE_RECONSTRUCTED")
        result = evaluate_0800_production_candidate(
            source, {gate: "PASS" for gate in PRODUCTION_GATES}, image_sha256="1" * 64,
        )
        self.assertEqual("BLOCKED", result["status"])
        self.assertIn("PROVENANCE_NOT_LIVE_CAPTURED", result["errors"])

    def test_missing_or_changed_report_receipt_blocks_publication(self):
        report = _report_with_receipt()
        self.assertEqual("PASS", validate_0800_publication_report(report)["status"])
        changed = copy.deepcopy(report)
        changed["fullText"] += " changed"
        self.assertEqual("BLOCKED", validate_0800_publication_report(changed)["status"])

    def test_changed_08_report_cannot_bypass_receipt_via_index_workflow(self):
        before = [{"date": "2099-01-01", "time": "08:00", "fullText": "old"}]
        after = before + [{"date": "2099-01-02", "time": "08:00", "fullText": "new"}]
        result = verify_changed_0800_reports(before, after)
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual(["2099-01-02_08-00"], result["report_ids"])

    def test_unchanged_historical_08_report_does_not_get_rewritten_by_gate(self):
        historical = {"date": "2026-10-09", "time": "08:00", "fullText": "unchanged historical body"}
        self.assertEqual("PASS", verify_changed_0800_reports([historical], [historical])["status"])

    def test_qa_and_identity_hashes_are_persisted_under_nonproduction_artifacts(self):
        source = _ready_payload("SYNTHETIC_FIXTURE")
        qa = validate_0800_generation_contract(source)
        result = {"generation_qa": qa, "required_validation_gates": {"PRODUCTION_READY": "BLOCKED"}}
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as temp_root:
            path = write_0800_qa_evidence(source, result, temp_root)
            import json
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(source["report_id"], record["report_id"])
            self.assertEqual(source["body_hash"], record["body_sha256"])
            self.assertIsNone(record["infographic_sha256"])
            self.assertEqual("SYNTHETIC_FIXTURE", record["snapshot_provenance"])

    def test_managed_apps_script_workflow_and_cli_entries_are_connected(self):
        web = (ROOT / "apps-script/MarketReportWebSync.gs").read_text(encoding="utf-8")
        auto = (ROOT / "apps-script/MarketReportAutoPublish.gs").read_text(encoding="utf-8")
        prepublish = (ROOT / "apps-script/MarketReportPrePublishValidation.gs").read_text(encoding="utf-8")
        history = (ROOT / "apps-script/MarketReportHistoricalImport.gs").read_text(encoding="utf-8")
        structured = (ROOT / "apps-script/MarketReportStructuredImport.gs").read_text(encoding="utf-8")
        menu = (ROOT / "apps-script/MarketReportMenu.gs").read_text(encoding="utf-8")
        self.assertIn("requireMarketReport0800GenerationQa_(report)", web)
        self.assertIn("Strict report pre-publish QA is unavailable; publication is blocked.", auto)
        self.assertIn("requireMarketReport0800GenerationQa_(report)", prepublish)
        self.assertIn("requireMarketReport0800GenerationQa_(report)", history)
        self.assertIn("requireMarketReport0800GenerationQa_(report)", structured)
        self.assertIn("create0800ReportFromQaJsonPrompt", menu)
        for workflow in ("structure-market-reports.yml", "sync-latest-report-publication.yml",
                         "sync-latest-report-watchdog.yml", "rebuild-report-history-index.yml"):
            content = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
            self.assertIn("check_0800_publication_gate.py", content, workflow)
        deploy = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
        self.assertIn("--require-latest-0800", deploy)


if __name__ == "__main__":
    unittest.main()
