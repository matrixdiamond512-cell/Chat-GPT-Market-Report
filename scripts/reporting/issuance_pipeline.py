"""Fail-closed G2 -> Google Docs -> portal issuance transaction.

This module is the production integration boundary. It has no default TEST_ONLY
or production credentials and performs no side effect until explicitly called
with configured adapters. Offline tests inject in-memory adapters.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import hashlib
import json
from typing import Protocol

from scripts.persist_report_slot_evidence import validate_stored_slot_evidence
from .context import aware


class IssuanceBlocked(ValueError):
    """A fail-closed validation or downstream readback failure."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DocsReadback:
    document_id: str
    document_revision_id: str
    full_text: str
    body_hash: str
    saved_at: str


@dataclass(frozen=True)
class PortalReadback:
    report_id: str
    revision: int
    snapshot_id: str
    document_id: str
    document_revision_id: str
    full_text: str
    body_hash: str
    status: str


class DocsWriter(Protocol):
    def save_exact(self, *, title: str, report_id: str, revision: int,
                   full_text: str, body_hash: str, evidence_id: str,
                   snapshot_id: str) -> DocsReadback: ...


class PortalPublisher(Protocol):
    def publish_and_readback(self, *, report: dict, docs: DocsReadback,
                             evidence: dict) -> PortalReadback: ...


class ClaimStore(Protocol):
    def claim(self, *, report_id: str, revision: int, body_hash: str,
              evidence_id: str, snapshot_id: str) -> None: ...


class GcsCreateOnlyClaimStore:
    """Durable per-slot idempotency claim; conflicting retries are rejected."""

    def __init__(self, bucket_name: str, *, prefix: str = "issuance-claims/", client=None):
        if not bucket_name or "test" in bucket_name.lower():
            raise ValueError("PRODUCTION_CLAIM_BUCKET_REQUIRED")
        if client is None:
            from google.cloud import storage
            client = storage.Client()
        self._bucket = client.bucket(bucket_name)
        self._prefix = prefix.strip("/") + "/"

    def claim(self, *, report_id: str, revision: int, body_hash: str,
              evidence_id: str, snapshot_id: str) -> None:
        key = f"{self._prefix}{report_id}-r{revision}.json"
        record = json.dumps({
            "report_id": report_id, "revision": revision, "body_hash": body_hash,
            "evidence_id": evidence_id, "snapshot_id": snapshot_id,
        }, sort_keys=True, separators=(",", ":")) + "\n"
        blob = self._bucket.blob(key)
        try:
            blob.upload_from_string(record, content_type="application/json",
                                    if_generation_match=0)
        except Exception as exc:
            # A precondition failure may mean an identical retry. Read and
            # compare the existing object; never overwrite a conflicting claim.
            try:
                blob.reload()
                existing = blob.download_as_text(if_generation_match=blob.generation)
            except Exception as read_exc:
                raise IssuanceBlocked("ISSUANCE_CLAIM_CREATE_OR_READ_FAILED") from read_exc
            if existing != record:
                raise IssuanceBlocked("DUPLICATE_SLOT_ISSUANCE_CONFLICT") from exc


def load_pinned_production_evidence(*, project_id: str, bucket_name: str,
                                    object_name: str, generation: int,
                                    client=None) -> dict:
    """Read one exact GCS generation and return the production evidence envelope."""
    if (not project_id or not bucket_name or "test" in project_id.lower() or
            "test" in bucket_name.lower()):
        raise IssuanceBlocked("PRODUCTION_EVIDENCE_TARGET_NOT_CONFIGURED")
    if type(generation) is not int or generation <= 0:
        raise IssuanceBlocked("EVIDENCE_GENERATION_REQUIRED")
    if client is None:
        from google.cloud import storage
        client = storage.Client(project=project_id)
    blob = client.bucket(bucket_name).blob(object_name, generation=generation)
    try:
        payload = blob.download_as_bytes(if_generation_match=generation)
        blob.reload()
    except Exception as exc:
        raise IssuanceBlocked("PINNED_EVIDENCE_READBACK_FAILED") from exc
    if int(blob.generation) != generation:
        raise IssuanceBlocked("PINNED_EVIDENCE_GENERATION_MISMATCH")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IssuanceBlocked("EVIDENCE_BYTES_INVALID") from exc
    evidence = json.loads(text)
    if not isinstance(evidence, dict):
        raise IssuanceBlocked("EVIDENCE_BYTES_NOT_OBJECT")
    return {
        "environment": "PRODUCTION",
        "evidence_object": {
            "environment": "PRODUCTION", "project_id": project_id,
            "bucket": bucket_name, "object": object_name,
            "generation": generation, "bytes": text,
            "object_sha256": hashlib.sha256(payload).hexdigest(),
            "evidence_id": evidence.get("evidenceId"),
        },
    }


class GoogleDocsApiWriter:
    """Create-only Google Docs writer with exact Docs API full-text readback.

    The caller must explicitly configure a document folder and OAuth identity.
    This adapter never logs the report body or credentials.
    """

    DRIVE_API = "https://www.googleapis.com/drive/v3"
    DOCS_API = "https://docs.googleapis.com/v1"

    def __init__(self, *, folder_id: str, root_folder_id: str, session=None):
        if not folder_id or not root_folder_id:
            raise ValueError("DOCS_TARGET_FOLDER_REQUIRED")
        if session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            credentials, _ = google.auth.default(scopes=[
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/documents",
            ])
            session = AuthorizedSession(credentials)
        self._folder_id = folder_id
        self._root_folder_id = root_folder_id
        self._session = session

    def _json(self, method: str, url: str, *, params=None, body=None):
        response = self._session.request(method, url, params=params, json=body, timeout=30)
        if not response.ok:
            raise IssuanceBlocked(f"GOOGLE_API_{method}_FAILED:{response.status_code}")
        return response.json() if response.content else {}

    def _read_doc(self, document_id: str) -> tuple[str, str]:
        doc = self._json("GET", f"{self.DOCS_API}/documents/{document_id}")
        pieces = []
        def walk(elements):
            for element in elements or []:
                if "paragraph" in element:
                    for item in element["paragraph"].get("elements", []):
                        pieces.append(item.get("textRun", {}).get("content", ""))
                if "table" in element:
                    for row in element["table"].get("tableRows", []):
                        for cell in row.get("tableCells", []):
                            walk(cell.get("content", []))
                if "tableOfContents" in element:
                    walk(element["tableOfContents"].get("content", []))
        walk(doc.get("body", {}).get("content", []))
        return "".join(pieces).lstrip("\ufeff"), str(doc.get("revisionId", ""))

    def save_exact(self, *, title: str, report_id: str, revision: int,
                   full_text: str, body_hash: str, evidence_id: str,
                   snapshot_id: str) -> DocsReadback:
        if _sha256(full_text) != body_hash or not full_text:
            raise IssuanceBlocked("DOCS_INPUT_BODY_HASH_INVALID")
        if not full_text.endswith("\n"):
            raise IssuanceBlocked("DOCS_INPUT_TERMINAL_NEWLINE_REQUIRED")
        folder = self._json("GET", f"{self.DRIVE_API}/files/{self._folder_id}",
                            params={"fields": "id,mimeType,parents,trashed"})
        if (folder.get("id") != self._folder_id or folder.get("mimeType") !=
                "application/vnd.google-apps.folder" or folder.get("trashed") is True or
                self._root_folder_id not in folder.get("parents", [])):
            raise IssuanceBlocked("DOCS_TARGET_FOLDER_IDENTITY_MISMATCH")
        q = ("name = '" + title.replace("\\", "\\\\").replace("'", "\\'") +
             "' and '" + self._folder_id + "' in parents and trashed = false")
        found = self._json("GET", f"{self.DRIVE_API}/files", params={
            "q": q, "pageSize": 100,
            "fields": "files(id,name,mimeType,parents,appProperties,createdTime,modifiedTime,webViewLink)"})
        matches = found.get("files", [])
        if len(matches) > 1:
            raise IssuanceBlocked("DOCS_DUPLICATE_TITLE_CONFLICT")
        properties = {"report_id": report_id, "revision": str(revision),
                      "body_hash": body_hash, "evidence_id": evidence_id,
                      "snapshot_id": snapshot_id}
        if matches:
            item = matches[0]
            if (item.get("mimeType") != "application/vnd.google-apps.document" or
                    item.get("parents") != [self._folder_id] or
                    item.get("appProperties") != properties):
                raise IssuanceBlocked("DOCS_EXISTING_IDENTITY_CONFLICT")
            document_id = item["id"]
            existing, existing_revision = self._read_doc(document_id)
            if existing != full_text:
                raise IssuanceBlocked("DOCS_EXISTING_BODY_CONFLICT")
            revision_id = existing_revision
        else:
            created = self._json("POST", f"{self.DRIVE_API}/files", params={
                "fields": "id,name,mimeType,parents,appProperties,createdTime,modifiedTime,webViewLink"},
                body={"name": title, "mimeType": "application/vnd.google-apps.document",
                      "parents": [self._folder_id], "appProperties": properties})
            document_id = created.get("id")
            if not document_id:
                raise IssuanceBlocked("DOCS_CREATE_ID_MISSING")
            try:
                self._json("POST", f"{self.DOCS_API}/documents/{document_id}:batchUpdate",
                           body={"requests": [{"insertText": {"location": {"index": 1},
                                                                "text": full_text}}]})
            except Exception as exc:
                # Leave a conflict marker in place; never create a duplicate on
                # retry. An operator must reconcile this partial save.
                raise IssuanceBlocked("DOCS_CREATE_INSERT_INCOMPLETE") from exc
            item = self._json("GET", f"{self.DRIVE_API}/files/{document_id}", params={
                "fields": "id,name,mimeType,parents,appProperties,createdTime,modifiedTime,webViewLink"})
            if (item.get("id") != document_id or item.get("name") != title or
                    item.get("mimeType") != "application/vnd.google-apps.document" or
                    item.get("parents") != [self._folder_id] or item.get("appProperties") != properties):
                raise IssuanceBlocked("DOCS_CREATED_FILE_IDENTITY_MISMATCH")
            readback, revision_id = self._read_doc(document_id)
            if readback != full_text or _sha256(readback) != body_hash:
                raise IssuanceBlocked("DOCS_READBACK_MISMATCH")
        readback, revision_id = self._read_doc(document_id)
        if not revision_id or readback != full_text or _sha256(readback) != body_hash:
            raise IssuanceBlocked("DOCS_READBACK_MISMATCH")
        saved_at = item.get("modifiedTime")
        if not saved_at:
            raise IssuanceBlocked("DOCS_SAVE_TIME_MISSING")
        return DocsReadback(document_id, revision_id, readback, _sha256(readback), saved_at)


def _validate_scenario_review(review: dict, report: dict, body_hash: str) -> None:
    if not isinstance(review, dict) or review.get("status") != "APPROVED":
        raise IssuanceBlocked("SCENARIO_HUMAN_REVIEW_REQUIRED")
    if review.get("report_id") != report.get("report_id") or review.get("body_hash") != body_hash:
        raise IssuanceBlocked("SCENARIO_REVIEW_IDENTITY_MISMATCH")
    if not review.get("reviewer") or not review.get("reviewed_at"):
        raise IssuanceBlocked("SCENARIO_REVIEW_ATTESTATION_MISSING")
    if (review.get("branching_validated") is not True or
            review.get("invalidation_trigger_is_decision_change") is not True):
        raise IssuanceBlocked("SCENARIO_SEMANTIC_REVIEW_REQUIRED")
    try:
        aware(review["reviewed_at"])
    except (KeyError, ValueError) as exc:
        raise IssuanceBlocked("SCENARIO_REVIEW_TIME_INVALID") from exc

    items = review.get("scenarios")
    required = ("main_scenario", "alternative_scenario", "invalidation_trigger")
    if not isinstance(items, dict):
        raise IssuanceBlocked("SCENARIO_REVIEW_ITEMS_MISSING")
    text = report.get("fullText")
    for name in required:
        scenario = items.get(name)
        if not isinstance(scenario, dict):
            raise IssuanceBlocked("SCENARIO_REVIEW_ITEM_MISSING:" + name)
        for field in ("condition", "development", "market_impact"):
            item = scenario.get(field)
            if not isinstance(item, dict) or not str(item.get("text", "")).strip():
                raise IssuanceBlocked(f"SCENARIO_REVIEW_FIELD_MISSING:{name}.{field}")
            source = item.get("source")
            if not isinstance(source, dict):
                raise IssuanceBlocked(f"SCENARIO_SOURCE_MISSING:{name}.{field}")
            start, end, quote = source.get("start"), source.get("end"), source.get("quote")
            if type(start) is not int or type(end) is not int or not isinstance(quote, str):
                raise IssuanceBlocked(f"SCENARIO_SOURCE_POSITION_INVALID:{name}.{field}")
            if start < 0 or end <= start or end > len(text) or text[start:end] != quote:
                raise IssuanceBlocked(f"SCENARIO_SOURCE_QUOTE_MISMATCH:{name}.{field}")
            if not item["text"].strip() or item["text"].strip() not in quote:
                raise IssuanceBlocked(f"SCENARIO_SUMMARY_NOT_SUPPORTED:{name}.{field}")


def validate_issuance_bundle(bundle: dict, *, expected_project_id: str,
                             expected_evidence_bucket: str) -> tuple[dict, dict, str]:
    """Bind one production G2 body to one immutable pre-slot evidence object.

    TEST_ONLY evidence is rejected by an explicit environment/project/bucket
    envelope check before body validation. The supplied bytes must already have
    been fetched from the pinned GCS generation by the caller.
    """
    if not isinstance(bundle, dict) or bundle.get("environment") != "PRODUCTION":
        raise IssuanceBlocked("NON_PRODUCTION_EVIDENCE_FORBIDDEN")
    if (not expected_project_id or not expected_evidence_bucket or
            "test" in expected_project_id.lower() or "test" in expected_evidence_bucket.lower()):
        raise IssuanceBlocked("PRODUCTION_EVIDENCE_TARGET_NOT_CONFIGURED")
    envelope = bundle.get("evidence_object")
    if not isinstance(envelope, dict):
        raise IssuanceBlocked("EVIDENCE_OBJECT_ENVELOPE_MISSING")
    if envelope.get("project_id") != expected_project_id or envelope.get("bucket") != expected_evidence_bucket:
        raise IssuanceBlocked("EVIDENCE_OBJECT_TARGET_MISMATCH")
    if envelope.get("environment") != "PRODUCTION":
        raise IssuanceBlocked("TEST_ONLY_EVIDENCE_REJECTED")
    if type(envelope.get("generation")) is not int or envelope["generation"] <= 0:
        raise IssuanceBlocked("EVIDENCE_GENERATION_REQUIRED")
    encoded = envelope.get("bytes")
    if not isinstance(encoded, str):
        raise IssuanceBlocked("EVIDENCE_BYTES_NOT_SUPPLIED")
    try:
        evidence_bytes = encoded.encode("utf-8")
        evidence = json.loads(evidence_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise IssuanceBlocked("EVIDENCE_BYTES_INVALID") from exc
    if hashlib.sha256(evidence_bytes).hexdigest() != envelope.get("object_sha256"):
        raise IssuanceBlocked("EVIDENCE_OBJECT_HASH_MISMATCH")

    g2 = bundle.get("g2")
    if not isinstance(g2, dict):
        raise IssuanceBlocked("G2_BODY_MISSING")
    report = g2.get("report")
    if not isinstance(report, dict):
        raise IssuanceBlocked("G2_REPORT_MISSING")
    full_text = report.get("fullText")
    body_hash = _sha256(full_text) if isinstance(full_text, str) else ""
    if not body_hash or g2.get("body_hash") != body_hash or report.get("bodyHash") != body_hash:
        raise IssuanceBlocked("G2_BODY_HASH_MISMATCH")
    report_id = report.get("report_id")
    if not isinstance(report_id, str) or report_id != f"{report.get('date')}_{str(report.get('time', '')).replace(':', '-')}":
        raise IssuanceBlocked("G2_REPORT_ID_MISMATCH")
    if report.get("time") != "08:00" or type(report.get("revision")) is not int:
        raise IssuanceBlocked("G2_SLOT_OR_REVISION_INVALID")
    if g2.get("report_id") != report_id or g2.get("revision") != report["revision"]:
        raise IssuanceBlocked("G2_IDENTITY_MISMATCH")

    try:
        frozen = validate_stored_slot_evidence(evidence_bytes, report["date"], report["time"])
    except (ValueError, KeyError, TypeError) as exc:
        raise IssuanceBlocked("FROZEN_EVIDENCE_INVALID:" + str(exc)) from exc
    if frozen.get("reportId") != report_id or frozen.get("revision") != report["revision"]:
        raise IssuanceBlocked("FROZEN_EVIDENCE_IDENTITY_MISMATCH")
    snapshot = frozen.get("snapshot") or {}
    context = frozen.get("context") or {}
    if (g2.get("evidence_id") != frozen.get("evidenceId") or
            g2.get("snapshot_id") != snapshot.get("snapshot_id") or
            report.get("snapshot_id") != snapshot.get("snapshot_id") or
            report.get("context") != context or report.get("snapshot") != snapshot):
        raise IssuanceBlocked("G2_SNAPSHOT_BINDING_MISMATCH")
    if envelope.get("evidence_id") != frozen.get("evidenceId"):
        raise IssuanceBlocked("EVIDENCE_ID_MISMATCH")
    _validate_scenario_review(g2.get("scenario_review"), report, body_hash)
    return report, frozen, body_hash


def run_issuance(bundle: dict, *, expected_project_id: str,
                 expected_evidence_bucket: str, docs_writer: DocsWriter,
                 portal: PortalPublisher, claim_store: ClaimStore) -> dict:
    """Execute Docs save/readback then existing portal publication adapter.

    A durable idempotency claim is created before either write. Both external
    stages must return exact identity and content readback. A failure stops
    before the next stage; retries are safe only for the exact same claim.
    """
    report, evidence, body_hash = validate_issuance_bundle(
        bundle, expected_project_id=expected_project_id,
        expected_evidence_bucket=expected_evidence_bucket,
    )
    g2 = bundle["g2"]
    try:
        frozen_at = aware(g2["frozen_at"])
    except (KeyError, ValueError, TypeError) as exc:
        raise IssuanceBlocked("G2_FREEZE_TIME_INVALID") from exc
    claim_store.claim(
        report_id=report["report_id"], revision=report["revision"],
        body_hash=body_hash, evidence_id=evidence["evidenceId"],
        snapshot_id=evidence["snapshot"]["snapshot_id"],
    )
    docs = docs_writer.save_exact(
        title=report["title"], report_id=report["report_id"],
        revision=report["revision"], full_text=report["fullText"],
        body_hash=body_hash, evidence_id=evidence["evidenceId"],
        snapshot_id=evidence["snapshot"]["snapshot_id"],
    )
    if (not docs.document_id or not docs.document_revision_id or
            docs.full_text != report["fullText"] or docs.body_hash != body_hash):
        raise IssuanceBlocked("DOCS_READBACK_MISMATCH")
    try:
        saved_at = aware(docs.saved_at)
    except ValueError as exc:
        raise IssuanceBlocked("DOCS_SAVED_AT_INVALID") from exc
    if saved_at <= frozen_at:
        raise IssuanceBlocked("G2_BODY_NOT_FROZEN_BEFORE_DOCS_SAVE")
    slot_at = aware(f"{report['date']}T{report['time']}:00+09:00")
    if saved_at < slot_at or saved_at > slot_at + timedelta(minutes=40):
        raise IssuanceBlocked("DOCS_SAVE_TIME_OUTSIDE_SLOT_WINDOW")

    portal_result = portal.publish_and_readback(report=report, docs=docs, evidence=evidence)
    if (portal_result.report_id != report["report_id"] or
            portal_result.revision != report["revision"] or
            portal_result.snapshot_id != evidence["snapshot"]["snapshot_id"] or
            portal_result.document_id != docs.document_id or
            portal_result.document_revision_id != docs.document_revision_id or
            portal_result.full_text != report["fullText"] or
            portal_result.body_hash != body_hash or portal_result.status != "PUBLISHED"):
        raise IssuanceBlocked("PORTAL_READBACK_MISMATCH")
    return {
        "status": "E2E_READBACK_PASS",
        "environment": "PRODUCTION",
        "report_id": report["report_id"],
        "revision": report["revision"],
        "body_hash": body_hash,
        "evidence_id": evidence["evidenceId"],
        "snapshot_id": evidence["snapshot"]["snapshot_id"],
        "document_id": docs.document_id,
        "document_revision_id": docs.document_revision_id,
        "portal_status": portal_result.status,
    }
