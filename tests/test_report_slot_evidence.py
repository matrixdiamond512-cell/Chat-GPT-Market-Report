import hashlib
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import call, patch

from scripts.persist_report_slot_evidence import (
    build_slot_evidence,
    gcs_reference_path,
    canonical_bytes,
    persist_gcs_slot_evidence,
    require_slot_window,
    persist_slot_evidence,
    reconcile_gcs_slot_evidence,
    validate_stored_slot_evidence,
)
from scripts.reporting.snapshot import digest




class FakeNotFound(Exception):
    def code(self):
        return 404


class FakePreconditionFailed(Exception):
    def code(self):
        return 412


class FakeGcsBlob:
    def __init__(self, store, name, generation=None):
        self.store = store
        self.name = name
        self.requested_generation = generation
        self.metadata = None

    def upload_from_string(self, payload, *, content_type, if_generation_match):
        if if_generation_match != 0:
            raise AssertionError("create-only precondition required")
        if self.name in self.store:
            raise FakePreconditionFailed("object already exists")
        self.store[self.name] = {
            "payload": bytes(payload),
            "generation": 731,
            "time_created": self.store.get("_created_at_override", datetime(2026, 10, 16, 7, 51, tzinfo=timezone(timedelta(hours=9)))),
            "metadata": self.metadata,
            "corrupt_readback": self.store.get("_corrupt_readback", False),
        }

    def reload(self):
        record = self.store.get(self.name)
        if record is None:
            raise FakeNotFound()
        if self.requested_generation is not None and self.requested_generation != record["generation"]:
            raise FakeNotFound()
        self.generation = record["generation"]
        self.time_created = record["time_created"]
        self.metadata = record["metadata"]

    def download_as_bytes(self, *, if_generation_match):
        record = self.store.get(self.name)
        if record is None or if_generation_match != record["generation"]:
            raise FakeNotFound()
        if record.get("corrupt_readback"):
            return b"corrupt"
        return record["payload"]


class FakeGcsBucket:
    def __init__(self, store):
        self.store = store

    def blob(self, name, generation=None):
        return FakeGcsBlob(self.store, name, generation)


class FakeGcsClient:
    def __init__(self):
        self.store = {}
        self.corrupt_readback = False

    def bucket(self, name):
        return FakeGcsBucket(self.store)


class ReportSlotEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.market_path = self.root / "latest.json"
        self.output = self.root / "evidence"
        self.run_at = datetime(2026, 10, 16, 7, 51, tzinfo=timezone(timedelta(hours=9)))
        self.payload = {
            "generatedAt": "2026-10-16T07:50:00+09:00",
            "reportDate": "2026-10-16",
            "reportSlot": "08:00",
            "overallStatus": "verified",
            "markets": {
                "USDJPY": {
                    "id": "USDJPY",
                    "marketType": "FX",
                    "unit": "JPY",
                    "value": 157.8,
                    "change": 0.0,
                    "changePercent": 0.0,
                    "comparisonBasis": "previous_close",
                    "asOf": "2026-10-16T07:49:00+09:00",
                    "sourceId": "source-usdjpy",
                    "sourceUrl": "https://example.test/usdjpy",
                    "verificationStatus": "verified",
                    "freshnessStatus": "fresh",
                    "displayValue": "157.8",
                }
            },
        }
        self.write_payload()

    def tearDown(self):
        self.temp.cleanup()

    def write_payload(self):
        self.market_path.write_text(json.dumps(self.payload, ensure_ascii=False), encoding="utf-8")

    def persist(self, *args, **kwargs):
        kwargs.setdefault("now", self.run_at)
        return persist_slot_evidence(*args, **kwargs)

    def test_persists_bound_snapshot_context_and_exact_source_hash(self):
        path, created = self.persist("2026-10-16", "08:00", self.market_path, self.output)
        self.assertTrue(created)
        record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(record["evidenceStatus"], "READY_FOR_DRAFT")
        self.assertEqual(record["reportId"], "2026-10-16_08-00")
        self.assertEqual(record["context"]["data_cutoff"], "2026-10-16T07:50:00+09:00")
        self.assertEqual(record["evidenceCreatedAt"], "2026-10-16T07:51:00+09:00")
        self.assertEqual(record["snapshot"]["report_id"], record["reportId"])
        self.assertEqual(record["snapshot"]["revision"], record["revision"])
        self.assertEqual(record["snapshotHash"], digest(record["snapshot"]))
        self.assertEqual(record["acquisitionSource"]["contentHash"], hashlib.sha256(self.market_path.read_bytes()).hexdigest())

    def test_identical_repeat_is_no_op(self):
        first_path, first_created = self.persist("2026-10-16", "08:00", self.market_path, self.output)
        second_path, second_created = self.persist("2026-10-16", "08:00", self.market_path, self.output)
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_path, second_path)

    def test_existing_immutable_evidence_can_be_validated_without_latest_data(self):
        path, _ = self.persist("2026-10-16", "08:00", self.market_path, self.output)
        original = path.read_bytes()
        validated = validate_stored_slot_evidence(original, "2026-10-16", "08:00")
        self.assertEqual(validated["reportId"], "2026-10-16_08-00")
        self.assertEqual(validated["evidenceId"], json.loads(original)["evidenceId"])
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_HASH_MISMATCH"):
            tampered = json.loads(original)
            tampered["snapshot"]["captured_at"] = "2026-10-16T07:59:00+09:00"
            validate_stored_slot_evidence(json.dumps(tampered).encode("utf-8"), "2026-10-16", "08:00")

    def test_changed_acquisition_cannot_overwrite_same_revision(self):
        path, _ = self.persist("2026-10-16", "08:00", self.market_path, self.output)
        original = path.read_bytes()
        self.payload["markets"]["USDJPY"]["value"] = 158.1
        self.write_payload()
        with self.assertRaises(FileExistsError):
            self.persist("2026-10-16", "08:00", self.market_path, self.output)
        self.assertEqual(path.read_bytes(), original)

    def test_wrong_slot_and_stale_or_future_cutoff_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "INPUT_SLOT_MISMATCH"):
            self.persist("2026-10-16", "12:00", self.market_path, self.output)
        self.payload["reportSlot"] = "08:00"
        self.payload["generatedAt"] = "2026-10-16T07:30:00+09:00"
        self.write_payload()
        with self.assertRaisesRegex(ValueError, "INPUT_STALE"):
            self.persist("2026-10-16", "08:00", self.market_path, self.output)
        self.payload["generatedAt"] = "2026-10-16T08:01:00+09:00"
        self.write_payload()
        with self.assertRaisesRegex(ValueError, "INPUT_STALE"):
            self.persist("2026-10-16", "08:00", self.market_path, self.output)

    def test_live_evidence_must_be_created_strictly_before_slot(self):
        jst = timezone(timedelta(hours=9))
        with self.assertRaisesRegex(ValueError, "BLOCKED_SCHEDULE_WINDOW_MISMATCH"):
            self.persist(
                "2026-10-16", "08:00", self.market_path, self.output,
                require_live_before_slot=True, now=datetime(2026, 10, 16, 8, 0, tzinfo=jst),
            )
        self.assertFalse(list(self.output.glob("*.json")))
        simulated_now = datetime(2026, 10, 16, 7, 59, tzinfo=jst)
        with patch(
            "scripts.persist_report_slot_evidence.require_slot_window",
            side_effect=[None, None, None, None],
        ) as cutoff_check:
            path, created = self.persist(
                "2026-10-16", "08:00", self.market_path, self.output,
                require_live_before_slot=True, now=simulated_now,
            )
        self.assertEqual(cutoff_check.call_args_list[0], call("2026-10-16", "08:00", now=simulated_now))
        self.assertEqual(cutoff_check.call_args_list[-1], call("2026-10-16", "08:00"))
        self.assertTrue(created)
        self.assertTrue(path.exists())

    def test_live_evidence_is_removed_if_write_crosses_slot_cutoff(self):
        with patch(
            "scripts.persist_report_slot_evidence.require_slot_window",
            side_effect=[None, None, None, ValueError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:SCHEDULE_LATE")],
        ) as cutoff_check:
            with self.assertRaisesRegex(ValueError, "BLOCKED_SCHEDULE_WINDOW_MISMATCH"):
                self.persist(
                    "2026-10-16", "08:00", self.market_path, self.output,
                    require_live_before_slot=True,
                )
        self.assertEqual(cutoff_check.call_args_list[-1], call("2026-10-16", "08:00"))
        self.assertFalse(list(self.output.glob("*.json")))

    def test_cutoff_cleanup_preserves_a_replacement_written_by_another_actor(self):
        evidence_path = self.output / "2026-10-16_08-00-r1.json"
        calls = 0

        def replace_then_cross_cutoff(report_date, report_time, *, now=None):
            nonlocal calls
            calls += 1
            if calls == 4:
                evidence_path.rename(evidence_path.with_suffix(".owned"))
                evidence_path.write_bytes(b"other actor's evidence")
                raise ValueError("BLOCKED_SCHEDULE_WINDOW_MISMATCH:SCHEDULE_LATE")

        with patch(
            "scripts.persist_report_slot_evidence.require_slot_window",
            side_effect=replace_then_cross_cutoff,
        ):
            with self.assertRaisesRegex(ValueError, "BLOCKED_SCHEDULE_WINDOW_MISMATCH"):
                self.persist(
                    "2026-10-16", "08:00", self.market_path, self.output,
                    require_live_before_slot=True,
                )
        self.assertEqual(evidence_path.read_bytes(), b"other actor's evidence")



    def test_slot_window_boundaries_weekdays_date_change_and_delayed_run(self):
        jst = timezone(timedelta(hours=9))
        target_date = "2026-10-16"  # Friday
        accepted = datetime(2026, 10, 16, 7, 45, tzinfo=jst)
        self.assertEqual(require_slot_window(target_date, "08:00", now=accepted), accepted)
        blocked_cases = [
            ("2026-10-16", "08:00", datetime(2026, 10, 16, 7, 44, 59, tzinfo=jst), "early"),
            ("2026-10-16", "08:00", datetime(2026, 10, 16, 8, 0, tzinfo=jst), "SCHEDULE_LATE"),
            ("2026-10-20", "21:00", datetime(2026, 10, 20, 3, 52, tzinfo=jst), "SCHEDULE_LATE"),
            ("2026-10-17", "08:00", datetime(2026, 10, 17, 7, 51, tzinfo=jst), "non-weekday"),
            ("2026-10-17", "21:00", datetime(2026, 10, 17, 3, 52, tzinfo=jst), "SCHEDULE_LATE"),
            ("2026-10-19", "08:00", datetime(2026, 10, 16, 7, 51, tzinfo=jst), "early"),
        ]
        for report_date, slot, now, reason in blocked_cases:
            with self.subTest(report_date=report_date, slot=slot, now=now):
                with self.assertRaisesRegex(ValueError, reason):
                    require_slot_window(report_date, slot, now=now)

    def test_gcs_create_only_generation_hash_binding_and_identical_retry(self):
        evidence_path, _ = self.persist("2026-10-16", "08:00", self.market_path, self.output)
        evidence = evidence_path.read_bytes()
        client = FakeGcsClient()
        first = persist_gcs_slot_evidence(
            evidence, "test-evidence", "pre-draft-evidence/2026-10-16_08-00-r1.json",
            "2026-10-16", "08:00", client=client, now=self.run_at,
        )
        second = persist_gcs_slot_evidence(
            evidence, "test-evidence", "pre-draft-evidence/2026-10-16_08-00-r1.json",
            "2026-10-16", "08:00", client=client, now=self.run_at,
        )
        record = client.store[first["object"]]
        self.assertEqual(first["generation"], 731)
        self.assertEqual(second, first)
        self.assertEqual(first["canonicalStore"], "gcs")
        self.assertEqual(first["reportId"], "2026-10-16_08-00")
        self.assertEqual(first["revision"], 1)
        self.assertEqual(first["evidenceId"], json.loads(evidence)["evidenceId"])
        self.assertEqual(first["snapshotId"], json.loads(evidence)["snapshot"]["snapshot_id"])
        self.assertEqual(first["contentSha256"], hashlib.sha256(evidence).hexdigest())
        self.assertEqual(record["payload"], evidence)
        self.assertEqual(record["metadata"]["contentsha256"], first["contentSha256"])
        self.assertEqual(record["metadata"]["sourcedatahash"],
                         json.loads(evidence)["acquisitionSource"]["contentHash"])

    def test_gcs_create_only_rejects_different_existing_bytes_without_overwrite(self):
        evidence_path, _ = self.persist("2026-10-16", "08:00", self.market_path, self.output)
        original = evidence_path.read_bytes()
        client = FakeGcsClient()
        persist_gcs_slot_evidence(
            original, "test-evidence", "pre-draft-evidence/2026-10-16_08-00-r1.json",
            "2026-10-16", "08:00", client=client, now=self.run_at,
        )
        altered_record = json.loads(original.decode("utf-8"))
        altered_record["conflictMarker"] = "do-not-overwrite"
        altered = canonical_bytes(altered_record)
        with self.assertRaisesRegex(FileExistsError, "BLOCKED_GCS_EVIDENCE_CONFLICT"):
            persist_gcs_slot_evidence(
                altered, "test-evidence", "pre-draft-evidence/2026-10-16_08-00-r1.json",
                "2026-10-16", "08:00", client=client, now=self.run_at,
            )
        self.assertEqual(client.store["pre-draft-evidence/2026-10-16_08-00-r1.json"]["payload"], original)

    def test_gcs_readback_hash_mismatch_fails_closed(self):
        evidence_path, _ = self.persist("2026-10-16", "08:00", self.market_path, self.output)
        client = FakeGcsClient()
        client.store["_corrupt_readback"] = True
        with self.assertRaisesRegex(RuntimeError, "EVIDENCE_WRITE_FAILED"):
            persist_gcs_slot_evidence(
                evidence_path.read_bytes(), "test-evidence",
                "pre-draft-evidence/2026-10-16_08-00-r1.json",
                "2026-10-16", "08:00", client=client, now=self.run_at,
            )

    def test_partial_local_success_can_retry_exact_bytes_to_gcs_and_mirror(self):
        evidence_path, _ = self.persist("2026-10-16", "08:00", self.market_path, self.output)
        expected = evidence_path.read_bytes()
        client = FakeGcsClient()
        restored = reconcile_gcs_slot_evidence(
            "2026-10-16", "08:00", self.output, "test-evidence", "pre-draft-evidence",
            client=client, now=self.run_at,
        )
        self.assertTrue(restored)
        reference_path = gcs_reference_path(evidence_path)
        self.assertTrue(reference_path.exists())
        self.assertEqual(evidence_path.read_bytes(), expected)
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        self.assertEqual(reference["generation"], 731)
        self.assertEqual(reference["contentSha256"], hashlib.sha256(expected).hexdigest())

    def test_gcs_existing_object_reconciles_missing_local_mirror_exactly(self):
        evidence_path, _ = self.persist("2026-10-16", "08:00", self.market_path, self.output)
        expected = evidence_path.read_bytes()
        client = FakeGcsClient()
        persist_gcs_slot_evidence(
            expected, "test-evidence", "pre-draft-evidence/2026-10-16_08-00-r1.json",
            "2026-10-16", "08:00", client=client, now=self.run_at,
        )
        evidence_path.unlink()
        restored = reconcile_gcs_slot_evidence(
            "2026-10-16", "08:00", self.output, "test-evidence", "pre-draft-evidence",
            client=client, now=self.run_at,
        )
        self.assertTrue(restored)
        self.assertEqual(evidence_path.read_bytes(), expected)
        self.assertTrue(gcs_reference_path(evidence_path).exists())

    def test_local_mirror_conflict_with_gcs_canonical_is_not_overwritten(self):
        evidence_path, _ = self.persist("2026-10-16", "08:00", self.market_path, self.output)
        expected = evidence_path.read_bytes()
        client = FakeGcsClient()
        persist_gcs_slot_evidence(
            expected, "test-evidence", "pre-draft-evidence/2026-10-16_08-00-r1.json",
            "2026-10-16", "08:00", client=client, now=self.run_at,
        )
        changed = json.loads(expected.decode("utf-8"))
        changed["conflictMarker"] = "local-differs-from-canonical"
        changed_bytes = canonical_bytes(changed)
        evidence_path.write_bytes(changed_bytes)
        with self.assertRaisesRegex(FileExistsError, "BLOCKED_GCS_EVIDENCE_CONFLICT"):
            reconcile_gcs_slot_evidence(
                "2026-10-16", "08:00", self.output, "test-evidence", "pre-draft-evidence",
                client=client, now=self.run_at,
            )
        self.assertEqual(evidence_path.read_bytes(), changed_bytes)



    def test_gcs_metadata_source_hash_is_required_on_generation_readback(self):
        evidence_path, _ = self.persist("2026-10-16", "08:00", self.market_path, self.output)
        client = FakeGcsClient()
        object_name = "pre-draft-evidence/2026-10-16_08-00-r1.json"
        persist_gcs_slot_evidence(
            evidence_path.read_bytes(), "test-evidence", object_name,
            "2026-10-16", "08:00", client=client, now=self.run_at,
        )
        client.store[object_name]["metadata"]["sourcedatahash"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "EVIDENCE_WRITE_FAILED"):
            persist_gcs_slot_evidence(
                evidence_path.read_bytes(), "test-evidence", object_name,
                "2026-10-16", "08:00", client=client, now=self.run_at,
            )

    def test_gcs_object_timestamp_after_cutoff_is_rejected(self):
        evidence_path, _ = self.persist("2026-10-16", "08:00", self.market_path, self.output)
        client = FakeGcsClient()
        object_name = "pre-draft-evidence/2026-10-16_08-00-r1.json"
        # The fake store simulates a slow/late server-side object create.
        client.store["_created_at_override"] = datetime(2026, 10, 16, 8, 0, tzinfo=timezone(timedelta(hours=9)))
        with self.assertRaisesRegex(RuntimeError, "EVIDENCE_WRITE_FAILED"):
            persist_gcs_slot_evidence(
                evidence_path.read_bytes(), "test-evidence", object_name,
                "2026-10-16", "08:00", client=client, now=self.run_at,
            )

    def test_weekend_new_report_is_rejected(self):
        self.payload["generatedAt"] = "2026-10-17T07:50:00+09:00"
        self.payload["reportDate"] = "2026-10-17"
        self.write_payload()
        with self.assertRaisesRegex(ValueError, "BLOCKED_SCHEDULE_WINDOW_MISMATCH:non-weekday"):
            self.persist("2026-10-17", "08:00", self.market_path, self.output)


if __name__ == "__main__":
    unittest.main()
