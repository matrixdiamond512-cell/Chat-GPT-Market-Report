from __future__ import annotations

import unittest

from scripts.build_chatgpt_report_input import ITEMS, apply_acquired_snapshot_market
from scripts.build_personal_market_report import (
    PersonalReportError,
    _comparable_change,
    render_report,
    report_sheet_row,
    validate_sheet_target_ids,
)


class PersonalMarketReportTests(unittest.TestCase):
    def test_report_lists_all_28_and_distinguishes_verified_reference_and_missing(self):
        markets = {}
        for index, (label, symbol, unit, market_type, session) in enumerate(ITEMS):
            markets[symbol] = {
                "displayName": label,
                "value": index + 1,
                "displayValue": str(index + 1),
                "unit": unit,
                "asOf": "2026-10-09",
                "sourceName": "fixture-source",
                "verificationStatus": "verified",
                "marketType": market_type,
                "session": session,
            }
        markets["wti"]["verificationStatus"] = "fallback"
        markets["wti"]["fallbackUsed"] = True
        markets["fear_greed"]["verificationStatus"] = "unavailable"
        markets["fear_greed"]["value"] = None
        markets["fear_greed"]["displayValue"] = "取得不能"
        payload = {
            "generatedAt": "2026-10-12T08:00:00+09:00",
            "reportDate": "2026-10-12",
            "reportSlot": "08:00",
            "overallStatus": "degraded",
            "snapshotFreshness": "latest_available_confirmed_per_market",
            "validationNotes": ["市場別に最新確認済み日が異なります。"],
            "markets": markets,
            "news": [{"title": "銀行決算と米CPIに注目", "provider": "Reuters",
                      "url": "https://www.tradingview.com/news/reuters.test/",
                      "publishedAt": "2026-10-11T13:00:46Z", "permission": "headline"}],
        }

        body = render_report(payload)

        self.assertEqual(body.count("\n| "), 29)  # column header plus all 28 report fields
        self.assertIn("| Fear & Greed Index | — |", body)
        self.assertIn("参考値: 12", body)
        self.assertIn("未取得", body)
        self.assertIn("検証済み", body)
        self.assertIn("市場別に最新確認済み日が異なります。", body)
        self.assertIn("各項目はレポート生成時点で確認できた最新の市場別データです。", body)
        row = report_sheet_row(payload, body)
        self.assertEqual(row[4:7], [22, 5, 1])
        self.assertEqual(row[7], body)

    def test_historical_report_marks_age_and_builds_sections_from_the_same_snapshot(self):
        markets = {}
        for label, symbol, unit, market_type, session in ITEMS:
            markets[symbol] = {
                "displayName": label, "value": None, "displayValue": "—", "unit": unit,
                "asOf": "", "sourceName": "", "verificationStatus": "unavailable",
                "marketType": market_type, "session": session,
            }
        markets["dow"].update({"value": 51654.95, "displayValue": "51654.95", "asOf": "2026-10-09", "fetchedAt": "2026-10-12T02:48:43Z", "sourceName": "TradingView official MCP", "verificationStatus": "verified", "verificationBasis": "二次資料の終値照合", "changePercent": 0.8})
        markets["nikkei225_futures_cme_yen"].update({"value": 69085, "displayValue": "69085", "unit": "円", "asOf": "2026-10-09", "fetchedAt": "2026-10-12T02:48:43Z", "sourceName": "TradingView official MCP", "verificationStatus": "reference_only", "referenceOnly": True, "marketType": "futures_cme", "priceType": "continuous_bar_close", "note": "限月別清算値は未確認"})
        body = render_report({
            "generatedAt": "2026-10-12T04:53:47+09:00", "reportDate": "2026-10-09〜2026-10-10",
            "reportSlot": "履歴再構成", "overallStatus": "historical_only", "historicalSnapshot": True,
            "markets": markets,
            "news": [{"title": "銀行決算と米CPIに注目", "provider": "Reuters",
                      "url": "https://www.tradingview.com/news/reuters.test/",
                      "publishedAt": "2026-10-11T13:00:46Z", "permission": "headline"}],
            "detailedReport": {
                "date": "2026-10-08", "theme": "古い文章は使用しない",
            },
        })
        self.assertIn("履歴データからの再構成です", body)
        self.assertIn("同一スナップショットに基づく詳細分析", body)
        self.assertIn("同じスナップショットから生成", body)
        self.assertIn("ニュース", body)
        self.assertIn("クロスアセット資金フロー", body)
        self.assertIn("需給・ポジション", body)
        self.assertIn("主要6市場の見通し", body)
        self.assertIn("金利・金融環境（今回のスナップショット）", body)
        self.assertIn("上昇 1・下落 0", body)
        self.assertNotIn("古い文章は使用しない", body)
        self.assertIn("銀行決算と米CPIに注目", body)
        self.assertIn("2026-10-11T13:00:46Z", body)
        self.assertIn("参考値: 69085", body)
        self.assertIn("参考値（清算値未確認）", body)

    def test_report_analysis_changes_only_when_snapshot_evidence_changes(self):
        markets = {symbol: {
            "displayName": label, "value": 100, "displayValue": "100", "unit": unit,
            "asOf": "2026-10-12", "fetchedAt": "2026-10-12T06:00:00Z",
            "sourceName": "official-test", "verificationStatus": "verified", "marketType": mtype,
            "changePercent": -0.4,
        } for label, symbol, unit, mtype, _ in ITEMS}
        first = render_report({"reportDate": "2026-10-12", "generatedAt": "2026-10-12T06:01:00Z", "markets": markets})
        markets["sp500"]["changePercent"] = 0.7
        second = render_report({"reportDate": "2026-10-12", "generatedAt": "2026-10-12T06:02:00Z", "markets": markets})
        self.assertIn("上昇 0・下落 5", first)
        self.assertIn("上昇 1・下落 4", second)
        self.assertNotEqual(first, second)
        self.assertIn("建玉", second)

    def test_computed_change_requires_prior_date_and_same_source(self):
        market = {"verificationStatus": "verified", "asOf": "2026-10-12", "sourceId": "series-a",
                  "value": 110, "previousClose": 100}
        self.assertIsNone(_comparable_change(market))
        market["previousCloseAsOf"] = "2026-10-09"
        self.assertEqual(_comparable_change(market), 10)
        market["previousCloseSourceId"] = "series-b"
        self.assertIsNone(_comparable_change(market))

    def test_snapshot_overlay_uses_market_specific_dates_and_keeps_source_provenance(self):
        base = {"value": 100, "asOf": "2026-10-09", "verificationStatus": "unavailable"}
        snapshot = {
            "generatedAt": "2026-10-12T08:00:00+09:00",
            "markets": {
                "dow": {
                    "value": 101.5,
                    "asOf": "2026-10-09T16:00:00-04:00",
                    "fetchedAt": "2026-10-10T08:00:00+09:00",
                    "verificationStatus": "verified",
                    "sourceId": "official-test",
                    "sourceName": "Official fixture",
                    "unit": "pt",
                },
                "btcusd": {
                    "value": 102.5,
                    "asOf": "2026-10-10T00:00:00Z",
                    "fetchedAt": "2026-10-10T00:05:00Z",
                    "verificationStatus": "verified",
                    "sourceId": "crypto-test",
                    "sourceName": "Crypto fixture",
                    "unit": "USD",
                },
                "nasdaq": {
                    "value": 999,
                    "asOf": "2026-10-13",
                    "fetchedAt": "2026-10-12",
                    "verificationStatus": "verified",
                },
            },
        }

        dow = apply_acquired_snapshot_market(base, snapshot, "dow")
        btc = apply_acquired_snapshot_market(base, snapshot, "btcusd")
        future = apply_acquired_snapshot_market(base, snapshot, "nasdaq")

        self.assertEqual(dow["value"], 101.5)
        self.assertEqual(dow["sourceId"], "official-test")
        self.assertEqual(btc["value"], 102.5)
        self.assertEqual(btc["asOf"], "2026-10-10T00:00:00Z")
        self.assertEqual(future, base)

    def test_test_sheet_write_requires_a_distinct_known_production_target(self):
        validate_sheet_target_ids("private-test-id", "production-id")
        with self.assertRaises(PersonalReportError):
            validate_sheet_target_ids("private-test-id", "")
        with self.assertRaises(PersonalReportError):
            validate_sheet_target_ids("same-id", "same-id")

    def test_report_row_identity_is_stable_for_an_exact_snapshot_and_body(self):
        payload = {
            "generatedAt": "2026-10-12T01:00:00Z", "dataDateRange": "2026-10-09",
            "markets": {"dow": {"value": 100, "asOf": "2026-10-09", "sourceId": "source-a", "sourceName": "A", "unit": "pt", "verificationStatus": "verified", "fetchedAt": "2026-10-12T00:00:00Z"}},
        }
        body = "same immutable report"
        first = report_sheet_row(payload, body)
        retry = report_sheet_row({**payload, "generatedAt": "2026-10-12T02:00:00Z"}, body)
        revised = report_sheet_row(payload, body + " revised")
        self.assertEqual(first[0], retry[0])
        self.assertNotEqual(first[0], revised[0])


if __name__ == "__main__":
    unittest.main()
