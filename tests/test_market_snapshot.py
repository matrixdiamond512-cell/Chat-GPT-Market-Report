import dataclasses
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from reporting.context import ReportContext
from reporting.snapshot import Market, MarketDataSnapshot
from build_market_json import attach_market_data


def context():
    return ReportContext.create('2026-10-02', '21:00', '2026-10-02T20:55:00+09:00')


def market(**updates):
    data = dict(instrument='WTI', marketType='FUTURES', venue='NYMEX', contractMonth='2026-11', priceValue=89.47,
                priceUnit='USD/bbl', changeValue=-1.0, changePct=-1.1, direction='DOWN', comparisonBasis='previous_close',
                asOf='2026-10-02T20:50:00+09:00', source=[{'id': 'fixture', 'url': 'https://example.test/quote'}],
                status='VALID', unavailableReason=None, displayText='89.47ドル')
    data.update(updates)
    return Market(**data)


class SnapshotTests(unittest.TestCase):
    def snapshot(self, m=None):
        return MarketDataSnapshot.capture(context(), [m or market()], '2026-10-02T20:54:00+09:00')

    def test_same_report_id_and_retry(self):
        s = self.snapshot()
        s.validate_context(context())
        self.assertEqual(s, MarketDataSnapshot.restore(s.to_dict()))

    def test_deep_immutable(self):
        s = self.snapshot()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            s.report_id = 'bad'
        with self.assertRaises(TypeError):
            s.markets[0].source[0]['id'] = 'changed'

    def test_cross_day_reject(self):
        with self.assertRaises(ValueError):
            self.snapshot().validate_context(ReportContext.create('2026-10-01', '21:00', '2026-10-01T20:55:00+09:00'))
        with self.assertRaises(ValueError):
            MarketDataSnapshot.from_acquisition(context(), {'generatedAt': '2026-10-01T20:54:00+09:00', 'reportSlot': '21:00'})

    def test_unavailable_preserved(self):
        m = market(priceValue=None, changeValue=None, changePct=None, direction='UNKNOWN', status='UNAVAILABLE', unavailableReason='取得不能: source offline', displayText='取得不能')
        self.assertEqual(self.snapshot(m).markets[0].unavailableReason, '取得不能: source offline')
        self.assertIsNone(m.priceValue)

    def test_stale_preserved(self):
        self.assertEqual(self.snapshot(market(status='STALE')).markets[0].status, 'STALE')

    def test_source_asof_unit_propagate(self):
        m = self.snapshot().to_dict()['markets'][0]
        self.assertEqual((m['source'][0]['id'], m['asOf'], m['priceUnit']), ('fixture', '2026-10-02T20:50:00+09:00', 'USD/bbl'))

    def test_latest_never_reattaches_to_body(self):
        original = {'latestReport': {'marketData': {'old': True}}, 'reports': [{'marketData': {'old': True}}]}
        result = attach_market_data(original, {'generatedAt': '2026-10-04T12:00:00+09:00'})
        self.assertEqual(result['latestReport'], original['latestReport'])
        self.assertEqual(result['reports'], original['reports'])
        self.assertIn('marketDataUpdatedAt', result)
