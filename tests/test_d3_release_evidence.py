"""No network. Fixtures are fabricated and must never be published."""
import copy
import json
import unittest
from datetime import date
from pathlib import Path

from scripts.reporting.context import ReportContext
from scripts.reporting.snapshot import MarketDataSnapshot
from scripts.reporting.d3_release_evidence import (
    inspect_saved_input, validate_release_evidence,
    prepare_evidence_bound_request,
)

ROOT=Path(__file__).resolve().parents[1]


def actual_21h():
    ctx=ReportContext.create("2026-10-14","21:00","2026-10-14T21:00:00+09:00",mode="historical")
    payload=json.loads((ROOT/"data/market/history/2026-10-14_21-00.json").read_text(encoding="utf-8"))
    snap=MarketDataSnapshot.from_acquisition(ctx,payload)
    return ctx,payload,snap


def synthetic_evidence(ctx,snap,categories=("news","rates","positioning","events")):
    # Fake *test fixtures* ONLY: no real market headlines or news are claimed.
    evidence={"schema":"market-report-evidence/v1","report_id":ctx.report_id,
              "snapshot_id":snap.snapshot_id,"sources":{}}
    for category in categories:
        entry={"id":"fixture_"+category+"_0001",
               "text":"TEST FIXTURE ONLY: synthetic source record, not market news",
               "url":"https://example.com/fixtures/"+category,
               "published_at":ctx.report_date+"T17:00:00+09:00",
               "as_of":ctx.report_date+"T20:00:00+09:00"}
        if category=="events":
            entry["event_at"]=ctx.report_date+"T22:00:00+09:00"
        evidence["sources"][category]=[entry]
    return evidence


class TestEvidenceGate(unittest.TestCase):
    def test_real_saved_data_missing_news_rates_positions_events_blocks(self):
        ctx,payload,snap=actual_21h()
        result=inspect_saved_input(context=ctx,payload=payload,evidence=None)
        self.assertEqual(result.state,"BLOCKED")
        self.assertIn("EVIDENCE_MANIFEST_MISSING", result.rejection_reasons)
        self.assertFalse(result.publishable)

    def test_approved_shape_fixture_builds_deterministic_model_request(self):
        ctx,payload,snap=actual_21h()
        data=synthetic_evidence(ctx,snap)
        ready=validate_release_evidence(ctx,snap,data)
        self.assertTrue(ready.ready)
        self.assertFalse(ready.publishable)
        self.assertEqual(len(ready.evidence_sha256),64)
        req=prepare_evidence_bound_request(ctx,snap,data,instructions="実際の凍結情報のみ使用。")
        encoded=json.loads(req["input"])
        self.assertEqual(encoded["independent_evidence_sha256"],ready.evidence_sha256)
        self.assertEqual(encoded["independently_sourced_context"],data)
        self.assertTrue(req["store"] is False)
        self.assertEqual(req["tools"],[])
        self.assertEqual(req,prepare_evidence_bound_request(ctx,snap,data,instructions="実際の凍結情報のみ使用。"))

    def test_missing_any_critical_category_is_blocked(self):
        ctx,_,snap=actual_21h()
        for category in ("news","rates","positioning","events"):
            with self.subTest(category=category):
                evidence=synthetic_evidence(ctx,snap)
                del evidence["sources"][category]
                result=validate_release_evidence(ctx,snap,evidence)
                self.assertIn("REQUIRED_SOURCE_MISSING:"+category,result.rejection_reasons)
                self.assertFalse(result.ready)

    def test_future_stale_identity_and_non_https_sources_block(self):
        ctx,_,snap=actual_21h()
        tests=[
            ("snapshot_id","invalid","EVIDENCE_SNAPSHOT_ID_MISMATCH"),
            ("news_as_of","2026-10-14T22:00:00+09:00","SOURCE_AFTER_REPORT_CUTOFF:news[0]"),
            ("rates_as_of","2026-09-14T20:00:00+09:00","SOURCE_STALE:rates[0]"),
            ("news_url","http://example.com/foo","SOURCE_URL_INVALID:news[0]"),
        ]
        for typ,val,expect in tests:
            with self.subTest(typ=typ):
                e=synthetic_evidence(ctx,snap)
                if typ=="snapshot_id":e["snapshot_id"]=val
                elif typ=="news_as_of":e["sources"]["news"][0]["as_of"]=val
                elif typ=="rates_as_of":e["sources"]["rates"][0]["as_of"]=val
                elif typ=="news_url":e["sources"]["news"][0]["url"]=val
                r=validate_release_evidence(ctx,snap,e)
                self.assertIn(expect,r.rejection_reasons)
                with self.assertRaisesRegex(ValueError,"EVIDENCE_PREFLIGHT_BLOCKED"):
                    prepare_evidence_bound_request(ctx,snap,e,instructions="dummy")

    def test_live_latest_snapshot_cannot_use_16h_label_after_cutoff(self):
        data=json.loads((ROOT/"data/market/latest.json").read_text(encoding="utf-8"))
        ctx=ReportContext.create("2026-10-14","16:00","2026-10-14T16:00:00+09:00",mode="historical")
        result=inspect_saved_input(context=ctx,payload=data,evidence=None)
        self.assertEqual(result.state,"BLOCKED")
        self.assertTrue(result.rejection_reasons[0].startswith(("MARKET_INPUT_INVALID", "MARKET_SNAPSHOT_INVALID")), result.rejection_reasons)

    def test_morning_also_requires_valuation_breadth_equity_and_cme(self):
        from test_shadow_worker_offline import fixture_market
        # Create actual-typed *synthetic* six-market fixture at 07:40 for
        # a genuine morning cutoff. This is not a claim about real prices.
        ctx=ReportContext.create("2026-10-15","08:00","2026-10-15T08:00:00+09:00")
        from scripts.reporting.shadow_worker import REQUIRED_SIX
        markets=tuple(fixture_market(k,i,as_of="2026-10-15T07:35:00+09:00")
                      for i,k in enumerate(REQUIRED_SIX))
        snap=MarketDataSnapshot.capture(ctx, markets, "2026-10-15T07:40:00+09:00")
        data=synthetic_evidence(ctx,snap)
        for x in data["sources"].values():
            x[0]["as_of"]="2026-10-15T07:45:00+09:00"
            x[0]["published_at"]="2026-10-15T07:00:00+09:00"
        data["sources"]["events"][0]["event_at"]="2026-10-15T08:30:00+09:00"
        result=validate_release_evidence(ctx,snap,data)
        for cat in ("valuation","breadth","us_equities","cme_futures"):
            self.assertIn("REQUIRED_SOURCE_MISSING:"+cat,result.rejection_reasons)
        self.assertFalse(result.ready)


if __name__=="__main__":
    unittest.main()
