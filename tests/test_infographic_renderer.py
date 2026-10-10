from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reporting.infographic_fixtures import build_synthetic_fixture
from reporting.infographic_renderer import (
    SLOT_LABELS, TEMPLATE_CONFIG, InfographicRenderError, render_infographic,
    validate_source, verify_no_legacy_status_text,
)


class FormalInfographicRendererTests(unittest.TestCase):
    def test_non_morning_synthetic_slots_render_one_page_with_complete_qa(self):
        for slot in ("12:00", "16:00", "21:00"):
            with self.subTest(slot=slot):
                source = build_synthetic_fixture(slot)
                result = render_infographic(source)
                self.assertEqual("READY", result["status"], result.get("errors"))
                self.assertEqual("SYNTHETIC_FORMAL_LAYOUT_FIXTURE", result["artifact_type"])
                self.assertEqual("UNCHANGED", result["report_status"])
                self.assertEqual(16, len(result["layout"]["cards"]))
                self.assertEqual(1, result["layout"]["pages"])
                self.assertEqual(6, len(result["numeric_checks"]))
                self.assertTrue(all(item["status"] == "PASS" for item in result["numeric_checks"]))
                self.assertEqual([], result["missing_fact_ids"])
                self.assertEqual("PASS", result["visual_qa"]["status"])
                self.assertGreaterEqual(result["visual_qa"]["effective_body_font_px"], 12)
                self.assertGreaterEqual(result["visual_qa"]["effective_heading_font_px"], 14)
                self.assertGreaterEqual(result["quality_score"]["total"], 24)
                self.assertTrue(result["image_bytes"].startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertEqual(64, len(result["image_sha256"]))

    def test_template_section_labels_and_order_match_slot_contract(self):
        expected = {
            "08:00": "主要市場の前営業日終値",
            "12:00": "08:00からの変化",
            "16:00": "東京市場サマリー",
            "21:00": "現在の市場サマリー",
        }
        for slot, label in expected.items():
            with self.subTest(slot=slot):
                template = TEMPLATE_CONFIG["templates"][slot]
                source = build_synthetic_fixture(slot)
                if slot == "08:00":
                    from reporting.infographic_0800_fixed import CONFIG
                    self.assertEqual(17, len(source["sections"]))
                    self.assertEqual([item["id"] for item in CONFIG["sections"]],
                                     [item["section_id"] for item in source["sections"]])
                else:
                    self.assertEqual(16, len(template["sections"]))
                    self.assertEqual(label, template["sections"][0][1])
                    self.assertEqual([item[0] for item in template["sections"]],
                                     [item["section_id"] for item in source["sections"]])

    def test_numeric_registry_matches_draw_call_text_exactly(self):
        result = render_infographic(build_synthetic_fixture("12:00"))
        for entry in result["numeric_checks"]:
            self.assertEqual(entry["source_excerpt"], entry["draw_call_text"])
            self.assertIn(entry["value"], entry["draw_call_text"])
            self.assertIn(entry["unit"], entry["draw_call_text"])
            self.assertIn(entry["as_of"], entry["draw_call_text"])

    def test_source_body_hash_mismatch_blocks_before_rendering(self):
        source = build_synthetic_fixture("12:00")
        source["full_text"] += "\nchanged"
        with self.assertRaisesRegex(InfographicRenderError, "SOURCE_BODY_HASH_MISMATCH"):
            validate_source(source)

    def test_structured_source_required_fields_are_enforced_without_jsonschema(self):
        source = build_synthetic_fixture("12:00")
        source.pop("market_theme")
        with self.assertRaisesRegex(InfographicRenderError, "STRUCTURED_SOURCE_SCHEMA_FIELDS_MISSING:market_theme"):
            validate_source(source)

    def test_missing_critical_fact_blocks_before_png(self):
        source = build_synthetic_fixture("16:00")
        source["sections"][0]["fact_ids"] = []
        with self.assertRaisesRegex(InfographicRenderError, "SECTION_FACTS_MISSING"):
            render_infographic(source)

    def test_market_numeric_drift_is_rejected_against_source_excerpt(self):
        source = build_synthetic_fixture("21:00")
        source["numeric_registry"][0]["value"] = "999.99"
        with self.assertRaisesRegex(InfographicRenderError, "NUMERIC_SOURCE_PROVENANCE_MISSING"):
            validate_source(source)

    def test_foreign_slot_identity_is_rejected(self):
        source = build_synthetic_fixture("08:00")
        source["report_datetime"] = "2026-10-09T12:00:00+09:00"
        with self.assertRaisesRegex(InfographicRenderError, "REPORT_ID_MISMATCH"):
            validate_source(source)

    def test_debug_and_approval_state_phrases_are_not_emitted(self):
        for slot in ("12:00", "16:00", "21:00"):
            result = render_infographic(build_synthetic_fixture(slot))
            for binding in result["render_bindings"]:
                self.assertTrue(verify_no_legacy_status_text(binding["draw_call_text"]))
            self.assertEqual("SYNTHETIC_FORMAL_LAYOUT_FIXTURE", result["artifact_type"])
            self.assertEqual("NOT_RUN", result["optional_qa"]["vision"])

    def test_0800_uses_dedicated_fixed_single_sheet_template(self):
        result = render_infographic(build_synthetic_fixture("08:00"))
        self.assertEqual("READY", result["status"], result.get("errors"))
        self.assertEqual(1, result["layout"]["pages"])
        self.assertEqual(16, len(result["layout"]["cards"]))
        self.assertEqual("08:00_FIXED_SINGLE_SHEET", result["layout"]["template_mode"])
        self.assertTrue(result["image_bytes"].startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(64, len(result["image_sha256"]))
        self.assertFalse(result["production_eligible"])
        self.assertEqual("SYNTHETIC_FORMAL_LAYOUT_FIXTURE", result["artifact_type"])

    def test_0800_generic_auto_layout_path_is_forbidden(self):
        with self.assertRaisesRegex(InfographicRenderError, "0800_GENERIC_AUTO_LAYOUT_FORBIDDEN"):
            render_infographic(build_synthetic_fixture("08:00"), template_mode="GENERIC_AUTO_LAYOUT")

    def test_0800_never_paginates_and_has_fixed_geometry_contract(self):
        from reporting.infographic_0800_fixed import CONFIG, FIXED_LAYOUT, FIXED_ZONES
        result = render_infographic(build_synthetic_fixture("08:00"))
        cards = result["layout"]["cards"]
        expected_sections = [
            "overall_judgment", "attention_points", "market_theme", "material_market_relationship",
            "ny_timeline", "ny_indices", "major_market_data", "ny_market_points",
            "cross_asset_flow", "positioning", "six_market_outlook", "latest_news",
            "scenario_analysis", "handoff", "top_three_conditions", "final_summary",
        ]
        self.assertEqual(expected_sections, [card["section_id"] for card in cards])
        self.assertFalse(result["layout"]["pagination_enabled"])
        self.assertTrue(all(card["page"] == 1 and card["fixed_zone"] for card in cards))
        self.assertEqual(16, len(cards))
        self.assertTrue(all({"x", "y", "width", "height", "row_group", "render_mode"} <= set(card)
                            for card in cards))
        for card, zone in zip(cards, FIXED_ZONES):
            self.assertEqual((zone["x"], zone["y"], zone["width"], zone["height"]),
                             (card["x"], card["y"], card["width"], card["height"]))
            self.assertEqual(zone["row_group"], card["row_group"])
            self.assertEqual("PASS", result["visual_reference"]["status"])
        self.assertEqual(6, next(card["market_count"] for card in cards
                                 if card["source_section_id"] == "six_market_outlook"))
        self.assertEqual("six_market_table", next(card["render_mode"] for card in cards
                                               if card["source_section_id"] == "six_market_outlook"))
        self.assertEqual("top", next(card["row_group"] for card in cards
                                      if card["source_section_id"] == "ny_timeline"))
        self.assertEqual(16, len(FIXED_ZONES))
        self.assertFalse(FIXED_LAYOUT["pagination_enabled"])
        self.assertTrue(all(zone["fixed_zone"] and zone["page"] == 1 for zone in CONFIG["fixed_layout"]["zones"]))

    def test_0800_native_render_precedes_768px_check(self):
        result = render_infographic(build_synthetic_fixture("08:00"))
        qa = result["visual_qa"]
        self.assertEqual("PASS", qa["status"], qa)
        self.assertGreater(qa["native_width_px"], 768)
        self.assertEqual(768, qa["readability_test_width_px"])
        self.assertTrue(qa["render_native_before_downscale"])

    def test_current_portal_keeps_debug_preview_out_of_formal_lane(self):
        portal = (Path(__file__).resolve().parents[1] / "assets/js/report-core-v3.js").read_text(encoding="utf-8")
        self.assertIn('image.artifact_type !== "FORMAL_INFOGRAPHIC" || image.debug_preview === true', portal)
        self.assertIn('report.infographic_status !== "READY"', portal)

    def test_render_bindings_preserve_all_required_fact_ids(self):
        result = render_infographic(build_synthetic_fixture("12:00"))
        self.assertEqual(result["required_fact_ids"], result["rendered_fact_ids"])
        self.assertEqual([], result["missing_fact_ids"])
        self.assertEqual([], result["extra_fact_ids"])


if __name__ == "__main__":
    unittest.main()
