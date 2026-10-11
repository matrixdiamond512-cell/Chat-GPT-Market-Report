from __future__ import annotations

import unittest

from scripts.build_chatgpt_report_input import ITEMS
from scripts.build_personal_market_snapshot import build_snapshot, SnapshotError, READY_COLUMNS, REFERENCE_COLUMNS
from scripts.build_personal_market_report import report_counts


class PersonalSnapshotTests(unittest.TestCase):
    def _source(self):
        ready = [READY_COLUMNS]
        for index, (field, value, unit, mtype, session, market_date, anchor, evidence) in enumerate([
            ("dow", 101.1, "pt", "index", "us_cash", "2026-10-09", "2026-10-09T13:30:00Z", "secondary"),
            ("nasdaq", 102.2, "pt", "index", "us_cash", "2026-10-09", "2026-10-09T13:30:00Z", "official"),
            ("sp500", 103.3, "pt", "index", "us_cash", "2026-10-09", "2026-10-09T13:30:00Z", "official"),
            ("russell2000", 104.4, "pt", "index", "us_cash", "2026-10-09", "2026-10-09T13:30:00Z", "secondary"),
            ("usdjpy", 105.5, "JPY per USD", "spot", "forex_daily", "2026-10-09", "2026-10-08T21:00:00Z", "NY close"),
            ("eurusd", 106.6, "USD per EUR", "spot", "forex_daily", "2026-10-09", "2026-10-08T21:00:00Z", "NY close"),
            ("btcusd", 107.7, "USD", "spot", "utc_daily", "2026-10-10", "2026-10-10T00:00:00Z", "UTC close"),
            ("vix", 108.8, "pt", "index", "us_volatility", "2026-10-09", "2026-10-09T07:15:00Z", "secondary"),
            ("us10y", 109.9, "%", "bond_yield", "us_treasury_daily", "2026-10-09", "", "Treasury official"),
        ]):
            ready.append([f"ready-{index}", field, value, unit, mtype, session, market_date, anchor,
                          "TradingView official MCP" if field != "us10y" else "U.S. Treasury",
                          evidence, "VERIFIED", "2026-10-11T17:48:43Z"])
        references = [REFERENCE_COLUMNS]
        for index, (field, value, unit, symbol, session, market_date, anchor) in enumerate([
            ("gold", 201.1, "USD/oz", "COMEX:GC1!", "comex", "2026-10-09", "2026-10-09T22:00:00Z"),
            ("wti", 202.2, "USD/bbl", "NYMEX:CL1!", "nymex", "2026-10-09", "2026-10-09T22:00:00Z"),
            ("nikkei225_futures_ose", 203.3, "円", "OSE:NK2251!", "ose", "2026-10-09", "2026-10-09T08:00:00Z"),
            ("cme_nikkei225_jpy", 204.4, "円", "CME:NIY1!", "cme", "2026-10-09", "2026-10-09T22:00:00Z"),
            ("cme_nikkei225_usd", 205.5, "USD", "CME:NKD1!", "cme", "2026-10-09", "2026-10-09T22:00:00Z"),
        ]):
            references.append([f"reference-{index}", field, value, unit, symbol, "CONTINUOUS_BAR_CLOSE",
                               session, market_date, anchor, "TradingView official MCP", "REFERENCE_ONLY",
                               "NOT_CONFIRMED; continuous bar is not settlement", "2026-10-11T17:48:43Z"])
        return {"reportReadyValues": ready, "referenceValues": references}

    def test_normalizes_nine_verified_and_five_reference_rows_with_lineage(self):
        source = self._source()
        payload = build_snapshot(source, "2026-10-12T04:53:47+09:00")
        self.assertEqual(report_counts(payload), (9, 5, 14))
        self.assertEqual(payload["dataDateRange"], "2026-10-09〜2026-10-10")
        self.assertEqual(payload["markets"]["usdjpy"]["asOf"], "2026-10-09")
        self.assertEqual(payload["markets"]["btcusd"]["asOf"], "2026-10-10")
        self.assertEqual(payload["markets"]["nikkei225_futures_cme_usd"]["unit"], "USD")
        self.assertEqual(payload["markets"]["nikkei225_futures_ose"]["verificationStatus"], "reference_only")
        self.assertEqual(payload["markets"]["nikkei225_futures_ose"]["priceType"], "continuous_bar_close")
        self.assertEqual(payload["markets"]["dow"]["fetchedAt"], "2026-10-11T17:48:43Z")
        self.assertNotIn("detailedReport", payload)

    def test_rejects_future_dated_observation(self):
        source = self._source()
        source["reportReadyValues"][1][6] = "2026-10-13"
        with self.assertRaises(SnapshotError):
            build_snapshot(source, "2026-10-12T04:53:47+09:00")

    def test_old_report_text_is_not_an_input_to_the_common_snapshot(self):
        source = self._source()
        source["detailedReport"] = {"date": "2026-10-08", "fullText": "stale narrative"}
        payload = build_snapshot(source, "2026-10-12T04:53:47+09:00")
        self.assertNotIn("detailedReport", payload)

    def test_operator_attested_manual_official_value_joins_snapshot_without_becoming_tradingview(self):
        source = self._source()
        source["reportReadyValues"].append([
            "manual-nikkei-cash-20261012", "nikkei225_cash", 70000, "円", "index", "japan_cash",
            "2026-10-12", "", "日経平均プロフィル（手動確認）", "Operator reviewed the manual source date and value.",
            "VERIFIED_MANUAL", "2026-10-12T00:10:00Z",
        ])
        payload = build_snapshot(source, "2026-10-12T00:30:00Z")
        self.assertEqual(payload["markets"]["nikkei225_cash"]["verificationStatus"], "verified")
        self.assertEqual(payload["markets"]["nikkei225_cash"]["sourceId"], "manual_official_nikkei")
        self.assertIn("Operator reviewed", payload["markets"]["nikkei225_cash"]["verificationBasis"])
        self.assertEqual(report_counts(payload), (10, 5, 13))

    def test_all_manual_nikkei_metrics_join_the_same_report_snapshot(self):
        source = self._source()
        for index, (field, value, unit, market_type) in enumerate([
            ("nikkei225_cash", 70000, "円", "index"),
            ("nikkei_vi", 24.5, "pt", "index"),
            ("nikkei225_dev25", 1.25, "%", "technical"),
            ("nikkei225_dev200", 8.5, "%", "technical"),
            ("nikkei225_per", 17.0, "倍", "technical"),
            ("nikkei225_pbr", 1.8, "倍", "technical"),
            ("nikkei225_eps", 4117.647058823529, "円", "technical"),
        ]):
            source["reportReadyValues"].append([
                f"manual-{field}-20261012", field, value, unit, market_type, "japan_cash",
                "2026-10-12", "", "日経平均プロフィル（手動確認）",
                "Operator reviewed the official index-based source and same-date consistency.",
                "VERIFIED_MANUAL", "2026-10-12T00:10:00Z",
            ])

        payload = build_snapshot(source, "2026-10-12T00:30:00Z")
        for field, _, _, _ in [
            ("nikkei225_cash", 0, "", ""), ("nikkei_vi", 0, "", ""),
            ("nikkei225_dev25", 0, "", ""), ("nikkei225_dev200", 0, "", ""),
            ("nikkei225_per", 0, "", ""), ("nikkei225_pbr", 0, "", ""),
            ("nikkei225_eps", 0, "", ""),
        ]:
            self.assertEqual(payload["markets"][field]["verificationStatus"], "verified")
            self.assertEqual(payload["markets"][field]["sourceId"], "manual_official_nikkei")
        self.assertEqual(report_counts(payload), (16, 5, 7))


if __name__ == "__main__":
    unittest.main()

