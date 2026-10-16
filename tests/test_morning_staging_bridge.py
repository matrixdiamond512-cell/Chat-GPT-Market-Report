"""TEST_ONLY integration of canonical report, frozen evidence and infographic gates."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from morning_fixture import formal_contract_fixture
from scripts.persist_report_slot_evidence import build_slot_evidence, canonical_bytes
from scripts.bind_morning_report_evidence import assemble
from scripts.reporting.infographic import build_spec
from scripts.reporting.infographic_summary import build_summary
from scripts.reporting.morning_layout import render_html
from reporting.infographic import ValidationFailure
from scripts.reporting.publication_evidence import verify_slot_evidence
from scripts.run_morning_infographic_staging import (
    canonical_hash, docs_readback_from_verified_import, validate_transaction,
)
from scripts.prepare_morning_infographic_inputs import prepare_inputs


def _summary_authoring(bound, view):
    by_id = {fact["id"]: fact for fact in view["facts"]}
    body = bound["fullText"]

    def unique_fact(fact_id):
        fact = by_id[fact_id]
        occurrences = sum(1 for line in body.splitlines() if fact["text"] in line)
        if occurrences == 1:
            return fact
        alternatives = [candidate for candidate in view["facts"]
                        if candidate.get("source_section") == fact.get("source_section")
                        and sum(1 for line in body.splitlines() if candidate["text"] in line) == 1]
        if not alternatives:
            raise AssertionError("fixture has no unique source anchor for " + str(fact_id))
        return max(alternatives, key=lambda candidate: len(candidate["text"]))

    claims = []

    def add(claim_id, panel, kind, fact_id, *, roles=(), label=""):
        fact = unique_fact(fact_id)
        claims.append({"id": claim_id, "panel": panel, "kind": kind,
                       "label": label, "text": fact["text"],
                       "source_anchors": [fact["text"]], "roles": list(roles)})

    add("p01", 1, "judgment", view["cards"][0]["headline"]["ref"], roles=["judgment_basis"])
    add("p02", 2, "focus", view["cards"][1]["items"][0]["ref"])
    add("p03", 3, "flow", view["cards"][2]["paragraphs"][0]["ref"])
    add("p04", 4, "risk", view["cards"][3]["items"][0]["ref"], roles=["risk_condition"])
    add("p05", 5, "timeline", view["cards"][4]["timeline"][0]["text"]["ref"])
    add("p06", 6, "market", view["cards"][5]["table"]["rows"][0][0]["ref"])
    add("p07", 7, "market", view["cards"][6]["table"]["rows"][0][0]["ref"])
    add("p08", 8, "metric", view["cards"][7]["table"]["rows"][0][0]["ref"])
    add("p09-flow", 9, "flow", view["cards"][8]["flow"]["evidence"]["ref"])
    add("p09-note", 9, "note", view["cards"][8]["flow"]["inflow"][0]["ref"])
    add("p10", 10, "news", view["cards"][9]["chains"][0]["nodes"][0]["ref"])
    add("p11", 11, "risk", view["cards"][10]["paragraphs"][0]["ref"])

    scenario_fields = {}
    scenario_map = (("main", "main_scenario"), ("upside", "alternative_scenario"),
                    ("downside", "invalidation_trigger"))
    for scenario, role in scenario_map:
        chain = next(row for row in view["cards"][11]["chains"] if row["scenario"] == scenario)
        node_ids = [node["ref"] for node in chain["nodes"]]
        claim_id = "p12-" + role
        field_anchors = {"condition": [by_id[node_ids[0]]["text"]],
                         "development": [by_id[node_ids[1]]["text"]],
                         "market_impact": [by_id[node_ids[2]]["text"]]}
        scenario_fields[role] = (claim_id, node_ids)
        claims.append({"id": claim_id, "panel": 12, "kind": "scenario",
                       "scenario_role": role, "roles": [role],
                       "label": role, "text": by_id[chain["evidence"]["ref"]]["text"],
                       "source_anchors": [by_id[chain["evidence"]["ref"]]["text"]],
                       "field_source_anchors": field_anchors,
                       "condition": field_anchors["condition"][0],
                       "development": field_anchors["development"][0],
                       "market_impact": field_anchors["market_impact"][0]})
        chain["scenario_role"] = role
        chain["summary_claim_id"] = claim_id
        chain["field_refs"] = {field: {"ref": node_id} for field, node_id in
                               zip(("condition", "development", "market_impact"), node_ids)}

    add("p13", 13, "outlook", view["cards"][12]["markets"][0]["price"]["ref"])
    add("p14-handoff", 14, "handoff", view["cards"][13]["paragraphs"][0]["ref"])
    add("p14-note", 14, "note", view["cards"][13]["paragraphs"][1]["ref"])
    add("p15", 15, "event", view["cards"][9]["paragraphs"][0]["ref"])
    add("p16-conclusion", 16, "conclusion", view["cards"][15]["conclusion"]["ref"])
    add("p16-note", 16, "note", view["cards"][15]["validation"][0]["ref"])
    return {"human_review": "PENDING", "claims": claims}, scenario_fields


class MorningStagingBridgeTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parents[1] / ".test-tmp-0800"
        temp_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temp_root)
        self.root = Path(self.temp.name)
        initial, self.view, _ = formal_contract_fixture()
        snapshot = initial["snapshot"]
        market_rows = {}
        for market in snapshot["markets"]:
            src = market["source"][0]
            market_rows[market["instrument"]] = {
                "id": market["instrument"], "marketType": market["marketType"],
                "unit": market["priceUnit"], "value": market["priceValue"],
                "change": market["changeValue"], "changePercent": market["changePct"],
                "comparisonBasis": market["comparisonBasis"], "asOf": market["asOf"],
                "sourceId": src["id"], "sourceUrl": src["url"],
                "verificationStatus": "verified", "freshnessStatus": "fresh",
                "displayValue": market["displayText"],
            }
        payload = {"generatedAt": snapshot["captured_at"], "reportDate": "2026-10-06",
                   "reportSlot": "08:00", "overallStatus": "verified", "markets": market_rows}
        self.evidence = build_slot_evidence("2026-10-06", "08:00", payload,
                                            json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        # The canonical report deliberately has no synthetic context/snapshot
        # attachment; the bridge must bind the independently frozen source.
        self.report = {key: copy.deepcopy(value) for key, value in initial.items()
                       if key not in ("context", "snapshot", "report_id", "snapshot_id", "synthetic_fixture")}
        self.report["sourceDocument"] = {
            "id": "doc-id", "url": "https://docs.google.com/document/d/doc-id/edit"
        }
        self.report["report_status"] = "DOC_READBACK_PASS"
        evidence_path = self.root / "slot-evidence.json"
        evidence_path.write_bytes(canonical_bytes(self.evidence))
        self.receipt = verify_slot_evidence(
            self.report, evidence_path,
            {"id": "doc-id", "createdTime": "2026-10-06T08:02:00+09:00",
             "modifiedTime": "2026-10-06T08:03:00+09:00"}, "doc-revision-1")
        self.report["publicationEvidence"] = {key: self.receipt[key] for key in (
            "evidenceId", "snapshotId", "contextHash", "snapshotHash", "bodyHash", "documentRevisionId")}
        self.bound = assemble(self.report, self.evidence["context"], self.evidence["snapshot"])
        self.original_body_evidence = {
            "capturedAt": "2026-10-06T08:01:00+09:00",
            "evidence_stage": "G2_DRAFT_NOT_SAVED", "validated_gates": ["G0", "G1", "G2"],
            "date": self.report["date"], "time": self.report["time"],
            "title": self.report["title"], "report_id": self.bound["report_id"],
            "revision": self.bound["revision"], "snapshot_id": self.bound["snapshot_id"],
            "bodyHash": self.report["bodyHash"], "fullText": self.report["fullText"],
            "context": self.evidence["context"], "snapshot": self.evidence["snapshot"],
        }
        self.view["report_id"] = self.bound["report_id"]
        self.view["snapshot_id"] = self.bound["snapshot_id"]
        self.view["body_hash"] = self.bound["bodyHash"]
        self.spec = build_spec(self.bound)
        self.summary_authoring, self.scenario_fields = _summary_authoring(self.bound, self.view)
        self.summary = build_summary(self.bound, self.summary_authoring)
        self.view_authoring = {key: copy.deepcopy(value) for key, value in self.view.items()
                               if key not in ("facts", "report_id", "revision", "snapshot_id", "body_hash")}
        anchor_occurrences = {}
        self.view_authoring["facts"] = []
        for fact in self.view["facts"]:
            key = (fact["source_section"], fact["text"])
            occurrence = anchor_occurrences.get(key, 0)
            anchor_occurrences[key] = occurrence + 1
            self.view_authoring["facts"].append(
                {name: value for name, value in fact.items()
                 if name not in ("start", "end", "text")}
                | {"source_anchor": fact["text"],
                   "source_anchor_occurrence": occurrence})
        self.docs_readback = docs_readback_from_verified_import(self.report, self.receipt)
        self.scenario_review = {
            "status": "PASS", "reviewer": "TEST_ONLY", "reviewed_at": "2026-10-06T09:00:00+09:00",
            "report_id": self.bound["report_id"], "revision": self.bound["revision"],
            "bodyHash": self.bound["bodyHash"], "snapshot_id": self.bound["snapshot_id"],
            "summary_sha256": canonical_hash(self.summary),
            "roles": {role: {"condition": "PASS", "development": "PASS", "market_impact": "PASS"}
                      for role in ("main_scenario", "alternative_scenario", "invalidation_trigger")},
        }

    def tearDown(self):
        self.temp.cleanup()

    def validate(self, **overrides):
        values = {"report": self.report,
                  "evidence_bytes": canonical_bytes(self.evidence),
                  "receipt": self.receipt,
                  "docs_readback": self.docs_readback,
                  "summary": self.summary,
                  "view": self.view,
                  "spec": self.spec,
                  "scenario_review": self.scenario_review,
                  "original_body_evidence": self.original_body_evidence,
                  "report_date": "2026-10-06"}
        values.update(overrides)
        return validate_transaction(**values)

    def test_same_transaction_passes_in_test_only_mode(self):
        bound, result = self.validate()
        self.assertEqual(result["transaction"]["report_id"], "2026-10-06_08-00")
        self.assertEqual(result["transaction"]["snapshot_id"], self.receipt["snapshotId"])
        self.assertEqual(result["projection"]["status"], "PASS")
        self.assertEqual(self.scenario_review["reviewer"], "TEST_ONLY")
        html, _ = render_html(bound, self.view, fixture=False, spec=self.spec)
        for label in ("メインシナリオ", "代替シナリオ", "崩れる条件"):
            self.assertIn(label, html)

    def test_report_compiles_summary_view_and_snapshot_bound_spec(self):
        bound, summary, view, spec = prepare_inputs(
            report=self.report, evidence_bytes=canonical_bytes(self.evidence),
            receipt=self.receipt, original_body_evidence=self.original_body_evidence,
            summary_authoring=self.summary_authoring, view_authoring=self.view_authoring)
        self.assertEqual(summary["bodyHash"], bound["bodyHash"])
        self.assertEqual(view["body_hash"], bound["bodyHash"])
        self.assertEqual(spec["snapshot_id"], bound["snapshot_id"])
        self.assertEqual(summary["human_review"], "PENDING")
        self.assertEqual(validate_transaction(
            report=self.report, evidence_bytes=canonical_bytes(self.evidence),
            receipt=self.receipt, docs_readback=self.docs_readback,
            summary=summary, view=view, spec=spec,
            scenario_review=self.scenario_review,
            original_body_evidence=self.original_body_evidence,
            report_date="2026-10-06")[1]["projection"]["status"], "PASS")

    def test_changed_docs_body_fails_before_render(self):
        altered = copy.deepcopy(self.docs_readback)
        altered["fullText"] += "改変"
        with self.assertRaises(ValidationFailure) as error:
            self.validate(docs_readback=altered)
        self.assertEqual(error.exception.reason, "STAGING_DOCS_BODY_OR_IDENTITY_MISMATCH")

    def test_pre_save_body_must_match_independent_docs_readback(self):
        altered = copy.deepcopy(self.original_body_evidence)
        altered["fullText"] += "保存前本文への改変"
        with self.assertRaises(ValidationFailure) as error:
            self.validate(original_body_evidence=altered)
        self.assertEqual(error.exception.reason, "STAGING_PRE_SAVE_BODY_HASH_INVALID")

    def test_pre_save_body_hash_is_compared_to_actual_imported_docs_body(self):
        altered = copy.deepcopy(self.original_body_evidence)
        altered["fullText"] += "別本文"
        altered["bodyHash"] = hashlib.sha256(altered["fullText"].encode("utf-8")).hexdigest()
        with self.assertRaises(ValidationFailure) as error:
            self.validate(original_body_evidence=altered)
        self.assertEqual(error.exception.reason, "STAGING_ORIGINAL_BODY_DIFFERS_FROM_DOCS_READBACK")

    def test_pre_save_evidence_captured_after_docs_save_is_rejected(self):
        altered = copy.deepcopy(self.original_body_evidence)
        altered["capturedAt"] = "2026-10-06T08:04:00+09:00"
        with self.assertRaises(ValidationFailure) as error:
            self.validate(original_body_evidence=altered)
        self.assertEqual(error.exception.reason, "STAGING_PRE_SAVE_CAPTURE_ORDER_INVALID")
        with self.assertRaises(ValidationFailure) as error:
            prepare_inputs(
                report=self.report, evidence_bytes=canonical_bytes(self.evidence),
                receipt=self.receipt, original_body_evidence=altered,
                summary_authoring=self.summary_authoring, view_authoring=self.view_authoring)
        self.assertEqual(error.exception.reason, "STAGING_PRE_SAVE_CAPTURE_ORDER_INVALID")

    def test_changed_snapshot_receipt_link_fails(self):
        altered = copy.deepcopy(self.receipt)
        altered["snapshotId"] = "snapshot-other"
        with self.assertRaises(ValidationFailure) as error:
            self.validate(receipt=altered)
        self.assertEqual(error.exception.reason, "STAGING_PUBLICATION_EVIDENCE_INVALID")

    def test_panel12_missing_one_required_field_link_fails(self):
        altered = copy.deepcopy(self.view)
        del altered["cards"][11]["chains"][0]["field_refs"]["condition"]
        with self.assertRaises(ValidationFailure) as error:
            self.validate(view=altered)
        self.assertEqual(error.exception.reason, "STAGING_PANEL12_FIELD_NOT_RENDERED")

    def test_stale_human_scenario_review_fails(self):
        altered = copy.deepcopy(self.scenario_review)
        altered["summary_sha256"] = "0" * 64
        with self.assertRaises(ValidationFailure) as error:
            self.validate(scenario_review=altered)
        self.assertEqual(error.exception.reason, "STAGING_HUMAN_SCENARIO_REVIEW_MISSING_OR_STALE")


if __name__ == "__main__":
    unittest.main()
