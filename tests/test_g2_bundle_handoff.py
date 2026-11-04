from __future__ import annotations

import hashlib
import json
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts.reporting.issuance_pipeline import IssuanceBlocked
from scripts.run_0800_issuance import (load_bundle, load_pinned_g2_bundle, main as issuance_main)


JST = ZoneInfo("Asia/Tokyo")
SLOT = datetime(2026, 11, 5, 8, 10, tzinfo=JST)


class FakeBlob:
    def __init__(self, payload: bytes, generation: int, created_at: str):
        self.payload = payload
        self.generation = generation
        self.time_created = datetime.fromisoformat(created_at)
        self.downloaded_generation = None

    def download_as_bytes(self, *, if_generation_match):
        self.downloaded_generation = if_generation_match
        if if_generation_match != self.generation:
            raise RuntimeError("generation precondition failed")
        return self.payload

    def reload(self):
        return None


class FakeBucket:
    def __init__(self, blob):
        self._blob = blob
        self.requested = []

    def blob(self, name, *, generation):
        self.requested.append((name, generation))
        return self._blob


class FakeStorage:
    def __init__(self, bucket):
        self._bucket = bucket
        self.project = None

    def bucket(self, name):
        self.project = name
        return self._bucket


def bundle(report_id="2026-11-05_08-00", revision=3, evidence_generation=71):
    full_text = "Trusted frozen G2 body"
    body_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
    return {
        "g2": {
            "report_id": report_id, "revision": revision,
            "frozen_at": "2026-11-05T07:55:00+09:00",
            "body_hash": body_hash, "evidence_id": "evidence-71",
            "snapshot_id": "snapshot-71", "scenario_review": {"status": "PASS"},
            "report": {"report_id": report_id, "revision": revision,
                       "date": "2026-11-05", "time": "08:00",
                       "fullText": full_text, "bodyHash": body_hash},
        },
        "evidence_ref": {"object": "evidence/2026-11-05_08-00.json",
                         "generation": evidence_generation},
    }


def storage_for(data, generation=88, created_at="2026-11-05T07:56:00+09:00"):
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    blob = FakeBlob(raw, generation, created_at)
    bucket = FakeBucket(blob)
    return FakeStorage(bucket), bucket, blob, raw


class PinnedG2BundleHandoffTests(unittest.TestCase):
    def test_pinned_gcs_invocation_without_explicit_target_blocks_before_cloud_access(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch

        output = io.StringIO()
        with patch.dict("os.environ", {}, clear=True), \
             patch("scripts.run_0800_issuance.load_pinned_g2_bundle") as read_bundle, \
             redirect_stdout(output):
            status = issuance_main(["--g2-bundle-object", "g2/slot.json",
                                    "--g2-bundle-generation", "88"])
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(output.getvalue())["reason"], "G2_BUNDLE_TARGET_INPUT_REQUIRED")
        read_bundle.assert_not_called()

    def test_reads_only_exact_producer_generation_and_reports_digest(self):
        data = bundle()
        client, bucket, blob, raw = storage_for(data)
        result = load_pinned_g2_bundle(project_id="market-prod", bucket_name="market-evidence",
                                       object_name="g2/2026-11-05_08-00.json",
                                       generation=88, client=client)
        self.assertEqual(bucket.requested, [("g2/2026-11-05_08-00.json", 88)])
        self.assertEqual(blob.downloaded_generation, 88)
        self.assertEqual(result["data"], data)
        self.assertEqual(result["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["generation"], 88)

    def test_rejects_generation_mismatch_without_falling_back_to_latest(self):
        data = bundle()
        client, _, blob, _ = storage_for(data, generation=89)
        with self.assertRaisesRegex(IssuanceBlocked, "PINNED_G2_BUNDLE_READBACK_FAILED"):
            load_pinned_g2_bundle(project_id="market-prod", bucket_name="market-evidence",
                                  object_name="g2/slot.json", generation=88, client=client)
        self.assertEqual(blob.downloaded_generation, 88)

    def test_rejects_test_target_for_production_handoff(self):
        with self.assertRaisesRegex(IssuanceBlocked, "PRODUCTION_G2_TARGET_NOT_CONFIGURED"):
            load_pinned_g2_bundle(project_id="test-market", bucket_name="market-evidence",
                                  object_name="g2/slot.json", generation=88,
                                  client=FakeStorage(FakeBucket(None)))

    def test_gcs_handoff_binds_explicit_report_revision_and_evidence_generation(self):
        data = bundle()
        client, _, _, _ = storage_for(data)
        evidence = {"evidence_object": {"generation": 71, "object": "evidence/2026-11-05_08-00.json"}}
        with patch.dict("os.environ", {"REPORT_EVIDENCE_PROJECT_ID": "market-prod",
                                      "REPORT_EVIDENCE_BUCKET": "market-evidence"}), \
             patch("scripts.run_0800_issuance.load_pinned_g2_bundle",
                   return_value={"data": data, "generation": 88, "object": "g2/slot.json",
                                 "bucket": "market-evidence", "created_at": "2026-11-05T07:56:00+09:00",
                                 "sha256": "a" * 64}), \
             patch("scripts.run_0800_issuance.load_pinned_production_evidence",
                   return_value=evidence) as read_evidence:
            loaded = load_bundle(None, now=SLOT, g2_object_name="g2/slot.json",
                                 g2_generation=88, expected_report_id="2026-11-05_08-00",
                                 expected_revision=3, expected_evidence_object="evidence/2026-11-05_08-00.json",
                                 expected_evidence_generation=71)
        self.assertEqual(loaded["g2"], data["g2"])
        self.assertEqual(loaded["g2_bundle"]["generation"], 88)
        self.assertIs(loaded["evidence_object"], evidence["evidence_object"])
        read_evidence.assert_called_once_with(project_id="market-prod",
            bucket_name="market-evidence", object_name="evidence/2026-11-05_08-00.json",
            generation=71)

    def test_gcs_handoff_stops_on_wrong_report_id_before_reading_evidence(self):
        data = bundle()
        with patch.dict("os.environ", {"REPORT_EVIDENCE_PROJECT_ID": "market-prod",
                                      "REPORT_EVIDENCE_BUCKET": "market-evidence"}), \
             patch("scripts.run_0800_issuance.load_pinned_g2_bundle",
                   return_value={"data": data, "generation": 88, "created_at": "2026-11-05T07:56:00+09:00",
                                 "object": "g2/slot.json", "bucket": "market-evidence",
                                 "sha256": "a" * 64}), \
             patch("scripts.run_0800_issuance.load_pinned_production_evidence") as read_evidence:
            with self.assertRaisesRegex(IssuanceBlocked, "G2_BUNDLE_TARGET_IDENTITY_MISMATCH"):
                load_bundle(None, now=SLOT, g2_object_name="g2/slot.json",
                            g2_generation=88, expected_report_id="other-report",
                            expected_revision=3, expected_evidence_object="evidence/2026-11-05_08-00.json",
                            expected_evidence_generation=71)
        read_evidence.assert_not_called()

    def test_gcs_handoff_rejects_bundle_created_after_slot(self):
        data = bundle()
        with patch.dict("os.environ", {"REPORT_EVIDENCE_PROJECT_ID": "market-prod",
                                      "REPORT_EVIDENCE_BUCKET": "market-evidence"}), \
             patch("scripts.run_0800_issuance.load_pinned_g2_bundle",
                   return_value={"data": data, "generation": 88, "created_at": "2026-11-05T08:01:00+09:00",
                                 "object": "g2/slot.json", "bucket": "market-evidence",
                                 "sha256": "a" * 64}), \
             patch("scripts.run_0800_issuance.load_pinned_production_evidence") as read_evidence:
            with self.assertRaisesRegex(IssuanceBlocked, "G2_BUNDLE_CREATED_AFTER_REPORT_SLOT"):
                load_bundle(None, now=SLOT, g2_object_name="g2/slot.json",
                            g2_generation=88, expected_report_id="2026-11-05_08-00",
                            expected_revision=3, expected_evidence_object="evidence/2026-11-05_08-00.json",
                            expected_evidence_generation=71)
        read_evidence.assert_not_called()


if __name__ == "__main__":
    unittest.main()
