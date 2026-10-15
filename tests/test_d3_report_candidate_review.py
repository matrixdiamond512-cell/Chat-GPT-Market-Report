"""Only offline fixtures. No paid sends or production publication."""
import copy
import json
import unittest

from scripts.reporting.d3_report_candidate_review import review_model_candidate
from test_d2_responses_contract import provider_fixture
from test_shadow_worker_offline import fixture_context, fixture_snapshot


def test_evidence(ctx, snap):
    return {
        "schema": "market-report-evidence/v1", "report_id":ctx.report_id,
        "snapshot_id":snap.snapshot_id,
        "sources": {
            cat:[{
                "id":"fixture"+cat+"000001",
                "text":"Only an artificial test fixture for API quality-gate testing",
                "url":"https://example.com/offline-fixture/"+cat,
                "published_at":"2026-10-15T14:00:00+09:00",
                "as_of":"2026-10-15T15:45:00+09:00",
                **({"event_at":"2026-10-15T17:00:00+09:00"} if cat=="events" else {}),
            }] for cat in ("news","rates","positioning","events")
        },
    }


class TestCandidateReview(unittest.TestCase):
    def setUp(self):
        self.ctx=fixture_context()
        self.snap=fixture_snapshot(self.ctx)
        self.response=provider_fixture(self.ctx,self.snap)

    def test_missing_external_news_or_positioning_never_accepts_model(self):
        e=test_evidence(self.ctx,self.snap)
        del e["sources"]["news"]
        r=review_model_candidate(context=self.ctx,snapshot=self.snap,evidence=e,
                                 raw_response=self.response)
        self.assertEqual(r.status,"BLOCKED_EVIDENCE")
        self.assertFalse(r.eligible_for_publication)

    def test_full_evidence_does_not_hide_missing_manual_sop_sections(self):
        e=test_evidence(self.ctx,self.snap)
        r=review_model_candidate(context=self.ctx,snapshot=self.snap,evidence=e,
                                 raw_response=self.response)
        self.assertEqual(r.status,"BLOCKED_NARRATIVE",r.reasons)
        self.assertTrue(any("REQUIRED_USER_SOP_SECTION_MISSING" in s for s in r.reasons))
        self.assertFalse(r.eligible_for_publication)

    def test_fixture_good_response_passes_private_only(self):
        raw=copy.deepcopy(self.response)
        parsed=json.loads(raw["output"][0]["content"][0]["text"])
        parsed["full_text"]+="\n材料と値動きの整合性\n実データと一致するか確認するためのフィクスチャ文章です。"
        parsed["full_text"]+="\n今日の主導市場\n架空の試験文章です。"
        parsed["full_text"]+="\nシナリオが崩れる条件\n架空の試験文章です。"
        parsed["full_text"]+="\n次の時間帯への引き継ぎ\n架空の試験文章です。"
        raw["output"][0]["content"][0]["text"]=json.dumps(parsed,ensure_ascii=False)
        r=review_model_candidate(context=self.ctx,snapshot=self.snap,
                                 evidence=test_evidence(self.ctx,self.snap),
                                 raw_response=raw)
        self.assertEqual(r.status,"PRIVATE_DRAFT_VALIDATED",r.reasons)
        self.assertIsNotNone(r.body_sha256)
        self.assertIsNotNone(r.evidence_sha256)
        self.assertFalse(r.eligible_for_publication)
        self.assertEqual(r.model_response_id,"resp_test12345")


if __name__=="__main__":
    unittest.main()
