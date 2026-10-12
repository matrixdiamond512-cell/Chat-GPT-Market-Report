from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reporting.infographic_0800_fixtures import build_synthetic_0800_source
from reporting.infographic_0800_generation_contract import (
    generate_0800_with_contract,
    validate_0800_generation_contract,
)


class Infographic0800GenerationContractTests(unittest.TestCase):
    def test_complete_new_report_fixture_passes_generation_qa(self):
        source = build_synthetic_0800_source()
        self.assertEqual("2099-01-01_08-00", source["report_id"])
        self.assertTrue(source["synthetic_fixture"])
        result = validate_0800_generation_contract(source)
        self.assertEqual("PASS", result["status"], result["errors"])
        self.assertEqual("PRE_SAVE_AND_PRE_RENDER_08_00_GENERATION_QA", result["gate"])
        self.assertGreater(result["fact_count"], 40)
        self.assertGreater(result["numeric_count"], 10)
        self.assertFalse(result["side_effects"]["google_docs_write"])
        self.assertFalse(result["side_effects"]["png_write"])

    def test_missing_required_fact_blocks_before_renderer_and_png_write(self):
        source = build_synthetic_0800_source()
        source["sections"] = [
            {**section, "fact_ids": []} if section["section_id"] == "top_three_conditions" else section
            for section in source["sections"]
        ]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "must-not-exist.png"
            result = generate_0800_with_contract(source, output)
            self.assertEqual("BLOCKED", result["status"])
            self.assertFalse(result["renderer_called"])
            self.assertFalse(output.exists())
            self.assertIn("EXACTLY_THREE_ORDERED_TOP_CONDITIONS_REQUIRED", result["generation_qa"]["errors"])

    def test_news_field_absence_blocks_instead_of_inference(self):
        source = build_synthetic_0800_source()
        news = next(fact for fact in source["structured_facts"] if fact["section_id"] == "news_materials")
        news["fields"].pop("time")
        result = validate_0800_generation_contract(source)
        self.assertEqual("FAIL", result["status"])
        self.assertTrue(any("time" in error and "REQUIRED_FIELD" in error for error in result["errors"]))

    def test_six_market_condition_missing_blocks(self):
        source = build_synthetic_0800_source()
        market = next(fact for fact in source["structured_facts"] if fact["section_id"] == "six_market_outlook")
        market["fields"].pop("bearish_condition")
        result = validate_0800_generation_contract(source)
        self.assertEqual("FAIL", result["status"])
        self.assertTrue(any("bearish_condition" in error for error in result["errors"]))

    def test_numeric_registry_drift_blocks(self):
        source = build_synthetic_0800_source()
        source["numeric_registry"][0]["value"] = "999"
        result = validate_0800_generation_contract(source)
        self.assertEqual("FAIL", result["status"])
        self.assertIn(f"NUMERIC_REGISTRY_IDENTITY_INVALID:{source['numeric_registry'][0]['numeric_id']}", result["errors"])

    def test_body_hash_or_excerpt_drift_blocks(self):
        source = build_synthetic_0800_source()
        source["body_text"] += "改変"
        result = validate_0800_generation_contract(source)
        self.assertEqual("FAIL", result["status"])
        self.assertIn("BODY_HASH_MISMATCH", result["errors"])

    def test_complete_fixture_passes_all_six_runtime_gates_but_stays_nonproduction(self):
        source = build_synthetic_0800_source()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "complete-fixture.png"
            result = generate_0800_with_contract(source, output, draft_preview=True)
            self.assertEqual("PASS", result["status"], result.get("render_result", {}).get("errors"))
            self.assertTrue(output.is_file())
            self.assertTrue(all(status == "PASS" for status in result["required_validation_gates"].values()))
            self.assertEqual("BLOCKED", result["production_ready"])
            self.assertFalse(result["render_result"]["production_eligible"])


if __name__ == "__main__":
    unittest.main()
