#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

DOC_URL_RE = re.compile(r"^https://docs\.google\.com/document/d/([A-Za-z0-9_-]+)/")


def load_latest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = payload.get("latestReport", payload)
    if not isinstance(report, dict):
        raise SystemExit(f"{path}: latest report is not an object")
    for key in ("date", "time", "title"):
        if not str(report.get(key, "")).strip():
            raise SystemExit(f"{path}: latest report missing {key}")
    return report


def parse_slot(date_text: str, time_text: str) -> datetime:
    return datetime.fromisoformat(f"{date_text}T{time_text}:00+09:00")


def receipt_path(root: Path, report: dict) -> Path:
    return root / f"{report['date']}_{str(report['time']).replace(':', '-')}.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", default="data/latest-report.json")
    parser.add_argument("--receipts", default="publication-receipts")
    parser.add_argument("--enforce-from", required=True)
    parser.add_argument("--require-publisher", default="chatgpt")
    args = parser.parse_args()

    report = load_latest(Path(args.latest))
    slot = parse_slot(str(report["date"]), str(report["time"]))
    enforce_from = datetime.fromisoformat(args.enforce_from)
    if slot < enforce_from:
        print(f"Drive receipt guard not enforced for legacy slot {report['date']} {report['time']}")
        return

    path = receipt_path(Path(args.receipts), report)
    if not path.exists():
        raise SystemExit(
            f"publication blocked: Google Drive receipt is missing for {report['date']} {report['time']}: {path}"
        )

    receipt = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "date", "time", "title", "status", "publisher", "driveFileId", "driveUrl", "savedAt"
    }
    missing = sorted(key for key in required if not str(receipt.get(key, "")).strip())
    if missing:
        raise SystemExit(f"{path}: required receipt fields missing/blank: {', '.join(missing)}")

    for key in ("date", "time", "title"):
        if receipt[key] != report[key]:
            raise SystemExit(f"{path}: {key} does not match latest report")

    if receipt["status"] != "saved":
        raise SystemExit(f"{path}: status must be 'saved'")
    if receipt["publisher"] != args.require_publisher:
        raise SystemExit(
            f"{path}: publisher must be {args.require_publisher!r}; got {receipt['publisher']!r}"
        )

    match = DOC_URL_RE.match(receipt["driveUrl"])
    if not match:
        raise SystemExit(f"{path}: driveUrl is not a Google Docs URL")
    if match.group(1) != receipt["driveFileId"]:
        raise SystemExit(f"{path}: driveFileId does not match driveUrl")

    try:
        saved_at = datetime.fromisoformat(receipt["savedAt"])
    except ValueError as exc:
        raise SystemExit(f"{path}: savedAt must be ISO-8601: {exc}")
    if saved_at.tzinfo is None:
        raise SystemExit(f"{path}: savedAt must include timezone")
    if saved_at < slot:
        raise SystemExit(f"{path}: savedAt precedes report slot")

    print(
        "Drive publication receipt verified: "
        f"{report['date']} {report['time']} -> {receipt['driveFileId']} ({receipt['publisher']})"
    )


if __name__ == "__main__":
    main()
