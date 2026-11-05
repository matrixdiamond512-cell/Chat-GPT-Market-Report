from __future__ import annotations

import json
import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from contextlib import redirect_stdout

from scripts.reporting.issuance_preflight import (run_preflight, run_configuration_diagnostic,
    _verify_g2_producer_identity)
from scripts.run_0800_issuance import (load_bundle, main as issuance_main, require_08_issuance_owner)
from scripts.reporting.issuance_pipeline import IssuanceBlocked


class FakeGitHub:
    def __init__(self, reviewers=1):
        self.reviewers = reviewers
        self.calls = []
    def get(self, path):
        self.calls.append(path)
        if path == "":
            return {"full_name": "acme/report", "permissions": {"push": True}}
        if path.startswith("/environments/"):
            rows = [{"type": "required_reviewers", "reviewers": [{"login": "reviewer"}] * self.reviewers}]
            return {"protection_rules": rows}
        return {"state": "active"}


class FakeGoogle:
    def __init__(self):
        self.methods = []
        self.principal_email = "preflight-reader@market-prod.iam.gserviceaccount.com"
    class Response:
        ok = True
        def __init__(self, payload): self.payload = payload
        def json(self): return self.payload
    def request(self, method, url, **kwargs):
        self.methods.append(method)
        is_docs = "/docs-folder" in url
        folder_id = "docs-folder" if is_docs else "root-folder"
        return self.Response({"id": folder_id, "parents": ["root-folder"] if is_docs else [],
                              "mimeType": "application/vnd.google-apps.folder", "trashed": False,
                              "capabilities": {"canAddChildren": is_docs}})
    def get_exact_evidence(self, bucket, object_name, generation):
        self.methods.append("GET_GCS_GENERATION")
        return bucket == "market-evidence" and object_name == "evidence/slot.json" and generation == "9"
    def read_exact_json_object(self, bucket, object_name, generation):
        self.methods.append("READ_GCS:" + object_name)
        full_text = "Synthetic test-only G2 body"
        body_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
        if object_name == "g2/slot.json":
            return {"generation": "10", "created_at": "2026-11-05T08:06:00+09:00",
                    "sha256": "a" * 64, "data": {"g2": {
                        "report_id": "2026-11-05_08-00", "revision": 1,
                        "frozen_at": "2026-11-05T08:05:00+09:00", "body_hash": body_hash,
                        "scenario_review": {"report_id": "2026-11-05_08-00", "body_hash": body_hash,
                            "reviewed_at": "2026-11-05T08:04:00+09:00"},
                        "report": {"report_id": "2026-11-05_08-00", "date": "2026-11-05",
                            "time": "08:00", "revision": 1, "fullText": full_text,
                            "bodyHash": body_hash}},
                        "evidence_ref": {"object": "evidence/slot.json", "generation": 9}}}
        return {"generation": "9", "created_at": "2026-11-05T07:40:00+09:00",
                "sha256": "b" * 64, "data": {"reportId": "2026-11-05_08-00",
                    "revision": 1, "evidenceId": "ev-1",
                    "snapshot": {"snapshot_id": "snap-1"}}}
    def test_claim_permissions(self, bucket):
        self.methods.append("TEST_IAM_PERMISSIONS")
        return {"read": bucket == "market-claims", "create": bucket == "market-claims"}


class IssuancePreflightTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "GITHUB_ACTIONS": "true", "GITHUB_REF": "refs/heads/main",
            "GITHUB_REPOSITORY": "acme/report", "REPORT_PREFLIGHT_GITHUB_TOKEN": "read-only-token",
            "REPORT_ISSUANCE_ENVIRONMENT": "report-publication",
            "REPORT_ISSUANCE_WIF_PROVIDER": "projects/123/locations/global/workloadIdentityPools/preflight/providers/github",
            "REPORT_ISSUANCE_READONLY_SERVICE_ACCOUNT": "preflight-reader@market-prod.iam.gserviceaccount.com",
            "REPORT_PAGES_BASE_URL": "https://example.invalid", "REPORT_EVIDENCE_PROJECT_ID": "market-prod",
            "REPORT_EVIDENCE_BUCKET": "market-evidence", "REPORT_EVIDENCE_OBJECT": "evidence/slot.json",
            "REPORT_EVIDENCE_GENERATION": "9", "REPORT_ISSUANCE_REPORT_ID": "2026-11-05_08-00",
            "REPORT_ISSUANCE_REVISION": "1", "REPORT_ISSUANCE_G2_BUNDLE_BUCKET": "market-evidence",
            "REPORT_ISSUANCE_G2_BUNDLE_OBJECT": "g2/slot.json", "REPORT_ISSUANCE_G2_BUNDLE_GENERATION": "10",
            "REPORT_ISSUANCE_CLAIM_BUCKET": "market-claims",
            "REPORT_ISSUANCE_DOCS_FOLDER_ID": "docs-folder", "REPORT_ISSUANCE_ROOT_FOLDER_ID": "root-folder",
            "REPORT_ISSUANCE_APPROVED": "true", "REPORT_ISSUANCE_WRITE_ENABLED": "true",
            "REPORT_ISSUANCE_CONTENTS_WRITE_VERIFIED": "true",
        }

    def test_admin_verified_read_only_preflight_is_ready(self):
        github, google = FakeGitHub(), FakeGoogle()
        result = run_preflight(env=self.env, github=github, google_probe=google, dom_runtime=True, pages_probe=lambda _url: True)
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(result["mode"], "AUTHENTICATED_READ_ONLY")
        self.assertEqual(result["checks"]["g2_evidence_binding"]["status"], "PASS")
        self.assertEqual(result["checks"]["issuance_owner"]["status"], "BLOCKED")
        self.assertEqual(result["checks"]["github"]["status"], "PASS")
        self.assertEqual(result["checks"]["github"]["credential_contents_write_permission"], "ADMIN_ATTESTED")
        self.assertFalse(result["secrets_emitted"])
        self.assertNotIn("read-only-token", json.dumps(result))
        self.assertEqual(google.methods[:2], ["GET", "GET"])
        self.assertIn("READ_GCS:g2/slot.json", google.methods)
        self.assertIn("READ_GCS:evidence/slot.json", google.methods)
        self.assertTrue(all(method == "GET" for method in google.methods[:2]))

    def test_g2_producer_identity_requires_matching_audit_record_not_env_self_report(self):
        class AuditGoogle(FakeGoogle):
            def read_g2_creation_audit(self, *, bucket, object_name, generation):
                return {"principal_email": "report-issuer@acme.iam.gserviceaccount.com",
                        "resource_name": f"projects/_/buckets/{bucket}/objects/{object_name}",
                        "generation": generation, "timestamp": "2026-11-04T23:06:00Z"}
        expected = "report-issuer@acme.iam.gserviceaccount.com"
        env = {**self.env, "REPORT_ISSUANCE_G2_PRODUCER_SERVICE_ACCOUNT": expected,
               "REPORT_ISSUANCE_G2_BUNDLE_BUCKET": "market-g2",
               "REPORT_ISSUANCE_G2_BUNDLE_OBJECT": "g2/slot.json",
               "REPORT_ISSUANCE_G2_BUNDLE_GENERATION": "10"}
        binding = {"status": "PASS", "g2_bundle_generation": "10",
                   "g2_bundle_sha256": "a" * 64,
                   "g2_frozen_at": "2026-11-05T08:05:00+09:00",
                   "g2_window_end": "2026-11-05T08:40:00+09:00"}
        verified = _verify_g2_producer_identity(env=env, google_probe=AuditGoogle(),
                                                 binding=binding)
        self.assertEqual(verified["status"], "PASS")
        self.assertEqual(verified["producer_principal"], expected)
        unverified = _verify_g2_producer_identity(env=env, google_probe=FakeGoogle(),
                                                  binding=binding)
        self.assertEqual(unverified["status"], "BLOCKED")
        self.assertEqual(unverified["reason"], "G2_CREATOR_AUDIT_READER_UNAVAILABLE")

        class WrongPrincipalGoogle(AuditGoogle):
            def read_g2_creation_audit(self, *, bucket, object_name, generation):
                event = super().read_g2_creation_audit(bucket=bucket, object_name=object_name,
                                                       generation=generation)
                event["principal_email"] = "other@acme.iam.gserviceaccount.com"
                return event
        wrong = _verify_g2_producer_identity(env=env, google_probe=WrongPrincipalGoogle(),
                                              binding=binding)
        self.assertEqual(wrong["status"], "BLOCKED")
        self.assertEqual(wrong["reason"], "G2_CREATOR_AUDIT_IDENTITY_MISMATCH")

    def test_object_contents_alone_do_not_prove_a_trusted_g2_producer(self):
        with tempfile.TemporaryDirectory() as folder:
            owner_path = Path(folder) / "issuance_ownership.json"
            owner_path.write_text(json.dumps({"schemaVersion": 1,
                "slotOwners": {"08:00": "g2_issuance_cli"}}), encoding="utf-8")
            env = {**self.env, "REPORT_ISSUANCE_OWNER_CONFIG_PATH": str(owner_path),
                   "REPORT_ISSUANCE_G2_PRODUCER_SERVICE_ACCOUNT":
                       "report-issuer@acme.iam.gserviceaccount.com"}
            result = run_preflight(env=env, github=FakeGitHub(), google_probe=FakeGoogle(),
                                   dom_runtime=True, pages_probe=lambda _url: True)
        self.assertEqual(result["checks"]["g2_evidence_binding"]["status"], "PASS")
        self.assertEqual(result["checks"]["g2_producer_identity"]["status"], "BLOCKED")
        self.assertEqual(result["checks"]["g2_producer_identity"]["reason"],
                         "G2_CREATOR_AUDIT_READER_UNAVAILABLE")
        self.assertFalse(result["checks"]["g2_producer_identity"]["producer_identity_verified"])
        self.assertEqual(result["status"], "NOT_READY")

    def test_preflight_rejects_pinned_g2_object_created_after_slot(self):
        class LateBundle(FakeGoogle):
            def read_exact_json_object(self, bucket, object_name, generation):
                result = super().read_exact_json_object(bucket, object_name, generation)
                if object_name == "g2/slot.json":
                    result["created_at"] = "2026-11-05T08:41:00+09:00"
                return result
        with tempfile.TemporaryDirectory() as folder:
            owner_path = Path(folder) / "issuance_ownership.json"
            owner_path.write_text(json.dumps({"schemaVersion": 1,
                "slotOwners": {"08:00": "g2_issuance_cli"}}), encoding="utf-8")
            env = {**self.env, "REPORT_ISSUANCE_OWNER_CONFIG_PATH": str(owner_path)}
            result = run_preflight(env=env, github=FakeGitHub(), google_probe=LateBundle(),
                                   dom_runtime=True, pages_probe=lambda _url: True)
        self.assertEqual(result["checks"]["g2_evidence_binding"]["status"], "BLOCKED")
        self.assertEqual(result["checks"]["g2_evidence_binding"]["reason"],
                         "G2_BUNDLE_CREATED_AFTER_REPORT_WINDOW")
        self.assertEqual(result["status"], "NOT_READY")

    def test_configuration_diagnostic_is_secret_free_and_never_ready(self):
        result = run_configuration_diagnostic(env={"GITHUB_REPOSITORY": "acme/report"})
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(result["mode"], "CONFIGURATION_DIAGNOSTIC")
        self.assertEqual(result["checks"]["g2_producer"]["reason"], "BLOCKED_G2_PRODUCER_MISSING")
        self.assertEqual(result["checks"]["cloud_and_github_permissions"]["status"], "NOT_RUN")
        self.assertFalse(result["secrets_emitted"])

    def test_google_principal_mismatch_blocks_preflight(self):
        google = FakeGoogle()
        google.principal_email = "different@market-prod.iam.gserviceaccount.com"
        result = run_preflight(env=self.env, github=FakeGitHub(), google_probe=google,
                               dom_runtime=True, pages_probe=lambda _url: True)
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(result["checks"]["google"]["status"], "BLOCKED")
        self.assertFalse(result["checks"]["google"]["expected_principal_match"])

    def test_protected_preflight_uses_wif_without_service_account_key(self):
        from pathlib import Path

        workflow = Path(".github/workflows/0800-issuance-production-preflight.yml").read_text(encoding="utf-8")
        source = Path("scripts/reporting/issuance_preflight.py").read_text(encoding="utf-8")
        self.assertIn("google-github-actions/auth@v3", workflow)
        self.assertIn("REPORT_PREFLIGHT_GITHUB_TOKEN: ${{ github.token }}", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("REPORT_ISSUANCE_READONLY_SERVICE_ACCOUNT", workflow)
        self.assertNotIn("GOOGLE_SERVICE_ACCOUNT_JSON", workflow)
        self.assertNotIn("GOOGLE_SERVICE_ACCOUNT_JSON", source)

    def test_missing_required_environment_reviewer_blocks_readiness(self):
        result = run_preflight(env=self.env, github=FakeGitHub(reviewers=0), google_probe=FakeGoogle(), dom_runtime=True)
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(result["checks"]["github"]["status"], "BLOCKED")

    def test_approved_environment_variable_cannot_replace_actual_reviewer_gate(self):
        # The self-asserted variable must not pass when GitHub reports no reviewers.
        result = run_preflight(env=self.env, github=FakeGitHub(reviewers=0),
                               google_probe=FakeGoogle(), dom_runtime=True, pages_probe=lambda _url: True)
        protected = result["checks"]["protected_execution"]
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(protected["status"], "BLOCKED")
        self.assertFalse(protected["reviewer_gate_configured"])
        self.assertEqual(protected["approval_for_current_run"], "NOT_INFERRED")
        self.assertTrue(protected["approval_environment_variable_ignored"])

    def test_environment_configuration_readiness_does_not_claim_run_approval(self):
        env = {**self.env, "REPORT_ISSUANCE_APPROVED": "false",
               "REPORT_ISSUANCE_WRITE_ENABLED": "false"}
        result = run_preflight(env=env, github=FakeGitHub(reviewers=1),
                               google_probe=FakeGoogle(), dom_runtime=True, pages_probe=lambda _url: True)
        protected = result["checks"]["protected_execution"]
        self.assertEqual(protected["status"], "PASS")
        self.assertEqual(protected["approval_for_current_run"], "NOT_INFERRED")
        self.assertTrue(protected["approval_environment_variable_ignored"])

    def test_unattested_fine_grained_contents_scope_remains_unknown(self):
        env = {**self.env, "REPORT_ISSUANCE_CONTENTS_WRITE_VERIFIED": "false"}
        result = run_preflight(env=env, github=FakeGitHub(), google_probe=FakeGoogle(), dom_runtime=True, pages_probe=lambda _url: True)
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(result["checks"]["github"]["credential_contents_write_permission"], "UNKNOWN")
        self.assertEqual(result["checks"]["github"]["status"], "UNKNOWN")

    def test_wrong_environment_is_blocked_by_preflight(self):
        env = {**self.env, "REPORT_ISSUANCE_ENVIRONMENT": "developer"}
        result = run_preflight(env=env, github=FakeGitHub(), google_probe=FakeGoogle(), dom_runtime=True)
        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(result["checks"]["protected_execution"]["status"], "BLOCKED")

    def test_08_entrypoint_rejects_wrong_slot_before_any_cloud_client_is_created(self):
        bundle = {"g2": {"report": {"date": "2026-11-05", "time": "12:00"}},
                  "evidence_ref": {"object": "evidence/slot.json", "generation": 9}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bundle.json"
            path.write_text(json.dumps(bundle), encoding="utf-8")
            with self.assertRaisesRegex(IssuanceBlocked, "TODAY_WEEKDAY_0800"):
                load_bundle(path)

    def test_08_entrypoint_rejects_invalid_date_before_cloud_client_is_created(self):
        bundle = {"g2": {"report": {"date": "not-a-date", "time": "08:00"}},
                  "evidence_ref": {"object": "evidence/slot.json", "generation": 9}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bundle.json"
            path.write_text(json.dumps(bundle), encoding="utf-8")
            with self.assertRaisesRegex(IssuanceBlocked, "ISSUANCE_REPORT_SLOT_INVALID"):
                load_bundle(path)

    def test_module_entrypoint_without_input_is_safely_blocked_without_credentials(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
            status = issuance_main([])
        payload = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertEqual(payload["reason"], "BLOCKED_G2_PRODUCER_MISSING")
        self.assertNotIn("secret", output.getvalue().lower())

    def test_missing_bundle_reports_missing_g2_producer(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
            status = issuance_main([])
        result = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(result["reason"], "BLOCKED_G2_PRODUCER_MISSING")

    def test_non_object_owner_config_blocks_without_crashing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "issuance_ownership.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(IssuanceBlocked, "ISSUANCE_OWNER_CONFIG_INVALID"):
                require_08_issuance_owner(path)
            env = {**self.env, "REPORT_ISSUANCE_OWNER_CONFIG_PATH": str(path)}
            result = run_preflight(env=env, github=FakeGitHub(), google_probe=FakeGoogle(),
                                   dom_runtime=True, pages_probe=lambda _url: True)
        self.assertEqual(result["checks"]["issuance_owner"]["status"], "BLOCKED")
        self.assertIsNone(result["checks"]["issuance_owner"]["owner"])
        self.assertEqual(result["status"], "NOT_READY")

    def test_08_ownership_is_shared_and_cli_stays_blocked_until_explicit_switch(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "issuance_ownership.json"
            path.write_text(json.dumps({"schemaVersion": 1,
                "slotOwners": {"08:00": "apps_script_legacy"}}), encoding="utf-8")
            with self.assertRaisesRegex(IssuanceBlocked, "ISSUANCE_OWNER_CONFLICT:08:00:apps_script_legacy"):
                require_08_issuance_owner(path)
            path.write_text(json.dumps({"schemaVersion": 1,
                "slotOwners": {"08:00": "g2_issuance_cli"}}), encoding="utf-8")
            self.assertEqual(require_08_issuance_owner(path), "g2_issuance_cli")

    def test_module_entrypoint_rejects_invalid_date_before_config_or_cloud_access(self):
        payload = {"g2": {"report": {"date": "not-a-date", "time": "08:00"}},
                   "evidence_ref": {"object": "evidence/slot.json", "generation": 9}}
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invalid-bundle.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
                status = issuance_main([str(path)])
        result = json.loads(output.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "ISSUANCE_REPORT_SLOT_INVALID")

    def test_entrypoint_reads_only_named_generation_and_returns_same_pinned_bytes(self):
        payload = {"g2": {
                       "report_id": "2026-11-05_08-00", "revision": 1,
                       "frozen_at": "2026-11-05T08:05:00+09:00",
                       "scenario_review": {"reviewed_at": "2026-11-05T08:04:00+09:00"},
                       "report": {"date": "2026-11-05", "time": "08:00"}},
                   "evidence_ref": {"object": "evidence/slot.json", "generation": 17}}
        envelope = {"evidence_object": {"generation": 17, "object": "evidence/slot.json"}}
        instant = datetime(2026, 11, 5, 8, 15, tzinfo=ZoneInfo("Asia/Tokyo"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bundle.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.dict("os.environ", {"REPORT_EVIDENCE_PROJECT_ID": "market-prod",
                                           "REPORT_EVIDENCE_BUCKET": "market-evidence"}), \
                 patch("scripts.run_0800_issuance.load_pinned_production_evidence", return_value=envelope) as read:
                result = load_bundle(path, now=instant)
        read.assert_called_once_with(project_id="market-prod", bucket_name="market-evidence",
                                     object_name="evidence/slot.json", generation=17)
        self.assertIs(result["evidence_object"], envelope["evidence_object"])


if __name__ == "__main__":
    unittest.main()

