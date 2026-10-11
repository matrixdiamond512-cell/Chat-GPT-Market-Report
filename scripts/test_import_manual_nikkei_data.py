from __future__ import annotations

import datetime as dt
import unittest

from scripts.import_manual_nikkei_data import ManualImportError, manual_report_ready_rows, normalize_manual_data


def make_payload() -> dict:
    start = dt.date(2025, 12, 1)
    history = []
    day = start
    close = 50000.0
    while len(history) < 200:
        if day.weekday() < 5:
            close += 10
            history.append({"date": day.isoformat(), "close": close})
        day += dt.timedelta(days=1)
    date = history[-1]["date"]
    return {
        "marketDate": date,
        "sourceName": "Nikkei official manual download",
        "sourceUrl": "https://indexes.nikkei.co.jp/",
        "sourceCapturedAt": f"{date}T16:00:00+09:00",
        "nikkei225Close": close,
        "nikkeiViClose": 24.12,
        "nikkei225ValuationBasis": "index_based",
        "nikkei225ForecastPER": 15.0,
        "nikkei225IndexPBR": 1.9,
        "nikkei225ReportedForecastEPS": round(close / 15.0, 2),
        "dailyCloseHistory": history,
    }


class ManualNikkeiImportTests(unittest.TestCase):
    def test_creates_cash_vi_and_exact_25_200_session_calculations(self) -> None:
        now = dt.datetime.fromisoformat("2026-10-12T12:00:00+09:00")
        result = normalize_manual_data(make_payload(), now=now)
        items = {item["id"]: item for item in result["items"]}
        self.assertEqual(set(items), {"nikkei225_cash", "nikkei_vi", "nikkei225_dev25", "nikkei225_dev200", "nikkei225_per", "nikkei225_pbr", "nikkei225_eps"})
        self.assertEqual(items["nikkei225_per"]["value"], 15.0)
        self.assertEqual(items["nikkei225_pbr"]["value"], 1.9)
        self.assertAlmostEqual(items["nikkei225_eps"]["value"], make_payload()["nikkei225Close"] / 15.0)
        self.assertIn("agrees with source-reported EPS", items["nikkei225_eps"]["seriesDefinition"])
        history = make_payload()["dailyCloseHistory"]
        for window, key in ((25, "nikkei225_dev25"), (200, "nikkei225_dev200")):
            closes = [row["close"] for row in history[-window:]]
            expected = (closes[-1] / (sum(closes) / window) - 1) * 100
            self.assertAlmostEqual(items[key]["value"], expected)
            self.assertIn(f"{window} latest dated sessions", items[key]["seriesDefinition"])
        self.assertTrue(all(item["evidenceStatus"] == "MANUAL_REVIEW" for item in result["items"]))

    def test_rejects_history_with_wrong_last_close_or_duplicate_date(self) -> None:
        payload = make_payload()
        payload["dailyCloseHistory"][-1]["close"] -= 1
        with self.assertRaisesRegex(ManualImportError, "exactly match"):
            normalize_manual_data(payload, now=dt.datetime.fromisoformat("2026-10-12T12:00:00+09:00"))
        payload = make_payload()
        payload["dailyCloseHistory"][-1]["date"] = payload["dailyCloseHistory"][-2]["date"]
        with self.assertRaisesRegex(ManualImportError, "duplicate dates"):
            normalize_manual_data(payload, now=dt.datetime.fromisoformat("2026-10-12T12:00:00+09:00"))

    def test_rejects_insufficient_history_and_future_market_date(self) -> None:
        payload = make_payload()
        payload["dailyCloseHistory"] = payload["dailyCloseHistory"][-199:]
        with self.assertRaisesRegex(ManualImportError, "at least 200"):
            normalize_manual_data(payload, now=dt.datetime.fromisoformat("2026-10-12T12:00:00+09:00"))
        payload = make_payload()
        payload["marketDate"] = "2026-10-13"
        with self.assertRaisesRegex(ManualImportError, "future"):
            normalize_manual_data(payload, now=dt.datetime.fromisoformat("2026-10-12T12:00:00+09:00"))

    def test_index_eps_must_match_same_date_close_and_forecast_per_at_published_precision(self) -> None:
        payload = make_payload()
        payload["nikkei225ReportedForecastEPS"] += 1
        with self.assertRaisesRegex(ManualImportError, "does not match source-reported"):
            normalize_manual_data(payload, now=dt.datetime.fromisoformat("2026-10-12T12:00:00+09:00"))
        payload = make_payload()
        payload["nikkei225ValuationBasis"] = "weighted_average"
        with self.assertRaisesRegex(ManualImportError, "must be index_based"):
            normalize_manual_data(payload, now=dt.datetime.fromisoformat("2026-10-12T12:00:00+09:00"))

    def test_valuation_fields_are_an_all_or_none_group(self) -> None:
        payload = make_payload()
        payload.pop("nikkei225IndexPBR")
        with self.assertRaisesRegex(ManualImportError, "must be supplied together"):
            normalize_manual_data(payload, now=dt.datetime.fromisoformat("2026-10-12T12:00:00+09:00"))

    def test_manual_values_reach_report_ready_only_after_explicit_source_review(self) -> None:
        result = normalize_manual_data(make_payload(), now=dt.datetime.fromisoformat("2026-10-12T12:00:00+09:00"))
        self.assertEqual(manual_report_ready_rows(result, False), [])
        ready = manual_report_ready_rows(result, True)
        self.assertEqual(len(ready), 7)
        self.assertTrue(all(row[10] == "VERIFIED_MANUAL" for row in ready))


if __name__ == "__main__":
    unittest.main()

