import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.postprocess_economic_calendar import (
    extract_bls_productivity,
    extract_dol_claims,
    extract_spanish_auction,
    process,
)


JST = ZoneInfo("Asia/Tokyo")


class PostprocessEconomicCalendarTest(unittest.TestCase):
    def write_payload(self, root: Path) -> None:
        payload = {
            "schemaVersion": "2.0.0",
            "pageId": "events",
            "generatedAt": "2026-08-06T21:40:00+09:00",
            "publishedAt": "2026-08-06T21:40:00+09:00",
            "dataAsOf": "2026-08-06T21:40:00+09:00",
            "timezone": "Asia/Tokyo",
            "status": "ok",
            "isStale": False,
            "sources": [],
            "errors": [],
            "events": [
                {
                    "id": "speech",
                    "date": "2026-08-06",
                    "time": "05:05",
                    "datetimeJst": "2026-08-06T05:05:00+09:00",
                    "category": "speech",
                    "title": "FOMCメンバー発言",
                    "eventNameOriginal": "FOMC Member Speaks",
                    "forecast": "",
                    "previous": "",
                    "actual": "",
                    "status": "result_pending",
                    "officialSource": {"id": "fed", "name": "Federal Reserve", "url": "https://example.com"},
                },
                {
                    "id": "numeric",
                    "date": "2026-08-06",
                    "time": "21:30",
                    "datetimeJst": "2026-08-06T21:30:00+09:00",
                    "category": "employment",
                    "title": "米新規失業保険申請件数",
                    "forecast": "220K",
                    "previous": "218K",
                    "actual": "",
                    "status": "result_pending",
                },
                {
                    "id": "future-speech",
                    "date": "2026-08-07",
                    "time": "01:00",
                    "datetimeJst": "2026-08-07T01:00:00+09:00",
                    "category": "speech",
                    "title": "中銀関係者発言",
                    "forecast": "",
                    "previous": "",
                    "actual": "",
                    "status": "scheduled",
                },
            ],
        }
        path = root / "data/events/latest.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_only_past_qualitative_event_is_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_payload(root)
            summary = process(
                root,
                dt.datetime(2026, 8, 6, 22, 0, tzinfo=JST),
                fetch_official=False,
            )

            payload = json.loads((root / "data/events.json").read_text(encoding="utf-8"))
            by_id = {item["id"]: item for item in payload["events"]}

            self.assertEqual(by_id["speech"]["status"], "released")
            self.assertEqual(by_id["speech"]["actual"], "数値発表なし（発言イベント）")
            self.assertEqual(by_id["speech"]["resultType"], "qualitative")
            self.assertEqual(by_id["numeric"]["status"], "result_pending")
            self.assertEqual(by_id["numeric"]["actual"], "")
            self.assertEqual(by_id["future-speech"]["status"], "scheduled")
            self.assertFalse(by_id["future-speech"]["resultExpected"])
            self.assertEqual(summary["changed"], 1)

            self.assertEqual(payload["days"][0]["date"], "2026-08-07")
            current_day = next(item for item in payload["days"] if item["date"] == "2026-08-06")
            self.assertEqual(current_day["releasedCount"], 1)
            self.assertEqual(current_day["resultPendingCount"], 1)

            completed = json.loads((root / "data/events/completed.json").read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in completed["events"]], ["speech"])

    def test_dol_claims_parser(self):
        page = """
        <article>
          <time>August 6, 2026</time>
          <h2>Unemployment Insurance Weekly Claims Report</h2>
          <p>In the week ending August 1, the advance figure for seasonally adjusted initial claims was 199,000.</p>
          <p>The previous week's level was revised up by 1,000 from 197,000 to 198,000.</p>
        </article>
        """
        self.assertEqual(
            extract_dol_claims(page, dt.date(2026, 8, 6)),
            ("199K", "198K"),
        )

    def test_bls_productivity_parser(self):
        page = """
        <p>Nonfarm business sector labor productivity increased 1.4 percent in the second quarter of 2026.</p>
        <p>Unit labor costs decreased 0.6 percent during the quarter.</p>
        """
        self.assertEqual(extract_bls_productivity(page, "prelim nonfarm productivity"), "1.4%")
        self.assertEqual(extract_bls_productivity(page, "prelim unit labor costs"), "-0.6%")

    def test_spanish_auction_parser(self):
        page = """
        <section>
          <p>Tipo de interés medio 3.395</p>
          <p>Ratio de cobertura 1.81</p>
          <p>Thursday, August 6, 2026 - 12:00</p>
        </section>
        """
        self.assertEqual(
            extract_spanish_auction(page, dt.date(2026, 8, 6)),
            "平均利回り 3.395% / 応札倍率 1.81倍",
        )


if __name__ == "__main__":
    unittest.main()
