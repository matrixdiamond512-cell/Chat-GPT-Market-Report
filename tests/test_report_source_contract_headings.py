import unittest

from scripts.report_source_contract import heading
from scripts.sync_latest_report_publication import sop_sections


class NumberedJapaneseHeadingTests(unittest.TestCase):
    def test_fullwidth_pipe_numbered_heading_is_recognized(self):
        self.assertEqual(
            heading("01｜今日の相場テーマ・総合判断"),
            "今日の相場テーマ・総合判断",
        )

    def test_numbered_heading_variants_remain_supported(self):
        self.assertEqual(heading("2. 結論"), "結論")
        self.assertEqual(heading("3）重要ニュース"), "重要ニュース")

    def test_explicit_labeled_conclusion_is_recognized(self):
        self.assertEqual(heading("結論：東京前場では半導体主導の上昇。"), "結論")

    def test_labeled_conclusion_keeps_inline_text_as_section_body(self):
        sections = sop_sections("01｜今日の相場テーマ\n相場説明\n結論：東京市場では半導体株が指数を支えた。")
        self.assertEqual(sections[-1], ("結論", "東京市場では半導体株が指数を支えた。"))

    def test_unmarked_prose_is_not_a_heading(self):
        self.assertEqual(heading("今日はAI株が相場を主導した。"), "")


if __name__ == "__main__":
    unittest.main()
