#!/usr/bin/env python3
"""Regression tests: session-date isolation and fetch-vs-persistence failures."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fetch_sector_performance as sector
import fetch_nikkei_contributions as nikkei


class CloseSheetSyncIntegrityTests(unittest.TestCase):
    @staticmethod
    def market(date: str, *, status: str = "verified", freshness: str = "fresh") -> dict:
        def rows(side: str) -> list[dict]:
            return [
                {"name": f"{side}-{i}", "change": f"+{i}.00%", "asOf": date}
                for i in range(1, 6)
            ]
        return {
            "status": status,
            "freshness": freshness,
            "asOf": date,
            "gainers": rows("gain"),
            "losers": rows("loss"),
        }

    def test_us_and_japan_get_distinct_trading_dates(self) -> None:
        payload = {
            "generatedAt": "2026-10-17T07:00:00+09:00",
            "markets": {
                "us": self.market("2026-10-16"),
                "japan": self.market("2026-10-15"),
            },
        }
        planned = sector.plan_sector_date_updates(payload)
        self.assertEqual([date for date, _ in planned], ["2026-10-16", "2026-10-15"])
        self.assertIn("米国セクター上昇1業種", planned[0][1])
        self.assertNotIn("東京業種上昇1業種", planned[0][1])
        self.assertIn("東京業種上昇1業種", planned[1][1])
        self.assertNotIn("米国セクター上昇1業種", planned[1][1])

    def test_unavailable_market_cannot_erase_existing_rows(self) -> None:
        payload = {
            "markets": {
                "us": self.market("2026-10-16", status="unavailable", freshness="unavailable"),
                "japan": self.market("2026-10-16"),
            },
        }
        updates = sector.plan_sector_date_updates(payload)
        self.assertEqual(len(updates), 1)
        self.assertIn("東京業種上昇1業種", updates[0][1])

    def test_mixed_date_items_are_rejected(self) -> None:
        bad = self.market("2026-10-16")
        bad["gainers"][0]["asOf"] = "2026-10-15"
        self.assertEqual(
            sector.plan_sector_date_updates({"markets": {"us": bad}}),
            [],
        )

    def test_nikkei_sheet_403_does_not_relabel_fetched_data(self) -> None:
        raw = {
            "dataDate": "2026-10-16",
            "asOf": "2026-10-16",
            "updatedAt": "2026-10-16T16:30:00+09:00",
            "generatedAt": "2026-10-16T16:30:00+09:00",
            "sourceAt": {"top": "2026-10-16T15:30:00+09:00"},
            "source": {"name": "Kabutan"},
            "top": [{"code": "8035", "contribution": "+134.00"}],
            "bottom": [{"code": "9983", "contribution": "-66.34"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nikkei.json"
            with (
                patch.object(nikkei, "OUTPUT_PATH", path),
                patch.object(nikkei, "load_json", return_value={}),
                patch.object(nikkei, "build_payload", return_value=raw),
                patch.object(nikkei, "merge_into_stocks", return_value=None),
                patch.object(nikkei, "sync_google_sheets", side_effect=RuntimeError("APIError [403]: permission")),
            ):
                self.assertEqual(nikkei.main(), 0)
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(value["status"], "verified")
            self.assertEqual(value["asOf"], "2026-10-16")
            self.assertEqual(value["top"][0]["code"], "8035")
            self.assertEqual(value["sheetSync"]["status"], "FAILED")
            self.assertIn("403", value["sheetSync"]["error"])


if __name__ == "__main__":
    unittest.main()
