import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from check_morning_quarantine import expected_quarantine

class Cases(unittest.TestCase):
    def setUp(self):
        self.report=[{"date":"2026-10-12","time":"08:00","report_status":"RECONSTRUCTED_UNVERIFIED"}]
        self.qa={"ready":False,"reportDate":"2026-10-12","reportSlot":"08:00","historicalMode":True,"blockingReasons":["28 items missing"]}
    def test_known_historical(self):
        self.assertTrue(expected_quarantine(self.report,self.qa,"2026-10-12"))
    def test_new_unverified_is_blocked(self):
        self.assertFalse(expected_quarantine(self.report,{**self.qa,"historicalMode":False},"2026-10-12"))
    def test_actual_qa_regression_is_blocked(self):
        reports=[{**self.report[0],"report_status":"DOC_READBACK_PASS"}]
        self.assertFalse(expected_quarantine(reports,self.qa,"2026-10-12"))
    def test_pass_cannot_be_quarantined(self):
        self.assertFalse(expected_quarantine(self.report,{**self.qa,"ready":True},"2026-10-12"))
    def test_different_date_is_blocked(self):
        self.assertFalse(expected_quarantine(self.report,self.qa,"2026-10-13"))
    def test_duplicate_report_is_blocked(self):
        self.assertFalse(expected_quarantine(self.report*2,self.qa,"2026-10-12"))
    def test_no_reasons_is_blocked(self):
        self.assertFalse(expected_quarantine(self.report,{**self.qa,"blockingReasons":[]},"2026-10-12"))

if __name__=="__main__":
    unittest.main()
