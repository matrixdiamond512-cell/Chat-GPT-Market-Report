#!/usr/bin/env python3
"""Publish saved Google Docs market reports using the existing Google service account.

No report drafting, pricing inference or document writes. GitHub canonical
history is append-only here. Source corrections need a separate reviewed path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))
SLOTS = ("08:00", "12:00", "16:00", "21:00")
# Monthly report folder is discovered by name, not a fixed October ID.
SOURCE = re.compile(r"^マーケットレポート_(\d{4}-\d{2}-\d{2})_(08|12|16|21)-00$")
FIELDS = "nextPageToken,files(id,name,mimeType,parents,createdTime,modifiedTime,headRevisionId,appProperties)"
DRIVE = "https://www.googleapis.com/drive/v3"
DOCS = "https://docs.googleapis.com/v1"

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def open_session() -> AuthorizedSession:
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON secret is not configured")
    config = json.loads(raw)
    cred = service_account.Credentials.from_service_account_info(config, scopes=[
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/documents.readonly",
    ])
    return AuthorizedSession(cred)

def get_json(session, endpoint, params=None):
    response = session.get(endpoint, params=params, timeout=35)
    if not response.ok:
        error = response.json().get("error", {})
        raise RuntimeError(f"Google API HTTP {response.status_code} ({error.get('status','')})")
    return response.json()

def eligible_sources(session, now, folder_id=None):
    # When the owner has shared the monthly report folder, limit discovery to
    # direct children of that authoritative folder, excluding identically
    # named orphan/root copies from older recovery attempts.
    query = "name contains 'マーケットレポート_' and mimeType = 'application/vnd.google-apps.document' and trashed = false"
    if folder_id:
        query += " and '" + folder_id.replace("'", "\\'") + "' in parents"
    page = None
    found = {}
    scanned = 0
    while True:
        params = {"q": query, "fields": FIELDS, "pageSize": 1000}
        if page:
            params["pageToken"] = page
        result = get_json(session, DRIVE + "/files", params)
        for item in result.get("files", []):
            scanned += 1
            m = SOURCE.fullmatch(item.get("name", ""))
            if not m:
                continue
            date = m.group(1)
            slot = m.group(2) + ":00"
            if slot not in SLOTS:
                continue
            try:
                due = datetime.fromisoformat(date + "T" + slot + ":00+09:00")
            except ValueError:
                continue
            if due > now or now - due > timedelta(days=3):
                continue
            key = (date, slot)
            found.setdefault(key, []).append(item)
        page = result.get("nextPageToken")
        if not page:
            break
        if scanned > 10000:
            raise RuntimeError("Drive scan exceeded safety limit")
    return found, scanned

def paragraph_text(doc: dict) -> str:
    """Preserve exact Docs text runs, including paragraph newlines."""
    parts = []
    def walk(elements):
        for element in elements:
            if "paragraph" in element:
                for part in element["paragraph"].get("elements", []):
                    parts.append(part.get("textRun", {}).get("content", ""))
            if "table" in element:
                for row in element["table"].get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        walk(cell.get("content", []))
            if "tableOfContents" in element:
                walk(element["tableOfContents"].get("content", []))
    walk(doc.get("body", {}).get("content", []))
    return "".join(parts).lstrip("\ufeff")

def build_report(session, date: str, slot: str, item: dict) -> dict:
    try:
        from scripts.report_source_contract import body_hash, title_for, validate_saved_body
        from scripts.sync_latest_report_publication import validate_sop_body
    except ModuleNotFoundError:
        from report_source_contract import body_hash, title_for, validate_saved_body
        from sync_latest_report_publication import validate_sop_body
    docid = item["id"]
    doc = get_json(session, f"{DOCS}/documents/{docid}",
                   {"fields": "documentId,title,revisionId,body(content)"})
    if doc.get("documentId") != docid or doc.get("title") != item.get("name"):
        raise RuntimeError(f"Docs identity/title changed: {date} {slot}")
    drive_after = get_json(session, f"{DRIVE}/files/{docid}", {
        "fields": "id,name,mimeType,parents,createdTime,modifiedTime,headRevisionId,appProperties"
    })
    if drive_after.get("id") != docid or drive_after.get("name") != item.get("name"):
        raise RuntimeError(f"Drive identity/title changed during Docs readback: {date} {slot}")
    for field in ("createdTime", "modifiedTime", "headRevisionId", "appProperties"):
        before = item.get(field)
        after = drive_after.get(field)
        if before and after != before:
            raise RuntimeError(f"Drive {field} changed during Docs readback: {date} {slot}")
        item[field] = after
    full_text = paragraph_text(doc)
    result = {
        "date": date,
        "time": slot,
        "title": title_for(date, slot),
        "fullText": full_text,
        "sourceDocument": {
            "id": docid,
            "url": f"https://docs.google.com/document/d/{docid}/edit"
        },
        "report_status": "SOURCE_ARCHIVED",
        "infographic_status": "NOT_VERIFIED",
        "structuredFromFullText": False,
        "revision": 1,
        "bodyHash": body_hash(full_text),
        "sourceRevisionId": doc.get("revisionId") or item.get("headRevisionId"),
        "sourceCreatedAt": item.get("createdTime"),
        "sourceModifiedAt": item.get("modifiedTime"),
    }
    validate_saved_body(result)
    validate_sop_body(result)
    return result


def publication_evidence(root: Path, report: dict, item: dict, *, require_issuance_binding: bool = False) -> tuple[dict | None, str | None]:
    """Return a strict contemporaneous receipt, or a fail-closed hold reason."""
    from reporting.publication_evidence import verify_slot_evidence
    evidence_path = root / "data" / "report-evidence" / f"{report['date']}_{report['time'].replace(':', '-')}-r{report['revision']}.json"
    try:
        receipt = verify_slot_evidence(report, evidence_path, item, str(report.get("sourceRevisionId") or ""))
        if require_issuance_binding:
            from reporting.importer_handoff import validate_docs_issuance_binding
            validate_docs_issuance_binding(item.get("appProperties"), report, receipt)
        return receipt, None
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return None, str(exc)

def import_exact_issuance_doc(root: Path, *, report: dict, docs, session) -> tuple[dict, dict]:
    """Import exactly one already-read-back issuance Doc, without a 3-day scan.

    The normal scheduled importer remains unchanged. This narrow entry point is
    for the issuance transaction and requires the precise Docs ID/revision and
    appProperties supplied by the caller.
    """
    try:
        from scripts.reporting.importer_handoff import validate_docs_issuance_binding
        from scripts.reporting.publication_evidence import validate_receipt
    except ModuleNotFoundError:
        from reporting.importer_handoff import validate_docs_issuance_binding
        from reporting.publication_evidence import validate_receipt

    report_id = report.get("report_id")
    date, slot = report.get("date"), report.get("time")
    expected_id = f"{date}_{str(slot).replace(':', '-')}"
    if report_id != expected_id or slot != "08:00" or type(report.get("revision")) is not int or report["revision"] <= 0:
        raise RuntimeError("ISSUANCE_TARGET_IDENTITY_INVALID")
    title = f"マーケットレポート_{date}_{slot.replace(':', '-')}"
    query = ("name = '" + title.replace("\\", "\\\\").replace("'", "\\'") +
             "' and mimeType = 'application/vnd.google-apps.document' and trashed = false")
    found = get_json(session, DRIVE + "/files", {
        "q": query, "fields": FIELDS, "pageSize": 100,
    }).get("files", [])
    if len(found) != 1 or found[0].get("id") != docs.document_id:
        raise RuntimeError("ISSUANCE_DOC_DUPLICATE_OR_ID_MISMATCH")
    item = found[0]
    rebuilt = build_report(session, date, slot, item)
    rebuilt["report_id"] = report_id
    rebuilt["revision"] = report.get("revision")
    if (rebuilt.get("sourceRevisionId") != docs.document_revision_id or
            rebuilt.get("fullText") != report.get("fullText") or
            rebuilt.get("bodyHash") != report.get("bodyHash")):
        raise RuntimeError("ISSUANCE_DOC_REVISION_OR_BODY_CHANGED")
    validate_docs_issuance_binding(item.get("appProperties"), report, {
        "evidenceId": report.get("evidence_id"),
        "snapshotId": report.get("snapshot_id"),
    })
    evidence_path = root / "data" / "report-evidence" / f"{date}_{slot.replace(':', '-')}-r{report['revision']}.json"
    receipt = verify_issuance_evidence(report, evidence_path, item, rebuilt["sourceRevisionId"])
    rebuilt["report_status"] = "DOC_READBACK_PASS"
    rebuilt["publicationEvidence"] = {key: receipt[key] for key in (
        "evidenceId", "snapshotId", "contextHash", "snapshotHash", "bodyHash", "documentRevisionId"
    )}
    validate_receipt(receipt, rebuilt)
    canonical_path = root / "reports" / f"{date}_{slot.replace(':', '-')}.json"
    receipt_path = root / "publication-receipts" / f"{date}_{slot.replace(':', '-')}.json"
    if canonical_path.exists() or receipt_path.exists():
        if not canonical_path.is_file() or not receipt_path.is_file():
            raise RuntimeError("ISSUANCE_PARTIAL_CANONICAL_CONFLICT")
        existing_report = read_json(canonical_path)
        existing_receipt = read_json(receipt_path)
        identity_fields = ("report_id", "date", "time", "revision", "bodyHash", "fullText", "sourceDocument", "publicationEvidence")
        if any(existing_report.get(key) != rebuilt.get(key) for key in identity_fields):
            raise RuntimeError("ISSUANCE_CANONICAL_CONFLICT")
        if any(existing_receipt.get(key) != receipt.get(key) for key in (
            "reportId", "revision", "driveFileId", "documentRevisionId", "bodyHash", "evidenceId", "snapshotId"
        )):
            raise RuntimeError("ISSUANCE_RECEIPT_CONFLICT")
        rebuilt, receipt = existing_report, existing_receipt
    else:
        save_json(canonical_path, rebuilt)
        save_json(receipt_path, receipt)
        if read_json(canonical_path) != rebuilt or read_json(receipt_path) != receipt:
            raise RuntimeError("ISSUANCE_CANONICAL_READBACK_FAILED")
    return rebuilt, receipt

def verify_issuance_evidence(report: dict, evidence_path: Path, item: dict, revision: str) -> dict:
    """Run the established evidence verifier and strict Docs issuance binding."""
    try:
        from scripts.reporting.publication_evidence import verify_slot_evidence
        from scripts.reporting.importer_handoff import validate_docs_issuance_binding
    except ModuleNotFoundError:
        from reporting.publication_evidence import verify_slot_evidence
        from reporting.importer_handoff import validate_docs_issuance_binding
    receipt = verify_slot_evidence(report, evidence_path, item, revision)
    validate_docs_issuance_binding(item.get("appProperties"), report, receipt)
    return receipt

def poll(root: Path, *, apply: bool, enforce_slot: bool, require_issuance_binding: bool = False):
    from reporting.ingestion_outcome import format_ingestion_status_lines
    from build_reports import _verified_source_revision
    now = datetime.now(JST)
    env = read_json(root / "data/latest-report.json")
    old_latest = env.get("latestReport")
    if not isinstance(old_latest, dict):
        raise RuntimeError("missing existing publication latestReport")
    session = open_session()
    try:
        # Locate the owner-authoritative month folder first; the service
        # account's inherited read access is verified through this lookup.
        month_folder_name = f"マーケットレポート{now.year}年{now.month}月"
        folders = get_json(session, DRIVE + "/files", {
            "q": "name = '" + month_folder_name + "' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            "fields": "nextPageToken,files(id,name,mimeType)",
            "pageSize": 100
        })
        folder_matches = folders.get("files", [])
        if len(folder_matches) > 1:
            raise RuntimeError(f"multiple accessible monthly report folders: {month_folder_name}")
        folder_id = folder_matches[0]["id"] if folder_matches else None
        folder_access = bool(folder_id)
        source_files, scanned = eligible_sources(session, now, folder_id=folder_id)
        print(f"Google Drive scan: {scanned} accessible report-name candidates; "
              f"{len(source_files)} recent slots; monthly_folder_access={folder_access}; "
              f"authoritative_folder_scoped={folder_access}")
        to_write = {}
        to_promote = {}
        invalid_sources = {}
        for key, matches in sorted(source_files.items()):
            path = root / "reports" / f"{key[0]}_{key[1].replace(':','-')}.json"
            if path.exists():
                # Once a canonical source has been established, its document ID
                # is the authority. A duplicate file with the same display
                # name must not make future report publishing fail globally.
                canonical = read_json(path)
                canonical_id = canonical.get("sourceDocument", {}).get("id")
                anchored = [candidate for candidate in matches
                            if candidate["id"] == canonical_id]
                if not canonical_id:
                    # Older reports often predate the sourceDocument field.
                    # Preserve their canonical content and flag for separate
                    # manual provenance audit; never adopt a new source ID.
                    print(f"EXISTING_CANONICAL_LEGACY_NO_SOURCE_ID: {key}; preserving archive")
                    continue
                if len(anchored) != 1:
                    # An old archive may be linked to a different Doc or a
                    # since-removed source. Do not overwrite or adopt another
                    # Doc; report as a conflict without blocking new slots.
                    print(f"EXISTING_CANONICAL_SOURCE_NOT_IN_MONTH_FOLDER: {key}; preserving archive")
                    continue
                if len(matches) > 1:
                    print(f"EXISTING_CANONICAL_NAME_DUPLICATE: {key}; "
                          f"anchored source retained, extra_docs={len(matches)-1}")
                # Preserve canonical text. A previously archived source can
                # only move forward after exact readback plus contemporaneous
                # snapshot evidence is independently verified.
                from reporting.publication_evidence import is_canonical_document
                if (canonical.get("report_status") == "SOURCE_ARCHIVED" and
                        is_canonical_document(anchored, canonical_id)):
                    try:
                        rebuilt = build_report(session, *key, anchored[0])
                        _verified_source_revision(rebuilt)
                    except (ValueError, SystemExit) as exc:
                        print(f"SOURCE_READBACK_BLOCKED: {key}: {exc}")
                        continue
                    if (rebuilt.get("bodyHash") != canonical.get("bodyHash") or
                            rebuilt.get("fullText") != canonical.get("fullText") or
                            rebuilt.get("sourceDocument") != canonical.get("sourceDocument")):
                        print(f"SOURCE_ARCHIVED_READBACK_CONFLICT: {key}; preserving canonical")
                        continue
                    receipt, hold = publication_evidence(root, rebuilt, anchored[0], require_issuance_binding=require_issuance_binding)
                    if receipt is None:
                        print(f"PUBLICATION_HELD: {key[0]} {key[1]}: {hold}")
                        continue
                    promoted = dict(canonical)
                    promoted["report_status"] = "DOC_READBACK_PASS"
                    promoted["publicationEvidence"] = {k: receipt[k] for k in (
                        "evidenceId", "snapshotId", "contextHash", "snapshotHash", "bodyHash", "documentRevisionId"
                    )}
                    receipt_path = root / "publication-receipts" / f"{key[0]}_{key[1].replace(':','-')}.json"
                    if receipt_path.exists() and read_json(receipt_path) != receipt:
                        print(f"PUBLICATION_RECEIPT_CONFLICT: {key}; canonical remains archived")
                        continue
                    to_promote[key] = (promoted, receipt)
                    continue
                # Published/legacy sources remain immutable and unchanged.
                continue
            if len(matches) != 1:
                # A new slot has no established document ID; conflicting
                # names cannot safely be assigned to a canonical source.
                raise RuntimeError(f"ambiguous new report with multiple Google Docs: {key}")
            item = matches[0]
            try:
                new_report = build_report(session, *key, item)
                _verified_source_revision(new_report)
            except (ValueError, SystemExit) as exc:
                # A historical source that does not satisfy the actual SOP
                # must not block independent, valid new reports.
                # The rejected document is never published or silently fixed.
                invalid_sources[key] = str(exc)
                print(f"SOURCE_VALIDATION_BLOCKED: {key[0]} {key[1]}: {exc}")
                continue
            receipt, hold = publication_evidence(root, new_report, item, require_issuance_binding=require_issuance_binding)
            if receipt is not None:
                new_report["report_status"] = "DOC_READBACK_PASS"
                new_report["publicationEvidence"] = {k: receipt[k] for k in (
                    "evidenceId", "snapshotId", "contextHash", "snapshotHash", "bodyHash", "documentRevisionId"
                )}
            else:
                print(f"PUBLICATION_HELD: {key[0]} {key[1]}: {hold}")
            to_write[key] = (new_report, receipt)
        if enforce_slot:
            # After a scheduled report's 40-minute completion window, ensure
            # its source exists, rather than silently succeeding with old data.
            today = now.date().isoformat()
            due = [t for t in SLOTS if datetime.fromisoformat(
                today + "T" + t + ":00+09:00") + timedelta(minutes=40) <= now]
            if due:
                expected = (today, due[-1])
                target = root / "reports" / f"{today}_{due[-1].replace(':','-')}.json"
                if expected in invalid_sources:
                    raise RuntimeError(f"REQUIRED_REPORT_SOURCE_INVALID: {expected}; {invalid_sources[expected]}")
                if expected not in source_files and not target.exists():
                    raise RuntimeError(
                        f"REPORT_SOURCE_MISSING {today} {due[-1]}; "
                        f"monthly_folder_access={folder_access}. "
                        "Share the monthly report folder with the service account "
                        "or share each newly saved Google Doc before its ingestion."
                    )
        print(json.dumps({
            "mode": "APPLY" if apply else "DRY_RUN",
            "new_slots": [f"{date} {slot}" for date,slot in sorted(to_write)],
            "promotion_slots": [f"{date} {slot}" for date,slot in sorted(to_promote)],
            "folder_access": folder_access,
        }, ensure_ascii=False))
        if not apply or (not to_write and not to_promote):
            return
        # Stage append-only canonical files. No overwrite, no older latest.
        for key, (report, receipt) in sorted(to_write.items()):
            path = root / "reports" / f"{key[0]}_{key[1].replace(':','-')}.json"
            if path.exists():
                raise RuntimeError("canonical changed during scan")
            save_json(path, report)
            if receipt is not None:
                save_json(root / "publication-receipts" / f"{key[0]}_{key[1].replace(':','-')}.json", receipt)
        for key, (report, receipt) in sorted(to_promote.items()):
            save_json(root / "reports" / f"{key[0]}_{key[1].replace(':','-')}.json", report)
            save_json(root / "publication-receipts" / f"{key[0]}_{key[1].replace(':','-')}.json", receipt)
        # Import is archive-first. Only reports that passed the pre-draft
        # snapshot, exact Docs readback, and existing body/SOP gate are eligible
        # for latest/dashboard; the existing publication selector applies them.
        subprocess.run([sys.executable, "scripts/sync_latest_report_publication.py"],
                       cwd=root, check=True)
        subprocess.run([sys.executable, "scripts/build_reports.py", "--canonical-only"],
                       cwd=root, check=True)
        subprocess.run([sys.executable, "scripts/verify_publication_consistency.py"],
                       cwd=root, check=True)
        for line in format_ingestion_status_lines(to_write, to_promote):
            print(line)
    finally:
        session.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--enforce-slot", action="store_true")
    ap.add_argument("--root", type=Path, help="isolated checkout root; requires --require-issuance-binding")
    ap.add_argument("--require-issuance-binding", action="store_true", help="require exact G2 identity/body/evidence appProperties on the Docs file")
    args = ap.parse_args()
    if args.root is not None and not args.require_issuance_binding:
        ap.error("--root is only allowed with --require-issuance-binding")
    if args.require_issuance_binding and args.root is None:
        ap.error("--require-issuance-binding requires an isolated --root")
    root = ROOT
    if args.root is not None:
        from reporting.importer_handoff import validate_staging_root
        try:
            root = validate_staging_root(args.root, importer_root=ROOT)
        except ValueError as exc:
            ap.error(str(exc))
    poll(root, apply=args.apply, enforce_slot=args.enforce_slot,
         require_issuance_binding=args.require_issuance_binding)

if __name__ == "__main__":
    main()
