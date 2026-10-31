"""Offline contract tests; adapters are fakes and never contact production."""
from __future__ import annotations

import hashlib
import json
import unittest

from scripts.persist_report_slot_evidence import build_slot_evidence, canonical_bytes
from scripts.reporting.issuance_pipeline import (
    DocsReadback, GoogleDocsApiWriter, IssuanceBlocked, PortalReadback, run_issuance,
    validate_issuance_bundle,
)


PROJECT = "market-report-production-shadow"
BUCKET = "market-report-production-evidence"


class FakeClaimStore:
    def __init__(self):
        self.claims = {}

    def claim(self, *, report_id, revision, body_hash, evidence_id, snapshot_id):
        key = (report_id, revision)
        claim = (body_hash, evidence_id, snapshot_id)
        old = self.claims.setdefault(key, claim)
        if old != claim:
            raise IssuanceBlocked("DUPLICATE_SLOT_ISSUANCE_CONFLICT")


class FakeDocs:
    def __init__(self, *, mutate=False, saved_at="2026-10-16T08:02:00+09:00"):
        self.mutate = mutate
        self.saved_at = saved_at
        self.calls = 0
        self.title = None

    def save_exact(self, *, title, report_id, revision, full_text, body_hash,
                   evidence_id, snapshot_id):
        self.calls += 1
        self.title = title
        text = full_text + " changed" if self.mutate else full_text
        return DocsReadback("doc-123", "revision-7", text,
                            hashlib.sha256(text.encode()).hexdigest(), self.saved_at)


class FakePortal:
    def __init__(self, *, mutate=False):
        self.mutate = mutate
        self.calls = 0

    def publish_and_readback(self, *, report, docs, evidence):
        self.calls += 1
        return PortalReadback(
            report["report_id"], report["revision"],
            evidence["snapshot"]["snapshot_id"], docs.document_id,
            docs.document_revision_id,
            docs.full_text + (" changed" if self.mutate else ""),
            hashlib.sha256((docs.full_text + (" changed" if self.mutate else "")).encode()).hexdigest(),
            "PUBLISHED",
        )


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self.payload = payload or {}
        self.status_code = status
        self.ok = status < 400
        self.content = json.dumps(self.payload).encode() if payload is not None else b""

    def json(self):
        return self.payload


class FakeGoogleSession:
    def __init__(self, full_text):
        self.full_text = full_text
        self.created = None
        self.calls = []

    def request(self, method, url, *, params=None, json=None, timeout=None):
        self.calls.append((method, url, params, json))
        if url.endswith("/files/month-folder"):
            return FakeResponse({"id": "month-folder", "mimeType": "application/vnd.google-apps.folder",
                                 "parents": ["root-folder"], "trashed": False})
        if url.endswith("/files") and method == "GET":
            return FakeResponse({"files": []})
        if url.endswith("/files") and method == "POST":
            self.created = {"id": "doc-123", "name": "Report", "mimeType": "application/vnd.google-apps.document",
                            "parents": ["month-folder"], "appProperties": json["appProperties"],
                            "createdTime": "2026-10-16T08:02:00Z", "modifiedTime": "2026-10-16T08:02:01Z"}
            return FakeResponse(self.created)
        if url.endswith("/documents/doc-123:batchUpdate"):
            return FakeResponse({"replies": [{}]})
        if url.endswith("/files/doc-123"):
            return FakeResponse(self.created)
        if url.endswith("/documents/doc-123"):
            return FakeResponse({"revisionId": "revision-7", "body": {"content": [
                {"paragraph": {"elements": [{"textRun": {"content": self.full_text}}]}}
            ]}})
        raise AssertionError(f"unexpected Google API request: {method} {url}")


class IssuancePipelineContractTests(unittest.TestCase):
    def setUp(self):
        scenario_lines = [
            "Main condition: above 100.",
            "Main development: rally continues.",
            "Main impact: equities rise.",
            "Alternative condition: below 100.",
            "Alternative development: pullback extends.",
            "Alternative impact: yen strengthens.",
            "Invalidation condition: yield breaks 5%.",
            "Invalidation development: main thesis fails.",
            "Invalidation impact: risk assets fall.",
        ]
        sections = [
            "結論", "総括", "今日の相場テーマ", "金利", "重要ニュース",
            "主要市場データ", "市場データ確認：金、WTI、日経平均、USD/JPY、EUR/USD、BTC。",
            "クロスアセット資金フロー", "需給・ポジション", "6市場の個別見通し",
            "メインシナリオ", scenario_lines[0], scenario_lines[1], scenario_lines[2],
            "代替シナリオ", scenario_lines[3], scenario_lines[4], scenario_lines[5],
            "崩れる条件", scenario_lines[6], scenario_lines[7], scenario_lines[8],
        ]
        sections.extend(["TEST_FIXTURE: synthetic body-length coverage."] * 28)
        self.full_text = "マーケットレポート｜2026/10/16（金）08:00\n" + "\n".join(sections) + "\n"
        payload = {
            "generatedAt": "2026-10-16T07:55:00+09:00",
            "reportDate": "2026-10-16", "reportSlot": "08:00",
            "overallStatus": "verified",
            "markets": {"USDJPY": {
                "id": "USDJPY", "marketType": "FX", "unit": "JPY", "value": 157.8,
                "change": 0.2, "changePercent": 0.1,
                "comparisonBasis": "previous_close", "asOf": "2026-10-16T07:54:00+09:00",
                "sourceId": "synthetic-test", "sourceUrl": "https://example.invalid/fixture",
                "verificationStatus": "verified", "freshnessStatus": "fresh", "displayValue": "157.8",
            }},
        }
        self.evidence = build_slot_evidence("2026-10-16", "08:00", payload,
                                            json.dumps(payload, sort_keys=True).encode())
        self.evidence_bytes = canonical_bytes(self.evidence)
        self.body_hash = hashlib.sha256(self.full_text.encode()).hexdigest()
        self.report = {
            "date": "2026-10-16", "time": "08:00", "title": "マーケットレポート｜2026/10/16（金）08:00",
            "report_id": "2026-10-16_08-00", "revision": 1, "fullText": self.full_text,
            "bodyHash": self.body_hash, "snapshot_id": self.evidence["snapshot"]["snapshot_id"],
            "snapshot": self.evidence["snapshot"], "context": self.evidence["context"],
        }
        scenarios = {}
        for name, labels in {
            "main_scenario": ("Main condition: above 100.", "Main development: rally continues.", "Main impact: equities rise."),
            "alternative_scenario": ("Alternative condition: below 100.", "Alternative development: pullback extends.", "Alternative impact: yen strengthens."),
            "invalidation_trigger": ("Invalidation condition: yield breaks 5%.", "Invalidation development: main thesis fails.", "Invalidation impact: risk assets fall."),
        }.items():
            fields = {}
            for field, quote in zip(("condition", "development", "market_impact"), labels):
                start = self.full_text.index(quote)
                fields[field] = {"text": quote, "source": {
                    "start": start, "end": start + len(quote), "quote": quote,
                }}
            scenarios[name] = fields
        self.bundle = {
            "environment": "PRODUCTION",
            "evidence_object": {
                "environment": "PRODUCTION", "project_id": PROJECT, "bucket": BUCKET,
                "generation": 123, "bytes": self.evidence_bytes.decode(),
                "object_sha256": hashlib.sha256(self.evidence_bytes).hexdigest(),
                "evidence_id": self.evidence["evidenceId"],
            },
            "g2": {
                "report": self.report, "report_id": self.report["report_id"],
                "revision": 1, "body_hash": self.body_hash,
                "evidence_id": self.evidence["evidenceId"],
                "snapshot_id": self.evidence["snapshot"]["snapshot_id"],
                "frozen_at": "2026-10-16T08:01:00+09:00",
                "scenario_review": {
                    "status": "APPROVED", "reviewer": "human-reviewer",
                    "reviewed_at": "2026-10-16T08:01:30+09:00",
                    "branching_validated": True,
                    "invalidation_trigger_is_decision_change": True,
                    "report_id": self.report["report_id"], "body_hash": self.body_hash,
                    "scenarios": scenarios,
                },
            },
        }

    def execute_pipeline(self, *, docs=None, portal=None):
        return run_issuance(self.bundle, expected_project_id=PROJECT,
                            expected_evidence_bucket=BUCKET,
                            docs_writer=docs or FakeDocs(), portal=portal or FakePortal(),
                            claim_store=FakeClaimStore())

    def test_same_run_docs_and_portal_exact_readback(self):
        docs = FakeDocs()
        result = self.execute_pipeline(docs=docs)
        self.assertEqual(result["status"], "E2E_READBACK_PASS")
        self.assertEqual(result["report_id"], self.report["report_id"])
        self.assertEqual(docs.title, "マーケットレポート_2026-10-16_08-00")

    def test_test_only_evidence_is_rejected_before_any_write(self):
        self.bundle["environment"] = "TEST_ONLY"
        docs, portal = FakeDocs(), FakePortal()
        with self.assertRaisesRegex(IssuanceBlocked, "NON_PRODUCTION_EVIDENCE_FORBIDDEN"):
            self.execute_pipeline(docs=docs, portal=portal)
        self.assertEqual((docs.calls, portal.calls), (0, 0))

    def test_tampered_source_evidence_is_rejected(self):
        self.bundle["evidence_object"]["bytes"] += " "
        with self.assertRaisesRegex(IssuanceBlocked, "EVIDENCE_OBJECT_HASH_MISMATCH"):
            self.execute_pipeline()

    def test_scenario_source_quote_mismatch_is_rejected(self):
        self.bundle["g2"]["scenario_review"]["scenarios"]["main_scenario"]["condition"]["source"]["quote"] = "fabricated"
        with self.assertRaisesRegex(IssuanceBlocked, "SCENARIO_SOURCE_QUOTE_MISMATCH"):
            self.execute_pipeline()

    def test_scenario_review_requires_human_branch_and_invalidation_attestation(self):
        self.bundle["g2"]["scenario_review"]["invalidation_trigger_is_decision_change"] = False
        docs, portal = FakeDocs(), FakePortal()
        with self.assertRaisesRegex(IssuanceBlocked, "SCENARIO_SEMANTIC_REVIEW_REQUIRED"):
            self.execute_pipeline(docs=docs, portal=portal)
        self.assertEqual((docs.calls, portal.calls), (0, 0))

    def test_changed_docs_body_stops_before_portal(self):
        portal = FakePortal()
        with self.assertRaisesRegex(IssuanceBlocked, "DOCS_READBACK_MISMATCH"):
            self.execute_pipeline(docs=FakeDocs(mutate=True), portal=portal)
        self.assertEqual(portal.calls, 0)

    def test_portal_readback_mismatch_fails(self):
        with self.assertRaisesRegex(IssuanceBlocked, "PORTAL_READBACK_MISMATCH"):
            self.execute_pipeline(portal=FakePortal(mutate=True))

    def test_same_claim_can_retry_but_changed_identity_conflicts(self):
        store = FakeClaimStore()
        claim = {"report_id": self.report["report_id"], "revision": 1,
                 "body_hash": self.body_hash, "evidence_id": self.evidence["evidenceId"],
                 "snapshot_id": self.evidence["snapshot"]["snapshot_id"]}
        store.claim(**claim)
        store.claim(**claim)
        with self.assertRaisesRegex(IssuanceBlocked, "DUPLICATE_SLOT_ISSUANCE_CONFLICT"):
            store.claim(**dict(claim, body_hash="0" * 64))

    def test_docs_save_must_follow_fixed_g2_body(self):
        with self.assertRaisesRegex(IssuanceBlocked, "G2_BODY_NOT_FROZEN_BEFORE_DOCS_SAVE"):
            self.execute_pipeline(docs=FakeDocs(saved_at="2026-10-16T08:00:30+09:00"))

    def test_report_body_mutation_breaks_hash_binding(self):
        self.bundle["g2"]["report"]["fullText"] += "tamper"
        with self.assertRaisesRegex(IssuanceBlocked, "G2_BODY_HASH_MISMATCH"):
            validate_issuance_bundle(self.bundle, expected_project_id=PROJECT,
                                     expected_evidence_bucket=BUCKET)

    def test_google_docs_writer_creates_in_month_folder_and_reads_exact_text(self):
        session = FakeGoogleSession(self.full_text)
        writer = GoogleDocsApiWriter(folder_id="month-folder", root_folder_id="root-folder", session=session)
        readback = writer.save_exact(
            title="Report", report_id=self.report["report_id"], revision=1,
            full_text=self.full_text, body_hash=self.body_hash,
            evidence_id=self.evidence["evidenceId"],
            snapshot_id=self.evidence["snapshot"]["snapshot_id"],
        )
        self.assertEqual(readback.full_text, self.full_text)
        self.assertEqual(readback.document_revision_id, "revision-7")
        create = next(call for call in session.calls if call[0] == "POST" and call[1].endswith("/files"))
        self.assertEqual(create[3]["parents"], ["month-folder"])
        self.assertEqual(create[3]["appProperties"]["body_hash"], self.body_hash)

    def test_google_docs_writer_rejects_non_exact_body_hash_and_terminal_shape(self):
        writer = GoogleDocsApiWriter(folder_id="month-folder", root_folder_id="root-folder",
                                     session=FakeGoogleSession(self.full_text))
        without_newline = self.full_text.rstrip("\n")
        with self.assertRaisesRegex(IssuanceBlocked, "DOCS_INPUT_TERMINAL_NEWLINE_REQUIRED"):
            writer.save_exact(title="Report", report_id=self.report["report_id"], revision=1,
                              full_text=without_newline,
                              body_hash=hashlib.sha256(without_newline.encode()).hexdigest(),
                              evidence_id=self.evidence["evidenceId"],
                              snapshot_id=self.evidence["snapshot"]["snapshot_id"])


if __name__ == "__main__":
    unittest.main()
