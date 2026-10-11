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
    def test_fetches_latest_dated_value_from_documented_month_feed(self):
        source = {
            "id": "us_treasury_yield_curve",
            "name": "U.S. Treasury Daily Par Yield Curve Rates",
            "kind": "treasury_yield_xml",
            "url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml",
            "data": "daily_treasury_yield_curve",
            "dateField": "NEW_DATE",
            "valueField": "BC_10YEAR",
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
        self.assertNotIn("value", result)

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
