import tempfile
from pathlib import Path
import unittest
from scripts.reporting.delivery_spool import DeliverySpool

class DeliverySpoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/"private/source.sqlite"
        self.store=DeliverySpool(self.path);self.key=("2026-11-24_12-00",1)
        self.body="TEST_ONLY 原文・句読点。".encode();self.png=b"\x89PNG\r\n\x1a\nTEST_ONLY"
        self.store.persist(*self.key,"DOCS",self.body)
    def tearDown(self):self.tmp.cleanup()
    def test_source_survives_restart_and_same_revision_cannot_overwrite(self):
        other=DeliverySpool(self.path);self.assertEqual(other.inspect(*self.key,"DOCS")["payload"],self.body)
        with self.assertRaises(ValueError):other.persist(*self.key,"DOCS",b"changed")
    def test_ambiguous_docs_failure_preserves_source_and_blocks_duplicate_write(self):
        calls=[]
        def fail(k,p):calls.append(k);raise OSError("TEST_ONLY timeout")
        with self.assertRaises(OSError):self.store.transfer(*self.key,"DOCS",write=fail,readback=lambda r:self.body)
        self.assertEqual(self.store.inspect(*self.key,"DOCS")["payload"],self.body)
        with self.assertRaises(ValueError):self.store.transfer(*self.key,"DOCS",write=fail,readback=lambda r:self.body)
        self.assertEqual(len(calls),1)
    def test_readback_retry_never_creates_a_second_doc(self):
        calls=[]
        def write(k,p):calls.append(k);return "fixture-doc"
        with self.assertRaises(ValueError):self.store.transfer(*self.key,"DOCS",write=write,readback=lambda r:b"wrong")
        self.assertEqual(self.store.transfer(*self.key,"DOCS",write=write,readback=lambda r:self.body),"fixture-doc")
        self.assertEqual(len(calls),1)
    def test_png_can_be_saved_while_docs_lane_failed_and_body_is_preserved(self):
        self.store.persist(*self.key,"PNG",self.png)
        def fail(k,p):raise OSError("TEST_ONLY Docs unavailable")
        with self.assertRaises(OSError):self.store.transfer(*self.key,"DOCS",write=fail,readback=lambda r:self.body)
        self.assertEqual(self.store.transfer(*self.key,"PNG",write=lambda k,p:"fixture-png",readback=lambda r:self.png),"fixture-png")
        self.assertEqual(self.store.inspect(*self.key,"DOCS")["state"],"UNKNOWN")
    def test_successful_lane_not_reexecuted_when_other_lane_retries(self):
        calls=[]
        def write(k,p):calls.append(k);return "fixture-doc"
        self.store.transfer(*self.key,"DOCS",write=write,readback=lambda r:self.body)
        self.store.transfer(*self.key,"DOCS",write=write,readback=lambda r:self.body)
        self.assertEqual(len(calls),1)
    def test_png_hash_is_immutable_and_quality_not_claimed(self):
        self.store.persist(*self.key,"PNG",self.png)
        with self.assertRaises(ValueError):self.store.persist(*self.key,"PNG",self.png+b"changed")
        result=self.store.inspect(*self.key,"PNG");self.assertEqual(result["state"],"PERSISTED")
        self.assertNotIn("quality",result)

if __name__=="__main__":unittest.main()
