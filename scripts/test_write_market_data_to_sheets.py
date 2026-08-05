from __future__ import annotations

import base64
import json
import unittest

from scripts.write_market_data_to_sheets import (
    load_service_account_info,
    market_rows,
    sync_payload,
    use_policy,
)


class FakeSheetsClient:
    def __init__(self):
        self.values = {"history": [["スナップショットID"]]}
        self.updates = []
        self.appends = []

    def ensure_sheets(self, names):
        return {name: index + 1 for index, name in enumerate(names)}

    def clear(self, sheet_name):
        self.updates.append(("clear", sheet_name))

    def update(self, sheet_name, cells, values):
        self.updates.append((sheet_name, cells, values))

    def get_values(self, sheet_name, cells):
        return self.values.get(sheet_name, [])

    def append(self, sheet_name, cells, values):
        self.appends.append((sheet_name, cells, values))

    def format_table(self, sheet_id, column_count, row_count):
        return None


class MarketDataSheetRowsTest(unittest.TestCase):
    def test_verified_market_is_usable(self):
        self.assertEqual(use_policy({"verificationStatus": "verified", "fallbackUsed": False}), "使用可")

    def test_fallback_market_is_labeled(self):
        self.assertEqual(use_policy({"verificationStatus": "fallback", "fallbackUsed": True}), "前回確認値（要注記）")

    def test_market_rows_preserve_source_and_market_type(self):
        payload = {
            "generatedAt": "2026-08-05T12:00:00+09:00",
            "reportSlot": "12:00",
            "overallStatus": "verified",
            "markets": {
                "usdjpy": {
                    "displayName": "USD/JPY",
                    "value": 157.8,
                    "displayValue": "157.80",
                    "unit": "円",
                    "verificationStatus": "verified",
                    "fallbackUsed": False,
                    "sourceName": "Example",
                    "sourceUrl": "https://example.com",
                    "marketType": "spot",
                    "session": "continuous",
                }
            },
        }
        row = market_rows(payload)[0]
        self.assertEqual(row[4], "usdjpy")
        self.assertEqual(row[6], "使用可")
        self.assertEqual(row[7], 157.8)
        self.assertEqual(row[20], "Example")
        self.assertEqual(row[22], "spot")

    def test_base64_service_account_is_supported(self):
        encoded = base64.b64encode(
            json.dumps({"client_email": "bot@example.com", "private_key": "key"}).encode("utf-8")
        ).decode("ascii")
        result = load_service_account_info(encoded)
        self.assertEqual(result["client_email"], "bot@example.com")

    def test_sync_writes_latest_history_and_rules(self):
        payload = {
            "generatedAt": "2026-08-05T12:00:00+09:00",
            "reportSlot": "12:00",
            "overallStatus": "verified",
            "markets": {
                "usdjpy": {
                    "displayName": "USD/JPY",
                    "value": 157.8,
                    "displayValue": "157.80",
                    "unit": "円",
                    "verificationStatus": "verified",
                    "fallbackUsed": False,
                }
            },
        }
        client = FakeSheetsClient()
        summary = sync_payload(client, payload, "input", "history", "rules")
        self.assertEqual(summary["inputRows"], 1)
        self.assertEqual(summary["historyRowsAdded"], 1)
        self.assertEqual(client.appends[0][0], "history")
        self.assertTrue(any(item[0] == "input" for item in client.updates if len(item) == 3))


if __name__ == "__main__":
    unittest.main()
