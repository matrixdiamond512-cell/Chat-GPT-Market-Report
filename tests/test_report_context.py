import dataclasses
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from reporting.context import ReportContext, ExecutionContext, aware
from resolve_market_report_slot import resolve_slot
from run_market_data_window import acquisition_day
from datetime import datetime


class ContextTests(unittest.TestCase):
    def context(self, **kw):
        return ReportContext.create('2026-10-02', '21:00', '2026-10-02T20:55:00+09:00', **kw)

    def test_explicit_date_required(self):
        with self.assertRaises((ValueError, TypeError)):
            ReportContext.create('', '21:00', '2026-10-02T20:55:00+09:00')

    def test_yesterday_regeneration_preserves_target(self):
        self.assertEqual(self.context(mode='recovery').report_date, '2026-10-02')
        execution = ExecutionContext('attempt-2', '2026-10-04T22:00:00+09:00')
        self.assertNotEqual(execution.execution_started_at[:10], self.context().report_date)

    def test_identity_readonly(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            self.context().report_id = '2026-10-04_21-00'

    def test_retry_restores_same_context(self):
        context = self.context()
        self.assertEqual(context, ReportContext(**json.loads(json.dumps(context.to_dict()))))

    def test_unknown_cron_fail_closed(self):
        with self.assertRaises(ValueError):
            resolve_slot('schedule', '15 0 * * *', 'auto', Path('missing'))

    def test_boundary_is_timezone_aware(self):
        self.assertEqual(aware('2026-10-02', date_boundary=True).isoformat(), '2026-10-02T00:00:00+09:00')
        with self.assertRaises(ValueError):
            aware('2026-10-02T21:00:00')

    def test_weekend_new_reject(self):
        for day in ('2026-10-03', '2026-10-04'):
            with self.assertRaises(ValueError):
                ReportContext.create(day, '08:00', day+'T07:55:00+09:00')

    def test_explicit_historical_mode(self):
        c = ReportContext.create('2026-10-03', '08:00', '2026-10-03T07:55:00+09:00', mode='historical')
        self.assertEqual(c.report_id, '2026-10-03_08-00')
        with self.assertRaises(ValueError):
            dataclasses.replace(c, report_id='bad')

    def test_acquisition_path_does_not_retag_historical_report(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'context.json'
            path.write_text(json.dumps(self.context(mode='recovery').to_dict()), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'historical'):
                acquisition_day(path, '21:00', datetime.fromisoformat('2026-10-04T12:00:00+09:00'))
            self.assertEqual(acquisition_day(path, '21:00', datetime.fromisoformat('2026-10-02T20:00:00+09:00')).isoformat(), '2026-10-02')
