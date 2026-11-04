from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.reporting.issuance_pipeline import IssuanceBlocked
from scripts.reporting.issuance_portal import (
    GitHubPagesVerifier, GitHubPortalPublisher, stage_pinned_evidence,
)
from test_issuance_pipeline import IssuancePipelineContractTests


class FakeImporter:
    def __init__(self, report, receipt=None):
        self.root = Path(".")
        self.report = report
        self.receipt = receipt or {"reportId": report["report_id"], "revision": report["revision"],
                                   "driveFileId": "doc-123", "documentRevisionId": "revision-7",
                                   "bodyHash": report["bodyHash"], "evidenceId": "evidence-1",
                                   "snapshotId": report["snapshot_id"]}
        self.calls = 0

    def import_exact(self, *, report, docs, evidence):
        self.calls += 1
        result = dict(self.report)
        result["sourceDocument"] = {"id": docs.document_id}
        result["sourceRevisionId"] = docs.document_revision_id
        return result, self.receipt


class FakeGitHub:
    def __init__(self, *, fail_write=False, fail_readback=False):
        self.fail_write = fail_write
        self.fail_readback = fail_readback
        self.calls = 0
        self.contents = None
        self.commit = "commit-1"

    def publish_files(self, *, expected_head, files, message):
        self.calls += 1
        if self.fail_write:
            raise IssuanceBlocked("GITHUB_WRITE_FAILED")
        if self.contents is not None and self.contents != files:
            raise IssuanceBlocked("GITHUB_CANONICAL_CONFLICT")
        self.contents = dict(files)
        return self.commit

    def verify_files(self, *, commit_sha, files):
        if self.fail_readback or self.contents != files:
            raise IssuanceBlocked("GITHUB_FILE_READBACK_FAILED")


class FakePages:
    def __init__(self, *, fail=False, mismatch=False, fail_first=False):
        self.fail = fail
        self.mismatch = mismatch
        self.fail_first = fail_first
        self.calls = 0

    def verify(self, *, report, commit_sha):
        self.calls += 1
        if self.fail or (self.fail_first and self.calls == 1):
            raise IssuanceBlocked("PAGES_DEPLOYMENT_FAILED")
        if self.mismatch:
            raise IssuanceBlocked("PAGES_PUBLIC_BODY_MISMATCH")
        return "pages-run-1", "https://example.invalid/reports/report.json"


class HttpResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self.ok = status < 400
        self._payload = payload
        self.content = b"{}" if payload is not None else b""

    def json(self):
        return self._payload


class WorkflowGateway:
    def __init__(self, conclusion="success"):
        self.conclusion = conclusion

    def workflow_runs(self, workflow, head_sha):
        return {"workflow_runs": [{"id": 88, "head_sha": head_sha, "run_number": 10,
                                   "status": "completed", "conclusion": self.conclusion}]}


class PublicSession:
    def __init__(self, report):
        self.report = report
        self.status = 200

    def get(self, url, *, timeout):
        return HttpResponse(self.status, self.report)


class DriveSession:
    def __init__(self, files):
        self.files = files
        self.queries = []

    def get(self, endpoint, *, params, timeout):
        self.queries.append(params["q"])
        return HttpResponse(200, {"files": self.files})


class IssuancePortalIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = IssuancePipelineContractTests()
        self.fixture.setUp()
        for name in ("report", "evidence", "bundle", "body_hash", "full_text"):
            setattr(self, name, getattr(self.fixture, name))

    def execute_pipeline(self, **kwargs):
        return self.fixture.execute_pipeline(**kwargs)

    def make_publisher(self, *, github=None, pages=None):
        report = dict(self.fixture.report)
        report.update({"evidence_id": self.fixture.evidence["evidenceId"], "snapshot_id": self.fixture.evidence["snapshot"]["snapshot_id"]})
        return GitHubPortalPublisher(
            importer=FakeImporter(report), github=github or FakeGitHub(),
            pages=pages or FakePages(), expected_head="main-sha",
        )

    def test_end_to_end_stubbed_import_commit_receipt_pages_and_public_body(self):
        github = FakeGitHub()
        pages = FakePages()
        result = self.execute_pipeline(portal=self.make_publisher(github=github, pages=pages))
        self.assertEqual(result["environment"], "TEST_ONLY")
        self.assertTrue(result["public_body_verified"])
        self.assertEqual(result["canonical_commit_sha"], "commit-1")
        self.assertEqual(github.calls, 1)
        self.assertEqual(pages.calls, 1)

    def test_github_write_failure_stops_pages(self):
        pages = FakePages()
        with self.assertRaisesRegex(IssuanceBlocked, "GITHUB_WRITE_FAILED"):
            self.execute_pipeline(portal=self.make_publisher(github=FakeGitHub(fail_write=True), pages=pages))
        self.assertEqual(pages.calls, 0)

    def test_receipt_or_canonical_readback_failure_stops_pages(self):
        pages = FakePages()
        with self.assertRaisesRegex(IssuanceBlocked, "GITHUB_FILE_READBACK_FAILED"):
            self.execute_pipeline(portal=self.make_publisher(github=FakeGitHub(fail_readback=True), pages=pages))
        self.assertEqual(pages.calls, 0)

    def test_pages_deploy_failure_does_not_claim_published(self):
        github = FakeGitHub()
        with self.assertRaisesRegex(IssuanceBlocked, "PAGES_DEPLOYMENT_FAILED") as caught:
            self.execute_pipeline(portal=self.make_publisher(github=github, pages=FakePages(fail=True)))
        self.assertEqual(github.calls, 1)
        self.assertIsNotNone(github.contents)  # canonical main commit requires reconcile/retry
        self.assertEqual(caught.exception.stage, "PAGES_DEPLOYMENT_AND_PUBLIC_READBACK")
        self.assertIn("GITHUB_CANONICAL_AND_RECEIPT_READBACK", caught.exception.completed_stages)
        self.assertTrue(caught.exception.retryable)

    def test_public_body_mismatch_is_not_published(self):
        with self.assertRaisesRegex(IssuanceBlocked, "PAGES_PUBLIC_BODY_MISMATCH"):
            self.execute_pipeline(portal=self.make_publisher(pages=FakePages(mismatch=True)))

    def test_concrete_pages_verifier_reads_the_exact_public_json_body(self):
        report = dict(self.fixture.report)
        report["report_id"] = report["report_id"]
        verifier = GitHubPagesVerifier(github=WorkflowGateway(), base_url="https://example.invalid",
                                       public_session=PublicSession(report), poll_interval=0)
        run_id, url = verifier.verify(report=report, commit_sha="commit-1")
        self.assertEqual(run_id, "88")
        self.assertTrue(url.endswith("2026-10-16_08-00.json"))

    def test_concrete_pages_verifier_rejects_failed_deploy_and_public_hash_mismatch(self):
        report = dict(self.fixture.report)
        with self.assertRaisesRegex(IssuanceBlocked, "PAGES_DEPLOYMENT_FAILED"):
            GitHubPagesVerifier(github=WorkflowGateway("failure"), base_url="https://example.invalid",
                                public_session=PublicSession(report), poll_interval=0).verify(
                                    report=report, commit_sha="commit-1")

    def test_strict_importer_queries_one_title_and_binds_exact_doc_revision(self):
        from scripts import sync_reports_from_drive as importer
        report = dict(self.fixture.report)
        report["evidence_id"] = self.fixture.evidence["evidenceId"]
        report["snapshot_id"] = self.fixture.evidence["snapshot"]["snapshot_id"]
        receipt = {"evidenceId": report["evidence_id"], "snapshotId": report["snapshot_id"]}
        item = {"id": "doc-123", "name": "マーケットレポート_2026-10-16_08-00",
                "appProperties": {"report_id": report["report_id"], "revision": "1",
                                  "body_hash": report["bodyHash"], "evidence_id": report["evidence_id"],
                                  "snapshot_id": report["snapshot_id"]}}
        rebuilt = {**report, "sourceRevisionId": "revision-7", "bodyHash": report["bodyHash"],
                   "fullText": report["fullText"], "sourceDocument": {"id": "doc-123"},
                   "title": "マーケットレポート｜2026/10/16（金）08:00",
                   "publicationEvidence": {"evidenceId": receipt["evidenceId"], "snapshotId": receipt["snapshotId"],
                                           "contextHash": "c", "snapshotHash": "s", "bodyHash": report["bodyHash"],
                                           "documentRevisionId": "revision-7"}}
        docs = type("Docs", (), {"document_id": "doc-123", "document_revision_id": "revision-7"})()
        session = DriveSession([item])
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(importer, "build_report", return_value=rebuilt), \
                patch.object(importer, "verify_issuance_evidence", return_value=receipt), \
                patch("scripts.reporting.publication_evidence.validate_receipt"):
            result, got_receipt = importer.import_exact_issuance_doc(Path(temp), report=report, docs=docs, session=session)
            self.assertEqual(result["report_id"], report["report_id"])
            self.assertEqual(got_receipt, receipt)
            self.assertEqual(len(session.queries), 1)
            self.assertIn("2026-10-16_08-00", session.queries[0])

    def test_strict_importer_rejects_duplicate_docs_and_changed_revision(self):
        from scripts import sync_reports_from_drive as importer
        report = dict(self.fixture.report)
        report["evidence_id"] = self.fixture.evidence["evidenceId"]
        report["snapshot_id"] = self.fixture.evidence["snapshot"]["snapshot_id"]
        item = {"id": "doc-123", "name": "マーケットレポート_2026-10-16_08-00", "appProperties": {}}
        docs = type("Docs", (), {"document_id": "doc-123", "document_revision_id": "revision-7"})()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "ISSUANCE_DOC_DUPLICATE_OR_ID_MISMATCH"):
                importer.import_exact_issuance_doc(Path(temp), report=report, docs=docs,
                                                   session=DriveSession([item, {**item, "id": "doc-duplicate"}]))
            changed = {**report, "sourceRevisionId": "other-revision", "bodyHash": report["bodyHash"],
                       "fullText": report["fullText"]}
            with patch.object(importer, "build_report", return_value=changed):
                with self.assertRaisesRegex(RuntimeError, "ISSUANCE_DOC_REVISION_OR_BODY_CHANGED"):
                    importer.import_exact_issuance_doc(Path(temp), report=report, docs=docs,
                                                       session=DriveSession([item]))
        bad_report = dict(report, bodyHash="0" * 64)
        with self.assertRaisesRegex(IssuanceBlocked, "PAGES_PUBLIC_BODY_MISMATCH"):
            GitHubPagesVerifier(github=WorkflowGateway(), base_url="https://example.invalid",
                                public_session=PublicSession(bad_report), poll_interval=0).verify(
                                    report=report, commit_sha="commit-1")

    def test_duplicate_retry_is_idempotent_and_retry_after_pages_failure_recovers(self):
        github = FakeGitHub()
        pages = FakePages(fail_first=True)
        publisher = self.make_publisher(github=github, pages=pages)
        with self.assertRaisesRegex(IssuanceBlocked, "PAGES_DEPLOYMENT_FAILED"):
            self.execute_pipeline(portal=publisher)
        result = self.execute_pipeline(portal=publisher)
        self.assertEqual(result["canonical_commit_sha"], "commit-1")
        self.assertEqual(github.calls, 2)
        self.assertEqual(pages.calls, 2)

    def test_evidence_stage_is_create_only_and_checks_generation_hash_and_identity(self):
        envelope = dict(self.fixture.bundle["evidence_object"])
        evidence = {"evidence_object": envelope, "evidence_id": self.fixture.evidence["evidenceId"]}
        report = dict(self.fixture.report)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = stage_pinned_evidence(root, report, evidence)
            again = stage_pinned_evidence(root, report, evidence)
            self.assertEqual(first["sha256"], again["sha256"])
            bad = {"evidence_object": {**envelope, "object_sha256": "0" * 64},
                   "evidence_id": self.fixture.evidence["evidenceId"]}
            with self.assertRaisesRegex(IssuanceBlocked, "ISSUANCE_EVIDENCE_HASH_MISMATCH"):
                stage_pinned_evidence(root, report, bad)
            wrong = {"evidence_object": envelope, "evidence_id": "different"}
            with self.assertRaisesRegex(IssuanceBlocked, "ISSUANCE_EVIDENCE_IDENTITY_MISMATCH"):
                stage_pinned_evidence(root, report, wrong)

    def test_live_writes_require_explicit_environment_gate(self):
        with patch.dict(os.environ, {"REPORT_ISSUANCE_WRITE_ENABLED": "false"}, clear=False):
            with self.assertRaisesRegex(IssuanceBlocked, "PRODUCTION_ISSUANCE_WRITE_NOT_ENABLED"):
                GitHubPortalPublisher.from_environment(importer=FakeImporter(self.fixture.report), expected_head="sha")

    def test_live_writes_require_protected_main_workflow_approval(self):
        env = {"REPORT_ISSUANCE_WRITE_ENABLED": "true", "GITHUB_ACTIONS": "false",
               "GITHUB_REF": "refs/heads/main", "REPORT_ISSUANCE_APPROVED": "false"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(IssuanceBlocked, "PROTECTED_MAIN_WORKFLOW_APPROVAL_REQUIRED"):
                GitHubPortalPublisher.from_environment(importer=FakeImporter(self.fixture.report), expected_head="sha")


if __name__ == "__main__":
    unittest.main()
