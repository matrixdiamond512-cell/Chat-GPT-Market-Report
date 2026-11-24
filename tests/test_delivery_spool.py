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

    def test_docs_success_png_failure_is_partial_and_docs_is_not_recreated(self):
        docs_calls=[];png_calls=[]
        self.store.persist(*self.key,"PNG",self.png)
        self.store.transfer(*self.key,"DOCS",write=lambda k,p:(docs_calls.append(k) or "doc-1"),readback=lambda r:self.body)
        with self.assertRaises(OSError):
            self.store.transfer(*self.key,"PNG",write=lambda k,p:(png_calls.append(k) or (_ for _ in ()).throw(OSError("TEST_ONLY PNG failure"))),readback=lambda r:self.png)
        self.assertEqual(self.store.delivery_status(*self.key)["status"],"PARTIAL")
        self.assertEqual(self.store.delivery_status(*self.key)["uncertainLanes"],["PNG"])
        self.store.transfer(*self.key,"DOCS",write=lambda k,p:(docs_calls.append(k) or "doc-duplicate"),readback=lambda r:self.body)
        self.assertEqual((len(docs_calls),len(png_calls)),(1,1))

    def test_successful_write_with_failed_readback_retries_readback_only(self):
        calls=[];reads=[]
        def write(k,p):calls.append(k);return "doc-readback"
        with self.assertRaises(ValueError):
            self.store.transfer(*self.key,"DOCS",write=write,readback=lambda r:(reads.append(r) or b"different"))
        self.assertEqual(self.store.inspect(*self.key,"DOCS")["state"],"READBACK_FAILED")
        self.store.transfer(*self.key,"DOCS",write=write,readback=lambda r:(reads.append(r) or self.body))
        self.assertEqual((len(calls),reads),(1,["doc-readback","doc-readback"]))

    def test_ambiguous_create_can_reconcile_existing_file_without_second_write(self):
        calls=[];self.store.persist(*self.key,"PNG",self.png)
        with self.assertRaises(OSError):
            self.store.transfer(*self.key,"PNG",write=lambda k,p:(calls.append(k) or (_ for _ in ()).throw(OSError("TEST_ONLY lost response"))),readback=lambda r:self.png)
        self.assertEqual(self.store.delivery_status(*self.key)["status"],"UNKNOWN")
        self.store.transfer(*self.key,"PNG",write=lambda k,p:(calls.append(k) or "duplicate"),
                            reconcile=lambda k,p:"drive-png-1",readback=lambda r:self.png)
        self.assertEqual((len(calls),self.store.inspect(*self.key,"PNG")["reference"]),(1,"drive-png-1"))

    def test_ambiguous_create_not_found_remains_blocked_and_never_recreates(self):
        calls=[]
        with self.assertRaises(OSError):
            self.store.transfer(*self.key,"DOCS",write=lambda k,p:(calls.append(k) or (_ for _ in ()).throw(OSError("TEST_ONLY timeout"))),readback=lambda r:self.body)
        with self.assertRaisesRegex(ValueError,"will not be recreated"):
            self.store.transfer(*self.key,"DOCS",write=lambda k,p:(calls.append(k) or "doc-2"),
                                reconcile=lambda k,p:None,readback=lambda r:self.body)
        self.assertEqual(len(calls),1)

    def test_successful_docs_with_missing_png_is_partial_not_complete(self):
        self.store.transfer(*self.key,"DOCS",write=lambda k,p:"doc-only",readback=lambda r:self.body)
        status=self.store.delivery_status(*self.key)
        self.assertEqual(status["status"],"PARTIAL")
        self.assertEqual(status["formalPublication"],"NOT_ASSESSED")
        self.assertEqual(status["imageQuality"],"NOT_ASSESSED")

    def test_docs_and_png_readbacks_are_complete_only_after_both_lanes(self):
        self.store.persist(*self.key,"PNG",self.png)
        self.store.transfer(*self.key,"DOCS",write=lambda k,p:"doc-complete",readback=lambda r:self.body)
        self.assertEqual(self.store.delivery_status(*self.key)["status"],"PARTIAL")
        self.store.transfer(*self.key,"PNG",write=lambda k,p:"png-complete",readback=lambda r:self.png)
        status=self.store.delivery_status(*self.key)
        self.assertEqual(status["status"],"COMPLETE")
        self.assertEqual(set(status["lanes"].values()),{"WRITE_READBACK_VERIFIED"})

    def test_png_report_id_must_have_its_own_matching_original_body(self):
        with self.assertRaisesRegex(ValueError,"persist original body"):
            self.store.persist("2026-11-24_16-00",1,"PNG",self.png)
        with self.assertRaisesRegex(ValueError,"persist original body"):
            self.store.persist(self.key[0],self.key[1]+1,"PNG",self.png)

    def test_reconciliation_failure_does_not_clear_original_bytes(self):
        with self.assertRaises(OSError):
            self.store.transfer(*self.key,"DOCS",write=lambda k,p:(_ for _ in ()).throw(OSError("TEST_ONLY timeout")),readback=lambda r:self.body)
        with self.assertRaises(OSError):
            self.store.transfer(*self.key,"DOCS",write=lambda k,p:"not-used",reconcile=lambda k,p:(_ for _ in ()).throw(OSError("TEST_ONLY lookup unavailable")),readback=lambda r:self.body)
        self.assertEqual(self.store.inspect(*self.key,"DOCS")["payload"],self.body)
        self.assertEqual(self.store.inspect(*self.key,"DOCS")["state"],"UNKNOWN")

if __name__=="__main__":unittest.main()
