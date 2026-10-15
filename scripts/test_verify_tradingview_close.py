from __future__ import annotations

import unittest

from scripts.verify_tradingview_close import verify_close_evidence


class TradingViewCloseEvidenceTests(unittest.TestCase):
    def test_official_nasdaq_close_accepts_only_at_published_precision(self) -> None:
        candidate = {
            "id": "nasdaq", "symbol": "NASDAQ:IXIC", "marketType": "index",
            "marketDate": "2026-10-09", "barAnchorUtc": "2026-10-09T13:30:00Z", "value": "123.4567",
        }
        evidence = {
            "type": "official_index_close", "sourceId": "nasdaq_global_index_watch",
            "marketDate": "2026-10-09", "timezone": "America/New_York",
            "closeTime": "16:00", "publishedDecimals": 2, "value": "123.46",
        }
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "VERIFIED")
        evidence["value"] = "123.47"
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "CONFLICT")

    def test_sp500_accepts_official_sp_dji_dashboard_value(self) -> None:
        candidate = {
            "id": "sp500", "symbol": "SP:SPX", "marketType": "index",
            "marketDate": "2026-10-09", "barAnchorUtc": "2026-10-09T13:30:00Z", "value": "123.456",
        }
        evidence = {
            "type": "official_index_close", "sourceId": "sp_dji_index_dashboard",
            "marketDate": "2026-10-09", "timezone": "America/New_York",
            "closeTime": "16:00", "publishedDecimals": 2, "value": "123.46",
        }
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "VERIFIED")

    def test_wrong_official_index_source_does_not_promote(self) -> None:
        candidate = {
            "id": "nasdaq", "symbol": "NASDAQ:IXIC", "marketType": "index",
            "marketDate": "2026-10-09", "barAnchorUtc": "2026-10-09T13:30:00Z", "value": 123.46,
        }
        evidence = {
            "type": "official_index_close", "sourceId": "unofficial",
            "marketDate": "2026-10-09", "timezone": "America/New_York",
            "closeTime": "16:00", "publishedDecimals": 2, "value": 123.46,
        }
        self.assertNotEqual(verify_close_evidence(candidate, evidence)["status"], "VERIFIED")


    def test_dow_provider_symbol_matches_trusted_daily_close_at_published_precision(self) -> None:
        candidate = {
            "id": "dow", "symbol": "DJ:DJI", "marketType": "index",
            "marketDate": "2026-10-09", "barAnchorUtc": "2026-10-09T13:30:00Z", "value": "51654.95",
        }
        evidence = {
            "type": "independent_daily_index_close", "sourceId": "ap_us_equity_close_summary",
            "marketDate": "2026-10-09", "timezone": "America/New_York",
            "closeTime": "16:00", "publishedDecimals": 2, "value": "51654.95",
        }
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "VERIFIED")
        evidence["marketDate"] = "2026-10-08"
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "CONFLICT")

    def test_russell_independent_daily_close_matches_at_two_decimals(self) -> None:
        candidate = {
            "id": "russell2000", "symbol": "CBOEFTSE:RUT", "marketType": "index",
            "marketDate": "2026-10-09", "barAnchorUtc": "2026-10-09T13:30:00Z", "value": "2806.9814",
        }
        evidence = {
            "type": "independent_daily_index_close", "sourceId": "ap_us_equity_close_summary",
            "marketDate": "2026-10-09", "timezone": "America/New_York",
            "closeTime": "16:00", "publishedDecimals": 2, "value": "2806.98",
        }
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "VERIFIED")

    def test_vix_requires_two_matching_daily_history_sources(self) -> None:
        candidate = {
            "id": "vix", "symbol": "CBOE:VIX", "marketType": "index",
            "marketDate": "2026-10-09", "barAnchorUtc": "2026-10-09T07:15:00Z", "value": "14.84",
        }
        evidence = {
            "type": "independent_volatility_index_close", "marketDate": "2026-10-09",
            "timezone": "America/New_York", "publishedDecimals": 2,
            "references": [
                {"sourceId": "yahoo_finance_vix_daily_history", "value": "14.84"},
                {"sourceId": "chartexchange_vix_daily_history", "value": "14.84"},
            ],
        }
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "VERIFIED")
        evidence["references"][1]["value"] = "14.83"
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "CONFLICT")

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

    def test_official_index_rejects_wrong_cash_session_anchor(self) -> None:
        candidate = {
            "id": "nasdaq", "symbol": "NASDAQ:IXIC", "marketType": "index",
            "marketDate": "2026-10-09", "barAnchorUtc": "2026-10-09T14:30:00Z", "value": 123.46,
        }
        evidence = {
            "type": "official_index_close", "sourceId": "nasdaq_global_index_watch",
            "marketDate": "2026-10-09", "timezone": "America/New_York",
            "closeTime": "16:00", "publishedDecimals": 2, "value": 123.46,
        }
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "CONFLICT")

    def test_forex_rejects_timestamp_claimed_as_17_but_not_17_local(self) -> None:
        candidate = {
            "id": "usdjpy", "symbol": "FX:USDJPY", "marketType": "spot",
            "marketDate": "2026-10-09", "barAnchorUtc": "2026-10-08T20:00:00Z", "value": "123.45",
        }
        evidence = {
            "type": "forex_daily_close", "timezone": "America/New_York",
            "closeTime": "17:00", "closeBoundaryUtc": "2026-10-09T20:00:00Z",
            "intradayBarStartUtc": "2026-10-09T19:00:00Z",
            "marketDate": "2026-10-09", "intradayClose": "123.45",
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
            "marketDate": "2026-10-10", "barAnchorUtc": "2026-10-10T00:00:00Z", "value": 123,
        }
        evidence = {
            "type": "same_exchange_utc_daily_close", "exchange": "BITSTAMP",
            "timezone": "UTC", "marketDate": "2026-10-10",
            "closeBoundaryUtc": "2026-10-11T00:00:00Z",
            "intradayBarStartUtc": "2026-10-10T23:00:00Z",
            "intradayClose": 123,
        }
        self.assertEqual(verify_close_evidence(candidate, evidence)["status"], "VERIFIED")
        evidence["exchange"] = "KRAKEN"
        self.assertNotEqual(verify_close_evidence(candidate, evidence)["status"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
