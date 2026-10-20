#!/usr/bin/env python3
"""Fail closed when the Drive latest-saved source reference would imply publication."""
from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "drive-source-selection.json"
KEY = re.compile(r"^20\d{2}-\d{2}-\d{2}_\d{2}-\d{2}$")
DOC = re.compile(r"^マーケットレポート_(20\d{2}-\d{2}-\d{2}_\d{2}-\d{2})$")
IMAGE = re.compile(r"^マーケットレポート_(20\d{2}-\d{2}-\d{2}_\d{2}-\d{2})\.png$")

def main() -> int:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != 1 or data.get("formalPublicationUnchanged") is not True:
        raise SystemExit("Source inventory must not be described as formal publication")
    items = data.get("items")
    if not isinstance(items, list) or len(items) != 21:
        raise SystemExit("Expected 21 source selections")
    seen = set()
    kinds = {"document": 0, "image": 0}
    for row in items:
        key, kind = row["slotKey"], row["kind"]
        if not KEY.fullmatch(key) or kind not in kinds:
            raise SystemExit("Invalid source selection key or kind")
        if (key, kind) in seen:
            raise SystemExit("Duplicate latest saved source for " + key)
        seen.add((key, kind))
        kinds[kind] += 1
        pattern = DOC if kind == "document" else IMAGE
        matched = pattern.fullmatch(row["filename"])
        if not matched or matched[1] != key or row["candidateCount"] < 2:
            raise SystemExit("Drive filename or duplicate candidate mismatch: " + key)
        recorded = datetime.fromisoformat(row["driveCreatedAt"].replace("Z", "+00:00"))
        if recorded.tzinfo is None:
            raise SystemExit("Naive Drive creation time")
        if not str(row.get("driveFileId") or "") or not str(row.get("driveMonthFolderId") or ""):
            raise SystemExit("Missing Drive file or parent ID: " + key)
        parsed = urlparse(row["driveUrl"])
        if parsed.scheme != "https" or parsed.hostname not in {"docs.google.com", "drive.google.com"}:
            raise SystemExit("Invalid Drive URL: " + key)
        if row["driveFileId"] not in parsed.path:
            raise SystemExit("URL/source ID mismatch: " + key)
        if kind == "document":
            length = row.get("checkedBodyCharacters")
            if not isinstance(length, int) or length < 0:
                raise SystemExit("Missing source text length: " + key)
            expected = "STRUCTURE_CHECK_PASSED" if length >= 1200 else "INCOMPLETE_OR_EMPTY"
            if row.get("bodyCheck") != expected:
                raise SystemExit("Source length classification mismatch: " + key)
            if row.get("publicationDecision") != "PENDING_EVIDENCE_AND_REVISION_VALIDATION":
                raise SystemExit("Document must not be auto-promoted: " + key)
        else:
            if row.get("mimeType") != "image/png" or row.get("publicationDecision") != "PENDING_IMAGE_HASH_MANIFEST_VALIDATION":
                raise SystemExit("PNG must not be promoted without image hash and manifest")
    if kinds != {"document": 18, "image": 3}:
        raise SystemExit("Expected 18 document sources and 3 PNG sources")
    html = (ROOT / "report.html").read_text(encoding="utf-8")
    if 'src="assets/js/report-drive-source-reference.js' not in html or 'href="drive-source-selection.html"' not in html:
        raise SystemExit("Portal references are not wired into report.html")
    for file in ("assets/js/report-drive-source-reference.js", "drive-source-selection.html"):
        if not (ROOT / file).is_file():
            raise SystemExit("Source reference asset missing: " + file)
    print("Drive latest-saved selection validated: 18 Docs, 3 PNG, publication unchanged.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
