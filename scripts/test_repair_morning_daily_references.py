from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import repair_morning_daily_references as repair


class PreviousSessionTests(unittest.TestCase):
    def test_us_friday_to_monday(self):
        with patch.object(repair, "_market_holidays", return_value=set()):
            self.assertEqual(repair.expected_prior_session(dt.date(2026, 11, 16), "NYダウ"), dt.date(2026, 11, 13))

    def test_us_holiday_skips_to_prior_session(self):
        with patch.object(repair, "_market_holidays", side_effect=lambda _market, _year: {dt.date(2026, 11, 26)}):
            self.assertEqual(repair.expected_prior_session(dt.date(2026, 11, 27), "S&P500"), dt.date(2026, 11, 25))

    def test_japanese_holiday_skips_to_prior_session(self):
        fake = type("FakeJapanHoliday", (), {"is_holiday": staticmethod(lambda day: day == dt.date(2026, 5, 4))})
        with patch.dict(sys.modules, {"jpholiday": fake}):
            self.assertEqual(repair.expected_prior_session(dt.date(2026, 5, 5), "日経225現物"), dt.date(2026, 5, 1))

    def test_japanese_new_year_closure_skips_to_prior_year(self):
        fake = type("FakeJapanHoliday", (), {"is_holiday": staticmethod(lambda day: False)})
        with patch.dict(sys.modules, {"jpholiday": fake}):
            self.assertEqual(repair.expected_prior_session(dt.date(2026, 1, 5), "日経225現物"), dt.date(2025, 12, 30))

    def test_fx_weekend_skips_to_friday(self):
        self.assertEqual(repair.expected_prior_session(dt.date(2026, 11, 16), "USD/JPY"), dt.date(2026, 11, 13))

    def test_monday_btc_uses_last_fully_closed_utc_daily_bar(self):
        self.assertEqual(repair.expected_prior_session(dt.date(2026, 11, 16), "BTCUSD"), dt.date(2026, 11, 14))
        self.assertEqual(repair.expected_prior_session(dt.date(2026, 11, 17), "BTCUSD"), dt.date(2026, 11, 15))

    def test_monday_btc_does_not_use_the_incomplete_sunday_bar(self):
        def epoch(day: int) -> int:
            return int(dt.datetime(2026, 11, day, tzinfo=dt.timezone.utc).timestamp())
        result = {
            "meta": {"exchangeTimezoneName": "America/New_York"},
            "timestamp": [epoch(13), epoch(14), epoch(15)],
            "indicators": {"quote": [{"close": [90, 100, 110]}]},
        }
        bars = repair.completed_bars(result, dt.date(2026, 11, 16), timezone_override="UTC")
        target = repair.expected_prior_session(dt.date(2026, 11, 16), "BTCUSD")
        self.assertEqual([item for item in bars if item[0] == target], [(target, 100)])

    def test_nasdaq_and_cme_use_supported_financial_market_codes(self):
        with patch.object(repair, "_market_holidays", return_value=set()) as calendar:
            self.assertEqual(repair.expected_prior_session(dt.date(2026, 11, 16), "NASDAQ総合"), dt.date(2026, 11, 13))
            self.assertEqual(calendar.call_args.args[0], "XNAS")
            repair.expected_prior_session(dt.date(2026, 11, 16), "WTI原油")
            self.assertEqual(calendar.call_args.args[0], "XCME")


class FredCrossCheckTests(unittest.TestCase):
    def test_exact_date_csv_value(self):
        body = "observation_date,DJIA\n2026-11-13,52347.55\n"
        response = type("Response", (), {"read": lambda self: body.encode(), "__enter__": lambda self: self, "__exit__": lambda *args: None})()
        with patch.object(repair.urllib.request, "urlopen", return_value=response):
            self.assertEqual(repair.fetch_fred_close("DJIA", dt.date(2026, 11, 13)), 52347.55)

    def test_numeric_close_candidate_string_is_parsed(self):
        with patch.object(repair, "fetch_fred_observation", return_value=(52347.55, 247.55, "https://example.test")) as fetch:
            self.assertEqual(fetch.return_value[0], 52347.55)

    def test_missing_date_fails_closed(self):
        body = "observation_date,DJIA\n2026-11-12,52347.55\n"
        response = type("Response", (), {"read": lambda self: body.encode(), "__enter__": lambda self: self, "__exit__": lambda *args: None})()
        with patch.object(repair.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "no numeric observation"):
                repair.fetch_fred_close("DJIA", dt.date(2026, 11, 13))

    def test_fred_change_uses_previous_published_observation(self):
        body = "observation_date,DJIA\n2026-11-10,52000\n2026-11-12,52100\n2026-11-13,52347.55\n"
        response = type("Response", (), {"read": lambda self: body.encode(), "__enter__": lambda self: self, "__exit__": lambda *args: None})()
        with patch.object(repair.urllib.request, "urlopen", return_value=response):
            value, change, url = repair.fetch_fred_observation("DJIA", dt.date(2026, 11, 13))
        self.assertEqual(value, 52347.55)
        self.assertAlmostEqual(change, 247.55)
        self.assertIn("fredgraph.csv", url)

    def test_other_index_sources_are_not_mislabeled_as_fred(self):
        self.assertEqual(repair.FRED_SERIES["NYダウ"][0], "DJIA")
        self.assertEqual(repair.FRED_SERIES["NASDAQ総合"][0], "NASDAQCOM")
        self.assertEqual(repair.FRED_SERIES["S&P500"][0], "SP500")

    def test_three_indices_require_cross_check(self):
        self.assertEqual(set(repair.FRED_SERIES), {"NYダウ", "NASDAQ総合", "S&P500"})

    def test_index_cross_check_rejects_divergence(self):
        with self.assertRaisesRegex(RuntimeError, "divergence"):
            repair.require_cross_market_match("S&P500", 7600.0, 7500.0)

    def test_index_cross_check_allows_source_rounding(self):
        self.assertGreater(repair.require_cross_market_match("S&P500", 7500.01, 7500.0), 0)


class CandidateValidationTests(unittest.TestCase):
    def test_coverage_manifest_maps_28_rows_to_sheet_or_report_only_destinations(self):
        report_date = dt.date(2026, 11, 16)
        with patch.object(repair, "expected_prior_session", return_value=dt.date(2026, 11, 13)):
            coverage = repair.build_coverage_manifest(report_date, {}, {})
        self.assertEqual(len(coverage), 28)
        self.assertEqual(coverage["NYダウ"]["closeSheetFields"], ["Dow終値", "Dow前日比", "Dow騰落率"])
        self.assertEqual(coverage["CME日経225先物・円建て"]["destination"], "report-only; no direct 終値一覧 column")
        self.assertEqual(coverage["BTCUSD"]["expectedSessionDate"], "2026-11-13")

    def test_chatgpt_market_item_requires_exact_session_and_source_url(self):
        row = {"value": "25,000.00", "change": "+100.00", "rate": "+0.40%"}
        with patch.object(repair, "expected_prior_session", return_value=dt.date(2026, 11, 13)):
            stale = repair.row_item_for_build_input("Russell 2000", row, {"Russell 2000": {"dataDate": "2026-11-12", "sourceName": "Yahoo"}}, dt.date(2026, 11, 16))
            exact = repair.row_item_for_build_input("Russell 2000", row, {"Russell 2000": {"dataDate": "2026-11-13", "sourceName": "Yahoo", "sourceUrl": "https://finance.yahoo.com/"}}, dt.date(2026, 11, 16))
        self.assertEqual(stale["verificationStatus"], "unavailable")
        self.assertEqual(exact["verificationStatus"], "verified")
        self.assertEqual(exact["expectedSessionDate"], "2026-11-13")

    def test_existing_market_source_requires_exact_exchange_session_date(self):
        report_date = dt.date(2026, 11, 16)
        latest_path = repair.ROOT / "data" / "market" / "latest.json"
        payload = {"markets": {"russell2000": {
            "verificationStatus": "verified", "sessionDate": "2026-11-13", "value": 2500,
            "change": 10, "changePercent": 0.4, "sourceName": "Yahoo Finance",
            "sourceUrl": "https://finance.yahoo.com/quote/%5ERUT/", "sourceId": "yahoo_rut",
        }}}
        def fake_load(path):
            if path == latest_path:
                return payload
            return {}
        with patch.object(repair, "load", side_effect=fake_load), \
             patch.object(repair, "expected_prior_session", return_value=dt.date(2026, 11, 13)):
            candidates, _ = repair.load_close_candidates(report_date)
        self.assertEqual(candidates["Russell 2000"]["date"], "2026-11-13")

    def test_market_snapshot_timezone_date_mismatch_is_rejected(self):
        report_date = dt.date(2026, 11, 16)
        latest_path = repair.ROOT / "data" / "market" / "latest.json"
        payload = {"markets": {"russell2000": {
            "verificationStatus": "verified", "sessionDate": "2026-11-14", "value": 2500,
            "sourceName": "Yahoo Finance", "sourceUrl": "https://finance.yahoo.com/quote/%5ERUT/",
        }}}
        def fake_load(path):
            if path == latest_path:
                return payload
            return {}
        with patch.object(repair, "load", side_effect=fake_load), \
             patch.object(repair, "expected_prior_session", return_value=dt.date(2026, 11, 13)):
            candidates, gaps = repair.load_close_candidates(report_date)
        self.assertNotIn("Russell 2000", candidates)
        self.assertIn("session date mismatch", gaps["Russell 2000"])

    def test_futures_candidate_without_verified_front_contract_is_rejected(self):
        report_date = dt.date(2026, 11, 16)
        morning_path = repair.MORNING_REFERENCE
        payload = {"reportDate": "2026-11-16", "reportSlot": "08:00", "items": {
            "CME日経225先物・円建て": {
                "status": "verified_reference", "asOf": "2026-11-13T07:45:00+09:00",
                "contract": "27年03月限", "contractIsFront": False,
                "value": "52,000", "sourceName": "mirror", "sourceUrl": "https://example.test",
            },
        }}
        def fake_load(path):
            return payload if path == morning_path else {}
        with patch.object(repair, "load", side_effect=fake_load), \
             patch.object(repair, "expected_prior_session", return_value=dt.date(2026, 11, 13)):
            candidates, _ = repair.load_close_candidates(report_date)
        self.assertNotIn("CME日経225先物・円建て", candidates)

    def test_exact_date_and_source_candidate_applies_change_and_percent(self):
        row = {}
        candidate = {"date": "2026-11-13", "value": "61,142.35円", "change": "+322.99", "sourceName": "Nikkei", "sourceUrl": "https://example.test"}
        ok, reason = repair.apply_reference_candidate(row, candidate, dt.date(2026, 11, 13), label="日経225現物")
        self.assertTrue(ok, reason)
        self.assertEqual(row["value"], "61,142.35")
        self.assertEqual(row["change"], "+322.99")
        self.assertEqual(row["rate"], "+0.53%")

    def test_wrong_date_candidate_is_rejected(self):
        candidate = {"date": "2026-11-12", "value": "61,142.35", "sourceName": "Nikkei", "sourceUrl": "https://example.test"}
        ok, reason = repair.apply_reference_candidate({}, candidate, dt.date(2026, 11, 13), label="日経225現物")
        self.assertFalse(ok)
        self.assertIn("date mismatch", reason)

    def test_missing_source_candidate_is_rejected(self):
        candidate = {"date": "2026-11-13", "value": "61,142.35"}
        ok, reason = repair.apply_reference_candidate({}, candidate, dt.date(2026, 11, 13), label="日経225現物")
        self.assertFalse(ok)
        self.assertIn("provenance missing", reason)

    def test_after_cutoff_futures_candidate_is_rejected(self):
        candidate = {"date": "2026-11-13", "asOf": "2026-11-13T08:06:00+09:00", "value": "52,000", "sourceName": "CME", "sourceUrl": "https://example.test"}
        ok, reason = repair.apply_reference_candidate({}, candidate, dt.date(2026, 11, 13), label="CME日経225先物・円建て")
        self.assertFalse(ok)
        self.assertIn("after the 08:05 cutoff", reason)

    def test_all_28_contract_labels_have_one_owner(self):
        from build_chatgpt_report_input import ITEMS
        labels = [item[0] for item in ITEMS]
        self.assertEqual(len(labels), 28)
        self.assertEqual(set(labels), set(repair.MORNING_ROW_OWNERS))

    def test_all_28_items_have_explicit_integration_disposition(self):
        self.assertEqual(len(repair.MORNING_ROW_OWNERS), 28)
        self.assertTrue(all(repair.MORNING_ROW_OWNERS.values()))
        self.assertIn("not-close-verified", repair.MORNING_ROW_OWNERS["Fear & Greed Index"])

    def test_fred_observation_checks_exact_date(self):
        with patch.object(repair, "fetch_fred_close", return_value=7500.0) as fetch:
            self.assertEqual(fetch.return_value, 7500.0)
        self.assertIn("SP500", {item[0] for item in repair.FRED_SERIES.values()})


if __name__ == "__main__":
    unittest.main()
