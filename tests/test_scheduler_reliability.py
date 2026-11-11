import unittest
from datetime import datetime, timedelta, timezone

from scripts.reporting.scheduler_reliability import (
    JST,
    ScheduleRequestError,
    assess_evidence_watchdog,
    validate_scheduled_invocation,
)

EXPECTED = "report-evidence-scheduler@example.iam.gserviceaccount.com"


def request(date="2026-11-11", slot="16:00", offset=13, attempt="attempt-1"):
    hour, minute = (int(part) for part in slot.split(":"))
    target = datetime.fromisoformat(date).replace(hour=hour, minute=minute, tzinfo=JST)
    scheduled = target - timedelta(minutes=offset)
    return {
        "reportDate": date,
        "reportSlot": slot,
        "reportId": f"{date}_{slot.replace(':', '-')}",
        "scheduledAt": scheduled.isoformat(),
        "attemptId": attempt,
    }


class ScheduleReliabilityTests(unittest.TestCase):
    def test_on_time_and_five_minute_delay_keep_explicit_identity(self):
        payload = request()
        for started in (datetime(2026, 11, 11, 15, 47, tzinfo=JST),
                        datetime(2026, 11, 11, 15, 52, tzinfo=JST)):
            with self.subTest(started=started):
                result = validate_scheduled_invocation(payload, verified_principal=EXPECTED,
                    expected_principal=EXPECTED, started_at=started)
                self.assertEqual(result.report_id, "2026-11-11_16-00")
                self.assertEqual(result.idempotency_key, "2026-11-11_16-00")

    def test_all_configured_attempt_offsets_and_retry_claim_are_stable(self):
        keys = []
        for offset in (13, 7, 3):
            with self.subTest(offset=offset):
                payload = request(offset=offset)
                started = datetime.fromisoformat(payload["scheduledAt"])
                result = validate_scheduled_invocation(payload, verified_principal=EXPECTED,
                    expected_principal=EXPECTED, started_at=started)
                keys.append(result.idempotency_key)
        self.assertEqual(keys, ["2026-11-11_16-00"] * 3)

    def test_wrong_identity_slot_and_self_asserted_report_id_are_rejected(self):
        with self.assertRaisesRegex(ScheduleRequestError, "AUTH"):
            validate_scheduled_invocation(request(), verified_principal="attacker",
                expected_principal=EXPECTED, started_at=datetime(2026, 11, 11, 15, 47, tzinfo=JST))
        for mutate, reason in (
            (lambda p: p.update(reportSlot="15:00"), "unsupported_slot"),
            (lambda p: p.update(reportId="2026-11-12_16-00"), "report_id_mismatch"),
            (lambda p: p.update(scheduledAt="2026-11-11T15:30:00+09:00"), "scheduled_at_not_allowed"),
            (lambda p: p.update(reportDate="2026-11-14", reportId="2026-11-14_16-00"), "report_date_not_weekday"),
        ):
            payload = request(); mutate(payload)
            with self.subTest(reason=reason), self.assertRaisesRegex(ScheduleRequestError, reason):
                validate_scheduled_invocation(payload, verified_principal=EXPECTED,
                    expected_principal=EXPECTED, started_at=datetime(2026, 11, 11, 15, 47, tzinfo=JST))

    def test_naive_timestamp_and_start_before_schedule_are_rejected(self):
        payload = request(); payload["scheduledAt"] = "2026-11-11T15:47:00"
        with self.assertRaisesRegex(ScheduleRequestError, "TIMEZONE_REQUIRED"):
            validate_scheduled_invocation(payload, verified_principal=EXPECTED,
                expected_principal=EXPECTED, started_at=datetime(2026, 11, 11, 15, 47, tzinfo=JST))
        with self.assertRaisesRegex(ScheduleRequestError, "started_before_schedule"):
            validate_scheduled_invocation(request(), verified_principal=EXPECTED,
                expected_principal=EXPECTED, started_at=datetime(2026, 11, 11, 15, 46, tzinfo=JST))

    def test_thirty_minute_hours_and_next_day_delay_are_fail_closed(self):
        for started in (datetime(2026, 11, 11, 16, 17, tzinfo=JST),
                        datetime(2026, 11, 11, 19, 0, tzinfo=JST),
                        datetime(2026, 11, 12, 15, 50, tzinfo=JST)):
            with self.subTest(started=started), self.assertRaisesRegex(ScheduleRequestError, "SCHEDULE_LATE"):
                validate_scheduled_invocation(request(), verified_principal=EXPECTED,
                    expected_principal=EXPECTED, started_at=started)

    def test_utc_timestamp_rollover_preserves_jst_report_date(self):
        payload = request(date="2026-11-12", slot="08:00", offset=13)
        payload["scheduledAt"] = "2026-11-11T22:47:00Z"
        result = validate_scheduled_invocation(payload, verified_principal=EXPECTED,
            expected_principal=EXPECTED, started_at=datetime(2026, 11, 11, 22, 52, tzinfo=timezone.utc))
        self.assertEqual(result.report_id, "2026-11-12_08-00")

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

    def test_watchdog_rejects_weekend_and_naive_clock(self):
        with self.assertRaisesRegex(ValueError, "report_date_not_weekday"):
            assess_evidence_watchdog("2026-11-14", "08:00",
                now=datetime(2026, 11, 14, 7, 58, tzinfo=JST), evidence_state="ABSENT")
        with self.assertRaisesRegex(ValueError, "naive_clock"):
            assess_evidence_watchdog("2026-11-11", "16:00",
                now=datetime(2026, 11, 11, 15, 58), evidence_state="ABSENT")


if __name__ == "__main__":
    unittest.main()

