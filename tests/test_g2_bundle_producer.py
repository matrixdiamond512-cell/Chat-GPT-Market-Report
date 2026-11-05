from __future__ import annotations

import hashlib
import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.persist_report_slot_evidence import build_slot_evidence, canonical_bytes
from scripts.reporting.g2_bundle_producer import (
    GcsCreateOnlyG2BundleStore, TrustedG2BundleProducer,
    build_frozen_g2_bundle,
)
from scripts.reporting.issuance_pipeline import IssuanceBlocked


PROJECT = "market-report-production-shadow"
EVIDENCE_BUCKET = "market-report-production-evidence"
G2_BUCKET = "market-report-production-g2"
JST = ZoneInfo("Asia/Tokyo")
SLOT = datetime(2026, 10, 16, 8, 6, tzinfo=JST)
EVIDENCE_OBJECT = "evidence/2026-10-16_08-00-r1.json"
EVIDENCE_GENERATION = 123


def fixture_source():
    generated_at = "2026-10-16T07:55:00+09:00"
    market_payload = {
        "generatedAt": generated_at, "reportDate": "2026-10-16",
        "reportSlot": "08:00", "overallStatus": "verified",
        "markets": {"USDJPY": {
            "id": "USDJPY", "marketType": "FX", "unit": "JPY",
            "value": 157.8, "change": 0.2, "changePercent": 0.1,
            "comparisonBasis": "previous_close", "asOf": generated_at,
            "sourceId": "synthetic-test", "sourceUrl": "https://example.invalid/fixture",
            "verificationStatus": "verified", "freshnessStatus": "fresh",
            "displayValue": "157.8",
        }},
    }
    evidence = build_slot_evidence(
        "2026-10-16", "08:00", market_payload,
        json.dumps(market_payload, sort_keys=True).encode("utf-8"),
        evidence_created_at=datetime.fromisoformat(generated_at))
    evidence_bytes = canonical_bytes(evidence)
    phrases = [
        "Main condition: above 100.", "Main development: rally continues.",
        "Main impact: equities rise.", "Alternative condition: below 100.",
        "Alternative development: pullback extends.", "Alternative impact: yen strengthens.",
        "Invalidation condition: yield breaks 5%.", "Invalidation development: main thesis fails.",
        "Invalidation impact: risk assets fall.",
    ]
    sections = [
        "結論", "総括", "今日の相場テーマ", "金利", "重要ニュース",
        "主要市場データ", "市場データ確認：金、WTI、日経平均、USD/JPY、EUR/USD、BTC。",
        "クロスアセット資金フロー", "需給・ポジション", "6市場の個別見通し",
        "メインシナリオ", phrases[0], phrases[1], phrases[2],
        "代替シナリオ", phrases[3], phrases[4], phrases[5],
        "崩れる条件", phrases[6], phrases[7], phrases[8],
    ]
    sections.extend(["TEST_FIXTURE: synthetic body-length coverage."] * 28)
    full_text = "マーケットレポート｜2026/10/16（金）08:00\n" + "\n".join(sections) + "\n"
    body_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
    report = {
        "date": "2026-10-16", "time": "08:00",
        "title": "マーケットレポート｜2026/10/16（金）08:00",
        "report_id": "2026-10-16_08-00", "revision": 1,
        "fullText": full_text,
    }
    scenarios = {}
    for name, triplet in {
        "main_scenario": phrases[0:3],
        "alternative_scenario": phrases[3:6],
        "invalidation_trigger": phrases[6:9],
    }.items():
        fields = {}
        for field, quote in zip(("condition", "development", "market_impact"), triplet):
            start = full_text.index(quote)
            fields[field] = {"text": quote, "source": {
                "start": start, "end": start + len(quote), "quote": quote}}
        scenarios[name] = fields
    review = {
        "status": "APPROVED", "reviewer": "fixture-reviewer",
        "reviewed_at": "2026-10-16T08:04:00+09:00",
        "branching_validated": True,
        "invalidation_trigger_is_decision_change": True,
        "scenarios": scenarios,
    }
    envelope = {
        "environment": "PRODUCTION", "project_id": PROJECT,
        "bucket": EVIDENCE_BUCKET, "object": EVIDENCE_OBJECT,
        "generation": EVIDENCE_GENERATION,
        "generation_readback": EVIDENCE_GENERATION,
        "created_at": generated_at, "bytes": evidence_bytes.decode("utf-8"),
        "object_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
        "evidence_id": evidence["evidenceId"],
    }
    return report, full_text, envelope, review, evidence


class FakeStore:
    def __init__(self):
        self.objects = {}
        self.calls = 0

    def create_only(self, *, report_id, revision, bundle):
        from scripts.reporting.g2_bundle_producer import G2BundleWriteReceipt
        self.calls += 1
        self.objects[(report_id, revision)] = bundle
        return G2BundleWriteReceipt("fixture/" + report_id + ".json", 44,
                                    "a" * 64, "CREATED")


class FakeBlob:
    def __init__(self):
        self.payload = None
        self.generation = None
        self.upload_calls = 0

    def upload_from_string(self, payload, *, content_type, if_generation_match):
        self.upload_calls += 1
        assert content_type == "application/json"
        if if_generation_match != 0 or self.payload is not None:
            raise RuntimeError("precondition failed")
        self.payload = bytes(payload)
        self.generation = 321
        self.time_created = datetime.fromisoformat("2026-10-16T08:05:10+09:00")

    def reload(self):
        if self.payload is None:
            raise RuntimeError("not found")

    def download_as_bytes(self, *, if_generation_match):
        if if_generation_match != self.generation or self.payload is None:
            raise RuntimeError("generation mismatch")
        return self.payload


class FakeBucket:
    def __init__(self, blob):
        self._blob = blob
        self.names = []

    def blob(self, name):
        self.names.append(name)
        return self._blob


class FakeClient:
    def __init__(self, bucket):
        self._bucket = bucket
        self.bucket_names = []

    def bucket(self, name):
        self.bucket_names.append(name)
        return self._bucket


class G2BundleProducerTests(unittest.TestCase):
    def setUp(self):
        self.report, self.full_text, self.evidence_object, self.review, self.evidence = fixture_source()

    def build(self, **overrides):
        args = {
            "report": self.report, "full_text": self.full_text,
            "evidence_object": self.evidence_object,
            "evidence_object_name": EVIDENCE_OBJECT,
            "evidence_generation": EVIDENCE_GENERATION,
            "frozen_at": "2026-10-16T08:05:00+09:00",
            "scenario_review": self.review, "now": SLOT,
            "expected_project_id": PROJECT,
            "expected_evidence_bucket": EVIDENCE_BUCKET,
        }
        args.update(overrides)
        return build_frozen_g2_bundle(**args)

    def test_freezes_task_text_and_binds_exact_evidence_identity(self):
        bundle = self.build()
        g2, report = bundle["g2"], bundle["g2"]["report"]
        self.assertEqual(g2["report_id"], "2026-10-16_08-00")
        self.assertEqual(g2["revision"], 1)
        self.assertEqual(g2["body_hash"], hashlib.sha256(self.full_text.encode()).hexdigest())
        self.assertEqual(report["fullText"], self.full_text)
        self.assertEqual(report["snapshot"], self.evidence["snapshot"])
        self.assertEqual(g2["evidence_id"], self.evidence["evidenceId"])
        self.assertEqual(bundle["evidence_ref"], {
            "object": EVIDENCE_OBJECT, "generation": EVIDENCE_GENERATION})

    def test_rejects_late_evidence_bytes_hash_or_identity(self):
        envelope = dict(self.evidence_object, object_sha256="0" * 64)
        with self.assertRaisesRegex(IssuanceBlocked, "EVIDENCE_HASH_MISMATCH"):
            self.build(evidence_object=envelope)
        envelope = dict(self.evidence_object, evidence_id="different-evidence")
        # The evidence bytes remain authoritative; changing only envelope metadata is not accepted.
        with self.assertRaisesRegex(IssuanceBlocked, "EVIDENCE_IDENTITY_MISMATCH"):
            self.build(evidence_object=envelope)

    def test_evidence_created_before_slot_remains_valid_for_later_g2_freeze(self):
        envelope = dict(self.evidence_object, created_at="2026-10-16T07:59:30+09:00")
        bundle = self.build(evidence_object=envelope)
        self.assertEqual(bundle["g2"]["frozen_at"], "2026-10-16T08:05:00+09:00")

    def test_rejects_evidence_created_after_slot(self):
        envelope = dict(self.evidence_object, created_at="2026-10-16T08:00:01+09:00")
        with self.assertRaisesRegex(IssuanceBlocked, "EVIDENCE_CREATED_TOO_LATE"):
            self.build(evidence_object=envelope)

    def test_accepts_g2_freeze_during_0800_issuance_window_after_slot_start(self):
        bundle = self.build(frozen_at="2026-10-16T08:05:00+09:00",
                            now=datetime(2026, 10, 16, 8, 6, tzinfo=JST))
        self.assertEqual(bundle["g2"]["frozen_at"], "2026-10-16T08:05:00+09:00")

    def test_rejects_freeze_outside_slot_window_or_after_current_clock(self):
        with self.assertRaisesRegex(IssuanceBlocked, "FREEZE_OUTSIDE_SLOT_WINDOW"):
            self.build(frozen_at="2026-10-16T07:59:59+09:00")
        with self.assertRaisesRegex(IssuanceBlocked, "FREEZE_OUTSIDE_SLOT_WINDOW"):
            self.build(frozen_at="2026-10-16T08:40:01+09:00")
        with self.assertRaisesRegex(IssuanceBlocked, "FREEZE_TIME_INVALID"):
            self.build(frozen_at="2026-10-16T08:07:00+09:00",
                       now=datetime(2026, 10, 16, 8, 6, tzinfo=JST))
        with self.assertRaisesRegex(IssuanceBlocked, "AFTER_SLOT_WINDOW"):
            self.build(now=datetime(2026, 10, 16, 8, 41, tzinfo=JST))

    def test_rejects_unapproved_or_late_scenario_review(self):
        with self.assertRaisesRegex(IssuanceBlocked, "HUMAN_REVIEW_REQUIRED"):
            self.build(scenario_review={**self.review, "status": "PENDING"})
        with self.assertRaisesRegex(IssuanceBlocked, "REVIEW_AFTER_FREEZE"):
            self.build(scenario_review={**self.review,
                                        "reviewed_at": "2026-10-16T08:05:30+09:00"})
        with self.assertRaisesRegex(IssuanceBlocked, "REVIEW_BEFORE_SLOT"):
            self.build(scenario_review={**self.review,
                                        "reviewed_at": "2026-10-16T07:59:30+09:00"})
        with self.assertRaisesRegex(IssuanceBlocked, "REVIEW_TIME_REQUIRED"):
            self.build(scenario_review={k: v for k, v in self.review.items()
                                       if k != "reviewed_at"})

    def test_rejects_scenario_review_bound_to_different_identity(self):
        with self.assertRaisesRegex(IssuanceBlocked, "SCENARIO_REVIEW_IDENTITY_MISMATCH"):
            self.build(scenario_review={**self.review, "report_id": "other-report"})

    def test_rejects_non_0800_or_mismatched_report_identity(self):
        with self.assertRaisesRegex(IssuanceBlocked, "SLOT_NOT_SUPPORTED"):
            self.build(report={**self.report, "time": "12:00"})
        with self.assertRaisesRegex(IssuanceBlocked, "REPORT_IDENTITY_INVALID"):
            self.build(report={**self.report, "report_id": "other-report"})

    def test_create_only_store_marks_uncertain_readback_retryable(self):
        class UnreadableBlob(FakeBlob):
            def upload_from_string(self, payload, *, content_type, if_generation_match):
                super().upload_from_string(payload, content_type=content_type,
                                           if_generation_match=if_generation_match)
                raise RuntimeError("creation response lost")
            def reload(self):
                raise RuntimeError("readback unavailable")
        bundle = self.build()
        store = GcsCreateOnlyG2BundleStore(project_id=PROJECT, bucket_name=G2_BUCKET,
                                            client=FakeClient(FakeBucket(UnreadableBlob())))
        with self.assertRaisesRegex(IssuanceBlocked, "G2_BUNDLE_CREATE_OR_READBACK_FAILED") as caught:
            store.create_only(report_id="2026-10-16_08-00", revision=1, bundle=bundle)
        self.assertTrue(caught.exception.retryable)

    def test_trusted_producer_writes_only_after_valid_freeze(self):
        store = FakeStore()
        producer = TrustedG2BundleProducer(
            store, expected_project_id=PROJECT,
            expected_evidence_bucket=EVIDENCE_BUCKET)
        bundle, receipt = producer.freeze_and_store(
            report=self.report, full_text=self.full_text,
            evidence_object=self.evidence_object,
            evidence_object_name=EVIDENCE_OBJECT,
            evidence_generation=EVIDENCE_GENERATION,
            frozen_at="2026-10-16T08:05:00+09:00",
            scenario_review=self.review, now=SLOT)
        self.assertEqual(store.calls, 1)
        self.assertEqual(receipt.sha256, "a" * 64)
        self.assertEqual(receipt.status, "CREATED")

    def test_create_only_gcs_store_writes_and_reads_exact_generation(self):
        blob, bucket = FakeBlob(), None
        bucket = FakeBucket(blob)
        client = FakeClient(bucket)
        store = GcsCreateOnlyG2BundleStore(project_id=PROJECT, bucket_name=G2_BUCKET,
                                            client=client)
        bundle = self.build()
        receipt = store.create_only(report_id="2026-10-16_08-00",
                                    revision=1, bundle=bundle)
        self.assertEqual(receipt.object_name, "g2-bundles/2026-10-16_08-00-r1.json")
        self.assertEqual(receipt.generation, 321)
        self.assertEqual(receipt.status, "CREATED")
        self.assertEqual(bucket.names, [receipt.object_name])
        self.assertEqual(client.bucket_names, [G2_BUCKET])
        self.assertEqual(json.loads(blob.payload), bundle)

    def test_identical_retry_reuses_existing_generation_without_overwrite(self):
        blob = FakeBlob()
        store = GcsCreateOnlyG2BundleStore(project_id=PROJECT, bucket_name=G2_BUCKET,
                                            client=FakeClient(FakeBucket(blob)))
        bundle = self.build()
        first = store.create_only(report_id="2026-10-16_08-00", revision=1, bundle=bundle)
        original = blob.payload
        second = store.create_only(report_id="2026-10-16_08-00", revision=1, bundle=bundle)
        self.assertEqual(first.generation, second.generation)
        self.assertEqual(second.status, "IDEMPOTENT_RETRY")
        self.assertEqual(blob.payload, original)
        self.assertEqual(blob.upload_calls, 2)

    def test_gcs_store_rejects_object_created_after_slot(self):
        class LateCreatedBlob(FakeBlob):
            def upload_from_string(self, payload, *, content_type, if_generation_match):
                super().upload_from_string(payload, content_type=content_type,
                                           if_generation_match=if_generation_match)
                self.time_created = datetime.fromisoformat("2026-10-16T08:40:01+09:00")
        blob = LateCreatedBlob()
        store = GcsCreateOnlyG2BundleStore(project_id=PROJECT, bucket_name=G2_BUCKET,
                                            client=FakeClient(FakeBucket(blob)))
        with self.assertRaisesRegex(IssuanceBlocked, "G2_BUNDLE_CREATED_AFTER_SLOT_WINDOW"):
            store.create_only(report_id="2026-10-16_08-00", revision=1,
                              bundle=self.build())

    def test_gcs_store_rejects_g2_object_created_before_body_freeze(self):
        class EarlyCreatedBlob(FakeBlob):
            def upload_from_string(self, payload, *, content_type, if_generation_match):
                super().upload_from_string(payload, content_type=content_type,
                                           if_generation_match=if_generation_match)
                self.time_created = datetime.fromisoformat("2026-10-16T08:04:59+09:00")
        blob = EarlyCreatedBlob()
        store = GcsCreateOnlyG2BundleStore(project_id=PROJECT, bucket_name=G2_BUCKET,
                                            client=FakeClient(FakeBucket(blob)))
        with self.assertRaisesRegex(IssuanceBlocked, "G2_BUNDLE_CREATED_BEFORE_FREEZE"):
            store.create_only(report_id="2026-10-16_08-00", revision=1,
                              bundle=self.build())

    def test_conflicting_existing_generation_blocks(self):
        blob = FakeBlob()
        store = GcsCreateOnlyG2BundleStore(project_id=PROJECT, bucket_name=G2_BUCKET,
                                            client=FakeClient(FakeBucket(blob)))
        good = self.build()
        store.create_only(report_id="2026-10-16_08-00", revision=1, bundle=good)
        different = json.loads(json.dumps(good))
        different["producer_metadata_fixture"] = "different"
        with self.assertRaisesRegex(IssuanceBlocked, "G2_BUNDLE_EXISTING_CONFLICT"):
            store.create_only(report_id="2026-10-16_08-00", revision=1, bundle=different)
        self.assertEqual(blob.upload_calls, 2)

    def test_invalid_owner_target_is_rejected_when_constructing_store(self):
        with self.assertRaisesRegex(ValueError, "PRODUCTION_G2_TARGET_REQUIRED"):
            GcsCreateOnlyG2BundleStore(project_id="market-test-project",
                                        bucket_name=G2_BUCKET,
                                        client=FakeClient(FakeBucket(FakeBlob())))


if __name__ == "__main__":
    unittest.main()
