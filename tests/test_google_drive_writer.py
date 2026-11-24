import hashlib
import json as json_module
import re
import threading
import unittest

from scripts.reporting.delivery_spool import DeliverySpool
from scripts.reporting.google_drive_writer import (
    DOC_MIME,
    DRIVE,
    FOLDER_MIME,
    GCSArtifactLock,
    DriveLockReleaseError,
    DriveLockBusy,
    DriveWriterError,
    DefinitiveWriteRejection,
    PNG_MIME,
    UPLOAD,
    DriveConflict,
    GoogleDriveReportWriter,
)


class Response:
    def __init__(self, status=200, *, body=None, content=b""):
        self.status_code = status
        self._body = body or {}
        self.content = content

    def json(self):
        return self._body


class MemoryDriveSession:
    """Small API fixture that stores only synthetic test documents/images."""

    def __init__(self):
        self.files = {}
        self.documents = {}
        self.calls = []
        self.next_id = 1
        self.incomplete_search = False
        self.lose_next_create_response = False
        self.hide_files_from_search = False
        self.files["sandbox-folder"] = {"id": "sandbox-folder", "name": "TEST_ONLY",
                                         "mimeType": FOLDER_MIME, "parents": [], "trashed": False}

    def request(self, method, url, *, params=None, json=None, data=None, headers=None, timeout=None):
        params = params or {}
        self.calls.append((method, url, params.copy()))
        if method == "GET" and url == DRIVE + "/files":
            query = params.get("q", "")
            files = list(self.files.values())
            name_match = re.search(r"name = '((?:\\.|[^'])*)'", query)
            if name_match:
                name = name_match.group(1).replace("\\'", "'").replace("\\\\", "\\")
                files = [item for item in files if item.get("name") == name and "sandbox-folder" in item.get("parents", [])]
            property_match = re.search(r"value='([0-9a-f]+)'", query)
            if property_match:
                value = property_match.group(1)
                files = [item for item in files if item.get("appProperties", {}).get("delivery_key") == value]
            if self.hide_files_from_search:
                files = []
            return Response(body={"files": files, "incompleteSearch": self.incomplete_search})
        if method == "GET" and url.endswith("/files/sandbox-folder"):
            return Response(body=self.files["sandbox-folder"])
        if method == "GET" and url.startswith(DRIVE + "/files/"):
            file_id = url.rsplit("/", 1)[-1]
            item = self.files[file_id]
            if params.get("alt") == "media":
                return Response(content=item["_bytes"])
            return Response(body={k: v for k, v in item.items() if not k.startswith("_")})
        if method == "POST" and url == UPLOAD:
            boundary = headers["Content-Type"].split("boundary=", 1)[1].encode("ascii")
            parts = data.split(b"--" + boundary)
            metadata = json_module.loads(parts[1].split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n", 1)[0])
            payload = parts[2].split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n", 1)[0]
            file_id = f"file-{self.next_id}"
            self.next_id += 1
            item = {"id": file_id, "name": metadata["name"], "mimeType": metadata["mimeType"],
                    "parents": metadata["parents"], "appProperties": metadata["appProperties"],
                    "trashed": False, "size": str(len(payload)) if metadata["mimeType"] == PNG_MIME else None,
                    "headRevisionId": "drive-rev-1", "_bytes": payload}
            self.files[file_id] = item
            if metadata["mimeType"] == DOC_MIME:
                self.documents[file_id] = {"documentId": file_id, "revisionId": "docs-rev-1", "text": payload.decode("utf-8")}
            if self.lose_next_create_response:
                self.lose_next_create_response = False
                raise TimeoutError("synthetic response loss after Drive accepted create")
            return Response(body={k: v for k, v in item.items() if not k.startswith("_")})
        if method == "GET" and url.startswith("https://docs.googleapis.com/v1/documents/"):
            file_id = url.rsplit("/", 1)[-1]
            doc = self.documents[file_id]
            return Response(body={"documentId": file_id, "revisionId": doc["revisionId"],
                                  "body": {"content": [{"paragraph": {"elements": [
                                      {"textRun": {"content": doc["text"]}}
                                  ]}}]}})
        raise AssertionError(f"Unexpected fixture request: {method} {url}")


class MemoryGCSLockSession:
    """Thread-safe fake for the GCS ifGenerationMatch=0 object claim."""

    def __init__(self):
        self.objects = {}
        self.calls = []
        self.generation = 0
        self.mutex = threading.Lock()
        self.fail_delete = False

    def request(self, method, url, *, params=None, data=None, headers=None, timeout=None):
        params = params or {}
        self.calls.append((method, url, dict(params)))
        name = params.get("name")
        if method == "POST" and params.get("ifGenerationMatch") == "0":
            with self.mutex:
                if name in self.objects:
                    return Response(412)
                self.generation += 1
                generation = str(self.generation)
                self.objects[name] = generation
                return Response(body={"generation": generation})
        if method == "DELETE":
            if self.fail_delete:
                return Response(503)
            object_name = url.rsplit("/o/", 1)[1].replace("%2F", "/")
            with self.mutex:
                if self.objects.get(object_name) != str(params.get("ifGenerationMatch")):
                    return Response(412)
                del self.objects[object_name]
                return Response(204)
        raise AssertionError(f"Unexpected fake GCS lock request: {method} {url}")


class GoogleDriveWriterTests(unittest.TestCase):
    def setUp(self):
        self.session = MemoryDriveSession()
        self.writer = GoogleDriveReportWriter(self.session, "sandbox-folder")
        self.report_id = "2026-11-24_12-00"
        self.revision = 3
        self.body = "TEST_ONLY Phase 2原文\n数値・句読点。".encode("utf-8")
        self.png = b"\x89PNG\r\n\x1a\nTEST_ONLY_BYTES"
        self.body_hash = hashlib.sha256(self.body).hexdigest()

    def key(self, kind, payload):
        return {"reportId": self.report_id, "revision": self.revision,
                "bodyHash": self.body_hash, "artifactHash": hashlib.sha256(payload).hexdigest(),
                "kind": kind}

    def test_docs_and_png_lanes_save_and_read_back_identity_parent_mime_size_and_content(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp:
            spool = DeliverySpool(Path(temp) / "test.sqlite")
            spool.persist(self.report_id, self.revision, "DOCS", self.body)
            spool.persist(self.report_id, self.revision, "PNG", self.png)
            doc_ref = spool.transfer(self.report_id, self.revision, "DOCS", write=self.writer.write_docs,
                                     readback=self.writer.readback, reconcile=self.writer.reconcile)
            png_ref = spool.transfer(self.report_id, self.revision, "PNG", write=self.writer.write_png,
                                     readback=self.writer.readback, reconcile=self.writer.reconcile)
            self.assertEqual(spool.delivery_status(self.report_id, self.revision)["status"], "COMPLETE")
            doc_evidence = spool.inspect(self.report_id, self.revision, "DOCS")["readback_metadata"]
            png_evidence = spool.inspect(self.report_id, self.revision, "PNG")["readback_metadata"]
            self.assertEqual(doc_evidence["fileId"], json_module.loads(doc_ref)["file_id"])
            self.assertEqual(doc_evidence["docsRevisionId"], "docs-rev-1")
            self.assertEqual(doc_evidence["parentId"], "sandbox-folder")
            self.assertEqual(doc_evidence["mimeType"], DOC_MIME)
            self.assertEqual(doc_evidence["contentSizeBytes"], len(self.body))
            self.assertEqual(png_evidence["fileId"], json_module.loads(png_ref)["file_id"])
            self.assertEqual(png_evidence["driveSizeBytes"], len(self.png))
            self.assertEqual(png_evidence["contentSizeBytes"], len(self.png))
            self.assertEqual(png_evidence["artifactHash"], hashlib.sha256(self.png).hexdigest())
            self.assertEqual(spool.inspect(self.report_id, self.revision, "PNG")["state"], "WRITE_READBACK_VERIFIED")

    def test_same_name_file_without_delivery_marker_blocks_create(self):
        name = f"マーケットレポート_{self.report_id}"
        self.session.files["existing"] = {"id": "existing", "name": name, "mimeType": DOC_MIME,
                                           "parents": ["sandbox-folder"], "trashed": False}
        with self.assertRaises(DriveConflict):
            self.writer.write_docs(self.key("DOCS", self.body), self.body)
        self.assertFalse(any(method == "POST" and url == UPLOAD for method, url, _ in self.session.calls))

    def test_incomplete_search_is_requested_and_blocks_create(self):
        self.session.incomplete_search = True
        with self.assertRaises(DefinitiveWriteRejection):
            self.writer.write_docs(self.key("DOCS", self.body), self.body)
        list_calls = [(method, url, params) for method, url, params in self.session.calls
                      if method == "GET" and url == DRIVE + "/files"]
        self.assertTrue(list_calls)
        self.assertIn("incompleteSearch", list_calls[0][2]["fields"])
        self.assertFalse(any(method == "POST" and url == UPLOAD for method, url, _ in self.session.calls))

    def test_existing_marker_with_wrong_parent_blocks_reuse(self):
        key = self.key("DOCS", self.body)
        props = self.writer._properties(key, self.body)
        self.session.files["misplaced"] = {"id": "misplaced", "name": f"マーケットレポート_{self.report_id}",
            "mimeType": DOC_MIME, "parents": ["other-folder"], "appProperties": props, "trashed": False}
        with self.assertRaises(DriveConflict):
            self.writer.write_docs(key, self.body)
        self.assertFalse(any(method == "POST" and url == UPLOAD for method, url, _ in self.session.calls))

    def test_existing_exact_delivery_is_reused_without_duplicate_upload(self):
        key = self.key("DOCS", self.body)
        ref = self.writer.write_docs(key, self.body)
        second = self.writer.write_docs(key, self.body)
        self.assertEqual(second, ref)
        self.assertEqual(sum(method == "POST" and url == UPLOAD for method, url, _ in self.session.calls), 1)

    def test_wrong_revision_or_body_hash_cannot_reuse_same_name(self):
        key = self.key("DOCS", self.body)
        self.writer.write_docs(key, self.body)
        wrong_key = dict(key, revision=self.revision + 1)
        with self.assertRaises(DriveConflict):
            self.writer.write_docs(wrong_key, self.body)

    def test_writer_requires_explicit_non_root_destination(self):
        for folder_id in ("", "root"):
            with self.assertRaises(ValueError):
                GoogleDriveReportWriter(self.session, folder_id)

    def test_two_writer_instances_share_atomic_lock_and_create_only_one_drive_file(self):
        import tempfile
        from pathlib import Path

        drive = MemoryDriveSession()
        lock_http = MemoryGCSLockSession()
        lock_a = GCSArtifactLock(lock_http, "test-lock-bucket")
        lock_b = GCSArtifactLock(lock_http, "test-lock-bucket")
        writer_a = GoogleDriveReportWriter(drive, "sandbox-folder", lock_store=lock_a, lock_required=True)
        writer_b = GoogleDriveReportWriter(drive, "sandbox-folder", lock_store=lock_b, lock_required=True)
        entered = threading.Event()
        continue_write = threading.Event()
        first_errors = []

        def first_writer():
            with tempfile.TemporaryDirectory() as temp:
                spool = DeliverySpool(Path(temp) / "one.sqlite")
                spool.persist(self.report_id, self.revision, "DOCS", self.body)

                def pause_then_write(key, payload):
                    entered.set()
                    self.assertTrue(continue_write.wait(5))
                    return writer_a.write_docs(key, payload)

                try:
                    spool.transfer(self.report_id, self.revision, "DOCS", write=pause_then_write,
                        readback=writer_a.readback, reconcile=writer_a.reconcile, guard=writer_a.transfer_guard)
                except Exception as exc:
                    first_errors.append(exc)

        thread = threading.Thread(target=first_writer)
        thread.start()
        self.assertTrue(entered.wait(5))
        with tempfile.TemporaryDirectory() as temp:
            other_spool = DeliverySpool(Path(temp) / "two.sqlite")
            other_spool.persist(self.report_id, self.revision, "DOCS", self.body)
            with self.assertRaises(DriveLockBusy):
                other_spool.transfer(self.report_id, self.revision, "DOCS", write=writer_b.write_docs,
                    readback=writer_b.readback, reconcile=writer_b.reconcile, guard=writer_b.transfer_guard)
            continue_write.set()
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(first_errors, [])
            # Once the owner finishes, a later machine retries safely by
            # finding and reading back the already-created file under the lock.
            other_spool.transfer(self.report_id, self.revision, "DOCS", write=writer_b.write_docs,
                readback=writer_b.readback, reconcile=writer_b.reconcile, guard=writer_b.transfer_guard)
            self.assertEqual(other_spool.inspect(self.report_id, self.revision, "DOCS")["state"],
                             "WRITE_READBACK_VERIFIED")
        self.assertEqual(sum(method == "POST" and url == UPLOAD for method, url, _ in drive.calls), 1)
        self.assertEqual(lock_http.objects, {})

    def test_lost_create_response_retains_shared_lock_and_blocks_other_spool_when_search_lags(self):
        import tempfile
        from pathlib import Path

        drive = MemoryDriveSession()
        drive.lose_next_create_response = True
        drive.hide_files_from_search = True
        lock_http = MemoryGCSLockSession()
        writer_a = GoogleDriveReportWriter(drive, "sandbox-folder",
            lock_store=GCSArtifactLock(lock_http, "test-lock-bucket"), lock_required=True)
        writer_b = GoogleDriveReportWriter(drive, "sandbox-folder",
            lock_store=GCSArtifactLock(lock_http, "test-lock-bucket"), lock_required=True)
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            spool_a = DeliverySpool(Path(one) / "one.sqlite")
            spool_b = DeliverySpool(Path(two) / "two.sqlite")
            for spool in (spool_a, spool_b):
                spool.persist(self.report_id, self.revision, "DOCS", self.body)
            with self.assertRaises(DriveWriterError):
                spool_a.transfer(self.report_id, self.revision, "DOCS", write=writer_a.write_docs,
                    readback=writer_a.readback, reconcile=writer_a.reconcile, guard=writer_a.transfer_guard)
            self.assertEqual(spool_a.inspect(self.report_id, self.revision, "DOCS")["state"], "UNKNOWN")
            with self.assertRaises(DriveLockBusy):
                spool_b.transfer(self.report_id, self.revision, "DOCS", write=writer_b.write_docs,
                    readback=writer_b.readback, reconcile=writer_b.reconcile, guard=writer_b.transfer_guard)
        self.assertEqual(sum(method == "POST" and url == UPLOAD for method, url, _ in drive.calls), 1)
        self.assertEqual(len(lock_http.objects), 1, "ambiguous create must leave a provider-wide fail-closed claim")

    def test_lock_release_failure_is_distinct_from_verified_drive_write(self):
        import tempfile
        from pathlib import Path

        lock_http = MemoryGCSLockSession()
        lock_http.fail_delete = True
        writer = GoogleDriveReportWriter(self.session, "sandbox-folder",
            lock_store=GCSArtifactLock(lock_http, "test-lock-bucket"), lock_required=True)
        with tempfile.TemporaryDirectory() as temp:
            spool = DeliverySpool(Path(temp) / "release.sqlite")
            spool.persist(self.report_id, self.revision, "DOCS", self.body)
            with self.assertRaises(DriveLockReleaseError) as raised:
                spool.transfer(self.report_id, self.revision, "DOCS", write=writer.write_docs,
                    readback=writer.readback, reconcile=writer.reconcile, guard=writer.transfer_guard)
            self.assertTrue(raised.exception.operation_succeeded)
            self.assertEqual(spool.inspect(self.report_id, self.revision, "DOCS")["state"], "WRITE_READBACK_VERIFIED")
        self.assertEqual(len(lock_http.objects), 1, "failed delete leaves the lock object for operator recovery")


if __name__ == "__main__":
    unittest.main()
