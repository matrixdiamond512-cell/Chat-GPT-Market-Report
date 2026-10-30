#!/usr/bin/env python3
"""Safely synchronize only the market-report Apps Script files into an EXISTING project.

Dry-run first and record the project SHA-256. Apply requires an exact expected SHA
as an optimistic concurrency guard. All unrelated Apps Script files are preserved.
Credentials are supplied from GitHub Actions secrets, never written to disk.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_FILES = (
    "MarketReportAutoPublish",
    "MarketReportMasterScheduler",
    "MarketReportWebSync",
    "MarketReportPrePublishValidation",
)
API = "https://script.googleapis.com/v1/projects/{script_id}/content"


def canonical_files(files):
    """Allow updateContent input fields only, excluding read-only response metadata."""
    return [
        {"name": item["name"], "type": item["type"], "source": item.get("source", "")}
        for item in files
    ]


def digest(files):
    value = json.dumps(canonical_files(files), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def prepare_update(remote_files, root=ROOT):
    """Replace only the designated source files while preserving every other file."""
    files = canonical_files(remote_files)
    seen = {item["name"] for item in files}
    absent = [name for name in TARGET_FILES if name not in seen]
    if absent:
        raise ValueError("Apps Script project missing required files: " + ", ".join(absent))
    for item in files:
        if item["name"] in TARGET_FILES:
            if item["type"] != "SERVER_JS":
                raise ValueError("Unexpected Apps Script file type: " + item["name"])
            path = root / "apps-script" / (item["name"] + ".gs")
            item["source"] = path.read_text(encoding="utf-8")
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-project-sha256", default="")
    args = parser.parse_args()
    script_id = os.environ.get("APPS_SCRIPT_ID", "").strip()
    raw = os.environ.get("APPS_SCRIPT_OAUTH_JSON", "").strip()
    if not script_id or not raw:
        raise SystemExit("Missing APPS_SCRIPT_ID or APPS_SCRIPT_OAUTH_JSON. No changes made.")
    try:
        info = json.loads(raw)
        if info.get("type") != "authorized_user":
            raise ValueError("OAuth authorized_user credentials required, not a service account")
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import AuthorizedSession
        creds = Credentials.from_authorized_user_info(
            info, scopes=["https://www.googleapis.com/auth/script.projects"])
        session = AuthorizedSession(creds)
        endpoint = API.format(script_id=script_id)
        response = session.get(endpoint, timeout=30)
        response.raise_for_status()
        remote = response.json().get("files", [])
        if not remote:
            raise ValueError("Remote Apps Script content was empty")
        before_sha = digest(remote)
        desired = prepare_update(remote)
        changed = [name for name in TARGET_FILES if next(x for x in remote if x["name"] == name).get("source", "")
                   != next(x for x in desired if x["name"] == name)["source"]]
        print(json.dumps({"status": "READY_TO_APPLY" if changed else "ALREADY_SYNCED",
                          "remote_project_sha256": before_sha, "changed_files": changed,
                          "file_count_preserved": len(remote), "apply_requested": args.apply},
                         ensure_ascii=False))
        if not args.apply:
            return
        if not args.expected_project_sha256 or args.expected_project_sha256 != before_sha:
            raise ValueError("Remote project SHA-256 differs from operator-approved dry-run; no update")
        if not changed:
            return
        # Immediately re-read before the write, to reduce unexpected concurrent edits.
        reread = session.get(endpoint, timeout=30)
        reread.raise_for_status()
        if digest(reread.json().get("files", [])) != before_sha:
            raise ValueError("Remote Apps Script files changed since preflight; no update")
        put = session.put(endpoint, json={"files": desired}, timeout=60)
        put.raise_for_status()
        verify = session.get(endpoint, timeout=30)
        verify.raise_for_status()
        after = canonical_files(verify.json().get("files", []))
        if digest(after) != digest(desired):
            raise ValueError("UPDATE_READBACK_MISMATCH: do not claim deployment succeeded")
        print(json.dumps({"status": "SOURCE_SYNC_VERIFIED", "changed_files": changed,
                          "project_sha256": digest(after)}, ensure_ascii=False))
        print("NOTE: Source sync does not install triggers or prove Google Drive→GitHub publication.")
    except Exception as exc:
        # Never print raw credentials, OAuth tokens, or HTTP response content.
        raise SystemExit("Apps Script sync FAILED (" + type(exc).__name__ + "). No success claimed.")


if __name__ == "__main__":
    main()
