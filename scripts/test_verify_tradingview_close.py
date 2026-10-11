from __future__ import annotations

import unittest

from scripts.verify_tradingview_close import verify_close_evidence


class TradingViewCloseEvidenceTests(unittest.TestCase):
    def test_official_nasdaq_close_accepts_only_at_published_precision(self) -> None:
        candidate = {
            "id": "nasdaq", "symbol": "NASDAQ:IXIC", "marketType": "index",
            "marketDate": "2026-10-09", "value": "123.4567",
        }
        evidence = {
            "type": "official_index_close", "sourceId": "nasdaq_global_index_watch",
            "marketDate": "2026-10-09", "timezone": "America/New_York",
            "closeTime": "16:00", "publishedDecimals": 2, "value": "123.46",
        }
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "VERIFIED")
        evidence["value"] = "123.47"
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "CONFLICT")

    def test_wrong_official_index_source_does_not_promote(self) -> None:
        candidate = {
            "id": "nasdaq", "symbol": "NASDAQ:IXIC", "marketType": "index",
            "marketDate": "2026-10-09", "value": 123.46,
        }
        evidence = {
            "type": "official_index_close", "sourceId": "unofficial",
            "marketDate": "2026-10-09", "timezone": "America/New_York",
            "closeTime": "16:00", "publishedDecimals": 2, "value": 123.46,
        }
        self.assertNotEqual(verify_close_evidence(candidate, evidence)["status"], "VERIFIED")

    def test_forex_daily_close_requires_matching_ny_17_boundary_and_market_date(self) -> None:
        candidate = {
            "id": "usdjpy", "symbol": "FX:USDJPY", "marketType": "spot",
            "marketDate": "2026-10-09", "barAnchorUtc": "2026-10-08T21:00:00Z",
            "value": "123.45",
        }
        evidence = {
            "type": "forex_daily_close", "timezone": "America/New_York",
            "closeTime": "17:00", "closeBoundaryUtc": "2026-10-09T21:00:00Z",
            "intradayBarStartUtc": "2026-10-09T20:00:00Z",
            "marketDate": "2026-10-09", "intradayClose": "123.45",
        }
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "VERIFIED")
        candidate["marketDate"] = "2026-10-08"
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "CONFLICT")

    def test_forex_close_rejects_a_daily_bar_with_the_wrong_boundary(self) -> None:
        candidate = {
            "id": "eurusd", "symbol": "FX:EURUSD", "marketType": "spot",
            "marketDate": "2026-10-09", "barAnchorUtc": "2026-10-08T20:00:00Z",
            "value": "1.2345",
        }
        evidence = {
            "type": "forex_daily_close", "timezone": "America/New_York",
            "closeTime": "17:00", "closeBoundaryUtc": "2026-10-09T21:00:00Z",
            "intradayBarStartUtc": "2026-10-09T20:00:00Z",
            "marketDate": "2026-10-09", "intradayClose": "1.2345",
        }
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "CONFLICT")

    def test_continuous_future_cannot_stand_in_for_named_contract_settlement(self) -> None:
        candidate = {
            "id": "cme_nikkei225_jpy", "symbol": "CME:NIY1!",
            "marketType": "futures_cme", "marketDate": "2026-10-09", "value": 123,
        }
        evidence = {
            "type": "official_futures_settlement", "continuousSymbol": "CME:NIY1!",
            "contract": "NIYZ6", "settlement": {"marketDate": "2026-10-09", "value": 123},
        }
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "CONFLICT")

    def test_btc_needs_same_exchange_and_utc_market_date(self) -> None:
        candidate = {
            "id": "btcusd", "symbol": "BITSTAMP:BTCUSD", "marketType": "spot",
            "marketDate": "2026-10-10", "value": 123,
        }
        evidence = {
            "type": "same_exchange_utc_daily_close", "exchange": "BITSTAMP",
            "timezone": "UTC", "marketDate": "2026-10-10", "value": 123,
        }
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "VERIFIED")
        evidence["exchange"] = "KRAKEN"
        self.assertNotEqual(verify_close_evidence(candidate, evidence)["status"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
