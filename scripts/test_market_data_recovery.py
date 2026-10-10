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


    def test_cme_lead_month_comes_from_live_vendor_listing(self):
        stamp = int(dt.datetime(2026, 10, 9, 17, tzinfo=dt.timezone.utc).timestamp())
        payload = {
            "chart": {"result": [{
                "meta": {"longName": "Nikkei/Yen Futures, Dec-2026"},
                "timestamp": [stamp - 86400, stamp],
                "indicators": {"quote": [{"close": [69000, 69085]}]},
            }]}
        }
        yen = morning.parse_cme(payload, "yen", dt.date(2026, 10, 11))
        self.assertEqual(yen["contractMonth"], "2026-12")
        self.assertEqual(yen["vendorSymbol"], "NIY=F")
        self.assertEqual(yen["value"], "69,085")
        dollar_payload = {
            "chart": {"result": [{
                "meta": {"shortName": "Nikkei/USD Futures, Dec-2026"},
                "timestamp": [stamp - 86400, stamp],
                "indicators": {"quote": [{"close": [68900, 69120]}]},
            }]}
        }
        dollar = morning.parse_cme(dollar_payload, "dollar", dt.date(2026, 10, 11))
        self.assertEqual(dollar["contractMonth"], "2026-12")
        self.assertEqual(dollar["vendorSymbol"], "NKD=F")

    def test_cme_does_not_infer_expiry_or_accept_future_dated_bar(self):
        stamp = int(dt.datetime(2026, 10, 12, 17, tzinfo=dt.timezone.utc).timestamp())
        payload = {"chart": {"result": [{
            "meta": {"longName": "Nikkei/Yen Futures"},
            "timestamp": [stamp],
            "indicators": {"quote": [{"close": [69085]}]},
        }]}}
        self.assertIsNone(morning.parse_cme(payload, "yen", dt.date(2026, 10, 11)))
        payload["chart"]["result"][0]["meta"]["longName"] = "Nikkei/Yen Futures, Dec-2026"
        self.assertIsNone(morning.parse_cme(payload, "yen", dt.date(2026, 10, 11)))

    def test_ose_quarter_selection_keeps_second_friday_rule(self):
        self.assertEqual(morning.front_quarter_contract(dt.date(2026, 10, 11), 2), (26, 12))
        ose = "大証ラージ 26年9月限 45,000 +100 44,900 45,100 44,800 1,000 15:30 大証ラージ 26年12月限 46,000 +200 45,800 46,200 45,700 1,000 16:00"
        self.assertEqual(morning.parse_ose(ose, dt.date(2026, 10, 11))["contractMonth"], "2026-12")

    def test_yahoo_sma_deviation_requires_window_and_normalizes_percent_points(self):
        import json
        stamps = [int(dt.datetime(2026, 10, 7, tzinfo=dt.timezone.utc).timestamp()) + i * 86400 for i in range(3)]
        payload = {"chart": {"result": [{
            "timestamp": stamps,
            "indicators": {"quote": [{"close": [100, 110, 120]}]},
        }]}}
        with patch.object(fetch, "http_text", return_value=json.dumps(payload)):
            result = fetch.fetch_yahoo_sma_deviation({
                "id": "test-sma", "name": "test", "symbol": "^N225", "window": 2,
                "marketType": "technical", "session": "daily",
            })
        self.assertAlmostEqual(result["value"], (120 / 115 - 1) * 100)
        self.assertEqual(result["window"], 2)
        self.assertAlmostEqual(result["movingAverage"], 115)

    def test_deviation_sheet_routes_use_existing_columns(self):
        from scripts import sync_market_close_sheet as close_sync
        self.assertEqual(close_sync.TECHNICAL_FIELDS["nikkei225_dev25"], "日経225_25日乖離率")
        self.assertEqual(close_sync.TECHNICAL_FIELDS["nikkei225_dev200"], "日経225_200日乖離率")
        self.assertIn("日経225_25日乖離率", close_sync.REQUIRED_CLOSE_HEADERS)

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


    def test_fred_csv_parses_latest_daily_yield_and_previous_close(self):
        csv_text = "observation_date,DGS10\n2026-10-08,5.27\n2026-10-09,5.26\n"
        source = {
            "id": "fred_dgs10", "name": "FRED DGS10",
            "url": "https://example.test/DGS10.csv", "sourceUrl": "https://fred.stlouisfed.org/series/DGS10",
            "seriesId": "DGS10", "dateField": "observation_date", "valueField": "DGS10",
            "marketType": "yield", "session": "daily",
        }
        with patch.object(fetch, "http_text", return_value=csv_text):
            result = fetch.fetch_fred_csv(source)
        self.assertEqual(result["value"], 5.26)
        self.assertEqual(result["previousClose"], 5.27)
        self.assertEqual(result["asOf"], "2026-10-09")

    def test_fred_csv_ignores_missing_observations_and_rejects_empty_series(self):
        source = {
            "id": "fred_dgs10", "name": "FRED DGS10",
            "url": "https://example.test/DGS10.csv", "seriesId": "DGS10",
            "marketType": "yield", "session": "daily",
        }
        with patch.object(fetch, "http_text", return_value="observation_date,DGS10\n2026-10-09,.\n"):
            with self.assertRaises(fetch.FetchError):
                fetch.fetch_fred_csv(source)

    def test_us10y_maps_to_existing_close_header(self):
        import json
        from scripts import sync_market_close_sheet as close_sync
        config = json.loads((fetch.ROOT / "config" / "market_data_sources.json").read_text(encoding="utf-8"))
        self.assertEqual(config["symbols"]["us10y"]["sources"][0]["seriesId"], "DGS10")
        self.assertEqual(close_sync.PRICE_FIELDS["us10y"], ("米10年債利回り", "", ""))
        self.assertIn("us10y", sheet_contract.MARKET_ORDER)


if __name__ == "__main__":
    unittest.main()
