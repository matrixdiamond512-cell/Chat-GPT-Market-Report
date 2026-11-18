import hashlib
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import call, patch

from scripts.persist_report_slot_evidence import persist_slot_evidence, validate_stored_slot_evidence, require_live_pre_slot_window
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

    def test_existing_immutable_evidence_can_be_validated_without_latest_data(self):
        path, _ = persist_slot_evidence("2026-10-16", "08:00", self.market_path, self.output)
        original = path.read_bytes()
        validated = validate_stored_slot_evidence(original, "2026-10-16", "08:00")
        self.assertEqual(validated["reportId"], "2026-10-16_08-00")
        self.assertEqual(validated["evidenceId"], json.loads(original)["evidenceId"])
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_HASH_MISMATCH"):
            tampered = json.loads(original)
            tampered["snapshot"]["captured_at"] = "2026-10-16T07:59:00+09:00"
            validate_stored_slot_evidence(json.dumps(tampered).encode("utf-8"), "2026-10-16", "08:00")

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

    def test_workflow_rejects_wrong_day_delayed_early_and_post_slot_runs(self):
        jst = timezone(timedelta(hours=9))
        with self.assertRaisesRegex(ValueError, "OUTSIDE_PRE_SLOT_WINDOW"):
            require_live_pre_slot_window(
                "2026-11-17", "21:00", now=datetime(2026, 11, 17, 6, 14, tzinfo=jst),
            )
        with self.assertRaisesRegex(ValueError, "OUTSIDE_PRE_SLOT_WINDOW"):
            require_live_pre_slot_window(
                "2026-11-17", "12:00", now=datetime(2026, 11, 17, 11, 44, tzinfo=jst),
            )
        # Exact lower cutoff and the last pre-slot second are permitted.
        require_live_pre_slot_window(
            "2026-11-17", "12:00", now=datetime(2026, 11, 17, 11, 45, tzinfo=jst),
        )
        require_live_pre_slot_window(
            "2026-11-17", "12:00", now=datetime(2026, 11, 17, 11, 59, 59, tzinfo=jst),
        )
        with self.assertRaisesRegex(ValueError, "AFTER_SLOT"):
            require_live_pre_slot_window(
                "2026-11-17", "12:00", now=datetime(2026, 11, 17, 12, 0, tzinfo=jst),
            )

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

    def test_cutoff_cleanup_preserves_a_replacement_written_by_another_actor(self):
        evidence_path = self.output / "2026-10-16_08-00-r1.json"
        calls = 0

        def replace_then_cross_cutoff(report_date, report_time, *, now=None):
            nonlocal calls
            calls += 1
            if calls == 3:
                evidence_path.rename(evidence_path.with_suffix(".owned"))
                evidence_path.write_bytes(b"other actor's evidence")
                raise ValueError("BLOCKED_LIVE_EVIDENCE_AFTER_SLOT")

        with patch(
            "scripts.persist_report_slot_evidence.require_before_slot",
            side_effect=replace_then_cross_cutoff,
        ):
            with self.assertRaisesRegex(ValueError, "BLOCKED_LIVE_EVIDENCE_AFTER_SLOT"):
                persist_slot_evidence(
                    "2026-10-16", "08:00", self.market_path, self.output,
                    require_live_before_slot=True,
                )
        self.assertEqual(evidence_path.read_bytes(), b"other actor's evidence")

    def test_weekend_new_report_is_rejected(self):
        self.payload["generatedAt"] = "2026-10-17T07:50:00+09:00"
        self.payload["reportDate"] = "2026-10-17"
        self.write_payload()
        with self.assertRaisesRegex(ValueError, "weekend"):
            persist_slot_evidence("2026-10-17", "08:00", self.market_path, self.output)


    def test_workflows_isolate_backlogged_slots_without_relaxing_cutoff(self):
        root = Path(__file__).resolve().parents[1]
        freeze = (root / ".github/workflows/freeze-report-slot-evidence.yml").read_text(encoding="utf-8")
        self.assertIn(
            "group: freeze-pre-draft-report-slot-evidence-"
            "${{ github.event.schedule || inputs.report_slot || github.run_id }}",
            freeze,
        )
        self.assertIn("require_live_pre_slot_window(", freeze)
        self.assertIn("--require-live-before-slot", freeze)
        workflows = (
            "market-data-intraday-anchor.yml",
            "market-data-intraday-fallback.yml",
            "market-data-intraday-health.yml",
        )
        for name in workflows:
            with self.subTest(workflow=name):
                content = (root / ".github/workflows" / name).read_text(encoding="utf-8")
                self.assertIn("group: market-data-intraday-window-${{", content)
                self.assertIn("|| inputs.report_slot || github.run_id", content)
                self.assertIn("&& '12'", content)
                self.assertIn("&& '16'", content)
                self.assertIn("&& '21'", content)
                for hour in ("2", "3", "6", "7", "11", "12"):
                    self.assertIn("contains(github.event.schedule, ' " + hour + " * * ')", content)
                self.assertIn("cancel-in-progress: false", content)


    def test_acquisition_completion_backup_is_fail_closed(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/freeze-report-evidence-on-acquisition.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_run:", workflow)
        self.assertIn("head_repository.full_name == github.repository", workflow)
        self.assertIn("head_branch == 'main'", workflow)
        self.assertIn("require_live_pre_slot_window(", workflow)
        self.assertIn("build_slot_evidence(", workflow)
        self.assertIn("validate_stored_slot_evidence(", workflow)
        self.assertIn("--require-live-before-slot", workflow)
        self.assertIn("require_before_slot(", workflow)
        self.assertIn("VERIFIED_PRE_DRAFT_EVIDENCE_ON_MAIN", workflow)
        self.assertIn("No evidence file was created", workflow)
        self.assertNotIn("--force", workflow)



if __name__ == "__main__":
    unittest.main()
