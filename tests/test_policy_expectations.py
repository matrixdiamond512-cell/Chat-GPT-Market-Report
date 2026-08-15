import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_rates_bonds_json as builder


class PolicyExpectationTests(unittest.TestCase):
    def stat(self, value, daily, weekly, previous=None):
        return {"value": value, "previous": previous, "changeBp": daily,
                "weekChangeBp": weekly, "date": date(2026, 8, 14)}

    def test_direction_thresholds(self):
        self.assertEqual(builder.policy_direction(-10)[0], -3)
        self.assertEqual(builder.policy_direction(-5)[0], -2)
        self.assertEqual(builder.policy_direction(3)[0], 0)
        self.assertEqual(builder.policy_direction(10)[0], 3)

    def test_policy_payload_and_spread(self):
        result = builder.build_policy_expectations(
            self.stat(4.15, -8, -12, 4.23), self.stat(4.63, -3, -6),
            self.stat(3.5, 0, 0), self.stat(3.75, 0, 0), self.stat(3.64, 0, 0),
            {"value": 48.0, "changeBp": 5.0})
        self.assertEqual(result["directionScore"], -2)
        self.assertEqual(result["us2yVsFedMidBp"], 52.5)
        self.assertIn("確率とは解釈しない", result["interpretation"])

    def test_daily_weekly_mismatch(self):
        result = builder.build_policy_expectations(
            self.stat(4.15, -5, 18), None, self.stat(3.5, 0, 0),
            self.stat(3.75, 0, 0), None, None)
        self.assertTrue(result["directionMismatch"])
        self.assertIn("方向が不一致", result["interpretation"])


if __name__ == "__main__":
    unittest.main()
