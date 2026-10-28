import unittest

from scripts.report_source_contract import heading


class NumberedJapaneseHeadingTests(unittest.TestCase):
    def test_fullwidth_pipe_numbered_heading_is_recognized(self):
        self.assertEqual(
            heading("01｜今日の相場テーマ・総合判断"),
            "今日の相場テーマ・総合判断",
        )

    def test_numbered_heading_variants_remain_supported(self):
        self.assertEqual(heading("2. 結論"), "結論")
        self.assertEqual(heading("3）重要ニュース"), "重要ニュース")

    def test_unmarked_prose_is_not_a_heading(self):
        self.assertEqual(heading("今日はAI株が相場を主導した。"), "")


if __name__ == "__main__":
    unittest.main()
