"""Offline tests of real saved market snapshot eligibility diagnostics."""
import copy
import json
import unittest
from pathlib import Path

from scripts.reporting.d3_latest_input_probe import probe_latest_market_input


ROOT = Path(__file__).resolve().parents[1]


class TestActualInputReadiness(unittest.TestCase):
    def test_invalid_inputs_always_block(self):
        for payload in (None, {}, {"generatedAt": "missing", "reportSlot": "16:00"}):
            result = probe_latest_market_input(payload)
            self.assertEqual(result["status"], "INPUT_BLOCKED")
            self.assertFalse(result["model_send_allowed"])
            self.assertFalse(result["publish_allowed"])

    def test_current_saved_snapshot_never_skips_cutoff_check(self):
        data = json.loads((ROOT / "data/market/latest.json").read_text(encoding="utf-8"))
        result = probe_latest_market_input(data)
        self.assertFalse(result["model_send_allowed"])
        self.assertFalse(result["publish_allowed"])
        self.assertIn(result["status"], ("INPUT_BLOCKED", "INPUT_READY_FOR_SAVED_SLOT_ONLY"))
        # An acquisition completed after its own reported publication slot
        # can never be treated as a valid model input for that slot.
        target = str(data["generatedAt"])[:10] + "T" + str(data["reportSlot"]) + ":00+09:00"
        if data["generatedAt"] > target:
            self.assertEqual(result["status"], "INPUT_BLOCKED")
            self.assertIn("SNAPSHOT_AFTER_SLOT", result["reason"])

    def test_forged_later_slot_is_rejected(self):
        data = json.loads((ROOT / "data/market/latest.json").read_text(encoding="utf-8"))
        changed = copy.deepcopy(data)
        changed["reportSlot"] = "08:00"
        result = probe_latest_market_input(changed)
        self.assertEqual(result["status"], "INPUT_BLOCKED")
        self.assertFalse(result["model_send_allowed"])


if __name__ == "__main__":
    unittest.main()
