import unittest
from datetime import datetime, timedelta, timezone

from scripts.reporting.scheduler_reliability import (
    JST,
    ScheduleRequestError,
    assess_evidence_watchdog,
    validate_scheduled_invocation,
)

PRINCIPAL = "report-evidence-scheduler@example.iam.gserviceaccount.com"
JOB = "projects/test-project/locations/asia-northeast1/jobs/market-report-1600-evidence"


def invoke(*, schedule_time="2026-11-11T15:47:00+09:00", started=None,
           principal=PRINCIPAL, job_name=JOB, slot="16:00"):
    return validate_scheduled_invocation(
        verified_principal=principal,
        expected_principal=PRINCIPAL,
        job_name=job_name,
        expected_job_name=JOB,
        report_slot=slot,
        schedule_time=schedule_time,
        started_at=started or datetime(2026, 11, 11, 15, 47, tzinfo=JST),
    )


class ScheduleReliabilityTests(unittest.TestCase):
    def test_on_time_and_five_minute_delay_keep_date_and_slot(self):
        for started in (datetime(2026, 11, 11, 15, 47, tzinfo=JST),
                        datetime(2026, 11, 11, 15, 52, tzinfo=JST)):
            with self.subTest(started=started):
                result = invoke(started=started)
                self.assertEqual((result.report_date, result.report_slot, result.report_id),
                                 ("2026-11-11", "16:00", "2026-11-11_16-00"))

    def test_scheduler_retry_has_same_idempotency_key(self):
        first = invoke(started=datetime(2026, 11, 11, 15, 47, tzinfo=JST))
        retry = invoke(started=datetime(2026, 11, 11, 15, 52, tzinfo=JST))
        self.assertEqual(first.idempotency_key, retry.idempotency_key)

    def test_wrong_identity_job_and_slot_are_rejected(self):
        with self.assertRaisesRegex(ScheduleRequestError, "principal_mismatch"):
            invoke(principal="attacker@example.com")
        with self.assertRaisesRegex(ScheduleRequestError, "job_name_mismatch"):
            invoke(job_name="projects/test/jobs/other")
        with self.assertRaisesRegex(ScheduleRequestError, "unsupported_slot"):
            invoke(slot="15:00")

    def test_schedule_time_is_required_timezone_aware_and_exact(self):
        for value, reason in ((None, "schedule_time_MISSING"),
                              ("2026-11-11T15:47:00", "TIMEZONE_REQUIRED"),
                              ("2026-11-11T15:30:00+09:00", "scheduled_at_not_allowed")):
            with self.subTest(value=value), self.assertRaisesRegex(ScheduleRequestError, reason):
                invoke(schedule_time=value)

    def test_delayed_30_minutes_hours_or_next_day_fails_closed(self):
        for started in (datetime(2026, 11, 11, 16, 17, tzinfo=JST),
                        datetime(2026, 11, 11, 19, 0, tzinfo=JST),
                        datetime(2026, 11, 12, 15, 50, tzinfo=JST)):
            with self.subTest(started=started), self.assertRaisesRegex(ScheduleRequestError, "SCHEDULE_LATE"):
                invoke(started=started)

    def test_jst_report_date_survives_utc_day_rollover(self):
        result = validate_scheduled_invocation(
            verified_principal=PRINCIPAL, expected_principal=PRINCIPAL,
            job_name="projects/test/locations/asia-northeast1/jobs/market-report-0800-evidence",
            expected_job_name="projects/test/locations/asia-northeast1/jobs/market-report-0800-evidence",
            report_slot="08:00", schedule_time="2026-11-11T22:47:00Z",
            started_at=datetime(2026, 11, 11, 22, 52, tzinfo=timezone.utc),
        )
        self.assertEqual(result.report_id, "2026-11-12_08-00")

    def test_weekend_occurrence_is_rejected(self):
        with self.assertRaisesRegex(ScheduleRequestError, "report_date_not_weekday"):
            validate_scheduled_invocation(
                verified_principal=PRINCIPAL, expected_principal=PRINCIPAL,
                job_name=JOB, expected_job_name=JOB, report_slot="16:00",
                schedule_time="2026-11-14T15:47:00+09:00",
                started_at=datetime(2026, 11, 14, 15, 47, tzinfo=JST),
            )

    def test_watchdog_is_independent_and_only_generates_warning_state(self):
        result = assess_evidence_watchdog("2026-11-11", "16:00",
            now=datetime(2026, 11, 11, 15, 58, tzinfo=JST), evidence_state="ABSENT")
        self.assertEqual(result["state"], "WARNING_EVIDENCE_MISSING")
        self.assertEqual(result["latestAttemptAt"], "none")
        self.assertEqual(result["notification"], "NOT_SENT")

    def test_watchdog_deadline_invalid_unknown_and_valid_states(self):
        cutoff = datetime(2026, 11, 11, 16, 0, tzinfo=JST)
        cases = (("ABSENT", cutoff, "BLOCKED_EVIDENCE_MISSING"),
                 ("INVALID", cutoff, "BLOCKED_EVIDENCE_INVALID"),
                 ("UNKNOWN", cutoff, "EVIDENCE_STATE_UNKNOWN"),
                 ("VALID", cutoff, "EVIDENCE_READY"),
                 ("ABSENT", cutoff - timedelta(minutes=4), "WAITING_FOR_EVIDENCE"))
        for evidence, now, expected in cases:
            with self.subTest(evidence=evidence, expected=expected):
                self.assertEqual(assess_evidence_watchdog("2026-11-11", "16:00",
                    now=now, evidence_state=evidence)["state"], expected)

    def test_watchdog_rejects_weekend_naive_clock_and_invalid_attempt_time(self):
        with self.assertRaisesRegex(ValueError, "report_date_not_weekday"):
            assess_evidence_watchdog("2026-11-14", "08:00",
                now=datetime(2026, 11, 14, 7, 58, tzinfo=JST), evidence_state="ABSENT")
        with self.assertRaisesRegex(ValueError, "naive_clock"):
            assess_evidence_watchdog("2026-11-11", "16:00",
                now=datetime(2026, 11, 11, 15, 58), evidence_state="ABSENT")
        with self.assertRaisesRegex(ValueError, "naive_attempt_clock"):
            assess_evidence_watchdog("2026-11-11", "16:00",
                now=datetime(2026, 11, 11, 15, 58, tzinfo=JST),
                evidence_state="ABSENT", latest_attempt_at=datetime(2026, 11, 11, 15, 52))


if __name__ == "__main__":
    unittest.main()

