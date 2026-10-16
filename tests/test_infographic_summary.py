import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from reporting.infographic import ValidationFailure
from reporting.infographic_summary import (build_summary, build_visual_encoding, render_summary_html,
                                           source_line_spans, validate_scenario_contract, validate_summary)


def synthetic_input():
    headings = ["総合判断", "今日の焦点", "相場テーマ", "重要条件", "NY時系列", "NY指数",
                "市場データ", "金利・評価", "資金フロー", "ニュース", "需給", "シナリオ",
                "6市場見通し", "引き継ぎ", "イベント", "結論"]
    lines = ["マーケットレポート｜2026/10/13（火）08:00"]
    claims = []
    kinds = {1:"judgment",2:"focus",3:"flow",4:"risk",5:"timeline",6:"market",7:"market",
             8:"metric",9:"flow",10:"news",11:"risk",12:"scenario",13:"outlook",
             14:"handoff",15:"event",16:"conclusion"}
    for number, heading in enumerate(headings, 1):
        lines.append(f"{number}．{heading}")
        if number == 12:
            scenarios = [
                ("main_scenario", "メインシナリオ", "原油93台・ドル高", "先物安で寄り弱含み", "AI半導体主導で下落"),
                ("alternative_scenario", "代替シナリオ", "原油92割れ・Nasdaq反発", "買い戻し進行", "先物68,800〜69,000円へ"),
                ("invalidation_trigger", "崩れる条件", "原油95超・先物68,000円割れ", "弱気見方を見直す", "下落加速リスク"),
            ]
            for role, label, condition, development, market_impact in scenarios:
                value = f"{label}：条件 {condition}。展開 {development}。市場影響 {market_impact}。"
                lines.append(value)
                scenario_role = role
                field_source_anchors = {
                    "condition": [condition],
                    "development": [development],
                    "market_impact": [market_impact],
                }
                claims.append({"id":f"p12-{role}","panel":12,"kind":"scenario","label":label,
                               "text":value,"scenario_role":scenario_role,"roles":[scenario_role],
                               "condition":condition,
                               "development":development,"market_impact":market_impact,
                               "source_anchors":[value],"field_source_anchors":field_source_anchors})
            continue
        value = f"原文パネル{number:02d}の記述"
        if number == 6:
            value = "原文NY指数51,000.25"
        lines.append(value)
        claims.append({"id":f"p{number:02d}","panel":number,"kind":kinds[number],
                       "roles":["judgment_basis"] if number == 1 else ["risk_condition"] if number == 4 else [],
                       "text":"51,000.25" if number == 6 else f"原文パネル{number:02d}の記述",
                       "source_anchors":[value if number != 6 else "51,000.25"]})
    for panel, kind in ((9,"note"),(14,"note"),(16,"note")):
        value=f"補足パネル{panel:02d}"
        lines.append(value)
        claims.append({"id":f"p{panel:02d}-note","panel":panel,"kind":kind,"text":value,"source_anchors":[value]})
    report={"date":"2026-10-13","time":"08:00","title":lines[0],"fullText":"\n".join(lines),
            "report_status":"TEST_ONLY"}
    return report,{"human_review":"PENDING","claims":claims}


class InfographicSummaryTests(unittest.TestCase):
    def setUp(self):
        self.report,self.authoring=synthetic_input()
        self.view=build_summary(self.report,self.authoring)

    def test_summary_maps_all_sixteen_panels_to_exact_unicode_source_spans(self):
        result=validate_summary(self.report,self.view)
        self.assertEqual(result["panel_count"],16)
        self.assertEqual(result["human_semantic_review"],"PENDING")
        self.assertFalse(result["publish_allowed"])
        for claim in self.view["claims"]:
            for ref in claim["source_refs"]:
                self.assertEqual(self.report["fullText"][ref["start"]:ref["end"]],ref["excerpt"])

    def test_displayed_number_must_exist_in_its_source_span(self):
        changed=copy.deepcopy(self.view)
        next(claim for claim in changed["claims"] if claim["id"]=="p06")["text"]="50,000.25"
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_NUMERIC_TOKEN_NOT_IN_SOURCE"):
            validate_summary(self.report,changed)

    def test_direction_word_must_exist_in_cited_source_span(self):
        report,authoring=synthetic_input()
        authoring["claims"][0]["text"]="リスクが上昇"
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_DIRECTION_TERM_NOT_IN_SOURCE"):
            build_summary(report,authoring)

    def test_numeric_units_must_match_the_cited_source(self):
        changed=copy.deepcopy(self.view)
        claim=next(claim for claim in changed["claims"] if claim["id"]=="p06")
        claim["text"]="51,000.25円"
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_NUMERIC_UNIT_NOT_IN_SOURCE"):
            validate_summary(self.report,changed)

    def test_source_line_number_tracks_actual_lines_including_blank_lines(self):
        report,authoring=synthetic_input()
        report["fullText"] = report["fullText"].replace("1．総合判断", "\n1．総合判断", 1)
        changed=build_summary(report,authoring)
        ref=changed["claims"][0]["source_refs"][0]
        self.assertEqual(ref["line"], 4)
        span=next(span for span in source_line_spans(report["fullText"]) if span["line"]==ref["line"])
        self.assertEqual(report["fullText"][span["start"]:span["end"]],span["text"])

    def test_critical_judgment_basis_and_risk_condition_must_be_present(self):
        changed=copy.deepcopy(self.view)
        for claim in changed["claims"]:
            claim["roles"]=[role for role in claim.get("roles",[]) if role!="risk_condition"]
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_CRITICAL_ROLES_MISSING"):
            validate_summary(self.report,changed)

    def test_critical_roles_must_be_assigned_to_their_designated_panels(self):
        changed=copy.deepcopy(self.view)
        risk=next(claim for claim in changed["claims"] if claim["panel"]==4)
        risk["roles"].remove("risk_condition")
        wrong=next(claim for claim in changed["claims"] if claim["panel"]==5)
        wrong["roles"].append("risk_condition")
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_CRITICAL_ROLES_MISSING"):
            validate_summary(self.report,changed)

    def test_panel12_requires_three_distinct_source_bound_scenario_roles(self):
        result=validate_summary(self.report,self.view)
        self.assertEqual(set(result["scenario_roles"]),{"main_scenario","alternative_scenario","invalidation_trigger"})
        self.assertEqual(len([c for c in self.view["claims"] if c["panel"]==12]),3)

    def test_panel12_missing_break_condition_fails_closed(self):
        changed=copy.deepcopy(self.view)
        changed["claims"]=[c for c in changed["claims"] if c.get("scenario_role")!="invalidation_trigger"]
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_REQUIRED_SCENARIO_ROLES_MISSING"):
            validate_summary(self.report,changed)

    def test_panel12_requires_condition_development_and_market_impact(self):
        changed=copy.deepcopy(self.view)
        next(c for c in changed["claims"] if c.get("scenario_role")=="main_scenario")["market_impact"]=""
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_SCENARIO_FIELDS_MISSING"):
            validate_summary(self.report,changed)

    def test_panel12_rejects_unreferenced_scenario_threshold(self):
        changed=copy.deepcopy(self.view)
        next(c for c in changed["claims"] if c.get("scenario_role")=="invalidation_trigger")["condition"]="原油99ドル超"
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_SCENARIO_FIELD_UNIT_NOT_IN_SOURCE"):
            validate_summary(self.report,changed)

    def test_panel12_main_and_alternative_must_have_different_branches(self):
        changed=copy.deepcopy(self.view)
        main=next(c for c in changed["claims"] if c.get("scenario_role")=="main_scenario")
        alternative=next(c for c in changed["claims"] if c.get("scenario_role")=="alternative_scenario")
        alternative["development"]=main["development"]
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_SCENARIO_BRANCHES_NOT_DISTINGUISHED"):
            validate_summary(self.report,changed)

    def test_panel12_each_field_has_an_exact_independent_source_span(self):
        for claim in (c for c in self.view["claims"] if c["panel"]==12):
            for field in ("condition", "development", "market_impact"):
                refs=claim["field_source_refs"][field]
                self.assertTrue(refs)
                self.assertEqual(len(refs),1)
                ref=refs[0]
                self.assertEqual(ref["excerpt"],claim[field])
                self.assertEqual(self.report["fullText"][ref["start"]:ref["end"]],claim[field])

    def test_panel12_missing_field_source_span_fails_closed(self):
        changed=copy.deepcopy(self.view)
        claim=next(c for c in changed["claims"] if c.get("scenario_role")=="main_scenario")
        claim["field_source_refs"]["development"]=[]
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_SOURCE_PROVENANCE_MISSING"):
            validate_summary(self.report,changed)

    def test_panel12_scenario_role_must_be_in_critical_role_contract(self):
        changed=copy.deepcopy(self.view)
        claim=next(c for c in changed["claims"] if c.get("scenario_role")=="alternative_scenario")
        claim["roles"]=[]
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_SCENARIO_CRITICAL_ROLE_MISSING"):
            validate_summary(self.report,changed)

    def test_panel12_contract_is_reusable_without_enabling_other_slot_rendering(self):
        self.report["time"]="12:00"
        result=validate_scenario_contract(self.report["fullText"],self.view["claims"])
        self.assertEqual(result["status"],"PASS")
        self.assertEqual(set(result["roles"]),{"main_scenario","alternative_scenario","invalidation_trigger"})
        self.assertEqual(result["human_semantic_review"],"PENDING")

    def test_panel12_html_has_three_named_independent_regions(self):
        reference=ROOT/"validation/formal-html-svg-0800-pc-readable-r50c-bottom-row-legibility/08-00-formal-html-svg.png"
        layout=json.loads((ROOT/"templates/infographic/approved/layout.json").read_text(encoding="utf-8"))
        with patch("reporting.infographic_summary.layout_config",return_value=layout):
            html,_=render_summary_html(self.report,self.view,reference)
        panel=html.split('data-card="12"',1)[1].split('</section>',1)[0]
        self.assertIn("シナリオ分析",panel)
        for label in ("メインシナリオ","代替シナリオ","崩れる条件"):
            self.assertEqual(panel.count(label),1)
        self.assertEqual(panel.count('class="scenario-field"'),9)

    def test_every_approved_panel_must_have_a_summary_item(self):
        changed=copy.deepcopy(self.view)
        changed["claims"]=[claim for claim in changed["claims"] if claim["panel"]!=5]
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_REQUIRED_PANELS_MISSING"):
            validate_summary(self.report,changed)

    def test_visual_encoding_is_a_separate_fixed_template_stage(self):
        report,authoring=synthetic_input()
        summary=build_summary(report,authoring)
        encoding=build_visual_encoding(summary)
        self.assertEqual(encoding["artifact_type"],"PILLOW_VISUAL_ENCODING_SPEC")
        self.assertEqual(encoding["geometry"],"APPROVED_FIXED_16_PANEL")
        self.assertEqual(len(encoding["claims_by_panel"]),16)
        self.assertEqual(encoding["claims_by_panel"]["13"],["p13"])
        self.assertIn("09",encoding["visual_channels"])
        self.assertEqual(encoding["panel13_quotes"],[])

    def test_human_review_and_publication_cannot_be_marked_complete_by_generator(self):
        changed=copy.deepcopy(self.view)
        changed["human_review"]="APPROVED"
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_REVIEW_OR_PUBLICATION_GATE"):
            validate_summary(self.report,changed)
        changed=copy.deepcopy(self.view)
        changed["publish_allowed"]=True
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_REVIEW_OR_PUBLICATION_GATE"):
            validate_summary(self.report,changed)

    def test_source_change_invalidates_summary_hash_and_spans(self):
        changed_report=dict(self.report)
        changed_report["fullText"] += "追記"
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_SOURCE_IDENTITY_MISMATCH"):
            validate_summary(changed_report,self.view)

    def test_claimed_bodyhash_must_match_the_exact_source_body(self):
        changed_report=dict(self.report)
        changed_report["bodyHash"]="0"*64
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_REPORT_BODYHASH_MISMATCH"):
            build_summary(changed_report,self.authoring)

    def test_summary_bodyhash_cannot_drift_from_report_identity(self):
        changed=copy.deepcopy(self.view)
        changed["bodyHash"]="f"*64
        with self.assertRaisesRegex(ValidationFailure,"SUMMARY_BODYHASH_IDENTITY_MISMATCH"):
            validate_summary(self.report,changed)

    def test_report_identity_is_not_manufactured_and_formal_generation_stays_blocked(self):
        self.assertIsNone(self.view["report_id"])
        self.assertIsNone(self.view["revision"])
        self.assertIsNone(self.view["snapshot_id"])
        self.assertIsNone(self.view["bodyHash"])
        result=validate_summary(self.report,self.view)
        self.assertEqual(result["formal_generation"],"NOT_READY")


if __name__ == "__main__":
    unittest.main()
