import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = [
    "merge-nikkei-metrics-into-stocks.yml",
    "restore-us-market-internals.yml",
    "update-japan-stock-movers.yml",
    "update-nikkei-contributions.yml",
    "update-nikkei-metrics.yml",
    "update-sector-performance.yml",
    "update-stock-sessions.yml",
    "update-stocks-history.yml",
    "update-tokyo-preopen.yml",
    "update-tokyo-stock-table.yml",
    "update-us-premarket.yml",
    "update-us-stock-breadth.yml",
    "update-us-stock-movers-contributions.yml",
]


class StockAutomationContractTests(unittest.TestCase):
    def test_stock_writers_use_retrying_publish_helper(self):
        for name in WORKFLOWS:
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            with self.subTest(workflow=name):
                self.assertIn("publish_stock_update.sh", text)
                self.assertRegex(text, r"cancel-in-progress:\s*false")

    def test_dedicated_market_slots_and_freshness_guards_remain(self):
        tokyo = (ROOT / ".github" / "workflows" / "update-tokyo-preopen.yml").read_text(encoding="utf-8")
        us = (ROOT / ".github" / "workflows" / "update-us-premarket.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "50 23 * * 0-4"', tokyo)
        self.assertIn('cron: "58 23 * * 0-4"', tokyo)
        self.assertIn("current.get('freshness') != 'fresh'", tokyo)
        self.assertIn('cron: "40 11 * * 1-5"', us)
        self.assertIn('cron: "55 11 * * 1-5"', us)
        self.assertIn("current = payload.get('current') or payload", us)
        self.assertIn("current.get('freshness') != 'fresh'", us)

    def test_scheduled_dispatcher_does_not_fan_out_all_writers(self):
        text = (ROOT / ".github" / "workflows" / "update-stocks.yml").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(?ms)^\s+schedule:\s*\n\s+- cron:")


if __name__ == "__main__":
    unittest.main()
