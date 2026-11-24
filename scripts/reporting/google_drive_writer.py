"""Narrow Google Drive/Docs writer for isolated report delivery tests.

The destination folder is explicit and never discovered from production
configuration. Every create is preceded by duplicate checks and followed by a
separate metadata/content readback. A readback is transfer evidence only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date
from urllib.parse import quote

from .delivery_spool import TransferReadback


DRIVE = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
DOCS = "https://docs.googleapis.com/v1"
DOC_MIME = "application/vnd.google-apps.document"
FOLDER_MIME = "application/vnd.google-apps.folder"
PNG_MIME = "image/png"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
REPORT_ID = re.compile(r"^\d{4}-\d{2}-\d{2}_(?:08|12|16|21)-00$")
FILE_FIELDS = "id,name,mimeType,parents,size,headRevisionId,appProperties,trashed"
MAX_INLINE_UPLOAD = 5 * 1024 * 1024


class DriveWriterError(RuntimeError):
    """Provider error without credential, request-body, or report-text details."""


class DriveConflict(DriveWriterError):
    """An existing name or identity cannot be safely reused."""

    definitely_not_created = True


class DefinitiveWriteRejection(DriveWriterError):
    """Google rejected a create request before accepting a file."""

    definitely_not_created = True


@dataclass(frozen=True)
class FileReference:
    file_id: str
    kind: str
    report_id: str
    revision: int
    body_hash: str
    artifact_hash: str

    def encode(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))

    @classmethod
    def decode(cls, value: str) -> "FileReference":
        try:
            data = json.loads(value)
            ref = cls(**data)
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise DriveWriterError("invalid saved Drive reference") from exc
        if not ref.file_id:
            raise DriveWriterError("saved Drive reference has no fileId")
        return ref


class GoogleDriveReportWriter:
    def __init__(self, session, folder_id: str, *, timeout: int = 35):
        folder_id = str(folder_id or "").strip()
        if not folder_id or folder_id.lower() == "root":
            raise ValueError("an explicit isolated Drive folder ID is required")
        self.session = session
        self.folder_id = folder_id
        self.timeout = timeout

    @classmethod
    def from_environment(cls, folder_id: str | None = None):
        """Use existing service-account material; never log or persist it."""
        raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        destination = folder_id or os.environ.get("GOOGLE_REPORT_WRITER_FOLDER_ID", "")
        if not raw:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not configured")
        if not destination:
            raise RuntimeError("GOOGLE_REPORT_WRITER_FOLDER_ID is not configured")
        try:
            from google.auth.transport.requests import AuthorizedSession
            from google.oauth2 import service_account
        except ImportError as exc:
            raise RuntimeError("google-auth is required for Google Drive writes") from exc
        try:
            account = json.loads(raw)
            credentials = service_account.Credentials.from_service_account_info(
                account,
                scopes=[
                    "https://www.googleapis.com/auth/drive.file",
                    "https://www.googleapis.com/auth/drive.metadata.readonly",
                ],
            )
        except Exception as exc:
            raise RuntimeError("Google Drive writer credentials could not be initialized") from exc
        return cls(AuthorizedSession(credentials), destination)

    @staticmethod
    def _body_hash(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _stable_key(key: dict) -> str:
        canonical = json.dumps(key, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _identity(self, key: dict, payload: bytes):
        report_id = key.get("reportId")
        revision = key.get("revision")
        kind = key.get("kind")
        if not isinstance(report_id, str) or not REPORT_ID.fullmatch(report_id):
            raise ValueError("invalid reportId")
        try:
            date.fromisoformat(report_id[:10])
        except ValueError as exc:
            raise ValueError("invalid report date") from exc
        if type(revision) is not int or revision < 1:
            raise ValueError("invalid revision")
        if kind not in {"DOCS", "PNG"} or not isinstance(payload, bytes) or not payload:
            raise ValueError("invalid transfer kind or payload")
        body_hash = key.get("bodyHash")
        artifact_hash = key.get("artifactHash")
        if not isinstance(body_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", body_hash):
            raise ValueError("invalid bodyHash")
        if artifact_hash != self._body_hash(payload):
            raise ValueError("artifactHash does not match original bytes")
        if kind == "DOCS":
            payload.decode("utf-8")
            if body_hash != artifact_hash:
                raise ValueError("Docs original hash must equal bodyHash")
        elif not payload.startswith(PNG_SIGNATURE):
            raise ValueError("PNG signature missing")
        return report_id, revision, kind, body_hash, artifact_hash

    def _properties(self, key: dict, payload: bytes) -> dict[str, str]:
        report_id, revision, kind, body_hash, artifact_hash = self._identity(key, payload)
        return {
            "delivery_key": self._stable_key(key),
            "report_id": report_id,
            "revision": str(revision),
            "kind": kind,
            "body_hash": body_hash,
            "artifact_hash": artifact_hash,
        }

    def _check_response(self, response):
        status = int(getattr(response, "status_code", 0) or 0)
        if 200 <= status < 300:
            return
        # These responses state that the create request was rejected. Timeouts,
        # 409, 429 and 5xx remain ambiguous and are never retried as new writes.
        message = f"Google API request failed (HTTP {status or 'unknown'})"
        if status in {400, 401, 403, 404}:
            raise DefinitiveWriteRejection(message)
        raise DriveWriterError(message)

    def _json_request(self, method: str, url: str, *, params=None, body=None):
        try:
            response = self.session.request(method, url, params=params, json=body, timeout=self.timeout)
        except Exception as exc:
            raise DriveWriterError("Google API request outcome is unknown") from exc
        self._check_response(response)
        try:
            result = response.json()
        except Exception as exc:
            raise DriveWriterError("Google API returned unreadable metadata") from exc
        if not isinstance(result, dict):
            raise DriveWriterError("Google API returned invalid metadata")
        return result

    def _list(self, query: str) -> list[dict]:
        token = None
        found = []
        while True:
            params = {"q": query, "fields": f"nextPageToken,files({FILE_FIELDS})", "pageSize": 1000,
                      "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
            if token:
                params["pageToken"] = token
            result = self._json_request("GET", DRIVE + "/files", params=params)
            if result.get("incompleteSearch") is True:
                raise DriveWriterError("Google Drive duplicate scan was incomplete")
            page = result.get("files", [])
            if not isinstance(page, list):
                raise DriveWriterError("Google Drive returned an invalid file list")
            found.extend(page)
            if len(found) > 10000:
                raise DriveWriterError("Drive duplicate scan exceeded safety limit")
            token = result.get("nextPageToken")
            if not token:
                return found

    def _folder(self):
        folder = self._json_request("GET", DRIVE + "/files/" + quote(self.folder_id, safe=""),
                                    params={"fields": "id,name,mimeType,trashed", "supportsAllDrives": "true"})
        if (folder.get("id") != self.folder_id or folder.get("mimeType") != FOLDER_MIME or
                folder.get("trashed") or not str(folder.get("name", "")).startswith("TEST_ONLY")):
            raise DriveConflict("configured destination must be an accessible TEST_ONLY folder")
        return folder

    @staticmethod
    def _escape_query(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _target(self, key: dict, payload: bytes):
        report_id, revision, kind, body_hash, artifact_hash = self._identity(key, payload)
        base = f"マーケットレポート_{report_id}"
        name = base if kind == "DOCS" else base + ".png"
        mime = DOC_MIME if kind == "DOCS" else PNG_MIME
        props = self._properties(key, payload)
        name_query = (f"'{self._escape_query(self.folder_id)}' in parents and "
                      f"name = '{self._escape_query(name)}' and trashed = false")
        named = self._list(name_query)
        keyed_query = f"appProperties has {{ key='delivery_key' and value='{props['delivery_key']}' }} and trashed = false"
        keyed = self._list(keyed_query)
        by_id = {item.get("id"): item for item in keyed if item.get("id")}
        for item in named:
            if item.get("id") not in by_id:
                raise DriveConflict("same-name Drive file exists without this delivery identity")
        matches = list(by_id.values())
        if len(matches) > 1 or len(named) > 1:
            raise DriveConflict("duplicate Drive files match this delivery identity")
        if not matches:
            return name, mime, props, None
        item = matches[0]
        if (item.get("name") != name or item.get("mimeType") != mime or
                item.get("parents") != [self.folder_id] or item.get("trashed") is True or
                item.get("appProperties") != props):
            raise DriveConflict("existing Drive file metadata conflicts with this delivery")
        reference = FileReference(str(item["id"]), kind, report_id, revision, body_hash, artifact_hash)
        observed = self._readback(reference)
        if observed.payload != payload:
            raise DriveConflict("existing Drive file content conflicts; existing file was not changed")
        return name, mime, props, reference

    @staticmethod
    def _multipart(metadata: dict, payload: bytes, media_mime: str):
        boundary = "codex_phase2_" + uuid.uuid4().hex
        chunks = [
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode(),
            json.dumps(metadata, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            f"\r\n--{boundary}\r\nContent-Type: {media_mime}\r\n\r\n".encode(),
            payload,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
        return boundary, b"".join(chunks)

    def _create(self, name: str, mime: str, props: dict, payload: bytes, media_mime: str):
        metadata = {"name": name, "mimeType": mime, "parents": [self.folder_id], "appProperties": props}
        if len(payload) > MAX_INLINE_UPLOAD:
            try:
                start = self.session.request(
                    "POST", UPLOAD,
                    params={"uploadType": "resumable", "fields": FILE_FIELDS, "supportsAllDrives": "true"},
                    json=metadata,
                    headers={"X-Upload-Content-Type": media_mime, "X-Upload-Content-Length": str(len(payload))},
                    timeout=self.timeout,
                )
            except Exception as exc:
                raise DriveWriterError("Google Drive resumable upload outcome is unknown") from exc
            self._check_response(start)
            upload_url = getattr(start, "headers", {}).get("Location")
            if not upload_url:
                raise DriveWriterError("Google Drive did not return a resumable upload URL")
            try:
                response = self.session.request(
                    "PUT", upload_url, data=payload,
                    headers={"Content-Type": media_mime, "Content-Length": str(len(payload))},
                    timeout=self.timeout,
                )
            except Exception as exc:
                raise DriveWriterError("Google Drive resumable upload outcome is unknown") from exc
            self._check_response(response)
            try:
                item = response.json()
            except Exception as exc:
                raise DriveWriterError("Google Drive upload returned unreadable metadata") from exc
            if not isinstance(item, dict) or not item.get("id"):
                raise DriveWriterError("Google Drive upload did not return fileId")
            return item
        boundary, data = self._multipart(metadata, payload, media_mime)
        try:
            response = self.session.request(
                "POST", UPLOAD,
                params={"uploadType": "multipart", "fields": FILE_FIELDS, "supportsAllDrives": "true"},
                data=data,
                headers={"Content-Type": f"multipart/related; boundary={boundary}"},
                timeout=self.timeout,
            )
        except Exception as exc:
            raise DriveWriterError("Google Drive create outcome is unknown") from exc
        self._check_response(response)
        try:
            item = response.json()
        except Exception as exc:
            raise DriveWriterError("Google Drive create returned unreadable metadata") from exc
        if not isinstance(item, dict) or not item.get("id"):
            raise DriveWriterError("Google Drive create did not return fileId")
        return item

    def _file_metadata(self, reference: FileReference):
        item = self._json_request("GET", DRIVE + "/files/" + quote(reference.file_id, safe=""),
                                  params={"fields": FILE_FIELDS, "supportsAllDrives": "true"})
        expected_name = f"マーケットレポート_{reference.report_id}" + (".png" if reference.kind == "PNG" else "")
        expected_mime = PNG_MIME if reference.kind == "PNG" else DOC_MIME
        expected_props = {
            "delivery_key": self._stable_key({"reportId": reference.report_id, "revision": reference.revision,
                                               "bodyHash": reference.body_hash, "artifactHash": reference.artifact_hash,
                                               "kind": reference.kind}),
            "report_id": reference.report_id,
            "revision": str(reference.revision),
            "kind": reference.kind,
            "body_hash": reference.body_hash,
            "artifact_hash": reference.artifact_hash,
        }
        if (item.get("id") != reference.file_id or item.get("name") != expected_name or
                item.get("mimeType") != expected_mime or item.get("parents") != [self.folder_id] or
                item.get("appProperties") != expected_props or item.get("trashed") is True):
            raise DriveConflict("Drive readback metadata does not match reportId/revision/parent/MIME")
        return item

    @staticmethod
    def _document_text(document: dict) -> str:
        parts = []

        def walk(elements):
            for element in elements or []:
                paragraph = element.get("paragraph")
                if paragraph:
                    for part in paragraph.get("elements", []):
                        parts.append(part.get("textRun", {}).get("content", ""))
                table = element.get("table")
                if table:
                    for row in table.get("tableRows", []):
                        for cell in row.get("tableCells", []):
                            walk(cell.get("content", []))
                toc = element.get("tableOfContents")
                if toc:
                    walk(toc.get("content", []))

        walk(document.get("body", {}).get("content", []))
        return "".join(parts)

    def _readback(self, reference: FileReference) -> TransferReadback:
        item = self._file_metadata(reference)
        common = {"fileId": item["id"], "parentId": self.folder_id, "mimeType": item["mimeType"],
                  "driveSizeBytes": int(item["size"]) if item.get("size") is not None else None,
                  "reportId": reference.report_id, "revision": reference.revision,
                  "bodyHash": reference.body_hash, "artifactHash": reference.artifact_hash}
        if reference.kind == "PNG":
            try:
                response = self.session.request(
                    "GET", DRIVE + "/files/" + quote(reference.file_id, safe=""),
                    params={"alt": "media", "supportsAllDrives": "true"}, timeout=self.timeout,
                )
            except Exception as exc:
                raise DriveWriterError("PNG content readback failed") from exc
            self._check_response(response)
            payload = bytes(getattr(response, "content", b""))
            if not payload.startswith(PNG_SIGNATURE) or self._body_hash(payload) != reference.artifact_hash:
                raise DriveConflict("PNG byte/hash readback mismatch")
            if common["driveSizeBytes"] != len(payload):
                raise DriveConflict("PNG Drive metadata size differs from readback bytes")
            common["contentSizeBytes"] = len(payload)
            return TransferReadback(payload, common)

        try:
            document = self._json_request("GET", DOCS + "/documents/" + quote(reference.file_id, safe=""))
        except Exception as exc:
            if isinstance(exc, DriveWriterError):
                raise
            raise DriveWriterError("Google Docs content readback failed") from exc
        if document.get("documentId") != reference.file_id or not document.get("revisionId"):
            raise DriveConflict("Google Docs ID or revision readback missing")
        text = self._document_text(document)
        payload = text.encode("utf-8")
        if self._body_hash(payload) != reference.artifact_hash:
            raise DriveConflict("Google Docs full-text/hash readback mismatch")
        # Native Docs do not expose binary file size. Preserve both the Drive
        # metadata value (when present) and exact UTF-8 content byte length.
        common["docsRevisionId"] = document["revisionId"]
        common["contentSizeBytes"] = len(payload)
        if common["driveSizeBytes"] is not None and common["driveSizeBytes"] != len(payload):
            common["driveSizeBytesMeaning"] = "provider-reported-native-doc-size; exact text bytes are contentSizeBytes"
        return TransferReadback(payload, common)

    def _write(self, key: dict, payload: bytes):
        report_id, revision, kind, body_hash, artifact_hash = self._identity(key, payload)
        try:
            self._folder()
            name, mime, props, existing = self._target(key, payload)
        except Exception as exc:
            # No create request was sent; the original remains safely retryable.
            raise DefinitiveWriteRejection("Drive preflight did not permit a create") from exc
        if existing:
            return existing.encode()
        media_mime = "text/plain; charset=UTF-8" if kind == "DOCS" else PNG_MIME
        item = self._create(name, mime, props, payload, media_mime)
        reference = FileReference(str(item["id"]), kind, report_id, revision, body_hash, artifact_hash)
        # The spool will persist this reference before its mandatory readback.
        return reference.encode()

    def write_docs(self, key: dict, payload: bytes) -> str:
        if key.get("kind") != "DOCS":
            raise ValueError("DOCS writer received another transfer kind")
        return self._write(key, payload)

    def write_png(self, key: dict, payload: bytes) -> str:
        if key.get("kind") != "PNG":
            raise ValueError("PNG writer received another transfer kind")
        return self._write(key, payload)

    def readback(self, encoded_reference: str) -> TransferReadback:
        return self._readback(FileReference.decode(encoded_reference))

    def reconcile(self, key: dict, payload: bytes) -> str | None:
        """Find a previously accepted create by exact appProperties/name.

        No result does not prove the prior create failed (Drive list visibility
        can lag), so callers must leave the spool UNKNOWN and never recreate.
        """
        self._identity(key, payload)
        self._folder()
        _name, _mime, _props, existing = self._target(key, payload)
        return existing.encode() if existing else None
