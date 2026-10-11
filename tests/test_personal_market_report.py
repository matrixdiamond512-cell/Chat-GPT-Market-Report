from __future__ import annotations

import unittest

from scripts.build_chatgpt_report_input import ITEMS, apply_acquired_snapshot_market
from scripts.build_personal_market_report import render_report, report_sheet_row


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
            "markets": markets,
        }

        body = render_report(payload)

        self.assertEqual(body.count("\n| "), 29)  # column header plus all 28 report fields
        self.assertIn("| Fear & Greed Index | — |", body)
        self.assertIn("参考値: 12", body)
        self.assertIn("未取得", body)
        self.assertIn("検証済み", body)
        row = report_sheet_row(payload, body)
        self.assertEqual(row[5], 28)
        self.assertEqual(row[6], body)

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


if __name__ == "__main__":
    unittest.main()

