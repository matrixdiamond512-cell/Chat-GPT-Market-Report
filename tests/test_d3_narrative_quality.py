"""Narrative QA fixtures are synthetic. No real reports are published."""
import json
import unittest
from pathlib import Path
from scripts.reporting.context import ReportContext
from scripts.reporting.snapshot import MarketDataSnapshot
from scripts.reporting.d3_narrative_quality import check_narrative_quality,expected_title

ROOT=Path(__file__).resolve().parents[1]


def fixture():
    ctx=ReportContext.create("2026-10-14","21:00","2026-10-14T21:00:00+09:00",mode="historical")
    payload=json.loads((ROOT/"data/market/history/2026-10-14_21-00.json").read_text(encoding="utf-8"))
    snap=MarketDataSnapshot.from_acquisition(ctx,payload)
    title=expected_title(ctx)
    sections=[
        "今日の相場テーマ","前回からの変化","主要市場データ",
        "重要ニュース","クロスアセット資金フロー","需給・ポジション",
        "重要イベント","個別市場見通し","シナリオ","リスク管理",
        "材料と値動きの整合性","今日の主導市場",
        "シナリオが崩れる条件","次の時間帯への引き継ぎ","結論"
    ]
    report=title+"\n\n"+"\n\n".join(k+"\n"+"検証専用のサンプル文章です。正式な市場レポートではありません。"*14 for k in sections)
    return ctx,snap,title,report


class TestNarrativeQuality(unittest.TestCase):
    def test_good_anchored_fixture_passes(self):
        ctx,snap,title,body=fixture()
        result=check_narrative_quality(ctx,snap,title,body)
        self.assertEqual(result.status,"PASS",result.issues)
        self.assertFalse(result.publishable)

    def test_actual_generation_wrong_weekday_is_blocked(self):
        ctx,snap,title,body=fixture()
        body=body.replace("（水）","（木）",1)
        result=check_narrative_quality(ctx,snap,title,body)
        self.assertIn("EXACT_TITLE_OR_WEEKDAY_MISMATCH",result.issues)

    def test_opposite_gold_wti_together_claim_is_blocked(self):
        ctx,snap,title,body=fixture()
        changed=body.replace("今日の相場テーマ\n","今日の相場テーマ\n本日の焦点は、金と原油の強含みが同時進行。\n",1)
        x=check_narrative_quality(ctx,snap,title,changed)
        self.assertIn("OBSERVED_DIRECTION_CONTRADICTION:今日の相場テーマ:金:DOWN!=UP",x.issues)

    def test_correct_actual_gold_down_crude_up_passes(self):
        ctx,snap,title,body=fixture()
        body=body.replace("前回からの変化\n","前回からの変化\n金は下落、原油は上昇しました。\n",1)
        self.assertEqual(check_narrative_quality(ctx,snap,title,body).status,"PASS")

    def test_user_required_sections_and_handoff_block(self):
        ctx,snap,title,body=fixture()
        for missing in ["今日の主導市場","材料と値動きの整合性","次の時間帯への引き継ぎ"]:
            modified=body.replace(missing+"\n","除外した項目\n",1)
            result=check_narrative_quality(ctx,snap,title,modified)
            self.assertEqual(result.status,"BLOCKED")
            if missing=="次の時間帯への引き継ぎ":
                self.assertIn("SESSION_HANDOFF_MISSING",result.issues)
            else:
                self.assertIn("REQUIRED_USER_SOP_SECTION_MISSING:"+missing,result.issues)


if __name__=="__main__":
    unittest.main()
