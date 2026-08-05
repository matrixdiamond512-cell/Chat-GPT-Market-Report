import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts.resolve_market_report_slot import JST, resolve_slot


class ResolveMarketReportSlotTests(unittest.TestCase):
    def test_schedule_maps_to_report_slot(self):
        now = dt.datetime(2026, 8, 5, 20, 50, tzinfo=JST)
        self.assertEqual(
            resolve_slot(
                "schedule",
                "50 11 * * 1-5",
                "auto",
                Path("missing"),
                now,
            ),
            "21:00",
        )

    def test_delayed_schedule_uses_actual_japan_time(self):
        now = dt.datetime(2026, 8, 5, 22, 13, tzinfo=JST)
        self.assertEqual(
            resolve_slot(
                "schedule",
                "50 6 * * 1-5",
                "auto",
                Path("missing"),
                now,
            ),
            "21:00",
        )

    def test_push_uses_latest_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reports.json"
            path.write_text(json.dumps({"reports": [
                {"date": "2026-08-05", "time": "16:00"},
                {"date": "2026-08-05", "time": "21:00"},
            ]}), encoding="utf-8")
            self.assertEqual(resolve_slot("push", "", "auto", path), "21:00")

    def test_manual_dispatch_never_writes_manual(self):
        now = dt.datetime(2026, 8, 5, 21, 5, tzinfo=JST)
        self.assertEqual(
            resolve_slot("workflow_dispatch", "", "auto", Path("missing"), now),
            "21:00",
        )


if __name__ == "__main__":
    unittest.main()
