import hashlib
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import call, patch

from scripts.persist_report_slot_evidence import persist_slot_evidence
from scripts.reporting.snapshot import digest


class ReportSlotEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.market_path = self.root / "latest.json"
        self.output = self.root / "evidence"
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

    def test_persists_bound_snapshot_context_and_exact_source_hash(self):
        path, created = persist_slot_evidence("2026-10-16", "08:00", self.market_path, self.output)
        self.assertTrue(created)
        record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(record["evidenceStatus"], "READY_FOR_DRAFT")
        self.assertEqual(record["reportId"], "2026-10-16_08-00")
        self.assertEqual(record["context"]["data_cutoff"], "2026-10-16T07:50:00+09:00")
        self.assertEqual(record["snapshot"]["report_id"], record["reportId"])
        self.assertEqual(record["snapshot"]["revision"], record["revision"])
        self.assertEqual(record["snapshotHash"], digest(record["snapshot"]))
        self.assertEqual(record["acquisitionSource"]["contentHash"], hashlib.sha256(self.market_path.read_bytes()).hexdigest())

    def test_identical_repeat_is_no_op(self):
        first_path, first_created = persist_slot_evidence("2026-10-16", "08:00", self.market_path, self.output)
        second_path, second_created = persist_slot_evidence("2026-10-16", "08:00", self.market_path, self.output)
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_path, second_path)

    def test_changed_acquisition_cannot_overwrite_same_revision(self):
        path, _ = persist_slot_evidence("2026-10-16", "08:00", self.market_path, self.output)
        original = path.read_bytes()
        self.payload["markets"]["USDJPY"]["value"] = 158.1
        self.write_payload()
        with self.assertRaises(FileExistsError):
            persist_slot_evidence("2026-10-16", "08:00", self.market_path, self.output)
        self.assertEqual(path.read_bytes(), original)

    def test_wrong_slot_and_stale_or_future_cutoff_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "date/slot/cutoff"):
            persist_slot_evidence("2026-10-16", "12:00", self.market_path, self.output)
        self.payload["reportSlot"] = "08:00"
        self.payload["generatedAt"] = "2026-10-16T07:30:00+09:00"
        self.write_payload()
        with self.assertRaisesRegex(ValueError, "allowed pre-draft"):
            persist_slot_evidence("2026-10-16", "08:00", self.market_path, self.output)
        self.payload["generatedAt"] = "2026-10-16T08:01:00+09:00"
        self.write_payload()
        with self.assertRaisesRegex(ValueError, "date/slot/cutoff"):
            persist_slot_evidence("2026-10-16", "08:00", self.market_path, self.output)

    def test_live_evidence_must_be_created_strictly_before_slot(self):
        jst = timezone(timedelta(hours=9))
        with self.assertRaisesRegex(ValueError, "BLOCKED_LIVE_EVIDENCE_AFTER_SLOT"):
            persist_slot_evidence(
                "2026-10-16", "08:00", self.market_path, self.output,
                require_live_before_slot=True, now=datetime(2026, 10, 16, 8, 0, tzinfo=jst),
            )
        self.assertFalse(list(self.output.glob("*.json")))
        simulated_now = datetime(2026, 10, 16, 7, 59, tzinfo=jst)
        with patch(
            "scripts.persist_report_slot_evidence.require_before_slot",
            side_effect=[None, None, None],
        ) as cutoff_check:
            path, created = persist_slot_evidence(
                "2026-10-16", "08:00", self.market_path, self.output,
                require_live_before_slot=True, now=simulated_now,
            )
        self.assertEqual(cutoff_check.call_args_list[0], call("2026-10-16", "08:00", now=simulated_now))
        self.assertEqual(cutoff_check.call_args_list[-1], call("2026-10-16", "08:00"))
        self.assertTrue(created)
        self.assertTrue(path.exists())

    def test_live_evidence_is_removed_if_write_crosses_slot_cutoff(self):
        with patch(
            "scripts.persist_report_slot_evidence.require_before_slot",
            side_effect=[None, None, ValueError("BLOCKED_LIVE_EVIDENCE_AFTER_SLOT")],
        ) as cutoff_check:
            with self.assertRaisesRegex(ValueError, "BLOCKED_LIVE_EVIDENCE_AFTER_SLOT"):
                persist_slot_evidence(
                    "2026-10-16", "08:00", self.market_path, self.output,
                    require_live_before_slot=True,
                )
        self.assertEqual(cutoff_check.call_args_list[-1], call("2026-10-16", "08:00"))
        self.assertFalse(list(self.output.glob("*.json")))

    def test_weekend_new_report_is_rejected(self):
        self.payload["generatedAt"] = "2026-10-17T07:50:00+09:00"
        self.payload["reportDate"] = "2026-10-17"
        self.write_payload()
        with self.assertRaisesRegex(ValueError, "weekend"):
            persist_slot_evidence("2026-10-17", "08:00", self.market_path, self.output)


if __name__ == "__main__":
    unittest.main()
