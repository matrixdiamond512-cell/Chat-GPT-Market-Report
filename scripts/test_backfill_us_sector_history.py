#!/usr/bin/env python3
"""Offline regression for safe all-11-sector dated historical rebuild."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from backfill_us_sector_history import (
    US_SECTORS, complete_market_days, make_plan, returns_from_closes,
)


class UsSectorHistoryBackfillTests(unittest.TestCase):
    def test_price_return_uses_actual_prior_observation_and_rejects_long_gap(self):
        closes = {"2026-10-12": 100., "2026-10-13": 102.,
                  "2026-10-14": 101., "2026-10-29": 150.}
        r = returns_from_closes(closes)
        self.assertAlmostEqual(r["2026-10-13"], .02)
        self.assertAlmostEqual(r["2026-10-14"], 101 / 102 - 1)
        self.assertNotIn("2026-10-29", r)

    def market(self):
        symbols = list(US_SECTORS)
        return {sym: {"2026-10-13": (i + 1) / 1000.,
                      "2026-10-14": -(i + 1) / 1000.}
                for i, sym in enumerate(symbols)}

    def test_all_11_required_same_date(self):
        market = self.market()
        complete = complete_market_days(market)
        self.assertEqual(set(complete), {"2026-10-13", "2026-10-14"})
        market["XLE"].pop("2026-10-13")
        self.assertNotIn("2026-10-13", complete_market_days(market))
        market.pop("XLK")
        self.assertEqual(complete_market_days(market), {})

    def test_blank_only_plan_never_mixes_existing_rank(self):
        market = complete_market_days(self.market())
        headers = ["日付"] + [
            f"米国セクター{direction}{i}{suffix}"
            for direction in ("上昇", "下落")
            for i in range(1, 6)
            for suffix in ("業種", "騰落率")
        ] + ["米国セクター取得元"]
        rows = [headers, ["2026/10/13"], ["2026/10/14", "既存のランキング"]]
        updates = make_plan(rows, market)
        self.assertEqual(len(updates), 21)
        self.assertTrue(all(x["date"] == "2026-10-13" for x in updates))
        self.assertEqual(sum(x["header"].endswith("騰落率") for x in updates), 10)
        self.assertEqual(sum(x["header"].endswith("業種") for x in updates), 10)
        self.assertTrue(all(1 <= x["column"] <= len(headers) for x in updates))

    def test_no_weekend_or_outlier_days(self):
        markets = self.market()
        for symbol in markets:
            markets[symbol]["2026-10-17"] = .01
        self.assertNotIn("2026-10-17", complete_market_days(markets))
        markets["XLU"]["2026-10-14"] = 1.0
        self.assertNotIn("2026-10-14", complete_market_days(markets))

    def test_nonmatching_trading_day_cannot_backfill(self):
        market = complete_market_days(self.market())
        headers = ["日付"] + [
            f"米国セクター{direction}{i}{suffix}"
            for direction in ("上昇", "下落")
            for i in range(1, 6)
            for suffix in ("業種", "騰落率")
        ]
        self.assertEqual(make_plan([headers, ["2026/10/15"]], market), [])


if __name__ == "__main__":
    unittest.main()
