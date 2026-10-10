import datetime as dt
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import fetch_morning_reference as morning
from scripts import fetch_market_data as fetch
from scripts import verify_market_report_readiness as readiness


class RecoveryTests(unittest.TestCase):
    def test_front_contract_follows_quarterly_roll(self):
        self.assertEqual(morning.front_quarter_contract(dt.date(2026, 9, 10), 3), (26, 9))
        self.assertEqual(morning.front_quarter_contract(dt.date(2026, 10, 11), 3), (26, 12))
        cme = "CME￥ 26年09月限 45,000 +100 44,900 45,100 44,800 15:30 CME￥ 26年12月限 46,000 +200 45,800 46,200 45,700 16:00"
        ose = "大証ラージ 26年9月限 45,000 +100 44,900 45,100 44,800 1,000 15:30 大証ラージ 26年12月限 46,000 +200 45,800 46,200 45,700 1,000 16:00"
        self.assertEqual(morning.parse_cme(cme, "yen", dt.date(2026, 10, 11))["contractMonth"], "2026-12")
        self.assertEqual(morning.parse_cme(cme, "yen", dt.date(2026, 9, 10))["contractMonth"], "2026-09")
        self.assertEqual(morning.parse_cme(cme, "yen", dt.date(2026, 10, 11))["contractMonth"], "2026-12")
        self.assertEqual(morning.parse_ose(ose, dt.date(2026, 10, 11))["contractMonth"], "2026-12")

    def test_validated_primary_does_not_wait_for_fallback(self):
        calls = []
        config = {"sources": [{"id": "primary", "kind": "test", "priority": 1},
                              {"id": "fallback", "kind": "test", "priority": 2}]}
        def fetcher(source):
            calls.append(source["id"])
            return {"value": 1.0, "sourceId": source["id"], "marketType": "spot", "session": "global"}
        with patch.dict(fetch.FETCHERS, {"test": fetcher}):
            with patch.object(fetch, "validate_candidate", return_value=(True, "", "")):
                with patch.object(fetch, "format_market", side_effect=lambda _i, _c, _v, item: item):
                    market, _ = fetch.fetch_symbol("x", config, {}, None, 3)
        self.assertEqual(calls, ["primary"])
        self.assertEqual(market["sourceId"], "primary")

    def test_08_readiness_blocks_an_incomplete_28_item_report(self):
        now = dt.datetime(2026, 10, 11, 8, 0, tzinfo=morning.JST)
        ids = ["dow", "nasdaq", "sp500", "russell2000", "nikkei225_cash",
               "nikkei225_futures_cme_yen", "nikkei225_futures_cme_usd", "nikkei225_futures_ose",
               "usdjpy", "eurusd", "gold", "wti", "btcusd", "vix", "nikkei_vi", "fear_greed",
               "us10y", "jp10y", "nikkei225_per", "nikkei225_pbr", "nikkei225_eps",
               "nikkei225_dev25", "nikkei225_dev200", "tse_prime_turnover", "tse_prime_volume",
               "tse_prime_advancers", "tse_prime_decliners", "tse_prime_ad_ratio25"]
        payload = {"reportSlot": "08:00", "expectedCount": 28, "dataComplete": False,
                   "unavailableLabels": ["日本10年国債利回り"], "markets": {key: {"value": i, "verificationStatus": "verified"} for i, key in enumerate(ids)}}
        with patch.object(readiness, "ROOT", Path(".")):
            with patch.object(readiness, "load_json", return_value=payload):
                blocking = []
                readiness.validate_report_input(now, "08:00", blocking, [])
        self.assertTrue(any("日本10年国債利回り" in reason for reason in blocking))


if __name__ == "__main__":
    unittest.main()
