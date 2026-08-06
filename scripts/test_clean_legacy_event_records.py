from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.clean_legacy_event_records import clean


JST = ZoneInfo("Asia/Tokyo")


class CleanLegacyEventRecordsTest(unittest.TestCase):
    def test_only_normalized_calendar_events_remain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data/events/history").mkdir(parents=True)
            normalized = {
                "id": "event-normalized",
                "sourceKey": "2026-08-06|21:30|USD|unemployment claims",
                "sourceType": "forex_factory_weekly",
                "date": "2026-08-06",
                "time": "21:30",
                "datetimeJst": "2026-08-06T21:30:00+09:00",
                "title": "米新規失業保険申請件数",
                "status": "released",
                "actual": "199K",
            }
            legacy_extract = {
                "id": "event-old-1",
                "sourceType": "market_report_extraction",
                "date": "2026-08-06",
                "time": "21:30",
                "datetimeJst": "2026-08-06T21:30:00+09:00",
                "title": "米新規失業保険申請件数",
                "status": "needs_result",
            }
            legacy_seed = {
                "id": "event-old-2",
                "sourceType": "market_report_manual_seed",
                "date": "2026-08-06",
                "time": "23:00",
                "datetimeJst": "2026-08-06T23:00:00+09:00",
                "title": "旧手入力イベント",
                "status": "needs_result",
            }
            payload = {
                "schemaVersion": "2.0.0",
                "pageId": "events",
                "generatedAt": "2026-08-06T22:22:07+09:00",
                "dataAsOf": "2026-08-06T22:22:07+09:00",
                "timezone": "Asia/Tokyo",
                "status": "ok",
                "isStale": False,
                "retention": {"days": 365},
                "sources": [],
                "errors": [],
                "events": [normalized, legacy_extract, legacy_seed],
            }
            for path in (
                root / "data/events/latest.json",
                root / "data/events.json",
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            (root / "data/events/history/2026-08-06.json").write_text(
                json.dumps({"date": "2026-08-06", "events": [normalized, legacy_extract, legacy_seed]}, ensure_ascii=False),
                encoding="utf-8",
            )

            summary = clean(root, dt.datetime(2026, 8, 6, 22, 30, tzinfo=JST))
            self.assertEqual(summary["events"], 1)
            self.assertEqual(summary["removed"], 2)

            latest = json.loads((root / "data/events/latest.json").read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in latest["events"]], ["event-normalized"])
            self.assertEqual(latest["days"][0]["eventCount"], 1)
            self.assertEqual(latest["legacyRecordsRemoved"], 2)

            history = json.loads((root / "data/events/history/2026-08-06.json").read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in history["events"]], ["event-normalized"])

            completed = json.loads((root / "data/events/completed.json").read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in completed["events"]], ["event-normalized"])

            clean(root, dt.datetime(2026, 8, 6, 22, 31, tzinfo=JST))
            latest_again = json.loads((root / "data/events/latest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(latest_again["events"]), 1)


if __name__ == "__main__":
    unittest.main()
