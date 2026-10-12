from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_morning_report_qa import ITEMS, parse_rows


def numbered_close_table(missing: str | None = None) -> str:
    lines = ["2. 前営業日終値・主要市場データ"]
    for number, label in enumerate(ITEMS, start=1):
        if label == missing:
            continue
        value = "5.23%前後" if label == "米10年債利回り" else "17.35倍" if label == "日経225予想PER" else "取得不能（検証値なし）"
        lines.extend((f"{number}. {label}", value, "—", "—", "取得不能"))
    lines.extend(("3. 昨夜のNY市場", "材料の確認。"))
    return "\n".join(lines)


class MorningReportTableParsingTests(unittest.TestCase):
    def test_arabic_numbered_28_items_are_detected_through_section_three(self):
        rows = parse_rows(numbered_close_table())
        self.assertEqual(28, len(rows))
        self.assertEqual(ITEMS, [row["label"] for row in rows])
        self.assertEqual("5.23%前後", rows[16]["value"])
        self.assertEqual("17.35倍", rows[18]["value"])

    def test_missing_instrument_is_not_counted_as_a_false_28th_row(self):
        rows = parse_rows(numbered_close_table(missing="WTI原油"))
        self.assertEqual(27, len(rows))
        self.assertNotIn("WTI原油", [row["label"] for row in rows])

    def test_circled_number_format_remains_supported(self):
        text = "2. 前営業日終値・主要市場データ\n① NYダウ\n51,000\n+10\n+0.02%\n上昇"
        rows = parse_rows(text)
        self.assertEqual(1, len(rows))
        self.assertEqual("NYダウ", rows[0]["label"])


if __name__ == "__main__":
    unittest.main()
