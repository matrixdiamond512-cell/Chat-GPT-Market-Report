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

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))
SLOTS = ("08:00", "12:00", "16:00", "21:00")
# Monthly report folder is discovered by name, not a fixed October ID.
SOURCE = re.compile(r"^マーケットレポート_(\d{4}-\d{2}-\d{2})_(08|12|16|21)-00$")
FIELDS = "nextPageToken,files(id,name,mimeType,parents)"
DRIVE = "https://www.googleapis.com/drive/v3"
DOCS = "https://docs.googleapis.com/v1"

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def open_session() -> AuthorizedSession:
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
    from report_source_contract import body_hash, title_for, validate_saved_body
    from sync_latest_report_publication import validate_sop_body
    docid = item["id"]
    doc = get_json(session, f"{DOCS}/documents/{docid}",
                   {"fields": "documentId,title,body(content)"})
    if doc.get("documentId") != docid or doc.get("title") != item.get("name"):
        raise RuntimeError(f"Docs identity/title changed: {date} {slot}")
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
    }
    validate_saved_body(result)
    validate_sop_body(result)
    return result

def poll(root: Path, *, apply: bool, enforce_slot: bool):
    from report_identity import internal_report_key
    from build_reports import _verified_source_revision
    from sync_latest_report_publication import sync_dashboard
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
        latest_slot = (old_latest["date"], old_latest["time"])
        to_write = {}
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
                # Preserve already published source text and revision. Never
                # replace it by a separately parsed version from Google Docs.
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
            to_write[key] = new_report
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
            "folder_access": folder_access,
        }, ensure_ascii=False))
        if not apply or not to_write:
            return
        # Stage append-only canonical files. No overwrite, no older latest.
        for key, report in sorted(to_write.items()):
            path = root / "reports" / f"{key[0]}_{key[1].replace(':','-')}.json"
            if path.exists():
                raise RuntimeError("canonical changed during scan")
            save_json(path, report)
        newest = max(to_write)
        if newest > latest_slot:
            selected = to_write[newest]
            env["latestReport"] = selected
            env["dataAsOf"] = f"{newest[0]}T{newest[1]}:00+09:00"
            save_json(root / "data/latest-report.json", env)
            sync_dashboard(selected)
        subprocess.run([sys.executable, "scripts/build_reports.py", "--canonical-only"],
                       cwd=root, check=True)
        subprocess.run([sys.executable, "scripts/verify_publication_consistency.py"],
                       cwd=root, check=True)
        print("CANONICAL_REPORT_INGESTION_VERIFIED: "+", ".join(
            internal_report_key(to_write[x]) for x in sorted(to_write)))
    finally:
        session.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--enforce-slot", action="store_true")
    args = ap.parse_args()
    poll(ROOT, apply=args.apply, enforce_slot=args.enforce_slot)

if __name__ == "__main__":
    main()
