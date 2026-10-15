"""The canonical Docs reader stores only explicitly labeled source timelines."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from reporting.market_timeline import parse_saved_timeline


class MarketTimelineIngestionTests(unittest.TestCase):
    def test_all_october_15_slot_bodies_extract_their_own_phase_sets(self):
        expected = {
            "08:00": {"NY開場前", "寄り付き", "序盤", "中盤", "終盤・引け", "東京への引き継ぎ"},
            "12:00": {"寄り付き前", "寄り付き", "前場序盤", "中盤", "前引け"},
            "16:00": {"午前の振り返り", "後場開始", "後場中盤", "大引け", "欧州への引き継ぎ"},
            "21:00": {"欧州開場前", "寄り付き", "序盤", "中盤", "NYへの引き継ぎ"},
        }
        for slot, phases in expected.items():
            report_id = f"2026-10-15_{slot.replace(':', '-')}"
            report = json.loads((ROOT / "reports" / f"{report_id}.json").read_text(encoding="utf-8"))
            timeline = parse_saved_timeline(report)
            self.assertIsNotNone(timeline, report_id)
            self.assertEqual(timeline["evidenceStatus"], "AFTER_ISSUANCE_AMENDMENT")
            self.assertEqual(timeline["amendmentDate"], "2026/10/16")
            self.assertTrue(phases.issubset({event["phase"] for event in timeline["events"]}), report_id)

    def test_october_15_amendment_is_bound_to_exact_saved_report(self):
        report = json.loads((ROOT / "reports/2026-10-15_12-00.json").read_text(encoding="utf-8"))
        timeline = parse_saved_timeline(report)
        self.assertIsNotNone(timeline)
        self.assertEqual(timeline["reportId"], "2026-10-15_12-00")
        self.assertEqual(timeline["reportRevision"], report["revision"])
        self.assertEqual(timeline["sourceBodyHash"], report["bodyHash"])
        self.assertEqual(timeline["sourceDocumentRevisionId"], report.get("sourceRevisionId"))
        self.assertEqual(timeline["sourceDocumentId"], report["sourceDocument"]["id"])
        self.assertEqual(timeline["evidenceStatus"], "AFTER_ISSUANCE_AMENDMENT")
        self.assertEqual(timeline["amendmentDate"], "2026/10/16")
        self.assertEqual(timeline["publicationStatus"], report["report_status"])
        self.assertGreater(len(timeline["events"]), 0)
        for event in timeline["events"]:
            self.assertTrue(event["event"])
            self.assertTrue(event["reaction"])
            self.assertTrue(event["meaning"])
            self.assertTrue(event["nextWatch"])
            self.assertTrue(event["sources"])

    def test_unknown_time_is_not_fabricated(self):
        report = {
            "date":"2026-10-16", "time":"12:00", "revision":1,
            "bodyHash":"body-hash", "report_status":"SOURCE_ARCHIVED",
            "fullText":"2026-10-16 12:00\n東京前場の時系列\n"
                "時刻記載なし 前場中盤｜出来事：実際の事象。反応：日経平均が下落。"
                "意味：売りが続いた。次は：前引け。出典：保存本文。",
        }
        timeline = parse_saved_timeline(report)
        self.assertEqual(timeline["events"][0]["occurredAt"], None)
        self.assertEqual(timeline["events"][0]["timePrecision"], "time-not-recorded")

    def test_unstructured_prose_does_not_create_timeline(self):
        report = {"date":"2026-10-16", "time":"08:00", "fullText":"NY市場の時系列\n株価が上昇し、金利に注目。"}
        self.assertIsNone(parse_saved_timeline(report))


if __name__ == "__main__":
    unittest.main()
