import unittest
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from validate_market_reports import (
  source_backed_21_sections,source_backed_21_value,validate_report_content,
)
from reporting.timeline import TIMELINE_COLUMNS, TIMELINE_PERIODS
ROOT=Path(__file__).resolve().parents[1]
class SourceBackedTests(unittest.TestCase):
    def source(self):
        return json.loads((ROOT/"reports/2026-10-12_21-00.json").read_text(encoding="utf-8"))
    def test_authentic_source_sections_are_extracted(self):
        data=self.source()
        sections=source_backed_21_sections(data["fullText"])
        for name in ("consistency","crossAssetFlow","handover","news","positioning","riskManagement"):
            with self.subTest(name=name):
                self.assertTrue(source_backed_21_value(sections,name),name)
    def test_authentic_21h_source_passes_with_compliant_timeline_fixture(self):
        # Preserve the authentic report text; append a clearly synthetic table
        # so this test isolates the existing source-backed checks from the new
        # required timeline contract.
        data=self.source()
        rows=["1．市場時系列", "|"+"|".join(TIMELINE_COLUMNS)+"|", "|---|---|---|---|---|---|---|"]
        for index,(period,_aliases) in enumerate(TIMELINE_PERIODS["21:00"]):
            rows.append(
              f"|{period}|15:00-16:00|市場の状態を確認し、売買材料の変化を観測しました。"
              "|株価が下落し、金利低下が広がりました。|金利との連動を示し、次の時間帯も注目します。"
              f"|市場観測時刻 15:30、合成根拠 SYN-{index+1}。|次の時間帯は金利と先物の反応を確認します。|"
            )
        data["fullText"] += "\n"+"\n".join(rows)
        errors,warnings=[],[]
        validate_report_content(data,"report",True,errors,warnings)
        self.assertEqual(errors,[])
    def test_missing_real_content_still_fails(self):
        data=self.source()
        data["fullText"]="マーケットレポート｜2026/10/12（月）21:00\n21時"
        errors,warnings=[],[]
        validate_report_content(data,"report",True,errors,warnings)
        self.assertTrue(errors)
    def test_unqualified_unconfirmed_is_blocked(self):
        data=self.source()
        data["fullText"]+="\n必要情報は未確認"
        errors,warnings=[],[]
        validate_report_content(data,"report",True,errors,warnings)
        self.assertTrue(any("内部確認用語" in e for e in errors))
if __name__=="__main__":
    unittest.main()
