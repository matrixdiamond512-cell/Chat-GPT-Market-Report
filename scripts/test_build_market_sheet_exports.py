from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_market_sheet_exports import build_exports


class MarketSheetExportTest(unittest.TestCase):
    def test_builds_latest_and_deduplicated_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            market_dir = Path(temp_dir)
            history_dir = market_dir / "history"
            history_dir.mkdir()
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
            (market_dir / "latest.json").write_text(json.dumps(payload), encoding="utf-8")
            (history_dir / "first.json").write_text(json.dumps(payload), encoding="utf-8")
            (history_dir / "duplicate.json").write_text(json.dumps(payload), encoding="utf-8")

            latest_count, history_count = build_exports(market_dir)

            self.assertEqual(latest_count, 1)
            self.assertEqual(history_count, 1)
            with (market_dir / "chatgpt_input.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[1][4], "usdjpy")
            self.assertEqual(rows[1][6], "使用可")


if __name__ == "__main__":
    unittest.main()
