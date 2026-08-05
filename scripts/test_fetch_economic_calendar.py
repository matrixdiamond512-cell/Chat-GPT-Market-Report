import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("fetch_economic_calendar.py")
SPEC = importlib.util.spec_from_file_location("economic_calendar", SCRIPT)
calendar = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(calendar)


class EconomicCalendarTest(unittest.TestCase):
    def setUp(self):
        self.repo = SCRIPT.parents[1]
        self.config = calendar.load_json(self.repo / "config/economic_calendar.json", {})
        self.now = calendar.parse_datetime("2026-08-05T12:00:00+09:00").astimezone(calendar.JST)

    def raw_event(self, **overrides):
        event = {
            "title": "ISM Services PMI",
            "country": "USD",
            "date": "2026-08-05T10:00:00-04:00",
            "impact": "High",
            "forecast": "52.1",
            "previous": "50.8",
        }
        event.update(overrides)
        return event

    def build_in_temp(self, rows, previous=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/events").mkdir(parents=True)
            (root / "data/events/event_dictionary.json").write_text(
                (self.repo / "data/events/event_dictionary.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            if previous:
                (root / "data/events/latest.json").write_text(
                    json.dumps({"events": previous}, ensure_ascii=False), encoding="utf-8"
                )
            return calendar.build_payload(root, self.config, rows, self.now)

    def test_timezone_is_converted_to_jst(self):
        event = self.build_in_temp([self.raw_event()])["events"][0]
        self.assertEqual(event["date"], "2026-08-05")
        self.assertEqual(event["time"], "23:00")
        self.assertEqual(event["scheduledAtUtc"], "2026-08-05T14:00:00Z")

    def test_low_impact_is_curated(self):
        self.assertFalse(calendar.should_include(self.raw_event(impact="Low", title="Minor Housing Data"), self.config))
        self.assertTrue(calendar.should_include(self.raw_event(impact="Low", title="10-y Bond Auction"), self.config))
        self.assertTrue(calendar.should_include(self.raw_event(impact="Low", title="FOMC Member Daly Speaks"), self.config))
        self.assertTrue(calendar.should_include(self.raw_event(impact="Low", title="Trade Balance", country="CNY"), self.config))
        self.assertFalse(calendar.should_include(self.raw_event(impact="Low", title="Trade Balance", country="AUD"), self.config))

    def test_importance_override_and_market_order(self):
        event = self.build_in_temp([
            self.raw_event(title="FOMC Statement", impact="Medium")
        ])["events"][0]
        self.assertEqual(event["importance"], 3)
        self.assertEqual([row[0] for row in event["scenarios"]], calendar.MARKET_ORDER)
        self.assertEqual([row[0] for row in event["outlook"]], calendar.MARKET_ORDER)

    def test_saved_result_is_preserved_when_provider_omits_actual(self):
        initial = self.build_in_temp([
            self.raw_event(actual="53.4")
        ])["events"][0]
        initial["resultExplanation"] = "予想を上回り、米2年債が上昇。"
        refreshed = self.build_in_temp([self.raw_event()], [initial])["events"][0]
        self.assertEqual(refreshed["actual"], "53.4")
        self.assertEqual(refreshed["status"], "released")
        self.assertEqual(refreshed["resultExplanation"], "予想を上回り、米2年債が上昇。")

    def test_result_provider_actual_is_matched_without_raw_storage(self):
        result_rows = [
            {
                "title": "ISM Services PMI",
                "country": "US",
                "date": "2026-08-05T14:00:00.000Z",
                "actual": 53.4,
                "actualRaw": 53.4,
                "forecast": 52.1,
                "previous": 50.8,
                "source": "Institute for Supply Management",
                "source_url": "https://www.ismworld.org/",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/events").mkdir(parents=True)
            (root / "data/events/event_dictionary.json").write_text(
                (self.repo / "data/events/event_dictionary.json").read_text(encoding="utf-8"), encoding="utf-8"
            )
            payload = calendar.build_payload(root, self.config, [self.raw_event()], self.now, result_rows)
        event = payload["events"][0]
        self.assertEqual(event["actual"], "53.4")
        self.assertEqual(event["status"], "released")
        self.assertEqual(event["resultSource"]["name"], "Institute for Supply Management")

    def test_result_value_uses_forecast_scale(self):
        self.assertEqual(calendar.result_value({"actualRaw": 44000}, "actual", "68K"), "44K")
        self.assertEqual(calendar.result_value({"actualRaw": -73300000000}, "actual", "-73.0B"), "-73.3B")

    def test_future_legacy_event_without_result_is_not_retained(self):
        old = {
            "id": "legacy",
            "date": "2026-08-06",
            "time": "12:00",
            "title": "古い推測予定",
            "category": "speech",
            "sourceType": "market_report_extraction",
            "resultExplanation": "発表後に自動更新します。",
            "comparison": [["米2年債", "データ次第", "未計測", "確認中"]],
        }
        payload = self.build_in_temp([self.raw_event()], [old])
        self.assertNotIn("古い推測予定", [item["title"] for item in payload["events"]])

    def test_outputs_do_not_store_provider_raw_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = self.build_in_temp([self.raw_event()])
            calendar.write_outputs(root, payload, self.config, self.now)
            names = [path.name.lower() for path in root.rglob("*") if path.is_file()]
            self.assertFalse(any("raw" in name for name in names))
            latest = json.loads((root / "data/events/latest.json").read_text(encoding="utf-8"))
            self.assertFalse(latest["retention"]["rawProviderDataStored"])


if __name__ == "__main__":
    unittest.main()
