"""Market acquisition must preserve saved report projections byte for byte."""
from copy import deepcopy
import unittest
from scripts.build_market_json import attach_market_data


class MarketProjectionTests(unittest.TestCase):
    def test_new_live_prices_cannot_change_either_saved_projection(self):
        canonical={'date':'2026-11-12','time':'12:00','revision':1,'bodyHash':'original',
            'fullText':'saved source','marketData':{'snapshot':'frozen','value':100}}
        dashboard={'latestReport':deepcopy(canonical),'reports':[deepcopy(canonical)],
            'currentReportKey':'2026-11-12 12:00'}
        before=deepcopy(dashboard)
        live={'generatedAt':'2026-11-13T03:30:00+09:00','overallStatus':'verified','value':200}
        output=attach_market_data(dashboard,live)
        self.assertEqual(output['latestReport'],canonical)
        self.assertEqual(output['reports'],[canonical])
        self.assertEqual(output['marketData'],live)
        self.assertEqual(dashboard,before)

    def test_absent_frozen_market_data_is_not_backfilled_from_live(self):
        report={'date':'2026-11-12','time':'21:00','fullText':'saved'}
        output=attach_market_data({'latestReport':report,'reports':[report]}, {'overallStatus':'blocked','missingRequired':['USDJPY']})
        self.assertNotIn('marketData',output['latestReport'])
        self.assertNotIn('marketData',output['reports'][0])
        self.assertTrue(any('USDJPY' in x for x in output['errors']))


if __name__ == '__main__':unittest.main()
