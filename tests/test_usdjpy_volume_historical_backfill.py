"""Offline historical USDJPY volume-price backfill regressions."""
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_usdjpy_volume_price_backfill as runner
import update_usdjpy_volume_prices as core
from stooq_usdjpy_ohlc import parse_csv
from yahoo_jp_usdjpy_ohlc import parse_history


class PriceBackfillTest(unittest.TestCase):
    def test_yahoo_japan_daily_ohlc_parser(self):
        html = '<table><tr><th>日付</th><th>始値</th><th>高値</th><th>安値</th><th>終値</th></tr>' \
               '<tr><td>2025/10/1</td><td>149.10</td><td>149.75</td><td>148.95</td><td>149.30</td></tr></table>'
        self.assertEqual(parse_history(html)["2025-10-01"]["close"], 149.30)

    def test_stooq_daily_csv_parser_rejects_bad_candles(self):
        csv_text = "Date,Open,High,Low,Close\n" \
                   "2025-09-30,149.10,149.30,148.80,149.00\n" \
                   "2025-10-01,149.10,149.75,148.95,149.30\n" \
                   "2025-10-02,149.10,148.75,148.95,149.30\n"
        candles = parse_csv(csv_text, start_date="2025-10-01", end_date="2025-10-10")
        self.assertEqual(list(candles), ["2025-10-01"])
        self.assertEqual(candles["2025-10-01"]["close"], 149.30)

    def test_old_gap_outside_last_20_is_filled_without_replacing_prices_or_volume(self):
        newer_days = []
        day = date(2026, 5, 1)
        while len(newer_days) < 21:
            if day.weekday() < 5:
                newer_days.append(day.isoformat())
            day += timedelta(days=1)
        rows = [
            {"targetDate": d, "publicationDate": d,
             "spotVolume": 3000 + i, "avg20": 3000, "vs20": 0, "vs20Pct": 0,
             "open": 159.10, "high": 159.70, "low": 159.0, "close": 159.20,
             "priceChangePct": 0.12}
            for i, d in enumerate(reversed(newer_days))
        ]
        rows.append({
            "targetDate": "2025-10-01", "publicationDate": "2025-10-02",
            "spotVolume": 3210, "avg20": 3210, "vs20": 0, "vs20Pct": 0,
            "open": None, "high": None, "low": None, "close": None,
            "priceChangePct": None,
        })
        fixture = {"data": {"records": rows, "priceRecords": []},
                   "sources": [], "components": {}}
        yahoo = {
            "2025-09-30": {"date": "2025-09-30", "open": 149.0,
                           "high": 149.2, "low": 148.7, "close": 149.0},
            "2025-10-01": {"date": "2025-10-01", "open": 149.1,
                           "high": 149.75, "low": 148.95, "close": 149.30},
        }
        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "usdjpy-volume.json"
            file_path.write_text(json.dumps(fixture), encoding="utf-8")
            with patch.object(core, "PATH", file_path), \
                 patch.object(runner, "fetch_history", return_value=yahoo), \
                 patch.object(core, "fetch_yahoo", side_effect=AssertionError("unnecessary fallback")), \
                 patch.object(runner, "fetch_stooq", side_effect=AssertionError("unnecessary fallback")):
                runner.main()
            updated = json.loads(file_path.read_text(encoding="utf-8"))
        by_day = {r["targetDate"]: r for r in updated["data"]["records"]}
        self.assertEqual(by_day["2025-10-01"]["close"], 149.30)
        self.assertEqual(by_day["2025-10-01"]["spotVolume"], 3210)
        self.assertEqual(by_day["2025-10-01"]["priceSourceId"], "YAHOO_JP_USDJPY")
        self.assertEqual(by_day[newer_days[-1]]["close"], 159.20)
        self.assertEqual(updated["data"]["priceRange"]["count"], 22)
        self.assertEqual(updated["components"]["usdjpyOhlc"]["status"], "ok")
        self.assertEqual(updated["data"]["priceAcquisition"]["missingAllDates"], [])


if __name__ == "__main__":
    unittest.main()
