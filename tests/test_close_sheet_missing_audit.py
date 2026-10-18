from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from audit_close_sheet_missing import audit_rows, state
from backfill_verified_close_archives import contribution_values, sector_values, plan_blank_only_updates


class AuditCloseSheetMissingTests(unittest.TestCase):
    def test_states_are_not_equated_to_verified_closes(self):
        self.assertEqual(state(""), "blank")
        self.assertEqual(state("  "), "blank")
        self.assertEqual(state("休場"), "not_applicable")
        self.assertEqual(state("対象外"), "not_applicable")
        self.assertEqual(state("取得不能（公表停止）"), "unavailable")
        self.assertEqual(state("公表待ち"), "unavailable")
        self.assertEqual(state("0"), "filled")
        self.assertEqual(state("157.89"), "filled")

    def test_core_and_extra_are_counted_independently(self):
        headers = ["日付"] + [f"H{i}" for i in range(2, 187)]
        row = [""] * 186
        row[0] = "2026/10/16"
        row[1] = "157.89"
        row[2] = "休場"
        row[3] = "公表待ち"
        row[65] = "99"
        data = audit_rows([headers, row])
        self.assertEqual(data["rows"], 1)
        self.assertEqual(data["coreBlank"], 61)
        self.assertEqual(data["extraBlank"], 120)
        self.assertEqual(data["coreUnavailable"], 1)
        self.assertEqual(data["extraUnavailable"], 0)
        self.assertEqual(data["missingByDate"][0]["coreClosed"], 1)

    def test_duplicate_date_is_rejected(self):
        headers = ["日付"] + [f"C{i}" for i in range(2, 187)]
        with self.assertRaisesRegex(ValueError, "Duplicate report date"):
            audit_rows([headers, ["2026/10/16"], ["2026-10-16"]])

    def test_truncated_schema_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "186 headers"):
            audit_rows([["日付", "price"], ["2026/10/16", "11"]])



class StockHistoryBackfillTests(unittest.TestCase):
    def test_only_verified_five_by_five_contributions(self):
        section = {
            "status": "verified", "freshness": "fresh", "asOf": "2026-09-24",
            "top": [
                {"code": f"{2000 + n}", "shortName": f"Positive{n}", "contribution": str(10.0 - n)}
                for n in range(5)
            ],
            "bottom": [
                {"code": f"{3000 + n}", "shortName": f"Negative{n}", "contribution": str(-1.0 - n)}
                for n in range(5)
            ],
            "source": {"name": "Kabutan"},
        }
        values = contribution_values(section)
        self.assertEqual(values["日経225寄与度基準日"], "2026-09-24")
        self.assertEqual(len(values), 33)
        section["top"][0]["contribution"] = "-1.0"
        self.assertEqual(contribution_values(section), {})

    def test_no_old_or_mixed_date_sector_history(self):
        item = lambda name, date: {"name": name, "change": "+1.00%", "asOf": date}
        section = {
            "status": "verified", "freshness": "fresh",
            "asOf": "2026-10-14",
            "gainers": [item(f"up{i}", "2026-10-14") for i in range(5)],
            "losers": [item(f"down{i}", "2026-10-14") for i in range(5)],
        }
        date, values = sector_values(section, market="japan")
        self.assertEqual(date, "2026-10-14")
        self.assertEqual(values["東京業種下落1業種"], "down0")
        section["gainers"][2]["asOf"] = "2026-10-13"
        self.assertEqual(sector_values(section, market="japan"), (None, {}))
        section["gainers"][2]["asOf"] = "2026-10-14"
        section["status"] = "unavailable"
        self.assertEqual(sector_values(section, market="japan"), (None, {}))

    def test_backfill_only_blank_matching_date(self):
        headers = ["日付", "日経225寄与度上位1コード", "日経225寄与度上位1銘柄"]
        existing = [
            headers,
            ["2026/09/24", "6857", ""],
            ["2026/09/23", "", ""],
        ]
        candidates = {
            ("contributions", "2026-09-24"): {
                "sourcePath": "data/history/stocks/2026-09-24.json",
                "values": {"日経225寄与度上位1コード": "8035", "日経225寄与度上位1銘柄": "東エレク"},
            }
        }
        planned = plan_blank_only_updates(existing, candidates)
        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0]["row"], 2)
        self.assertEqual(planned[0]["col"], 3)
        self.assertEqual(planned[0]["value"], "東エレク")


if __name__ == "__main__":
    unittest.main()
