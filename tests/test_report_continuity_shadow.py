from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch
from scripts.resolve_market_report_slot import resolve_report_identity, JST
from scripts.report_continuity_shadow import FakeStorage, EvidenceWriter, JobCoordinator, readiness
from scripts import run_market_data_window as window


def instant(value):
    return datetime.fromisoformat(value).replace(tzinfo=JST)


class ContinuityTests(unittest.TestCase):
    def identity(self, now=None):
        return resolve_report_identity(schedule_time_utc="2026-10-16T11:47:00Z",
                                       attempt_minutes=13,
                                       now=now or instant("2026-10-16T20:50"))

    def test_midnight_delay_preserves_id(self):
        identity = self.identity(instant("2026-10-17T00:33"))
        self.assertEqual(identity.report_id, "2026-10-16_21-00")
        self.assertEqual(identity.status, "EXPIRED")

    def test_seven_hour_delay(self):
        self.assertEqual(self.identity(instant("2026-10-17T04:00")).status, "EXPIRED")

    def test_noon_delay_and_draft_independence(self):
        now = instant("2026-10-16T17:05")
        identity = resolve_report_identity(report_date="2026-10-16", report_slot="12:00", now=now)
        self.assertEqual(identity.status, "EXPIRED")
        state = readiness(identity, now=now, snapshot_at=None, acquisition_valid=False,
                          evidence_valid=False, draft_input_valid=True)
        self.assertTrue(state["draftAllowed"])
        self.assertFalse(state["publicationEligible"])
        self.assertEqual(state["chatStatus"], "UNKNOWN")

    def test_invalid_inputs(self):
        for kwargs in [dict(report_date="2026-10-17", report_slot="08:00"),
                       dict(report_date="2026-10-18", report_slot="08:00"),
                       dict(report_date="2026-10-16", report_slot="07:00"),
                       dict(report_date="2026-10-19", report_slot="08:00"),
                       dict(schedule_time_utc="2026-10-16T11:47:00", attempt_minutes=13),
                       dict(schedule_time_utc="2026-10-16T11:47:00Z", report_date="2026-10-16"),
                       dict(schedule_time_utc="2026-10-16T11:47:00Z", attempt_minutes=12)]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                resolve_report_identity(now=instant("2026-10-16T20:50"), **kwargs)

    def test_all_scheduler_attempts(self):
        for offset in (3, 7, 13):
            scheduled = datetime.fromisoformat("2026-10-16T12:00:00+00:00") - timedelta(minutes=offset)
            self.assertEqual(resolve_report_identity(schedule_time_utc=scheduled.isoformat(),
                attempt_minutes=offset, now=instant("2026-10-16T20:59")).report_id, "2026-10-16_21-00")

    def test_freshness(self):
        now = instant("2026-10-16T21:00")
        for delta, expected in [(16, False), (15, True), (-1, False)]:
            state = readiness(self.identity(), now=now, snapshot_at=now-timedelta(minutes=delta),
                acquisition_valid=True, evidence_valid=True, draft_input_valid=True)
            self.assertEqual(state["acquisitionReady"], expected)
            self.assertFalse(state["publicationEligible"])

    def test_window_rejects_future_and_weekend_before_io(self):
        from datetime import date
        for day in (date(2026, 10, 17), date(2026, 10, 19)):
            with self.assertRaises(ValueError):
                window.resolve_window_day(day, instant("2026-10-16T20:50"))

    def test_corrupt_readback_and_retry_after_transient_failure(self):
        store = FakeStorage(lambda: instant("2026-10-16T20:50"))
        writer = EvidenceWriter(store, store.clock)
        original = store.read
        with patch.object(store, 'read', side_effect=OSError('readback unavailable')):
            with self.assertRaises(OSError):
                writer.write(self.identity(), b'a')
        self.assertEqual(writer.write(self.identity(), b'a')["status"], "NO_OP")
        from scripts.report_continuity_shadow import StoredObject
        with patch.object(store, 'read', return_value=StoredObject(b'corrupt', 1, store.clock())):
            self.assertEqual(writer.write(self.identity(), b'a')["status"], "CONFLICT")

    def test_default_off(self):
        store = FakeStorage(lambda: instant("2026-10-16T20:50"))
        self.assertEqual(JobCoordinator(EvidenceWriter(store, store.clock)).run(self.identity(), b'a')["status"], "DISABLED")
        self.assertEqual(store._objects, {})

    def test_duplicate_conflict_and_restart(self):
        store = FakeStorage(lambda: instant("2026-10-16T20:50"))
        def run(data):
            return JobCoordinator(EvidenceWriter(store, store.clock), enabled=True).run(self.identity(), data)["status"]
        with ThreadPoolExecutor(2) as pool:
            self.assertCountEqual(list(pool.map(run, [b'a', b'a'])), ["CREATED", "NO_OP"])
        self.assertEqual(run(b'b'), "CONFLICT")
        self.assertEqual(run(b'a'), "NO_OP")

    def test_cutoff_before_and_after_storage(self):
        target = self.identity().target
        for server_time, clock in [(target, lambda: target-timedelta(seconds=1)),
                                   (target-timedelta(seconds=1), lambda: target)]:
            store = FakeStorage(lambda: server_time)
            self.assertEqual(EvidenceWriter(store, clock).write(self.identity(), b'a')["status"], "BLOCKED")
        clock_values = iter([target-timedelta(seconds=1), target])
        store = FakeStorage(lambda: target-timedelta(seconds=1))
        self.assertEqual(EvidenceWriter(store, lambda: next(clock_values)).write(self.identity(), b'a')["reason"], "CUTOFF_CROSSED")

    def test_window_explicit_previous_day_and_legacy(self):
        # Stop at audit_path: verify date selection without production I/O.
        for arg, expected in [([], "2026-10-17"), (["--report-date", "2026-10-16"], "2026-10-16")]:
            with patch('sys.argv', ['window', '--slot', '21:00', '--times', '20:47', *arg]), \
                 patch.object(window, 'now_jst', return_value=instant('2026-10-17T00:33')), \
                 patch.object(window, 'run'), \
                 patch.object(window, 'audit_path', side_effect=RuntimeError('stop')) as audit:
                with self.assertRaisesRegex(RuntimeError, 'stop'):
                    window.main()
                self.assertEqual(audit.call_args.args[0].isoformat(), expected)


if __name__ == '__main__':
    unittest.main()
