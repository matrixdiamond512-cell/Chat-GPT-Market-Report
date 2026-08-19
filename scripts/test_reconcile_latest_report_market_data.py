#!/usr/bin/env python3
import copy
import unittest

from reconcile_latest_report_market_data import reconcile_report_market_data


def sample_report():
    return {
        "date": "2026-08-19",
        "time": "12:00",
        "marketDataTable": {
            "rows": [
                {
                    "label": "金",
                    "value": "取得不能",
                    "change": "同日12:00値を確定できず",
                    "rate": "—",
                    "direction": "中立～やや強気",
                },
                {
                    "label": "WTI原油",
                    "value": "85.34ドル/bbl",
                    "change": "前日NY決済84.94ドルから上昇",
                    "rate": "—",
                    "direction": "強気寄り・高ボラ",
                },
                {
                    "label": "EUR/USD",
                    "value": "取得不能",
                    "change": "同日12:00値を確定できず",
                    "rate": "—",
                    "direction": "中立～やや弱気",
                },
            ]
        },
        "markets": [
            {
                "name": "金",
                "price": "取得不能",
                "change": "—",
                "direction": "中立～やや強気",
            },
            {
                "name": "WTI原油",
                "price": "85.34ドル/bbl",
                "change": "前日NY決済84.94ドルから上昇",
                "direction": "強気寄り・高ボラ",
            },
            {
                "name": "EUR/USD",
                "price": "取得不能",
                "change": "—",
                "direction": "中立～やや弱気",
            },
        ],
    }


def sample_snapshot():
    return {
        "generatedAt": "2026-08-19T12:15:54+09:00",
        "reportSlot": "12:00",
        "overallStatus": "verified",
        "markets": {
            "gold": {
                "value": 4408.4,
                "displayValue": "4,408.40",
                "changeText": "+42.40 / +0.97%",
                "changePercent": 0.9711,
                "verificationStatus": "verified",
                "asOf": "2026-08-19T12:05:17+09:00",
            },
            "eurusd": {
                "value": 1.1587,
                "displayValue": "1.15870",
                "changeText": "+0.00042 / +0.04%",
                "changePercent": 0.0363,
                "verificationStatus": "verified",
                "asOf": "2026-08-19T12:14:58+09:00",
            },
        },
    }


class ReconcileMarketDataTests(unittest.TestCase):
    def test_fills_only_unavailable_fields_and_preserves_valid_values(self):
        report = sample_report()
        changed = reconcile_report_market_data(report, sample_snapshot())

        self.assertEqual(changed, ["eurusd", "gold"])
        self.assertEqual(
            report["marketDataTable"]["rows"][0]["value"],
            "4,408.40ドル/oz（12:05 JST再取得）",
        )
        self.assertEqual(report["marketDataTable"]["rows"][1]["value"], "85.34ドル/bbl")
        self.assertEqual(
            report["markets"][2]["price"],
            "1.15870（12:14 JST再取得）",
        )
        self.assertEqual(report["markets"][1]["price"], "85.34ドル/bbl")
        self.assertEqual(
            report["dataProvenance"]["marketDataReconciliation"]["updatedSymbols"],
            ["eurusd", "gold"],
        )

    def test_skips_different_slot(self):
        report = sample_report()
        snapshot = copy.deepcopy(sample_snapshot())
        snapshot["reportSlot"] = "16:00"

        self.assertEqual(reconcile_report_market_data(report, snapshot), [])
        self.assertEqual(report["marketDataTable"]["rows"][0]["value"], "取得不能")

    def test_skips_unverified_values(self):
        report = sample_report()
        snapshot = copy.deepcopy(sample_snapshot())
        snapshot["markets"]["gold"]["verificationStatus"] = "fallback"

        self.assertEqual(reconcile_report_market_data(report, snapshot), [])
        self.assertEqual(report["marketDataTable"]["rows"][0]["value"], "取得不能")


if __name__ == "__main__":
    unittest.main()
