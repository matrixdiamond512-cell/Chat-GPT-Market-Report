import unittest
from unittest import mock
import json
import urllib.error

import scripts.fetch_market_data as market_data


class FetchMarketDataValidationTests(unittest.TestCase):
    def test_yahoo_session_date_uses_exchange_timezone_not_jst(self):
        source = {"id": "yahoo", "name": "Yahoo", "url": "https://example.test", "sourceUrl": "https://example.test/history", "symbol": "^DJI", "marketType": "index", "session": "daily"}
        payload = {"chart": {"result": [{
            "meta": {"regularMarketPrice": 50000, "previousClose": 49900, "regularMarketTime": 1794603600, "exchangeTimezoneName": "America/New_York"},
            "timestamp": [1794603600], "indicators": {"quote": [{"close": [50000]}]},
        }]}}
        with mock.patch.object(market_data, "http_text", return_value=json.dumps(payload)):
            result = market_data.fetch_yahoo_chart(source)
        self.assertEqual(result["sessionDate"], "2026-11-13")

    def test_http_404_is_reported_without_retrying_as_timeout(self):
        error = urllib.error.HTTPError("https://example.test", 404, "Not Found", {}, None)
        with mock.patch.object(market_data.urllib.request, "urlopen", side_effect=error) as opener:
            with self.assertRaises(market_data.FetchError) as raised:
                market_data.http_get("https://example.test")
        self.assertEqual(raised.exception.code, "HTTP_404")
        self.assertEqual(opener.call_count, 1)

    def test_coinmarketcap_crypto_fear_greed_keeps_previous_daily_value(self):
        source = {
            "id": "cmc",
            "name": "CoinMarketCap Crypto Fear and Greed Index",
            "url": "https://example.test/fear-greed",
            "sourceUrl": "https://coinmarketcap.com/charts/fear-and-greed-index/",
            "marketType": "crypto_sentiment",
            "session": "daily",
        }
        response = """{
          "status": {"error_code": 0},
          "data": [
            {"timestamp": "1785888000", "value": 74, "value_classification": "Greed"},
            {"timestamp": "1785801600", "value": 68, "value_classification": "Greed"}
          ]
        }"""
        with mock.patch.object(market_data, "http_text", return_value=response):
            result = market_data.fetch_coinmarketcap_fear_greed(source)
        self.assertEqual(result["value"], 74)
        self.assertEqual(result["previousClose"], 68)
        self.assertEqual(result["classification"], "Greed")
        self.assertEqual(result["marketType"], "crypto_sentiment")

    def test_implausible_previous_close_is_removed(self):
        candidate = {
            "value": 157.8,
            "previousClose": 100.0,
            "change": 57.8,
            "changePercent": 57.8,
        }
        warning = market_data.sanitize_candidate_change({"maxChangePercent": 8}, candidate)
        self.assertIn("discarded previous close", warning)
        self.assertIsNone(candidate["previousClose"])
        self.assertIsNone(candidate["change"])
        self.assertIsNone(candidate["changePercent"])

    def test_divergent_sources_keep_previous_verified_value(self):
        original = market_data.FETCHERS.get("fake")
        values = {"one": 157.8, "two": 148.1}

        def fake_fetch(source):
            return market_data.candidate(source, values[source["symbol"]])

        market_data.FETCHERS["fake"] = fake_fetch
        try:
            config = {
                "displayName": "USD/JPY",
                "unit": "円",
                "marketType": "spot",
                "session": "continuous",
                "sources": [
                    {"id": "a", "name": "A", "kind": "fake", "symbol": "one", "priority": 1, "marketType": "spot", "session": "continuous"},
                    {"id": "b", "name": "B", "kind": "fake", "symbol": "two", "priority": 2, "marketType": "spot", "session": "continuous"},
                ],
            }
            validation = {
                "min": 80,
                "max": 250,
                "maxChangePercent": 8,
                "maxSourceDivergencePercent": 1.5,
                "decimalPlaces": 2,
            }
            previous = {
                "value": 157.2,
                "displayValue": "157.20",
                "verificationStatus": "verified",
            }
            result, errors = market_data.fetch_symbol("usdjpy", config, validation, previous, 1)
            self.assertEqual(result["value"], 157.2)
            self.assertEqual(result["verificationStatus"], "fallback")
            self.assertTrue(any(item["code"] == "SOURCE_DIVERGENCE" for item in errors))
        finally:
            if original is None:
                market_data.FETCHERS.pop("fake", None)
            else:
                market_data.FETCHERS["fake"] = original


if __name__ == "__main__":
    unittest.main()
