"""No external services. Preserve v1 snapshots while validating v2 encoding."""
import unittest

from scripts.reporting.canonical_v2 import (
    CanonicalV2Error, canonical_v2_bytes, sha256_v2, tagged_v2,
)
from scripts.reporting.canonical_v2_golden import evidence


class TestCanonicalV2(unittest.TestCase):
    def test_decimals_never_coerce_to_json_numbers(self):
        sample = {"integral": 100.0, "integer": 100, "negative_zero": -0.0,
                  "scientific": 1e-7, "unicode": "金・ドル円🚀", "none": None}
        tagged = tagged_v2(sample)
        self.assertEqual(tagged["integral"], {"decimal_v2": "100.0"})
        self.assertEqual(tagged["integer"], 100)
        self.assertEqual(tagged["negative_zero"], {"decimal_v2": "-0.0"})
        self.assertEqual(tagged["scientific"], {"decimal_v2": "1e-07"})
        self.assertEqual(canonical_v2_bytes(sample), canonical_v2_bytes(tagged))
        self.assertEqual(sha256_v2(sample), sha256_v2(tagged))

    def test_snapshot_v1_id_immutable_and_new_digest_separate(self):
        proof, original, preserved = evidence()
        self.assertEqual(original, preserved)
        self.assertEqual(proof["snapshot"]["snapshot_id"], original)
        self.assertEqual(proof["canonicalization_version"], "report-canonical-json/v2")
        self.assertEqual(sha256_v2(proof["snapshot"]), proof["snapshot_digest_v2"])
        self.assertEqual(proof["legacy_snapshot_id"], original)
        self.assertEqual(sha256_v2(proof["context"]), proof["context_digest_v2"])
        self.assertNotEqual(original.replace("snapshot-", ""), proof["snapshot_digest_v2"])

    def test_unsafe_values_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf"),
                      2**53, -(2**53), object(), {"bad-key": 1},
                      {"test": "\uD800"}, {"decimal_v2": "1foo"},
                      {"decimal_v2": "NaN"}):
            with self.subTest(value=repr(value)):
                with self.assertRaises(CanonicalV2Error):
                    canonical_v2_bytes(value)

    def test_input_order_not_relevant_array_order_preserved(self):
        a = {"z": [{"a": 1.0}, {"a": -2.5}], "a": "日本語"}
        b = {"a": "日本語", "z": [{"a": 1.0}, {"a": -2.5}]}
        self.assertEqual(canonical_v2_bytes(a), canonical_v2_bytes(b))
        c = {"a": "日本語", "z": list(reversed(a["z"]))}
        self.assertNotEqual(canonical_v2_bytes(a), canonical_v2_bytes(c))


if __name__ == "__main__":
    unittest.main()
