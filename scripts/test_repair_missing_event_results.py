import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.repair_missing_event_results import (
    extract_claims_from_text,
    match_row,
    normalize_title,
    process,
)


JST = ZoneInfo("Asia/Tokyo")


class RepairMissingEventResultsTest(unittest.TestCase):
    def test_title_aliases(self):
        self.assertEqual(normalize_title("Unemployment Claims"), normalize_title("Initial Jobless Claims"))
        self.assertEqual(normalize_title("Spanish 10-y Bond Auction"), normalize_title("Spain 10 Year Government Bond Auction"))

    def test_match_claims_and_spanish_auction(self):
        rows = [
            {
                "country": "US",
                "date": "2026-08-06T12:30:00Z",
                "title": "Initial Jobless Claims",
                "actual": 199000,
                "unit": "",
            },
            {
                "country": "ES",
                "date": "2026-08-06T08:45:00Z",
                "title": "Spain 10 Year Government Bond Auction",
                "actual": 3.395,
                "unit": "%",
            },
        ]
        claims = {
            "currency": "USD",
            "datetimeJst": "2026-08-06T21:30:00+09:00",
            "eventNameOriginal": "Unemployment Claims",
            "category": "employment",
            "forecast": "203K",
        }
        auction = {
            "currency": "EUR",
            "datetimeJst": "2026-08-06T17:41:00+09:00",
            "eventNameOriginal": "Spanish 10-y Bond Auction",
            "category": "bond_auction",
        }
        self.assertEqual(match_row(claims, rows)["title"], "Initial Jobless Claims")
        self.assertEqual(match_row(auction, rows)["title"], "Spain 10 Year Government Bond Auction")

    def test_claims_pdf_text_parser(self):
        text = """
        UNEMPLOYMENT INSURANCE WEEKLY CLAIMS
        Thursday, August 6, 2026
        In the week ending August 1, the advance figure for seasonally adjusted initial claims was 199,000.
        The previous week's level was revised up by 1,000 from 197,000 to 198,000.
        """
        self.assertEqual(extract_claims_from_text(text, dt.date(2026, 8, 6)), ("199K", "198K"))

    def test_process_with_supplied_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "data/events/latest.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "2.0.0",
                        "pageId": "events",
                        "generatedAt": "2026-08-06T22:00:00+09:00",
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
                                "actual": "",
                                "status": "result_pending",
                            },
                            {
                                "id": "spain",
                                "date": "2026-08-06",
                                "time": "17:41",
                                "datetimeJst": "2026-08-06T17:41:00+09:00",
                                "currency": "EUR",
                                "title": "欧州 Spanish 10-y 国債入札",
                                "eventNameOriginal": "Spanish 10-y Bond Auction",
                                "category": "bond_auction",
                                "forecast": "",
                                "previous": "3.40|1.8",
                                "actual": "",
                                "status": "result_pending",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            rows = [
                {
                    "country": "US",
                    "date": "2026-08-06T12:30:00Z",
                    "title": "Initial Jobless Claims",
                    "actual": 199000,
                    "unit": "",
                    "source": "U.S. Department of Labor",
                    "source_url": "https://www.dol.gov/ui/data.pdf",
                },
                {
                    "country": "ES",
                    "date": "2026-08-06T08:45:00Z",
                    "title": "Spain 10 Year Government Bond Auction",
                    "actual": 3.395,
                    "unit": "%",
                    "source": "Tesoro Público",
                    "source_url": "https://www.tesoro.es/",
                },
            ]
            summary = process(
                root,
                dt.datetime(2026, 8, 6, 22, 30, tzinfo=JST),
                fetch_live=False,
                supplied_rows=rows,
            )
            payload = json.loads((root / "data/events.json").read_text(encoding="utf-8"))
            by_id = {item["id"]: item for item in payload["events"]}
            self.assertEqual(by_id["claims"]["actual"], "199K")
            self.assertEqual(by_id["claims"]["status"], "released")
            self.assertEqual(by_id["spain"]["actual"], "3.395%")
            self.assertEqual(by_id["spain"]["status"], "released")
            self.assertEqual(summary["matched"], 2)
            self.assertEqual(summary["pending"], 0)


if __name__ == "__main__":
    unittest.main()
