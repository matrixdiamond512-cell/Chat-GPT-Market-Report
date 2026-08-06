import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.validate_weekly_claims_result import process


JST = ZoneInfo("Asia/Tokyo")
OFFICIAL_TEXT = """
UNEMPLOYMENT INSURANCE WEEKLY CLAIMS
Thursday, August 6, 2026
In the week ending August 1, the advance figure for seasonally adjusted initial claims was 199,000.
The previous week's level was revised up by 1,000 from 197,000 to 198,000.
"""


class ValidateWeeklyClaimsResultTest(unittest.TestCase):
    def write_payload(self, root: Path) -> None:
        path = root / "data/events/latest.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": "2.0.0",
                    "pageId": "events",
                    "generatedAt": "2026-08-06T22:18:32+09:00",
                    "timezone": "Asia/Tokyo",
                    "sources": [],
                    "errors": [],
                    "events": [
                        {
                            "id": "claims",
                            "date": "2026-08-06",
                            "time": "21:30",
                            "datetimeJst": "2026-08-06T21:30:00+09:00",
                            "currency": "USD",
                            "title": "米新規失業保険申請件数",
                            "eventNameOriginal": "Unemployment Claims",
                            "category": "employment",
                            "forecast": "203K",
                            "previous": "197K",
                            "actual": "1801K",
                            "revised": "",
                            "status": "released",
                            "resultSource": {
                                "id": "tradingview_repair",
                                "name": "Department of Labour",
                                "url": "http://www.dol.gov",
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_official_pdf_overrides_continuing_claims_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_payload(root)
            summary = process(
                root,
                dt.datetime(2026, 8, 6, 22, 30, tzinfo=JST),
                supplied_pdf_text=OFFICIAL_TEXT,
            )
            payload = json.loads((root / "data/events.json").read_text(encoding="utf-8"))
            event = payload["events"][0]
            self.assertEqual(event["actual"], "199K")
            self.assertEqual(event["revised"], "198K")
            self.assertEqual(event["status"], "released")
            self.assertEqual(event["resultSource"]["id"], "us_dol_claims_pdf")
            self.assertEqual(event["resultValidation"], "official_pdf_verified")
            self.assertEqual(summary["corrected"], 1)
            self.assertEqual(summary["cleared"], 0)

    def test_suspicious_provider_value_is_removed_without_official_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_payload(root)
            summary = process(
                root,
                dt.datetime(2026, 8, 6, 22, 30, tzinfo=JST),
                supplied_pdf_text="",
            )
            payload = json.loads((root / "data/events.json").read_text(encoding="utf-8"))
            event = payload["events"][0]
            self.assertEqual(event["actual"], "")
            self.assertEqual(event["status"], "result_pending")
            self.assertTrue(event["resultExplanation"].startswith("取得不能（"))
            self.assertEqual(event["resultFetchStatus"], "unavailable")
            self.assertNotIn("resultSource", event)
            self.assertEqual(summary["corrected"], 0)
            self.assertEqual(summary["cleared"], 1)


if __name__ == "__main__":
    unittest.main()
