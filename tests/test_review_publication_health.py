"""Review 6034576678: current timestamps are not formal publication evidence."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import report_delivery_health as health
import sync_latest_report_publication as sync

class ReviewPublicationHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for d in ["reports","publication-receipts","data"]:(self.root/d).mkdir()
        self.now=dt.datetime(2026,11,24,12,5,tzinfo=health.JST)
        body="TEST_ONLY body; not a production report"
        h=hashlib.sha256(body.encode()).hexdigest()
        evidence={"evidenceId":"e"*64,"snapshotId":"fixture-snapshot","contextHash":"c"*64,"snapshotHash":"a"*64,"bodyHash":h,"documentRevisionId":"fixture-rev"}
        self.report={"date":"2026-11-24","time":"12:00","title":"TEST_ONLY", "revision":1,"fullText":body,"bodyHash":h,"report_status":"DOC_READBACK_PASS","sourceDocument":{"id":"fixture-doc","url":"https://docs.google.com/document/d/fixture-doc/edit"},"publicationEvidence":evidence}
        self.receipt={"schemaVersion":2,"date":self.report["date"],"time":"12:00","title":"TEST_ONLY","status":"DOC_READBACK_PASS","publisher":"google-drive-ingestion","driveFileId":"fixture-doc","driveUrl":self.report["sourceDocument"]["url"],"savedAt":"2026-11-24T12:03:00+09:00","reportId":"2026-11-24_12-00","revision":1,"bodyHash":h,"documentRevisionId":"fixture-rev","readback":{"status":"PASS","exactMatch":True,"bodyHash":h,"characterCount":len(body)},"sourceDocument":{"createdAt":"2026-11-24T12:02:00+09:00","modifiedAt":"2026-11-24T12:03:00+09:00"},**evidence}
        self.write("reports/2026-11-24_12-00.json",self.report)
        self.write("publication-receipts/2026-11-24_12-00.json",self.receipt)
        self.write("reports.json",[self.report])
    def tearDown(self):self.tmp.cleanup()
    def write(self,p,value):(self.root/p).write_text(json.dumps(value),encoding="utf-8")
    def assess(self,report=None):
        d={"status":"ok","isStale":False}
        health.apply_delivery_health(d,self.report if report is None else report,now=self.now,evidence_root=self.root)
        return d
    def test_valid_receipt_is_repository_evidence_not_pages_acceptance(self):
        d=self.assess();self.assertEqual(d["reportDelivery"]["slotFreshness"]["state"],"CURRENT")
        self.assertEqual(d["reportDelivery"]["formalPublication"]["state"],"VERIFIED")
        self.assertEqual(d["reportDelivery"]["pagesDisplay"]["state"],"NOT_VERIFIED")
    def test_current_slot_missing_receipt_cannot_be_ok(self):
        (self.root/"publication-receipts/2026-11-24_12-00.json").unlink()
        d=self.assess();self.assertEqual(d["reportDelivery"]["slotFreshness"]["state"],"CURRENT")
        self.assertEqual(d["reportDelivery"]["formalPublication"]["reason"],"RECEIPT_MISSING")
        self.assertNotEqual(d["status"],"ok")
    def test_source_archived_at_current_slot_is_not_formal(self):
        d=self.assess(dict(self.report,report_status="SOURCE_ARCHIVED"))
        self.assertEqual(d["reportDelivery"]["formalPublication"]["reason"],"SOURCE_NOT_FORMAL")
        self.assertNotEqual(d["status"],"ok")
    def test_failed_docs_readback_cannot_verify(self):
        self.receipt["readback"]["status"]="FAIL";self.write("publication-receipts/2026-11-24_12-00.json",self.receipt)
        d=self.assess();self.assertEqual(d["reportDelivery"]["formalPublication"]["state"],"FAILED")
        self.assertNotEqual(d["status"],"ok")
    def test_latest_report_missing_despite_current_data_as_of(self):
        d={"dataAsOf":"2026-11-24T12:00:00+09:00","status":"ok"}
        health.apply_delivery_health(d,{},now=self.now,evidence_root=self.root)
        self.assertEqual(d["reportDelivery"]["slotFreshness"]["state"],"MISSING")
        self.assertNotEqual(d["status"],"ok")
    def test_tampered_canonical_or_index_cannot_verify(self):
        self.write("reports.json",[])
        self.assertEqual(self.assess()["reportDelivery"]["formalPublication"]["reason"],"INDEX_MISMATCH")
        self.write("reports/2026-11-24_12-00.json",dict(self.report,fullText="changed"))
        self.assertEqual(self.assess()["reportDelivery"]["formalPublication"]["reason"],"CANONICAL_MISMATCH")
    def test_receipt_removed_after_noop_is_rechecked_and_source_not_ok(self):
        path=self.root/"data/dashboard.json";self.write("data/dashboard.json",{"status":"ok"})
        with patch.object(sync,"DASHBOARD",path):
            sync.sync_dashboard(self.report,now=self.now)
            (self.root/"publication-receipts/2026-11-24_12-00.json").unlink()
            self.assertEqual(sync.sync_dashboard(self.report,now=self.now),"UPDATED")
        d=json.loads(path.read_text(encoding="utf-8"))
        source=next(x for x in d["sources"] if x["id"]=="MARKET_REPORTS_JSON")
        self.assertEqual(source["status"],"unverified")
    def test_changed_revision_cannot_reuse_old_receipt(self):
        updated=dict(self.report,revision=2);self.write("reports/2026-11-24_12-00.json",updated);self.write("reports.json",[updated])
        self.assertEqual(self.assess(updated)["reportDelivery"]["formalPublication"]["state"],"FAILED")

if __name__=="__main__":unittest.main()
