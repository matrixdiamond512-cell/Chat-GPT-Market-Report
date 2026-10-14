import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "reporting"))

from report_source_contract import HEADING_ALIASES, section_bodies, validate_key_section_bodies
from sync_latest_report_publication import sop_headings, validate_report, validate_sop_body
from reporting.report import canonical_heading


class ReportHeadingRegistryTests(unittest.TestCase):
    def test_october_14_google_doc_heading_lines_are_canonicalized(self):
        morning = "6．金利・為替・クロスアセットの因果関係"
        midday = "11．主要6市場の短期見通し（条件付き）"
        evening_flow = "7．金利・為替・クロスアセット資金フロー"
        evening_handover = "14．NY時間への引き継ぎ・リスク管理"
        self.assertEqual(HEADING_ALIASES["金利・為替・クロスアセットの因果関係"], "クロスアセット資金フロー")
        self.assertEqual(HEADING_ALIASES["主要6市場の短期見通し（条件付き）"], "個別市場見通し")
        self.assertEqual(canonical_heading(morning), "クロスアセット資金フロー")
        self.assertEqual(canonical_heading(midday), "個別市場見通し")
        self.assertIn("金利・為替・クロスアセットの因果関係", sop_headings(morning))
        self.assertIn("主要6市場の短期見通し（条件付き）", sop_headings(midday))
        self.assertEqual(HEADING_ALIASES["金利・為替・クロスアセット資金フロー"], "クロスアセット資金フロー")
        self.assertEqual(HEADING_ALIASES["NY時間への引き継ぎ・リスク管理"], "引き継ぎ")
        self.assertIn("金利・為替・クロスアセット資金フロー", sop_headings(evening_flow))
        self.assertIn("NY時間への引き継ぎ・リスク管理", sop_headings(evening_handover))

    def test_actual_source_style_sections_are_required_to_have_content(self):
        source = """6．金利・為替・クロスアセットの因果関係
米10年債利回りの低下はドルの上昇圧力を和らげ、金とユーロを支えやすい。一方、原油供給リスクはインフレ懸念と金利上昇を通じて株式に逆風となる。実測資金フローとは区別する。
7．材料と値動きの整合性
確認可能な値動きと材料を照合する。
11．主要6市場の短期見通し（条件付き）
金：中立。金利低下なら支援、CPI上振れなら下落リスク。
WTI原油：中立。供給懸念は上振れ、供給増は下振れ要因。
日経225先物（大阪）：中立。重要な価格節目を維持できるか、半導体株の反発と合わせて確認する。
USD/JPY：中立。米CPI前後の金利差とドル需給の変化を確認する。
EUR/USD：中立。米金利と欧州指標による方向変化を確認する。
BTCUSD：中立。株式との相関変化と流動性の変化を確認する。
14．NY時間への引き継ぎ・リスク管理
次の米国時間に向け、金利と為替の変化を確認し、急変時はポジションを縮小する。
15．結論
条件を確認する.
"""
        sections = section_bodies(source)
        self.assertIn("クロスアセット資金フロー", sections)
        self.assertIn("個別市場見通し", sections)
        validate_key_section_bodies(source, "21:00")

    def test_prose_mentions_do_not_count_as_headings(self):
        prose = "本文で金利・為替・クロスアセットの因果関係と金利・為替・クロスアセット資金フロー、NY時間への引き継ぎ・リスク管理、主要6市場の短期見通し（条件付き）に触れる。"
        self.assertEqual(section_bodies(prose), {})
        with self.assertRaisesRegex(ValueError, "クロスアセット資金フロー"):
            validate_key_section_bodies(prose)

    def test_empty_or_insubstantial_section_body_stays_blocked(self):
        empty = "6．金利・為替・クロスアセットの因果関係\n7．次の章"
        with self.assertRaisesRegex(ValueError, "body is missing or insubstantial"):
            validate_key_section_bodies(empty)
        short = "6．金利・為替・クロスアセットの因果関係\n金利が動く。為替も動く。\n11．主要6市場の短期見通し（条件付き）"
        with self.assertRaisesRegex(ValueError, "body is missing or insubstantial"):
            validate_key_section_bodies(short)

    def test_21_slot_handover_requires_a_substantive_body_under_the_actual_heading(self):
        source = """7．金利・為替・クロスアセット資金フロー
金利低下はドルの上昇圧力を和らげる。一方、原油供給リスクは株式に逆風となる。
10．主要6市場の短期見通し
金：中立。金利低下なら支援、CPI上振れなら下落リスク。
WTI原油：中立。供給懸念は上振れ、供給増は下振れ要因。
日経225先物（大阪）：中立。重要な価格節目を確認する。
USD/JPY：中立。米金利差とドル需給を確認する。
EUR/USD：中立。米金利と欧州指標を確認する。
BTCUSD：中立。株式との相関と流動性を確認する。
14．NY時間への引き継ぎ・リスク管理
"""
        with self.assertRaisesRegex(ValueError, "引き継ぎ body is missing or insubstantial"):
            validate_key_section_bodies(source, "21:00")

    def test_sync_gate_rejects_content_words_without_required_heading(self):
        headings = ["今日の相場テーマ", "主要市場データ", "材料と値動きの整合性", "主導市場", "重要ニュース",
                    "需給・ポジション", "主要6市場の短期見通し", "シナリオ", "崩れる条件", "結論", "前回からの変化"]
        full_text = "\n".join(heading + "\n" + ("内容を確認する。 " * 20) for heading in headings)
        full_text += "\n本文 金利・為替・クロスアセットの因果関係を説明する。 " * 200
        report = {"date": "2026-10-14", "time": "08:00", "fullText": full_text}
        with self.assertRaisesRegex(SystemExit, "クロスアセット資金フロー"):
            validate_sop_body(report)

    def test_native_docs_route_does_not_skip_heading_gate(self):
        title = "マーケットレポート｜2026/10/14（水）08:00"
        labels = ["今日の相場テーマ", "主要市場データ", "材料と値動きの整合性", "主導市場", "重要ニュース",
                  "需給・ポジション", "主要6市場の短期見通し", "シナリオ", "崩れる条件", "結論", "前回からの変化"]
        full_text = title + "\n" + "\n".join(f"{n}．{label}\n内容を確認する。" for n, label in enumerate(labels, 1))
        full_text += "\n金 ゴールド WTI 原油 日経 USD/JPY EUR/USD BTC ビットコイン。" * 100
        report = {"date": "2026-10-14", "time": "08:00", "title": title,
                  "sourceDocUrl": "read-only-drive-source", "fullText": full_text}
        with self.assertRaisesRegex(SystemExit, "クロスアセット資金フロー"):
            validate_report(report)


if __name__ == "__main__":
    unittest.main()
