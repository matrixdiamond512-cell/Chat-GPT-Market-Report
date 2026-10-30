from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts.persist_report_slot_evidence import build_slot_evidence, canonical_bytes
from scripts.reporting.importer_handoff import (
    ImporterHandoffBlocked,
    stage_test_only_evidence,
    validate_docs_issuance_binding,
    validate_staging_root,
)


def _fake_google_auth_modules():
    names = (
        "google",
        "google.auth",
        "google.auth.transport",
        "google.auth.transport.requests",
        "google.oauth2",
        "google.oauth2.service_account",
    )
    modules = {}
    for name in names:
        module = types.ModuleType(name)
        module.__path__ = []
        modules[name] = module
    modules["google.auth.transport.requests"].AuthorizedSession = object
    modules["google.oauth2.service_account"].Credentials = object
    return modules


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


    def test_exact_generation_staging_feeds_receipt_and_strict_docs_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "isolated-staging"
            self.make_root(root)
            staged = self.stage(root)
            evidence_path = root / "data/report-evidence/2026-10-16_08-00-r1.json"
            body = "synthetic G2 body; TEST_ONLY integration fixture\n"
            body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
            report = {
                "date": self.date,
                "time": "08:00",
                "title": "マーケットレポート｜2026/10/16（金）08:00",
                "report_id": self.report_id,
                "revision": self.revision,
                "fullText": body,
                "bodyHash": body_hash,
                "sourceRevisionId": "test-doc-revision-7",
                "sourceDocument": {
                    "id": "test-doc-123",
                    "url": "https://docs.google.com/document/d/test-doc-123/edit",
                },
            }
            drive_file = {
                "id": "test-doc-123",
                "createdTime": "2026-10-16T08:02:00+09:00",
                "modifiedTime": "2026-10-16T08:02:01+09:00",
            }
            with patch.dict(sys.modules, _fake_google_auth_modules()):
                scripts_path = str(Path(__file__).resolve().parents[1] / "scripts")
                sys.path.insert(0, scripts_path)
                try:
                    importer_path = Path(__file__).resolve().parents[1] / "scripts/sync_reports_from_drive.py"
                    spec = importlib.util.spec_from_file_location(
                        "isolated_sync_reports_from_drive", importer_path
                    )
                    importer = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(importer)
                    receipt, hold = importer.publication_evidence(
                        root,
                        report,
                        {
                            **drive_file,
                            "appProperties": {
                                "report_id": self.report_id,
                                "revision": str(self.revision),
                                "body_hash": body_hash,
                                "evidence_id": json.loads(self.payload)["evidenceId"],
                                "snapshot_id": self.snapshot_id,
                            },
                        },
                        require_issuance_binding=True,
                    )
                    mismatched_properties = {
                        "report_id": self.report_id,
                        "revision": str(self.revision),
                        "body_hash": "0" * 64,
                        "evidence_id": receipt["evidenceId"],
                        "snapshot_id": receipt["snapshotId"],
                    }
                    blocked, reason = importer.publication_evidence(
                        root,
                        report,
                        {**drive_file, "appProperties": mismatched_properties},
                        require_issuance_binding=True,
                    )
                finally:
                    sys.path.remove(scripts_path)
            self.assertIsNone(hold)
            self.assertIsNotNone(receipt)
            self.assertEqual(staged["environment"], "TEST_ONLY")
            self.assertEqual(staged["generation"], self.generation)
            self.assertEqual(staged["object_sha256"], self.sha256)
            self.assertEqual(receipt["documentRevisionId"], "test-doc-revision-7")
            self.assertEqual(receipt["evidenceId"], json.loads(self.payload)["evidenceId"])
            self.assertEqual(receipt["snapshotId"], self.snapshot_id)
            self.assertIsNone(blocked)
            self.assertIn("body_hash", reason)


if __name__ == "__main__":
    unittest.main()
