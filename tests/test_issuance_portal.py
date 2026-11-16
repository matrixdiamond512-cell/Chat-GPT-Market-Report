from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.reporting.issuance_pipeline import IssuanceBlocked
from scripts.reporting.issuance_portal import (
    GitHubPagesVerifier, GitHubPortalPublisher, StrictGoogleDocsImporter,
    stage_pinned_evidence,
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

    def publish_files(self, *, expected_head, files, message, create_only_paths=()):
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


class ExactIssuanceDriveSession:
    def __init__(self, *, docs_id, drive_title, full_text, app_properties):
        self.docs_id, self.drive_title, self.full_text = docs_id, drive_title, full_text
        self.app_properties = app_properties
        self.item = {"id": docs_id, "name": drive_title,
                     "mimeType": "application/vnd.google-apps.document", "parents": ["month-folder"],
                     "createdTime": "2026-10-16T08:02:00+09:00",
                     "modifiedTime": "2026-10-16T08:02:01+09:00",
                     "headRevisionId": "revision-7", "appProperties": app_properties}

    def get(self, endpoint, *, params=None, timeout):
        if endpoint.endswith("/files"):
            return HttpResponse(200, {"files": [self.item]})
        if endpoint.endswith("/documents/doc-123"):
            return HttpResponse(200, {"documentId": self.docs_id, "title": self.drive_title,
                                      "revisionId": "revision-7", "body": {"content": [
                                          {"paragraph": {"elements": [{"textRun": {"content": self.full_text}}]}}
                                      ]}})
        if endpoint.endswith("/files/doc-123"):
            return HttpResponse(200, self.item)
        raise AssertionError("unexpected exact issuance Drive request: " + endpoint)


class DynamicPublicSession:
    def __init__(self, github):
        self.github = github

    def get(self, url, *, timeout):
        path = url.split("example.invalid/", 1)[1]
        data = self.github.contents.get(path)
        if data is None:
            return HttpResponse(404, {})
        import json
        return HttpResponse(200, json.loads(data.decode("utf-8")))


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

    def test_composed_run_issuance_uses_real_strict_importer_receipt_and_public_readback(self):
        import hashlib
        import json
        from test_issuance_pipeline import FakeDocs

        # Give the existing SOP validator a substantive 08:00 test report while
        # keeping scenario quote offsets bound to this exact pre-save body.
        report = self.fixture.report
        main_quotes = ("Main condition: above 100.", "Main development: rally continues.",
                       "Main impact: equities rise.")
        alt_quotes = ("Alternative condition: below 100.", "Alternative development: pullback extends.",
                      "Alternative impact: yen strengthens.")
        invalid_quotes = ("Invalidation condition: yield breaks 5%.",
                          "Invalidation development: main thesis fails.",
                          "Invalidation impact: risk assets fall.")
        paragraph = "確認済み材料と対応する価格反応を分離し、観測できた事実だけを記録する。 " * 5
        body_lines = [report["title"]]
        for heading in ("今日の相場テーマ", "主要市場データ", "材料と値動きの整合性", "主導市場",
                        "重要ニュース", "クロスアセット資金フロー", "需給・ポジション",
                        "6市場の個別見通し"):
            detail = ("金・XAU/USD、WTI原油、日経225先物、USD/JPY、EUR/USD、BTCUSDを確認する。 " + paragraph
                      if heading == "主要市場データ" else paragraph)
            body_lines.extend((heading, detail))
        body_lines.extend(("シナリオ", "メインシナリオ", *main_quotes, "代替シナリオ", *alt_quotes,
                           "崩れる条件", *invalid_quotes, "前回からの主な変化", paragraph,
                           "結論", paragraph))
        self.fixture.full_text = "\n".join(body_lines) + "\n"
        body_hash = hashlib.sha256(self.fixture.full_text.encode("utf-8")).hexdigest()
        report["fullText"] = self.fixture.full_text
        report["bodyHash"] = body_hash
        self.fixture.body_hash = body_hash
        self.fixture.bundle["g2"]["body_hash"] = body_hash
        self.fixture.bundle["g2"]["scenario_review"]["body_hash"] = body_hash
        scenarios = self.fixture.bundle["g2"]["scenario_review"]["scenarios"]
        for scenario_name, quotes in (("main_scenario", main_quotes),
                                      ("alternative_scenario", alt_quotes),
                                      ("invalidation_trigger", invalid_quotes)):
            for field_name, quote in zip(("condition", "development", "market_impact"), quotes):
                start = self.fixture.full_text.index(quote)
                scenarios[scenario_name][field_name]["source"] = {
                    "start": start, "end": start + len(quote), "quote": quote,
                }

        github = FakeGitHub()
        pages = GitHubPagesVerifier(github=WorkflowGateway(), base_url="https://example.invalid",
                                    public_session=DynamicPublicSession(github), poll_interval=0,
                                    dom_verifier=lambda report: None)
        app_properties = {"report_id": report["report_id"], "revision": "1",
                          "body_hash": report["bodyHash"],
                          "evidence_id": self.fixture.evidence["evidenceId"],
                          "snapshot_id": self.fixture.evidence["snapshot"]["snapshot_id"]}
        docs_session = ExactIssuanceDriveSession(
            docs_id="doc-123", drive_title="マーケットレポート_2026-10-16_08-00",
            full_text=report["fullText"], app_properties=app_properties,
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            def project_indexes():
                index = [{"date": report["date"], "time": report["time"], "title": report["title"],
                          "report_id": report["report_id"], "revision": report["revision"],
                          "bodyHash": report["bodyHash"], "fullText": report["fullText"]}]
                (root / "reports.json").write_text(json.dumps(index), encoding="utf-8")
                (root / "data").mkdir(exist_ok=True)
                (root / "data/latest-report.json").write_text(json.dumps({"latestReport": index[0]}), encoding="utf-8")
                (root / "data/dashboard.json").write_text(json.dumps({"latestReport": index[0]}), encoding="utf-8")

            strict_importer = StrictGoogleDocsImporter(
                root=root, docs_session=docs_session, projection_runner=project_indexes,
            )
            portal = GitHubPortalPublisher(
                importer=strict_importer, github=github, pages=pages, expected_head="main-sha",
            )
            result = self.fixture.execute_pipeline(docs=FakeDocs(), portal=portal)
            canonical_path = root / "reports/2026-10-16_08-00.json"
            receipt_path = root / "publication-receipts/2026-10-16_08-00.json"
            self.assertTrue(canonical_path.is_file())
            self.assertTrue(receipt_path.is_file())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["reportId"], report["report_id"])
            self.assertEqual(receipt["documentRevisionId"], "revision-7")
            self.assertIn("reports.json", github.contents)
            self.assertEqual(result["environment"], "TEST_ONLY")
            self.assertTrue(result["public_body_verified"])

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
        dom_calls = []
        verifier = GitHubPagesVerifier(github=WorkflowGateway(), base_url="https://example.invalid",
                                       public_session=PublicSession(report), poll_interval=0,
                                       dom_verifier=lambda target: dom_calls.append(target["report_id"]))
        run_id, url = verifier.verify(report=report, commit_sha="commit-1")
        self.assertEqual(run_id, "88")
        self.assertTrue(url.endswith("report.html?date=2026-10-16&time=08%3A00"))
        self.assertEqual(dom_calls, [report["report_id"]])

    def test_public_dom_mismatch_blocks_publication_after_json_readback(self):
        report = dict(self.fixture.report)
        def mismatch(_):
            raise IssuanceBlocked("PAGES_PUBLIC_DOM_READBACK_FAILED")
        verifier = GitHubPagesVerifier(github=WorkflowGateway(), base_url="https://example.invalid",
                                       public_session=PublicSession(report), poll_interval=0,
                                       dom_verifier=mismatch)
        with self.assertRaisesRegex(IssuanceBlocked, "PAGES_PUBLIC_DOM_READBACK_FAILED"):
            verifier.verify(report=report, commit_sha="commit-1")

    def test_concrete_pages_verifier_rejects_failed_deploy_and_public_hash_mismatch(self):
        report = dict(self.fixture.report)
        with self.assertRaisesRegex(IssuanceBlocked, "PAGES_DEPLOYMENT_FAILED"):
            GitHubPagesVerifier(github=WorkflowGateway("failure"), base_url="https://example.invalid",
                                public_session=PublicSession(report), poll_interval=0,
                                dom_verifier=lambda report: None).verify(
                                    report=report, commit_sha="commit-1")

    def test_strict_importer_queries_one_title_and_binds_exact_doc_revision(self):
        from scripts import sync_reports_from_drive as importer
        report = dict(self.fixture.report)
        report["evidence_id"] = self.fixture.evidence["evidenceId"]
        report["snapshot_id"] = self.fixture.evidence["snapshot"]["snapshot_id"]
        receipt = {"evidenceId": report["evidence_id"], "snapshotId": report["snapshot_id"],
                   "contextHash": "c", "snapshotHash": "s", "bodyHash": report["bodyHash"],
                   "documentRevisionId": "revision-7"}
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
                                public_session=PublicSession(bad_report), poll_interval=0,
                                dom_verifier=lambda report: None).verify(
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
            mismatched_payload = json.loads(envelope["bytes"])
            mismatched_payload["reportId"] = "2026-10-15_08-00"
            mismatched_raw = (json.dumps(mismatched_payload, ensure_ascii=False, sort_keys=True,
                                         separators=(",", ":")) + "\n").encode("utf-8")
            wrong_report = {"evidence_object": {**envelope, "bytes": mismatched_raw.decode("utf-8"),
                                                  "object_sha256": hashlib.sha256(mismatched_raw).hexdigest()},
                            "evidence_id": self.fixture.evidence["evidenceId"]}
            with self.assertRaisesRegex(IssuanceBlocked, "ISSUANCE_EVIDENCE_IDENTITY_MISMATCH"):
                stage_pinned_evidence(root, report, wrong_report)

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

    def test_live_writes_require_the_configured_protected_environment(self):
        env = {"REPORT_ISSUANCE_WRITE_ENABLED": "true", "GITHUB_ACTIONS": "true",
               "GITHUB_REF": "refs/heads/main", "REPORT_ISSUANCE_APPROVED": "true",
               "REPORT_ISSUANCE_ENVIRONMENT": "unprotected"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(IssuanceBlocked, "PROTECTED_MAIN_WORKFLOW_APPROVAL_REQUIRED"):
                GitHubPortalPublisher.from_environment(importer=FakeImporter(self.fixture.report), expected_head="sha")


class GitHubCreateOnlyRestTests(unittest.TestCase):
    class Response:
        def __init__(self, status, payload=None):
            self.status_code = status
            self.content = b"{}" if payload is not None else b""
            self._payload = payload or {}
        def json(self): return self._payload

    class Session:
        def __init__(self):
            self.head = "main-0"
            self.files = {}
            self.blob_count = self.commit_count = 0
            self.pending_tree = []
            self.fail_patch = False
            self.lose_patch_response = False
        def request(self, method, url, **kwargs):
            from urllib.parse import unquote, urlparse
            path = urlparse(url).path.split("/repos/acme/report", 1)[-1]
            if method == "GET" and path == "/git/ref/heads/main":
                return GitHubCreateOnlyRestTests.Response(200, {"object": {"sha": self.head}})
            if method == "GET" and path.startswith("/contents/"):
                file_path = unquote(path.split("/contents/", 1)[1].split("?", 1)[0])
                if file_path not in self.files:
                    return GitHubCreateOnlyRestTests.Response(404)
                import base64
                return GitHubCreateOnlyRestTests.Response(200, {"content": base64.b64encode(self.files[file_path]).decode()})
            if method == "GET" and path.startswith("/git/commits/"):
                return GitHubCreateOnlyRestTests.Response(200, {"tree": {"sha": "tree-0"}})
            if method == "POST" and path == "/git/blobs":
                self.blob_count += 1
                return GitHubCreateOnlyRestTests.Response(201, {"sha": "blob-" + str(self.blob_count)})
            if method == "POST" and path == "/git/trees":
                self.pending_tree = kwargs["json"]["tree"]
                return GitHubCreateOnlyRestTests.Response(201, {"sha": "tree-new"})
            if method == "POST" and path == "/git/commits":
                self.commit_count += 1
                return GitHubCreateOnlyRestTests.Response(201, {"sha": "commit-" + str(self.commit_count)})
            if method == "PATCH" and path == "/git/refs/heads/main":
                if self.fail_patch:
                    return GitHubCreateOnlyRestTests.Response(422, {"message": "Update is not a fast forward"})
                if kwargs["json"]["sha"] != "commit-" + str(self.commit_count):
                    return GitHubCreateOnlyRestTests.Response(422)
                self.head = kwargs["json"]["sha"]
                for row in self.pending_tree:
                    data = "blob-" + str(self.blob_count)
                    # This fake only needs tree/ref behavior; the write is inspected separately.
                    self.files[row["path"]] = b"new-content"
                return GitHubCreateOnlyRestTests.Response(200, {})
            raise AssertionError((method, path))

    def setUp(self):
        from scripts.reporting.issuance_portal import GitHubRestClient
        self.session = self.Session()
        self.client = GitHubRestClient(repository="acme/report", token="never-print", session=self.session)
        self.files = {"reports/2026-11-05_08-00.json": b"canonical-v1",
                      "publication-receipts/2026-11-05_08-00.json": b"receipt-v1",
                      "reports.json": b"index-v1"}
        self.create_only = tuple(list(self.files)[:2])

    def test_existing_canonical_or_receipt_mismatch_is_rejected_before_write(self):
        self.session.files = {**self.files, self.create_only[0]: b"old-canonical",
                              self.create_only[1]: b"receipt-v1"}
        with self.assertRaisesRegex(IssuanceBlocked, "GITHUB_CREATE_ONLY_PATH_CONFLICT"):
            self.client.publish_files(expected_head="main-0", files=self.files, message="x",
                                      create_only_paths=self.create_only)
        self.assertEqual(self.session.commit_count, 0)
        self.assertEqual(self.session.head, "main-0")

    def test_main_moved_before_start_is_rejected(self):
        self.session.head = "main-1"
        with self.assertRaisesRegex(IssuanceBlocked, "GITHUB_MAIN_MOVED_RECONCILE_REQUIRED"):
            self.client.publish_files(expected_head="main-0", files=self.files, message="x",
                                      create_only_paths=self.create_only)
        self.assertEqual(self.session.commit_count, 0)

    def test_main_compare_and_swap_conflict_does_not_claim_publication(self):
        self.session.fail_patch = True
        with self.assertRaisesRegex(IssuanceBlocked, "GITHUB_MAIN_UPDATE_CONFLICT_RECONCILE_REQUIRED"):
            self.client.publish_files(expected_head="main-0", files=self.files, message="x",
                                      create_only_paths=self.create_only)
        self.assertEqual(self.session.head, "main-0")

    def test_partial_success_retry_reuses_exact_commit_without_duplicate_commit(self):
        # Model the main ref update succeeding while the caller loses the response.
        self.session.fail_patch = False
        self.session.files = {}
        self.session.pending_tree = []
        self.session.request = self._successful_session_request_with_content
        first = self.client.publish_files(expected_head="main-0", files=self.files, message="x",
                                          create_only_paths=self.create_only)
        second = self.client.publish_files(expected_head=first, files=self.files, message="retry",
                                           create_only_paths=self.create_only)
        self.assertEqual(first, second)
        self.assertEqual(self.session.commit_count, 1)

    def _successful_session_request_with_content(self, method, url, **kwargs):
        response = self.Session.request(self.session, method, url, **kwargs)
        if method == "PATCH" and response.status_code == 200:
            self.session.files.update(self.files)
            if self.session.lose_patch_response:
                self.session.lose_patch_response = False
                return self.Response(500, {"message": "response lost after ref update"})
        return response

    def test_lost_success_response_retries_by_reconciling_exact_remote_files(self):
        self.session.lose_patch_response = True
        self.session.request = self._successful_session_request_with_content
        with self.assertRaisesRegex(IssuanceBlocked, "GITHUB_PATCH_FAILED:500"):
            self.client.publish_files(expected_head="main-0", files=self.files, message="x",
                                      create_only_paths=self.create_only)
        commit = self.client.publish_files(expected_head="main-0", files=self.files, message="retry",
                                           create_only_paths=self.create_only)
        self.assertEqual(commit, "commit-1")
        self.assertEqual(self.session.commit_count, 1)

    def test_one_sided_canonical_receipt_pair_is_rejected(self):
        self.session.files = {self.create_only[0]: self.files[self.create_only[0]]}
        with self.assertRaisesRegex(IssuanceBlocked, "GITHUB_CREATE_ONLY_PAIR_INCOMPLETE"):
            self.client.publish_files(expected_head="main-0", files=self.files, message="x",
                                      create_only_paths=self.create_only)


if __name__ == "__main__":
    unittest.main()
