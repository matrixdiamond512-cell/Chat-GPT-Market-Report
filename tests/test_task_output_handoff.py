"""Isolated task -> producer -> Docs equivalent -> canonical/receipt -> HTML DOM simulation."""
import copy
import hashlib
from html.parser import HTMLParser
import html
import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock

from test_g2_bundle_producer import fixture_source, PROJECT, EVIDENCE_BUCKET, SLOT
from test_issuance_pipeline import FakeDocs, FakeClaimStore
from test_issuance_portal import FakeImporter, FakeGitHub, DynamicPublicSession, WorkflowGateway
from scripts.reporting.g2_bundle_producer import TrustedG2BundleProducer, G2BundleWriteReceipt, _canonical_bytes
from scripts.reporting.issuance_pipeline import IssuanceBlocked, run_issuance
from scripts.reporting.issuance_portal import GitHubPortalPublisher, GitHubPagesVerifier
from scripts.reporting.task_output_handoff import VerifiedTaskInvocation, freeze_task_output


class ImmutableStore:
    def __init__(self):
        self.payload = None

    def create_only(self, *, report_id, revision, bundle):
        payload = _canonical_bytes(bundle)
        if self.payload is not None and self.payload != payload:
            raise IssuanceBlocked("G2_BUNDLE_EXISTING_CONFLICT")
        status = "CREATED" if self.payload is None else "IDEMPOTENT_RETRY"
        self.payload = payload
        return G2BundleWriteReceipt("fixture/g2.json", 44, hashlib.sha256(payload).hexdigest(), status)


class TextDOM(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = ""

    def handle_data(self, data):
        self.text += data


class TaskOutputHandoffTests(unittest.TestCase):
    def setUp(self):
        report, text, envelope, review, evidence = fixture_source()
        self.envelope = envelope
        self.request = {"schemaVersion": 1, "report": report, "full_text": text,
                        "body_sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "frozen_at": "2026-10-16T08:05:00+09:00", "scenario_review": review,
                        "evidence_ref": {"object": envelope["object"], "generation": envelope["generation"],
                                         "evidence_id": evidence["evidenceId"],
                                         "snapshot_id": evidence["snapshot"]["snapshot_id"]}}
        self.store = ImmutableStore()
        self.producer = TrustedG2BundleProducer(self.store, expected_project_id=PROJECT,
                                                expected_evidence_bucket=EVIDENCE_BUCKET)
        self.reader = Mock(return_value={"evidence_object": envelope})
        self.invocation = VerifiedTaskInvocation("task-08", "run-1", "host-verified-principal")

    def freeze(self, request=None, invocation=None, now=SLOT):
        return freeze_task_output(self.request if request is None else request,
            invocation=self.invocation if invocation is None else invocation,
            expected_task_id="task-08", expected_principal="host-verified-principal",
            producer=self.producer, evidence_reader=self.reader, now=now)

    def test_full_chain_and_exact_html_dom_simulation(self):
        frozen = self.freeze()
        bundle = {"environment": "PRODUCTION", "g2": frozen["bundle"]["g2"],
                  "evidence_object": self.envelope}
        report = bundle["g2"]["report"]
        github = FakeGitHub()
        receipt = {"reportId": report["report_id"], "revision": report["revision"],
                   "driveFileId": "doc-123", "documentRevisionId": "revision-7",
                   "bodyHash": report["bodyHash"], "evidenceId": frozen["evidence_ref"]["evidence_id"],
                   "snapshotId": frozen["evidence_ref"]["snapshot_id"]}
        observed_dom = []
        def verify_dom(public):
            dom = TextDOM()
            dom.feed("<main><pre>" + html.escape(public["fullText"]) + "</pre></main>")
            self.assertEqual(dom.text, self.request["full_text"])
            observed_dom.append(public["report_id"])
        pages = GitHubPagesVerifier(github=WorkflowGateway(), base_url="https://example.invalid",
            public_session=DynamicPublicSession(github), poll_interval=0, dom_verifier=verify_dom)
        with tempfile.TemporaryDirectory() as temp:
            importer = FakeImporter(report, receipt)
            importer.root = Path(temp)
            (importer.root / "reports.json").write_text(json.dumps([report]), encoding="utf-8")
            (importer.root / "data").mkdir()
            for name in ("latest-report.json", "dashboard.json"):
                (importer.root / "data" / name).write_text(json.dumps({"latestReport": report}), encoding="utf-8")
            portal = GitHubPortalPublisher(importer, github, pages, "fixture-head")
            result = run_issuance(bundle, expected_project_id=PROJECT, expected_evidence_bucket=EVIDENCE_BUCKET,
                docs_writer=FakeDocs(saved_at="2026-10-16T08:07:00+09:00"),
                portal=portal, claim_store=FakeClaimStore())
        self.assertEqual(observed_dom, [report["report_id"]])
        self.assertEqual(json.loads(github.contents["reports.json"])[0]["bodyHash"], report["bodyHash"])
        canonical = json.loads(github.contents["reports/2026-10-16_08-00.json"])
        receipt = json.loads(github.contents["publication-receipts/2026-10-16_08-00.json"])
        dom = TextDOM()
        dom.feed("<main><pre>" + html.escape(canonical["fullText"]) + "</pre></main>")
        self.assertEqual(dom.text, self.request["full_text"])
        self.assertEqual(receipt["bodyHash"], result["body_hash"])
        self.assertEqual(receipt["reportId"], frozen["report_id"])
        self.assertEqual(receipt["revision"], frozen["revision"])
        self.assertEqual(receipt["evidenceId"], frozen["evidence_ref"]["evidence_id"])
        self.assertEqual(receipt["snapshotId"], frozen["evidence_ref"]["snapshot_id"])
        self.assertEqual(frozen["g2_ref"]["generation"], 44)
        self.assertEqual(result["environment"], "TEST_ONLY")
        self.assertEqual(frozen["notification_status"], "NOT_RUN")
        output = os.environ.get("ISSUANCE_E2E_CANONICAL_OUTPUT")
        if output:
            Path(output).write_text(json.dumps(canonical, ensure_ascii=False), encoding="utf-8")

    def test_unverified_request_identity_cannot_authenticate(self):
        with self.assertRaisesRegex(IssuanceBlocked, "BLOCKED_G2_TASK_HANDOFF"):
            self.freeze(invocation={"task_id": "task-08", "principal": "host-verified-principal"})
        self.reader.assert_not_called()
        self.assertIsNone(self.store.payload)

    def test_wrong_principal_blocks(self):
        with self.assertRaisesRegex(IssuanceBlocked, "BLOCKED_G2_TASK_HANDOFF"):
            self.freeze(invocation=VerifiedTaskInvocation("task-08", "run", "other"))
        self.reader.assert_not_called()

    def test_body_and_evidence_mutations_block_before_write(self):
        for mutate, reason in [
            (lambda r: r.update(full_text=r["full_text"]+"changed"), "BODY_HASH_MISMATCH"),
            (lambda r: r["evidence_ref"].update(evidence_id="other"), "EVIDENCE_IDENTITY_MISMATCH"),
            (lambda r: r["evidence_ref"].update(snapshot_id="other"), "EVIDENCE_IDENTITY_MISMATCH"),
            (lambda r: r["report"].update(revision=2), "EVIDENCE_IDENTITY_MISMATCH"),
            (lambda r: r.update(frozen_at="2026-10-16T07:59:00+09:00"), "FREEZE_OUTSIDE_SLOT_WINDOW"),
            (lambda r: r.update(scenario_review={}), "REVIEW_TIME_REQUIRED"),
        ]:
            with self.subTest(reason=reason):
                request = copy.deepcopy(self.request)
                mutate(request)
                with self.assertRaisesRegex(IssuanceBlocked, reason):
                    self.freeze(request)
                self.assertIsNone(self.store.payload)

    def test_duplicate_reuses_and_conflict_blocks(self):
        first = self.freeze()
        self.assertEqual(first["g2_ref"], self.freeze()["g2_ref"])
        request = copy.deepcopy(self.request)
        request["frozen_at"] = "2026-10-16T08:05:01+09:00"
        with self.assertRaisesRegex(IssuanceBlocked, "EXISTING_CONFLICT"):
            self.freeze(request)

    def test_late_run_fails_closed(self):
        from datetime import timedelta
        with self.assertRaisesRegex(IssuanceBlocked, "AFTER_SLOT_WINDOW"):
            self.freeze(now=SLOT + timedelta(minutes=40))
        self.assertIsNone(self.store.payload)
        self.reader.assert_not_called()

    def test_reader_permission_failure_does_not_create_g2(self):
        self.reader.side_effect = IssuanceBlocked("PINNED_EVIDENCE_READBACK_FAILED")
        with self.assertRaisesRegex(IssuanceBlocked, "READBACK_FAILED"):
            self.freeze()
        self.assertIsNone(self.store.payload)


    def test_malformed_readback_fails_closed_without_creating_g2(self):
        for readback in (None, [], {}, {"evidence_object": None},
                         {"evidence_object": {"bytes": []}},
                         {"evidence_object": {"bytes": "[]"}},
                         {"evidence_object": {"bytes": '{"snapshot": []}'}},
                         {"evidence_object": {"bytes": "{"}}):
            with self.subTest(readback=readback):
                self.reader.return_value = readback
                with self.assertRaisesRegex(IssuanceBlocked, "TASK_OUTPUT_EVIDENCE_INVALID"):
                    self.freeze()
                self.assertIsNone(self.store.payload)

    def test_unclassified_reader_failure_is_retryable_without_success(self):
        self.reader.side_effect = TimeoutError("simulated response loss")
        with self.assertRaises(IssuanceBlocked) as caught:
            self.freeze()
        self.assertEqual(str(caught.exception), "TASK_OUTPUT_EVIDENCE_READ_FAILED")
        self.assertEqual(caught.exception.stage, "TASK_EVIDENCE_READ")
        self.assertTrue(caught.exception.retryable)
        self.assertIsNone(self.store.payload)

    def test_invalid_target_time_and_types_never_read_evidence(self):
        from datetime import datetime, timedelta
        mutations = [
            lambda r: r.update(schemaVersion=True),
            lambda r: r["report"].update(report_id="other-slot"),
            lambda r: r["report"].update(revision=True),
            lambda r: r["report"].update(date="2026-10-17"),
            lambda r: r["report"].update(time="12:00"),
            lambda r: r["evidence_ref"].update(generation=True),
            lambda r: r["evidence_ref"].update(snapshot_id=[]),
            lambda r: r["evidence_ref"].update(evidence_id=123),
            lambda r: r.update(frozen_at="2026-10-16T08:05:00"),
            lambda r: r.update(frozen_at="2026-10-16T08:41:00+09:00"),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                request = copy.deepcopy(self.request)
                mutate(request)
                with self.assertRaises(IssuanceBlocked):
                    self.freeze(request)
                self.reader.assert_not_called()
                self.assertIsNone(self.store.payload)
        for clock in (SLOT - timedelta(minutes=7), datetime(2026, 10, 16, 8, 6)):
            with self.subTest(clock=clock):
                with self.assertRaises(IssuanceBlocked):
                    self.freeze(now=clock)
                self.reader.assert_not_called()

    def test_invalid_g2_store_receipt_is_never_reported_as_success(self):
        self.store.create_only = Mock(return_value=None)
        with self.assertRaisesRegex(IssuanceBlocked, "TASK_OUTPUT_G2_RECEIPT_INVALID"):
            self.freeze()


if __name__ == "__main__":
    unittest.main()
