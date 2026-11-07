from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import fetch_market_data as market_data
from scripts import validate_market_data_source as source_validation


TREASURY_XML = b'''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
  <entry><content><m:properties xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
    <d:NEW_DATE>2026-10-08T00:00:00</d:NEW_DATE><d:BC_10YEAR>4.12</d:BC_10YEAR>
  </m:properties></content></entry>
  <entry><content><m:properties xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
    <d:NEW_DATE>2026-10-09T00:00:00</d:NEW_DATE><d:BC_10YEAR>4.15</d:BC_10YEAR>
  </m:properties></content></entry>
</feed>'''


class TreasurySourceTests(unittest.TestCase):
    def test_fetches_keyless_coinmarketcap_fear_and_greed_history(self):
        source = {
            "id": "coinmarketcap_crypto_fear_greed",
            "name": "CoinMarketCap Crypto Fear and Greed Index",
            "kind": "coinmarketcap_fear_greed",
            "url": "https://pro-api.coinmarketcap.com/public-api/v3/fear-and-greed/historical?start=1&limit=2",
        }
        payload = (
            '{"status":{"error_code":0},"data":['
            '{"timestamp":"1791676800","value":47,"value_classification":"Neutral"},'
            '{"timestamp":"1791590400","value":45,"value_classification":"Neutral"}]}'
        )
        with patch.object(market_data, "http_text", return_value=payload):
            result = market_data.fetch_coinmarketcap_fear_greed(source)

        self.assertEqual(result["value"], 47)
        self.assertEqual(result["previousClose"], 45)
        self.assertEqual(result["change"], 2)
        self.assertEqual(result["sourceId"], "coinmarketcap_crypto_fear_greed")
        self.assertEqual(market_data.parse_iso(result["asOf"]).date().isoformat(), "2026-10-11")

    def test_fetches_latest_dated_value_from_documented_month_feed(self):
        source = {
            "id": "us_treasury_yield_curve",
            "name": "U.S. Treasury Daily Par Yield Curve Rates",
            "kind": "treasury_yield_xml",
            "url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml",
            "data": "daily_treasury_yield_curve",
            "dateField": "NEW_DATE",
            "valueField": "BC_10YEAR",
            "sourceSeriesId": "daily_treasury_yield_curve:BC_10YEAR",
            "unit": "%",
            "publishedDecimalPlaces": 2,
            "marketType": "yield",
            "session": "daily",
            "timeoutSeconds": 45,
        }
        seen = {}

        def fake_http_get(url, timeout=8, headers=None):
            seen.update(url=url, timeout=timeout, headers=headers)
            return TREASURY_XML, "utf-8"

        with patch.object(market_data, "http_get", side_effect=fake_http_get):
            result = market_data.fetch_treasury_yield_xml(source)

        self.assertEqual(result["value"], 4.15)
        self.assertEqual(result["asOf"], "2026-10-09")
        self.assertEqual(result["sourceSeriesId"], "daily_treasury_yield_curve:BC_10YEAR")
        self.assertEqual(result["unit"], "%")
        self.assertEqual(result["reportedDecimalPlaces"], 2)
        self.assertEqual(result["sourceSeriesId"], "daily_treasury_yield_curve:BC_10YEAR")
        self.assertEqual(result["previousClose"], 4.12)
        self.assertIn("field_tdr_date_value_month=202610", seen["url"])
        self.assertEqual(seen["timeout"], 45)

    def test_collect_only_validation_reports_metadata_without_quote_value(self):
        with patch.object(market_data, "http_get", return_value=(TREASURY_XML, "utf-8")):
            result = source_validation.validate("us10y", "us_treasury_yield_curve")

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["marketDate"], "2026-10-09")
        self.assertTrue(result["valuePresent"])
        self.assertTrue(result["sourceMatches"])
        self.assertTrue(result["notFutureDated"])
        self.assertEqual(result["direction"], "UP")
        self.assertEqual(result["directionCheck"], "CONSISTENT")
        self.assertNotIn("value", result)
        self.assertNotIn("reason", result)

    def test_rejected_validation_does_not_expose_quote_in_diagnostic_metadata(self):
        raw = {"value": 9876.54, "asOf": "2026-10-09", "sourceId": "us_treasury_yield_curve"}
        with patch.object(market_data, "FETCHERS", {"treasury_yield_xml": lambda _source: raw}), patch.object(
            market_data,
            "validate_candidate",
            return_value=(False, "OUT_OF_RANGE", "9876.54 is outside the configured range"),
        ):
            result = source_validation.validate("us10y", "us_treasury_yield_curve")

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["validationCode"], "OUT_OF_RANGE")
        self.assertNotIn("value", result)
        self.assertNotIn("reason", result)
        self.assertNotIn("9876.54", str(result))

    def test_empty_or_malformed_feed_fails_closed(self):
        source = {
            "id": "us_treasury_yield_curve",
            "name": "Treasury",
            "url": "https://home.treasury.gov/feed",
            "marketType": "yield",
            "session": "daily",
        }
        with patch.object(market_data, "http_get", return_value=(b"<feed>", "utf-8")):
            with self.assertRaises(market_data.FetchError) as raised:
                market_data.fetch_treasury_yield_xml(source)
        self.assertEqual(raised.exception.code, "PARSE_ERROR")


if __name__ == "__main__":
    unittest.main()

