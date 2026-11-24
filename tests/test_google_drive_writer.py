import hashlib
import json as json_module
import re
import unittest

from scripts.reporting.delivery_spool import DeliverySpool
from scripts.reporting.google_drive_writer import (
    DOC_MIME,
    DRIVE,
    FOLDER_MIME,
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
            return Response(body={"files": files})
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
            return Response(body={k: v for k, v in item.items() if not k.startswith("_")})
        if method == "GET" and url.startswith("https://docs.googleapis.com/v1/documents/"):
            file_id = url.rsplit("/", 1)[-1]
            doc = self.documents[file_id]
            return Response(body={"documentId": file_id, "revisionId": doc["revisionId"],
                                  "body": {"content": [{"paragraph": {"elements": [
                                      {"textRun": {"content": doc["text"]}}
                                  ]}}]}})
        raise AssertionError(f"Unexpected fixture request: {method} {url}")


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


if __name__ == "__main__":
    unittest.main()
