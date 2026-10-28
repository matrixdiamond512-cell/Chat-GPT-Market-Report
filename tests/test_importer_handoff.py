from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.persist_report_slot_evidence import build_slot_evidence, canonical_bytes
from scripts.reporting.importer_handoff import (
    ImporterHandoffBlocked,
    stage_test_only_evidence,
    validate_docs_issuance_binding,
    validate_staging_root,
)


class FakeBlob:
    def __init__(self, payload: bytes, generation: int):
        self.payload = payload
        self.generation = generation

    def download_as_bytes(self, *, if_generation_match):
        if if_generation_match != self.generation:
            raise AssertionError("generation was not pinned")
        return self.payload

    def reload(self):
        return None


class FakeBucket:
    def __init__(self, blob):
        self._blob = blob

    def blob(self, name, *, generation):
        if generation != self._blob.generation:
            raise AssertionError("requested generation mismatch")
        return self._blob


class FakeClient:
    def __init__(self, payload, generation):
        self._bucket = FakeBucket(FakeBlob(payload, generation))

    def bucket(self, name):
        if name != "market-report-test-only-evidence":
            raise AssertionError("unexpected bucket")
        return self._bucket


class ImporterHandoffTests(unittest.TestCase):
    def setUp(self):
        self.date = "2026-10-16"
        self.revision = 1
        source = {
            "generatedAt": "2026-10-16T07:55:00+09:00",
            "reportDate": self.date,
            "reportSlot": "08:00",
            "overallStatus": "verified",
            "markets": {
                "USDJPY": {
                    "id": "USDJPY",
                    "marketType": "FX",
                    "unit": "JPY",
                    "value": 157.8,
                    "change": 0.2,
                    "changePercent": 0.1,
                    "comparisonBasis": "previous_close",
                    "asOf": "2026-10-16T07:54:00+09:00",
                    "sourceId": "synthetic-test",
                    "sourceUrl": "https://example.invalid/fixture",
                    "verificationStatus": "verified",
                    "freshnessStatus": "fresh",
                    "displayValue": "157.8",
                }
            },
        }
        evidence = build_slot_evidence(
            self.date, "08:00", source, json.dumps(source, sort_keys=True).encode()
        )
        self.payload = canonical_bytes(evidence)
        self.sha256 = hashlib.sha256(self.payload).hexdigest()
        self.snapshot_id = evidence["snapshot"]["snapshot_id"]
        self.generation = 123
        self.report_id = f"{self.date}_08-00"

    def make_root(self, root: Path, *, report_id=None, revision=None):
        root.mkdir(parents=True, exist_ok=True)
        (root / ".market-report-staging.json").write_text(
            json.dumps({
                "schemaVersion": 1,
                "mode": "LOCAL_STAGING_ONLY",
                "environment": "TEST_ONLY",
                "report_id": report_id or self.report_id,
                "revision": self.revision if revision is None else revision,
            }),
            encoding="utf-8",
        )

    def stage(self, root, **overrides):
        kwargs = {
            "staging_root": root,
            "importer_root": root.parent / "current-checkout",
            "project_id": "market-report-test-only",
            "bucket_name": "market-report-test-only-evidence",
            "object_name": "test-only/08-00/evidence/run/evidence.json",
            "generation": self.generation,
            "object_sha256": self.sha256,
            "report_date": self.date,
            "revision": self.revision,
            "expected_snapshot_id": self.snapshot_id,
            "client": FakeClient(self.payload, self.generation),
        }
        kwargs.update(overrides)
        return stage_test_only_evidence(**kwargs)

    def test_exact_generation_stages_identical_bytes_and_returns_test_only_status(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "stage"
            self.make_root(root)
            result = self.stage(root)
            dest = root / "data/report-evidence/2026-10-16_08-00-r1.json"
            self.assertEqual(result["status"], "LOCAL_STAGE_READBACK_PASS")
            self.assertEqual(result["environment"], "TEST_ONLY")
            self.assertEqual(dest.read_bytes(), self.payload)
            self.assertEqual(result["object_sha256"], self.sha256)

    def test_identical_retry_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "stage"
            self.make_root(root)
            first = self.stage(root)
            second = self.stage(root)
            self.assertEqual(first, second)

    def test_hash_mismatch_fails_before_local_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "stage"
            self.make_root(root)
            with self.assertRaisesRegex(ImporterHandoffBlocked, "GCS_OBJECT_HASH_MISMATCH"):
                self.stage(root, object_sha256="0" * 64)
            self.assertFalse((root / "data/report-evidence/2026-10-16_08-00-r1.json").exists())

    def test_snapshot_mismatch_fails_before_local_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "stage"
            self.make_root(root)
            with self.assertRaisesRegex(ImporterHandoffBlocked, "STORED_SLOT_SNAPSHOT_MISMATCH"):
                self.stage(root, expected_snapshot_id="wrong")
            self.assertFalse((root / "data/report-evidence/2026-10-16_08-00-r1.json").exists())

    def test_non_test_gcp_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "stage"
            self.make_root(root)
            with self.assertRaisesRegex(ImporterHandoffBlocked, "TEST_ONLY_GCS_TARGET_REQUIRED"):
                self.stage(root, project_id="market-report-production")

    def test_wrong_marker_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "stage"
            self.make_root(root, report_id="2026-10-15_08-00")
            with self.assertRaisesRegex(ImporterHandoffBlocked, "STAGING_MARKER_IDENTITY_MISMATCH"):
                self.stage(root)

    def test_conflicting_staged_object_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "stage"
            self.make_root(root)
            dest = root / "data/report-evidence/2026-10-16_08-00-r1.json"
            dest.parent.mkdir(parents=True)
            dest.write_bytes(b"operator data")
            with self.assertRaisesRegex(ImporterHandoffBlocked, "STAGING_EVIDENCE_CONFLICT"):
                self.stage(root)
            self.assertEqual(dest.read_bytes(), b"operator data")

    def test_missing_test_only_marker_blocks_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "stage"
            root.mkdir()
            with self.assertRaisesRegex(ImporterHandoffBlocked, "STAGING_MARKER_MISSING_OR_INVALID"):
                self.stage(root)

    def test_exact_docs_properties_bind_report_and_snapshot(self):
        report = {"report_id": self.report_id, "revision": 1, "bodyHash": "a" * 64}
        receipt = {"evidenceId": "evidence-1", "snapshotId": self.snapshot_id}
        props = {
            "report_id": self.report_id,
            "revision": "1",
            "body_hash": "a" * 64,
            "evidence_id": "evidence-1",
            "snapshot_id": self.snapshot_id,
        }
        validate_docs_issuance_binding(props, report, receipt)

    def test_changed_docs_property_blocks_import(self):
        report = {"report_id": self.report_id, "revision": 1, "bodyHash": "a" * 64}
        receipt = {"evidenceId": "evidence-1", "snapshotId": self.snapshot_id}
        props = {
            "report_id": self.report_id,
            "revision": "1",
            "body_hash": "b" * 64,
            "evidence_id": "evidence-1",
            "snapshot_id": self.snapshot_id,
        }
        with self.assertRaisesRegex(ImporterHandoffBlocked, "DOCS_ISSUANCE_BINDING_MISMATCH:body_hash"):
            validate_docs_issuance_binding(props, report, receipt)

    def test_staging_checkout_must_be_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            root.mkdir()
            with self.assertRaisesRegex(ImporterHandoffBlocked, "STAGING_ROOT_MUST_BE_ISOLATED"):
                validate_staging_root(root, importer_root=root)


if __name__ == "__main__":
    unittest.main()
