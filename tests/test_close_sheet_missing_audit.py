from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from audit_close_sheet_missing import audit_rows, state


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


if __name__ == "__main__":
    unittest.main()
