import datetime as dt
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import fetch_morning_reference as morning
from scripts import fetch_market_data as fetch
from scripts import verify_market_report_readiness as readiness
from scripts import write_market_data_to_sheets as sheet_contract
from scripts import fetch_market_data


class RecoveryTests(unittest.TestCase):
    def test_major_report_indices_are_required_and_exported(self):
        import json
        config = json.loads((fetch_market_data.ROOT / "config" / "market_data_sources.json").read_text(encoding="utf-8"))
        expected = {"dow", "nasdaq", "sp500", "russell2000", "nikkei225_cash"}
        symbols = config["symbols"]
        self.assertTrue(expected.issubset(symbols))
        self.assertTrue(all(symbols[key]["required"] for key in expected))
        self.assertTrue(expected.issubset(set(sheet_contract.MARKET_ORDER)))


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
        self.assertEqual(readiness.report_input_status(payload), "PARTIAL")
        self.assertEqual(readiness.report_input_status({}), "NOT_YET_GENERATED")


    def test_confirmed_same_date_jp10y_rate_can_be_reused(self):
        import json
        import tempfile
        from pathlib import Path

        fixture = {
            "meta": {"status": "confirmed", "isStale": False, "asOfDate": "2026-10-09"},
            "rates": [{
                "name": "日本10年国債利回り", "value": 3.001, "changeBp": -8.8,
                "asOf": "2026-10-09", "status": "confirmed",
            }],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "data").mkdir()
            (root / "data" / "rates-bonds.json").write_text(json.dumps(fixture), encoding="utf-8")
            source = {
                "id": "rates_bonds_jp10y", "name": "confirmed local rates",
                "path": "data/rates-bonds.json", "recordName": "日本10年国債利回り",
                "marketType": "yield", "session": "daily",
            }
            with patch.object(fetch, "ROOT", root):
                result = fetch.fetch_local_rates_json(source)
        self.assertEqual(result["value"], 3.001)
        self.assertEqual(result["asOf"], "2026-10-09")
        self.assertAlmostEqual(result["change"], -0.088)

    def test_jp10y_reuse_rejects_unconfirmed_or_mismatched_date(self):
        import json
        import tempfile
        from pathlib import Path

        for meta_status, record_date in (("unavailable", "2026-10-09"), ("confirmed", "2026-10-08")):
            fixture = {
                "meta": {"status": meta_status, "isStale": False, "asOfDate": "2026-10-09"},
                "rates": [{
                    "name": "日本10年国債利回り", "value": 3.001, "changeBp": -8.8,
                    "asOf": record_date, "status": "confirmed",
                }],
            }
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                (root / "data").mkdir()
                (root / "data" / "rates-bonds.json").write_text(json.dumps(fixture), encoding="utf-8")
                with patch.object(fetch, "ROOT", root):
                    with self.assertRaises(fetch.FetchError):
                        fetch.fetch_local_rates_json({
                            "id": "rates_bonds_jp10y", "name": "confirmed local rates",
                            "path": "data/rates-bonds.json", "recordName": "日本10年国債利回り",
                            "marketType": "yield", "session": "daily",
                        })

    def test_jp10y_uses_existing_close_header_without_changing_sheet_shape(self):
        from scripts import sync_market_close_sheet

        config = __import__("json").loads(
            (fetch.ROOT / "config" / "market_data_sources.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["symbols"]["jp10y"]["marketType"], "yield")
        self.assertEqual(sync_market_close_sheet.PRICE_FIELDS["jp10y"], ("日本10年債利回り", "", ""))
        self.assertIn("jp10y", sheet_contract.MARKET_ORDER)

    def test_historical_close_repair_attaches_same_date_confirmed_jp10y_only(self):
        import json
        import tempfile
        from pathlib import Path
        from scripts import sync_market_close_sheet as close_sync

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "data").mkdir()
            rate_data = {
                "generatedAt": "2026-10-10T02:34:06+09:00",
                "meta": {"status": "confirmed", "isStale": False, "asOfDate": "2026-10-09",
                         "updatedAt": "2026-10-10T02:34:06+09:00"},
                "rates": [{"name": "日本10年国債利回り", "value": 3.001, "changeBp": -8.8,
                           "asOf": "2026-10-09", "status": "confirmed", "source": "LSEG"}],
            }
            (root / "data" / "rates-bonds.json").write_text(json.dumps(rate_data), encoding="utf-8")
            payload = {"markets": {}}
            with patch.object(close_sync, "ROOT", root):
                self.assertTrue(close_sync.attach_local_confirmed_jp10y(payload, dt.date(2026, 10, 9)))
                self.assertFalse(close_sync.attach_local_confirmed_jp10y(payload, dt.date(2026, 10, 8)))
        self.assertEqual(payload["markets"]["jp10y"]["value"], 3.001)
        self.assertEqual(payload["markets"]["jp10y"]["asOf"], "2026-10-09")


if __name__ == "__main__":
    unittest.main()
