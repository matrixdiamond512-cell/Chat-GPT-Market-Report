#!/usr/bin/env python3
"""Validate browsable recovered history without granting official publication status."""
from __future__ import annotations
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data/report-recovery-2026-10.json"
FORMAL_INDEX = ROOT / "reports.json"
REQUIRED = {
    "2026-10-06_12-00", "2026-10-06_16-00",
    "2026-10-12_08-00", "2026-10-12_12-00",
    "2026-10-13_08-00", "2026-10-13_12-00", "2026-10-13_21-00",
    "2026-10-14_08-00", "2026-10-14_12-00",
    "2026-10-14_16-00", "2026-10-14_21-00",
    "2026-10-15_08-00", "2026-10-15_12-00",
    "2026-10-15_16-00", "2026-10-15_21-00",
    "2026-10-16_08-00", "2026-10-16_12-00",
    "2026-10-16_16-00", "2026-10-16_21-00",
}
RETROSPECTIVE = {"2026-10-06_12-00", "2026-10-06_16-00", "2026-10-13_12-00", "2026-10-16_12-00", "2026-10-16_16-00", "2026-10-16_21-00"}
POSTHOC_RETROSPECTIVES = {"2026-10-16_12-00", "2026-10-16_16-00", "2026-10-16_21-00"}
POSTHOC_RECORDED_AT = "2026-10-17T04:22:00+09:00"
DRIVE_READBACK_SUPPLEMENTS = {"2026-10-16_08-00"}


def fail(message: str) -> None:
    raise SystemExit("Recovery archive validation failed: " + message)


def main() -> int:
    data = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != 1 or data.get("kind") != "HISTORICAL_ARCHIVE_NOT_OFFICIAL_PUBLICATION":
        fail("schema and non-publication identity")
    items = data.get("reports")
    if not isinstance(items, list) or len(items) != len(REQUIRED):
        fail(f"expected exactly {len(REQUIRED)} source/retrospective entries")
    found: set[str] = set()
    indexed = json.loads(FORMAL_INDEX.read_text(encoding="utf-8"))
    public_ids = {f"{r['date']}_{r['time'].replace(':', '-')}" for r in indexed}
    if public_ids & REQUIRED:
        fail("recovery archive must not shadow officially indexed slots")

    for report in items:
        key = str(report.get("date", "")) + "_" + str(report.get("time", "")).replace(":", "-")
        if key in found or key not in REQUIRED:
            fail("duplicate or unexpected slot " + key)
        found.add(key)
        parsed = date.fromisoformat(report["date"])
        expected_title = f"マーケットレポート｜{parsed:%Y/%m/%d}（{'月火水木金土日'[parsed.weekday()]}）{report['time']}"
        full = report.get("fullText")
        if report.get("title") != expected_title or not isinstance(full, str) or not full.startswith(expected_title):
            fail("bad title or missing full text " + key)
        if len(full) < 600 or not str(report.get("archiveNotice", "")):
            fail("missing substantive text/provenance " + key)
        if report.get("archiveStatus") != "HISTORICAL_ARCHIVE" or report.get("verifiedAtSlot") is not False:
            fail("archive may not claim original verified publication " + key)
        if report.get("infographic_status") == "READY":
            fail("unverified infographic must not be shown " + key)
        if key in DRIVE_READBACK_SUPPLEMENTS:
            from datetime import datetime
            try:
                recorded = datetime.fromisoformat(report["recoveryRecordedAt"].replace("Z", "+00:00"))
                cutoff = datetime.fromisoformat("2026-10-16T08:40:00+09:00")
                if recorded.tzinfo is None or recorded < cutoff:
                    fail("invalid supplemental recovery timestamp " + key)
            except (ValueError, KeyError, TypeError):
                fail("missing supplemental recovery timestamp " + key)
        elif key in POSTHOC_RETROSPECTIVES:
            if (report.get("recoveryRecordedAt") != POSTHOC_RECORDED_AT
                or report.get("originalReportStatus") != "ORIGINAL_NOT_FOUND"
                or report.get("archiveType") != "RETROSPECTIVE_REPORT"):
                fail("posthoc retrospective identity/timestamp altered " + key)
        elif report.get("recoveryRecordedAt") != data["generatedAt"]:
            fail("original recovery timestamp altered " + key)
        canonical = ROOT / "reports" / (key + ".json")
        if key in RETROSPECTIVE:
            if key == "2026-10-13_12-00":
                if "【事後修復追補" not in full or "保存原本" not in full:
                    fail("missing partial-original warning " + key)
            elif report.get("archiveType") != "RETROSPECTIVE_REPORT" or not full.startswith(expected_title):
                fail("undisclosed retrospective " + key)
            if canonical.exists():
                fail("retrospective must not overwrite official canonical slot " + key)
        elif key in DRIVE_READBACK_SUPPLEMENTS:
            if canonical.exists():
                fail("supplemental readback must not overwrite canonical slot " + key)
            doc = report.get("sourceDocument") or {}
            doc_id = "1JBfE0AsvW5Ob_nA2lKDTLFAlYMhc8XbhasqwQ4oixdw"
            if (report.get("archiveType") != "DRIVE_SAVED_DOCUMENT"
                or report.get("originalReportStatus") != "DRIVE_DOC_READBACK_NOT_SLOT_VERIFIED"
                or doc.get("id") != doc_id
                or doc.get("url") != f"https://docs.google.com/document/d/{doc_id}/edit"
                or not report.get("driveRevisionId")
                or report.get("driveTextLength") != len(full)
                or not isinstance(report.get("missingAtSlotEvidence"), list)
                or not report.get("missingAtSlotEvidence")):
                fail("unverified supplemental document identity/readback " + key)
            if "補充発行版" not in full or "定時自動発行" not in full:
                fail("supplemental document must disclose late creation " + key)
        else:
            if not canonical.exists():
                fail("archived canonical source missing " + key)
            source = json.loads(canonical.read_text(encoding="utf-8"))
            if report.get("originalReportStatus") != source.get("report_status"):
                fail("status altered " + key)
            if report.get("originalBodyHash") != source.get("bodyHash"):
                fail("source identity altered " + key)
            if not full.startswith(source["fullText"]):
                fail("source full text altered " + key)
            if source.get("report_status") in {"PUBLISHED", "DOC_READBACK_PASS"}:
                fail("should not duplicate formally published source " + key)
    if found != REQUIRED:
        fail("missing slots " + str(sorted(REQUIRED - found)))
    print(f"PASS: {len(items)} recovered report slots; all existing full texts preserved; original publication gate unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
