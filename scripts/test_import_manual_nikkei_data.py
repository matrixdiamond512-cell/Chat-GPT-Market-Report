from __future__ import annotations

import datetime as dt
import unittest

from scripts.import_manual_nikkei_data import ManualImportError, normalize_manual_data


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
        "dailyCloseHistory": history,
    }


class ManualNikkeiImportTests(unittest.TestCase):
    def test_creates_cash_vi_and_exact_25_200_session_calculations(self) -> None:
        now = dt.datetime.fromisoformat("2026-10-12T12:00:00+09:00")
        result = normalize_manual_data(make_payload(), now=now)
        items = {item["id"]: item for item in result["items"]}
        self.assertEqual(set(items), {"nikkei225_cash", "nikkei_vi", "nikkei225_dev25", "nikkei225_dev200"})
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


if __name__ == "__main__":
    unittest.main()
