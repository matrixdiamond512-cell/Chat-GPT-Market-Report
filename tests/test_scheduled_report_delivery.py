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

    def observation(self, **changes):
        run = {"scheduled_for":"2026-10-13T08:00:00+09:00",
               "started_at":"2026-10-13T07:55:04+09:00",
               "completed_at":"2026-10-13T07:55:16+09:00", "status":"completed",
               "chatBody":"NOT_RUN", "DocsSave":"NOT_RUN"}
        run.update(changes)
        return module.observe_run(self.root, "2026-10-13", "08:00", run,
                                  module.datetime.fromisoformat("2026-10-13T08:45:00+09:00"))

    def test_completed_early_is_not_delivery_even_with_canonical(self):
        result = self.observation()
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["startOffsetSeconds"], -296)
        self.assertEqual(result["continuation"], "BLOCKED_PLATFORM_CAPABILITY")
        self.assertIn("DocsSave", result["unverifiedStages"])

    def test_cross_slot_preserves_target_and_missing_png(self):
        result = self.observation(completed_at="2026-10-13T08:01:00+09:00",
                                  chatBody="PASS", DocsSave="PASS", DocsReadback="PASS",
                                  sourceBundle="PASS", image="NOT_RUN")
        self.assertEqual(result["reportId"], "2026-10-13_08-00")
        self.assertEqual(result["unverifiedStages"], ["image"])
        self.assertEqual(result["status"], "FAIL")

    def test_complete_observations_still_require_canonical(self):
        (self.root / "reports/2026-10-13_08-00.json").unlink()
        result = self.observation(completed_at="2026-10-13T08:01:00+09:00",
                                  **dict.fromkeys(("chatBody","image","DocsSave","DocsReadback","sourceBundle"),"PASS"))
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("Missing published canonical", result["publication"]["reason"])

    def test_wrong_slot_observation_rejected(self):
        with self.assertRaisesRegex(ValueError, "slot"):
            self.observation(scheduled_for="2026-10-13T12:00:00+09:00")

    def test_naive_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError, "Timezone"):
            self.observation(started_at="2026-10-13T07:55:04")


if __name__ == "__main__":
    unittest.main()
