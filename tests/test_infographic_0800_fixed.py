from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reporting.infographic_0800_fixed import CONFIG, EXPECTED_IDS, render_0800_fixed, validate_0800_source
from reporting.infographic_0800_fixtures import build_synthetic_0800_source


_make_source = build_synthetic_0800_source

class Fixed0800InfographicTests(unittest.TestCase):
    def test_template_keeps_sixteen_numbered_zones_and_fixed_reference_order(self):
        self.assertEqual(17, len(CONFIG["sections"]))  # title metadata + 16 content zones
        self.assertEqual([item["id"] for item in CONFIG["sections"]], EXPECTED_IDS)
        self.assertEqual("landscape", CONFIG["canvas"]["orientation"])
        flattened = [sid for row in CONFIG["fixed_layout"]["rows"] for sid in row["section_ids"]]
        self.assertEqual(CONFIG["visual_reference_contract"]["panel_order"], flattened)
        self.assertEqual(16, len(CONFIG["fixed_layout"]["zones"]))
        self.assertEqual((1536, 1024), tuple(CONFIG["visual_reference_contract"]["canvas_dimensions_px"]))

    def test_missing_source_snapshot_blocks_without_writing_png(self):
        source = _make_source()
        source["source_snapshot_id"] = ""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "blocked.png"
            result = render_0800_fixed(source, path)
            self.assertEqual("NOT_READY", result["status"])
            self.assertIn("SOURCE_SNAPSHOT_ID_MISSING", result["validation"]["errors"])
            self.assertIsNone(result["image_bytes"])
            self.assertFalse(path.exists())

    def test_snapshot_fingerprint_is_bound_to_document_revision_and_body_hash(self):
        source = _make_source()
        self.assertEqual("PASS", validate_0800_source(source)["status"])
        source["source_snapshot_id"] = "docs-revision-sha256:tampered"
        result = validate_0800_source(source)
        self.assertEqual("NOT_READY", result["status"])
        self.assertIn("SOURCE_SNAPSHOT_IDENTITY_MISMATCH", result["errors"])

    def test_value_identity_can_pass_when_source_does_not_state_unit(self):
        source = _make_source()
        source["numeric_registry"][0]["unit"] = ""
        source["market_data_snapshot"]["numeric_registry"] = source["numeric_registry"]
        snapshot_without_hash = {key: value for key, value in source["market_data_snapshot"].items()
                                 if key != "snapshot_sha256"}
        source["market_data_snapshot"]["snapshot_sha256"] = hashlib.sha256(
            json.dumps(snapshot_without_hash, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        result = validate_0800_source(source)
        self.assertEqual("PASS", result["status"])
        item = next(entry for entry in result["numeric_checks"]
                    if entry["numeric_id"] == source["numeric_registry"][0]["numeric_id"])
        self.assertEqual("UNSPECIFIED", item["unit_status"])

    def test_reconstructed_snapshot_records_provenance_and_rejects_numeric_drift(self):
        source = _make_source(snapshot_provenance="SOURCE_RECONSTRUCTED")
        self.assertEqual("PASS", validate_0800_source(source)["market_data_snapshot"]["status"])
        self.assertEqual("SOURCE_RECONSTRUCTED", source["market_data_snapshot"]["snapshot_provenance"])
        source["market_data_snapshot"]["numeric_registry"][0]["value"] = "999"
        snapshot_payload = {key: value for key, value in source["market_data_snapshot"].items()
                            if key != "snapshot_sha256"}
        source["market_data_snapshot"]["snapshot_sha256"] = hashlib.sha256(
            json.dumps(snapshot_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        result = validate_0800_source(source)
        self.assertEqual("FAIL", result["market_data_snapshot"]["status"])
        self.assertIn("SNAPSHOT_NUMERIC_REGISTRY_MISMATCH", result["errors"])

    def test_complete_source_renders_one_fixed_sheet_independent_of_content_gate(self):
        result = render_0800_fixed(_make_source(), draft_preview=True)
        self.assertEqual("NOT_READY", result["status"], result.get("errors"))
        self.assertEqual(1, result["png_count"])
        self.assertEqual(16, len(result["layout"]["panels"]))
        self.assertEqual(CONFIG["visual_reference_contract"]["panel_order"], result["layout"]["panel_order"])
        self.assertEqual(result["required_fact_ids"], result["rendered_fact_ids"])
        self.assertEqual([], result["missing_fact_ids"])
        self.assertEqual([], result["extra_fact_ids"])
        self.assertTrue(all(item["status"] == "PASS" for item in result["numeric_checks"]))
        self.assertEqual(768, result["visual_qa"]["target_display_width_px"])
        self.assertEqual([1536, 1024], result["visual_qa"]["original_dimensions_px"])
        self.assertEqual("PASS", result["visual_reference"]["status"])
        self.assertEqual("BLOCKED", result["validation_gates"]["PRODUCTION_READY"])
        self.assertEqual("NOT_RUN", result["validation_gates"]["VISUAL_REVIEW"])
        self.assertEqual("PASS", result["visual_fidelity"]["status"])
        self.assertFalse(result["visual_fidelity"]["geometry_alone_sufficient"])
        self.assertIsNotNone(result["image_bytes"])
        self.assertEqual(64, len(result["image_sha256"]))

    def test_all_sixteen_zones_use_dedicated_visual_components_and_target_overflow_is_zero(self):
        result = render_0800_fixed(_make_source(), draft_preview=True)
        self.assertEqual(16, len(result["visual_fidelity"]["components"]))
        self.assertTrue(all(item["status"] == "PASS" for item in result["visual_fidelity"]["components"].values()))
        self.assertEqual([], [item for item in result["visual_qa"]["text_overflows"]
                              if any(f"{zone}:" in item for zone in ("ny_timeline", "news_materials", "scenario_analysis"))])

    def test_source_reconstructed_never_becomes_production_ready_from_visual_layout_pass(self):
        result = render_0800_fixed(_make_source(snapshot_provenance="SOURCE_RECONSTRUCTED"), draft_preview=True)
        self.assertEqual("PASS", result["validation_gates"]["SNAPSHOT_INTEGRITY"])
        self.assertEqual("NOT_RUN", result["validation_gates"]["VISUAL_REVIEW"])
        self.assertEqual("BLOCKED", result["validation_gates"]["PRODUCTION_READY"])
        self.assertFalse(result["production_eligible"])

    def test_attention_points_requires_five_source_items(self):
        source = _make_source()
        section = next(item for item in source["sections"] if item["section_id"] == "attention_points")
        section["fact_ids"] = section["fact_ids"][:4]
        result = validate_0800_source(source)
        self.assertEqual("NOT_READY", result["status"])
        self.assertTrue(any(item.startswith("ATTENTION_REQUIRED_FIVE_FACTS_MISSING") for item in result["errors"]))

    def test_source_gap_keeps_one_fixed_page_and_zone_visible(self):
        source = _make_source()
        source["sections"] = [
            {**section, "fact_ids": []} if section["section_id"] == "ny_timeline" else section
            for section in source["sections"]
        ]
        result = render_0800_fixed(source, draft_preview=True)
        self.assertEqual(1, result["layout"]["pages"])
        self.assertFalse(result["layout"]["pagination_enabled"])
        self.assertEqual("FAIL", result["validation_gates"]["CONTENT_COMPLETENESS"])
        self.assertEqual("PASS", result["validation_gates"]["LAYOUT_INTEGRITY"])
        timeline = next(card for card in result["layout"]["cards"]
                        if card["source_section_id"] == "ny_timeline")
        self.assertEqual("SOURCE_GAP", timeline["content_status"])

    def test_debug_preview_renders_with_missing_fields_but_never_becomes_ready(self):
        source = _make_source()
        source["source_snapshot_id"] = ""
        source["sections"] = [
            {**section, "fact_ids": []} if section["section_id"] == "top_three_conditions" else section
            for section in source["sections"]
        ]
        news = next(f for f in source["structured_facts"] if f["section_id"] == "news_materials")
        news["fields"].pop("time")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "debug-preview.png"
            result = render_0800_fixed(source, path, draft_preview=True)
            self.assertEqual("NOT_READY", result["status"])
            self.assertEqual("DEBUG_PREVIEW", result["artifact_type"])
            self.assertFalse(result["production_eligible"])
            self.assertIsNotNone(result["image_bytes"])
            self.assertTrue(path.is_file())
            self.assertEqual(1, result["png_count"])
            self.assertEqual(str(path), result["output_path"])
            self.assertEqual(64, len(result["image_sha256"]))
            self.assertTrue(any("SOURCE GAP" in binding.get("draw_call_text", "")
                                for binding in result["render_bindings"]))
            self.assertIn("SOURCE_SNAPSHOT_ID_MISSING", result["preview_missing_source_fields"])

    def test_existing_png_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "already-there.png"
            path.write_bytes(b"preserve-existing")
            before = path.read_bytes()
            result = render_0800_fixed(_make_source(), path, draft_preview=True)
            self.assertEqual("FAILED_VALIDATION", result["status"])
            self.assertIn("OUTPUT_EXISTS_REFUSE_OVERWRITE", result["errors"])
            self.assertEqual(before, path.read_bytes())

    def test_six_market_incomplete_fields_fail_closed(self):
        source = _make_source()
        market = next(f for f in source["structured_facts"] if f["section_id"] == "six_market_outlook")
        market["fields"].pop("bearish_condition")
        result = validate_0800_source(source)
        self.assertEqual("NOT_READY", result["status"])
        self.assertTrue(any("bearish_condition" in error for error in result["errors"]))

    def test_missing_news_time_or_reaction_is_not_inferred(self):
        source = _make_source()
        news = next(f for f in source["structured_facts"] if f["section_id"] == "news_materials")
        news["fields"].pop("time")
        result = validate_0800_source(source)
        self.assertEqual("NOT_READY", result["status"])
        self.assertTrue(any("NEWS_REQUIRED_SOURCE_FIELD_MISSING" in error for error in result["errors"]))

    def test_draw_call_numeric_drift_blocks_and_does_not_write_png(self):
        source = _make_source()
        source["numeric_registry"][0]["value"] = "99999"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "mismatch.png"
            result = render_0800_fixed(source, path)
            self.assertEqual("NOT_READY", result["status"])
            self.assertTrue(any("NUMERIC_IDENTITY_MISMATCH" in error for error in result["validation"]["errors"]))
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
