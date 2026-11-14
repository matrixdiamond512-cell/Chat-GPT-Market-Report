"""Offline boundaries for the independent 08:00 close-sync trigger."""
import unittest
from datetime import datetime, timedelta, timezone

from scripts.reporting.close_sync_trigger_contract import (
    JST, TriggerContractError, claim_body, claim_digest,
    resolve_trigger_intent,
)

JOB = "projects/market-report-test-only/locations/asia-northeast1/jobs/close-sync-0748-test"
CALLER_JOB = "close-sync-0748-test"


def intent(schedule="2026-11-15T22:48:00.270000Z",
           started="2026-11-16T07:48:04+09:00",
           job=CALLER_JOB, resource=JOB):
    return resolve_trigger_intent(
        job_header=job, expected_job_resource=resource,
        schedule_time_header=schedule,
        started_at=datetime.fromisoformat(started.replace("Z", "+00:00")),
    )


class CloseSyncTriggerContractTests(unittest.TestCase):
    def test_allowed_weekday_fractional_rfc3339_and_fixed_inputs(self):
        result = intent()
        self.assertEqual(result.report_id, "2026-11-16_08-00")
        self.assertEqual(result.service_date, "2026-11-16")
        self.assertEqual(result.inputs, {"permission_probe": "false", "scheduled_time": "07:50"})
        self.assertEqual(result.ref, "main")
        self.assertEqual(result.workflow, "market-data-08-anchor.yml")
        self.assertIn("CONTRACT_ONLY_NOT_DISPATCHED", result.public_diagnostic()["state"])
        self.assertEqual(claim_body(result), claim_body(intent(started="2026-11-16T07:49:59+09:00")))
        self.assertEqual(claim_digest(result), claim_digest(intent(started="2026-11-16T07:49:59+09:00")))

    def test_rejects_cross_job_and_unpinned_resource(self):
        with self.assertRaisesRegex(TriggerContractError, "SCHEDULER_JOB_MISMATCH"):
            intent(job="other-job")
        with self.assertRaisesRegex(TriggerContractError, "EXPECTED_JOB_RESOURCE_INVALID"):
            intent(resource="close-sync-0748-test")

    def test_weekend_is_rejected(self):
        with self.assertRaisesRegex(TriggerContractError, "NON_BUSINESS_WEEKDAY"):
            intent(schedule="2026-11-14T07:48:00+09:00",
                   started="2026-11-14T07:48:04+09:00")

    def test_wrong_minute_and_nonzero_seconds_rejected(self):
        for schedule in ("2026-11-16T07:47:00+09:00",
                         "2026-11-16T07:48:01+09:00",
                         "2026-11-16T07:53:00+09:00"):
            with self.subTest(schedule=schedule):
                with self.assertRaisesRegex(TriggerContractError, "SCHEDULE_TIME_MISMATCH"):
                    intent(schedule=schedule)

    def test_early_or_cutoff_started_rejected(self):
        with self.assertRaisesRegex(TriggerContractError, "START_BEFORE_SCHEDULE"):
            intent(started="2026-11-16T07:47:59+09:00")
        with self.assertRaisesRegex(TriggerContractError, "CLOSE_TRIGGER_AFTER_CUTOFF"):
            intent(started="2026-11-16T07:50:00+09:00")

    def test_ambiguous_dates_and_timezone_rejected(self):
        with self.assertRaisesRegex(TriggerContractError, "SCHEDULE_TIME_TZ_REQUIRED"):
            intent(schedule="2026-11-16T07:48:00")
        with self.assertRaisesRegex(TriggerContractError, "START_TIME_TZ_REQUIRED"):
            intent(started="2026-11-16T07:48:10")

    def test_same_business_day_different_offset_is_same_claim(self):
        first = intent()
        second = intent(started="2026-11-16T07:49:30+09:00")
        self.assertEqual(first.claim_key, second.claim_key)
        self.assertTrue(first.claim_key.startswith("test-only/close-dispatch/"))
        self.assertTrue(first.claim_key.endswith("/claim.json"))

    def test_no_network_or_secret_material_in_diagnostics(self):
        result = intent()
        self.assertNotIn("token", result.public_diagnostic())
        self.assertNotIn("authorization", str(result.public_diagnostic()).lower())
        self.assertNotIn("github_pat", str(claim_body(result)).lower())


if __name__ == "__main__":
    unittest.main()
