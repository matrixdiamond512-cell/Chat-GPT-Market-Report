import datetime as dt
import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from report_delivery_health import expected_slot, delivery_health, apply_delivery_health, JST
from build_market_json import attach_market_data
from prepare_pages_site import prepare_pages_site
from verify_pages_artifact import verify
import sync_latest_report_publication as sync

def moment(value): return dt.datetime.fromisoformat(value + "+09:00")

class ScheduleHealthTests(unittest.TestCase):
    def test_boundaries_weekend_and_monday(self):
        cases = [("2026-11-24T07:59:59", "2026-11-23_21-00"),
                 ("2026-11-24T08:00:00", "2026-11-24_08-00"),
                 ("2026-11-24T11:59:59", "2026-11-24_08-00"),
                 ("2026-11-24T12:00:00", "2026-11-24_12-00"),
                 ("2026-11-24T16:00:00", "2026-11-24_16-00"),
                 ("2026-11-24T21:00:00", "2026-11-24_21-00"),
                 ("2026-11-28T12:00:00", "2026-11-27_21-00"),
                 ("2026-11-29T22:00:00", "2026-11-27_21-00"),
                 ("2026-11-30T07:59:59", "2026-11-27_21-00")]
        for now, expected in cases:
            with self.subTest(now=now): self.assertEqual(expected_slot(moment(now)).strftime("%Y-%m-%d_%H-%M"), expected)
        self.assertEqual(expected_slot(moment("2026-11-24T12:00:00").astimezone(dt.timezone.utc)), expected_slot(moment("2026-11-24T12:00:00")))

    def test_missing_and_future_are_not_current(self):
        now=moment("2026-11-24T12:00:00")
        self.assertEqual(delivery_health({},now=now)["state"],"MISSING")
        self.assertEqual(delivery_health({"date":"2026-11-25","time":"12:00"},now=now)["state"],"MISSING")

    def test_idempotent_sync_still_expires_at_next_slot(self):
        report={"date":"2026-11-24","time":"08:00","title":"source","report_status":"PUBLISHED"}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"dashboard.json"
            sync.dump_json(path,{"status":"ok","isStale":False,"marketData":{"overallStatus":"verified"}})
            with patch.object(sync,"DASHBOARD",path):
                self.assertEqual(sync.sync_dashboard(report,now=moment("2026-11-24T08:00:00")),"UPDATED")
                self.assertEqual(sync.sync_dashboard(report,now=moment("2026-11-24T08:10:00")),"NO_OP")
                self.assertEqual(sync.sync_dashboard(report,now=moment("2026-11-24T12:00:00")),"UPDATED")
                stale=sync.load_json(path,{})
                self.assertEqual(stale["latestReport"],report)
                self.assertEqual((stale["status"],stale["isStale"],stale["staleReason"]),("degraded",True,"LATEST_REPORT_BEHIND_SCHEDULE"))
                self.assertEqual(sync.sync_dashboard(report,now=moment("2026-11-24T12:01:00")),"NO_OP")

    def test_current_report_clears_owned_reason_but_keeps_independent_problem(self):
        report={"date":"2026-11-24","time":"12:00"}
        d={"status":"degraded","isStale":True,"staleReason":"LATEST_REPORT_BEHIND_SCHEDULE","marketData":{"overallStatus":"degraded"}}
        apply_delivery_health(d,report,now=moment("2026-11-24T12:00:00"))
        self.assertEqual(d["status"],"degraded")
        self.assertFalse(d["isStale"])
        d={"status":"partial","isStale":True,"staleReason":"MARKET_DATA_PARTIAL"}
        apply_delivery_health(d,report,now=moment("2026-11-24T12:00:00"))
        self.assertEqual((d["status"],d["staleReason"]),("partial","MARKET_DATA_PARTIAL"))

    def test_market_refresh_cannot_hide_report_delay_or_emit_empty_missing(self):
        report={"date":"2026-10-13","time":"16:00"}
        d={"latestReport":report,"status":"ok","isStale":False}
        result=attach_market_data(d,{"overallStatus":"degraded","missingRequired":[]},now=moment("2026-11-24T12:00:00"))
        self.assertNotIn("missing=",result["errors"][0])
        self.assertEqual(result["reportDelivery"]["slotFreshness"]["state"],"BEHIND_SCHEDULE")
        self.assertEqual(result["status"],"degraded")
        self.assertFalse(d["isStale"])

    def test_independent_staleness_survives_a_report_outage_and_recovery(self):
        d={"status":"partial","isStale":True,"staleReason":"MARKET_DATA_PARTIAL"}
        apply_delivery_health(d,{"date":"2026-11-24","time":"08:00"},now=moment("2026-11-24T12:00:00"))
        self.assertEqual(d["staleReason"],"LATEST_REPORT_BEHIND_SCHEDULE")
        apply_delivery_health(d,{"date":"2026-11-24","time":"12:00"},now=moment("2026-11-24T12:00:00"))
        self.assertEqual((d["status"],d["isStale"],d["staleReason"]),("partial",True,"MARKET_DATA_PARTIAL"))

class PagesIsolationTests(unittest.TestCase):
    def test_only_allowlisted_files_and_eligible_reports_are_copied(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/"repo";site=Path(tmp)/"site"
            for folder in ["config","reports","docs","data/report-evidence","publication-receipts"]: (source/folder).mkdir(parents=True,exist_ok=True)
            for name in ["index.html","docs/private.md","data/report-evidence/private.json","publication-receipts/private.json","new-secret.txt"]:(source/name).write_text("private",encoding="utf-8")
            (source/"config/pages_public_files.json").write_text(json.dumps({"schemaVersion":1,"files":["index.html","reports/blocked.json"]}),encoding="utf-8")
            (source/"reports/blocked.json").write_text(json.dumps({"report_status":"SOURCE_ARCHIVED"}),encoding="utf-8")
            (source/"reports/public.json").write_text(json.dumps({"report_status":"PUBLISHED"}),encoding="utf-8")
            excluded=prepare_pages_site(source,site)
            self.assertEqual(excluded,["blocked.json"])
            self.assertEqual(sorted(p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()),["index.html","reports/public.json"])
            self.assertTrue((source/"reports/blocked.json").exists())

    def test_traversal_and_missing_allowlist_fail_before_any_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/"repo";source.mkdir();(source/"config").mkdir()
            for name in ["../private.txt","missing.txt","C:/private.txt"]:
                (source/"config/pages_public_files.json").write_text(json.dumps({"schemaVersion":1,"files":[name]}),encoding="utf-8")
                with self.assertRaises(ValueError):prepare_pages_site(source,Path(tmp)/"site")
                self.assertFalse((Path(tmp)/"site").exists())

    def test_exact_uploaded_artifact_id_and_uniqueness_are_required(self):
        artifact={"id":123,"name":"github-pages","size_in_bytes":50,"expired":False}
        self.assertEqual(verify({"artifacts":[artifact]},"123","github-pages"),artifact)
        for values in [[],[dict(artifact,id=124)],[dict(artifact,expired=True)],[artifact,artifact],[dict(artifact,size_in_bytes=0)]]:
            with self.assertRaises(ValueError):verify({"artifacts":values},"123","github-pages")

class WorkflowBoundaryTests(unittest.TestCase):
    def test_freshness_failure_runs_after_persistence_even_when_projection_is_noop(self):
        source=(ROOT/".github/workflows/sync-latest-report-publication.yml").read_text(encoding="utf-8")
        self.assertLess(source.index('git push origin main'),source.index('run: python scripts/report_delivery_health.py'))
        self.assertIn('if: success()',source[source.index('- name: Require the latest scheduled report'):])

    def test_pages_readback_precedes_deploy_and_uses_upload_id(self):
        source=(ROOT/".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
        self.assertLess(source.index('Read back the exact uploaded Pages artifact'),source.index('- name: Deploy to GitHub Pages'))
        self.assertIn('steps.pages-upload.outputs.artifact_id',source)
        self.assertIn('artifact_name: github-pages',source)
        self.assertIn('test "$mode" = workflow',source)

if __name__ == "__main__": unittest.main()
