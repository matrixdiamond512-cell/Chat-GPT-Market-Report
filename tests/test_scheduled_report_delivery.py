import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import sys

p = Path(__file__).resolve().parents[1] / "scripts" / "verify_scheduled_report_delivery.py"
sys.path.insert(0, str(p.parent))
spec = importlib.util.spec_from_file_location("delivery", p)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "reports").mkdir()
        (self.root / "data").mkdir()
        self.report = {"date": "2026-10-13", "time": "08:00", "fullText": "Original document text"}
        self.write("reports/2026-10-13_08-00.json", self.report)
        self.write("reports.json", [self.report])
        self.write("data/latest-report.json", {"latestReport": self.report})
        self.write("data/dashboard.json", {"latestReport": self.report,
                                            "currentReportKey": "2026-10-13_08-00"})

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, obj):
        (self.root / path).write_text(json.dumps(obj), encoding="utf-8")

    def test_complete_slot(self):
        self.assertEqual(module.verify(self.root, "2026-10-13", "08:00")["status"], "PASS")

    def test_delivery_health_marks_chatgpt_conversation_as_not_implemented(self):
        result = module.verify(self.root, "2026-10-13", "08:00")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["verifiedScope"], ["canonical-report", "history-index", "dashboard-projection"])
        self.assertEqual(result["chatgptConversationDelivery"]["status"], "NOT_IMPLEMENTED")

    def test_missing_canonical_detected(self):
        with self.assertRaisesRegex(ValueError, "Missing published canonical"):
            module.verify(self.root, "2026-10-13", "12:00")

    def test_latest_stale_detected(self):
        self.report["date"] = "2026-10-12"
        self.report["time"] = "21:00"
        self.write("data/latest-report.json", {"latestReport": self.report})
        with self.assertRaisesRegex(ValueError, "behind required slot"):
            module.verify(self.root, "2026-10-13", "08:00")

    def test_index_missing_detected(self):
        self.write("reports.json", [])
        with self.assertRaisesRegex(ValueError, "history index"):
            module.verify(self.root, "2026-10-13", "08:00")


if __name__ == "__main__":
    unittest.main()
