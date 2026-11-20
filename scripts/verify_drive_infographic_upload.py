#!/usr/bin/env python3
"""Check that a scheduled infographic PNG actually exists in Google Drive.

Separate from canonical/receipt checks: a successful GitHub build or a PNG
manifest is never evidence that Drive contains the original PNG bytes.
Uses the already configured read-only GOOGLE_SERVICE_ACCOUNT_JSON secret.
"""
from __future__ import annotations

import argparse
from datetime import date as calendar_date, datetime, timedelta, timezone
import hashlib
import json
import os
import struct

JST = timezone(timedelta(hours=9))
SCHEDULES = {
    "45 23 * * 0-4": "08:00",
    "45 3 * * 1-5": "12:00",
    "45 7 * * 1-5": "16:00",
    "45 12 * * 1-5": "21:00",
}
SLOTS = {"08:00", "12:00", "16:00", "21:00"}
DRIVE_API = "https://www.googleapis.com/drive/v3"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def expected_identity(day: str, slot: str) -> tuple[str, str]:
    checked = calendar_date.fromisoformat(day)
    if slot not in SLOTS:
        raise ValueError("Unknown slot: " + slot)
    month_folder = f"マーケットレポート図解{checked.year}年{checked.month}月"
    image_name = f"マーケットレポート_{day}_{slot.replace(':', '-')}.png"
    return month_folder, image_name


def choose_slot(slot: str, schedule: str) -> str:
    if schedule:
        if schedule not in SCHEDULES:
            raise ValueError("Unknown scheduled cron: " + schedule)
        return SCHEDULES[schedule]
    if slot not in SLOTS:
        raise ValueError("Missing or invalid manually requested slot")
    return slot


def quote_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def require_unique(items: list[dict], label: str) -> dict:
    if len(items) != 1:
        raise ValueError(f"{label}: expected exactly one item, found {len(items)}")
    return items[0]


def validate_png_bytes(data: bytes, reported_size: str) -> dict:
    if len(data) < 512 or not data.startswith(PNG_SIGNATURE):
        raise ValueError("Drive image data is missing, truncated or not PNG")
    if int(reported_size or 0) != len(data):
        raise ValueError("Drive image size differs from fetched bytes")
    width, height = struct.unpack(">II", data[16:24])
    if width < 100 or height < 100 or width > 20000 or height > 20000:
        raise ValueError("Drive image has invalid dimensions")
    return {
        "sizeBytes": len(data),
        "width": width,
        "height": height,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def read_session():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is missing; live Drive check cannot pass")
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return AuthorizedSession(creds)


def list_exact(session, *, name: str, mime: str, folder: str | None = None) -> list[dict]:
    q = (
        f"name = '{quote_query(name)}' and "
        f"mimeType = '{quote_query(mime)}' and trashed = false"
    )
    if folder:
        q += f" and '{quote_query(folder)}' in parents"
    response = session.get(DRIVE_API + "/files", params={
        "q": q,
        "fields": "nextPageToken,files(id,name,mimeType,size,parents,md5Checksum)",
        "pageSize": 100,
    }, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("nextPageToken"):
        raise RuntimeError("Too many matching Drive files; ambiguous identity")
    return payload.get("files") or []


def check_drive_png(session, day: str, slot: str) -> dict:
    folder_name, image_name = expected_identity(day, slot)
    folder = require_unique(
        list_exact(session, name=folder_name, mime="application/vnd.google-apps.folder"),
        "DRIVE_INFOGRAPHIC_FOLDER_AMBIGUOUS_OR_MISSING",
    )
    image = require_unique(
        list_exact(session, name=image_name, mime="image/png", folder=folder["id"]),
        "DRIVE_INFOGRAPHIC_MISSING_OR_DUPLICATED",
    )
    if folder["id"] not in image.get("parents", []):
        raise ValueError("DRIVE_INFOGRAPHIC_WRONG_PARENT")
    response = session.get(
        DRIVE_API + "/files/" + image["id"],
        params={"alt": "media"}, timeout=45
    )
    response.raise_for_status()
    result = validate_png_bytes(response.content, str(image.get("size") or ""))
    return {
        "status": "DRIVE_PNG_VERIFIED",
        "date": day,
        "slot": slot,
        "fileId": image["id"],
        "fileName": image_name,
        "folderId": folder["id"],
        "folderName": folder_name,
        "source": "Drive files.list + files.get(alt=media)",
        **result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", default="")
    parser.add_argument("--schedule", default="")
    parser.add_argument("--date", default="")
    args = parser.parse_args()
    slot = choose_slot(args.slot, args.schedule)
    day = args.date or datetime.now(JST).date().isoformat()
    result = check_drive_png(read_session(), day, slot)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
