"""No-network evidence gating and real repository snapshots, never paid API."""
import copy
import json
from pathlib import Path
import unittest

from scripts.reporting.context import ReportContext
from scripts.reporting.snapshot import MarketDataSnapshot
from scripts.reporting.d3_source_context import (
    SOURCES, create_source_context, load_repository_sources, verify_source_context,
)
from scripts.reporting.d2_responses_contract import build_request

ROOT = Path(__file__).resolve().parents[1]


def context(day="2026-10-15", time="12:00"):
    return ReportContext.create(day, time, day + "T" + time + ":00+09:00", mode="historical")


class TestSupplementaryEvidence(unittest.TestCase):
    def test_frozen_oct14_21h_excludes_all_later_files(self):
        c = context("2026-10-14", "21:00")
        b = create_source_context(c, load_repository_sources(ROOT))
        verify_source_context(c, b)
        self.assertFalse(b["entries"])
        self.assertTrue(all(x["category"] in
                            ("rates", "calendar", "usdjpy_position", "gold_position",
                             "nikkei_position", "news") for x in b["omissions"]))
        self.assertTrue(any(x["category"] == "news" for x in b["omissions"]))

    def test_current_real_files_only_admit_safely_dated_observations(self):
        c = context()
        b = create_source_context(c, load_repository_sources(ROOT))
        verify_source_context(c, b)
        categories = {x["category"] for x in b["entries"]}
        self.assertIn("rates", categories)
        self.assertIn("usdjpy_position", categories)
        self.assertIn("gold_position", categories)
        self.assertIn("nikkei_position", categories)
        self.assertTrue(any(x["category"] == "news" and
                            x["reason"] == "NO_VERIFIED_NEWS_ARTICLE_FEED"
                            for x in b["omissions"]))
        for item in b["entries"]:
            self.assertLessEqual(item["source_generated_at"], c.data_cutoff)
            self.assertTrue(item["source_url"].startswith("https://"))
        for row in (r for r in b["entries"] if r.get("category") == "rates"):
            observed = __import__("datetime").date.fromisoformat(row["as_of"])
            actual = __import__("datetime").date.fromisoformat(c.report_date)
            self.assertGreaterEqual((actual - observed).days, 1)
            self.assertLessEqual((actual - observed).days, 4)
        self.assertTrue(any(x.get("series") == "日本10年国債利回り" for x in b["entries"]))

    def test_observation_older_than_age_limit_is_excluded_independently_of_live_feed_updates(self):
        c = context()
        sources = load_repository_sources(ROOT)
        old = copy.deepcopy(sources)
        for row in old["rates"]["rates"]:
            if row.get("name") == "米10年債利回り":
                row["asOf"] = "2026-10-01"
        b = create_source_context(c, old)
        self.assertFalse(any(x.get("series") == "米10年債利回り" for x in b["entries"]))
        self.assertTrue(any(x.get("reason") == "米10年債利回り_UNVERIFIED_OR_STALE"
                            for x in b["omissions"]))

    def test_mutating_asof_or_source_without_hash_is_rejected(self):
        c = context()
        b = create_source_context(c, load_repository_sources(ROOT))
        for field, changed in [("source_generated_at", "2026-10-16T00:00:00+09:00"),
                               ("source_url", "https://attacker.invalid/path")]:
            d = copy.deepcopy(b)
            d["entries"][0][field] = changed
            with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, "SUPPLEMENTARY_CONTEXT_HASH_INVALID"):
                verify_source_context(c, d)

    def test_future_generated_payload_and_same_day_date_only_are_rejected(self):
        base = load_repository_sources(ROOT)
        c = context()
        bad = copy.deepcopy(base)
        bad["rates"]["generatedAt"] = "2026-10-15T12:00:01+09:00"
        b = create_source_context(c, bad)
        self.assertFalse(any(x["category"] == "rates" for x in b["entries"]))
        bad = copy.deepcopy(base)
        for r in bad["rates"]["rates"]:
            r["asOf"] = "2026-10-15"
        b = create_source_context(c, bad)
        self.assertFalse(any(x["category"] == "rates" for x in b["entries"]))

    def test_supplementary_evidence_attaches_to_verified_api_request_only(self):
        c = context()
        bundle = create_source_context(c, load_repository_sources(ROOT))
        raw = json.loads((ROOT/"data/market/history/2026-10-14_21-00.json").read_text())
        # A frozen previous-day market snapshot cannot be relabeled to 10/15.
        with self.assertRaises(ValueError):
            MarketDataSnapshot.from_acquisition(c, raw)
        old = context("2026-10-14","21:00")
        snapshot = MarketDataSnapshot.from_acquisition(old, raw)
        old_bundle = create_source_context(old, load_repository_sources(ROOT))
        req = build_request(old, snapshot, instructions="確認済みデータのみ使用",
                            supplementary_context=old_bundle)
        d = json.loads(req["input"])
        self.assertEqual(d["supplementary_context"]["sha256"], old_bundle["sha256"])
        self.assertEqual(d["supplementary_context"]["report_id"], old.report_id)
        self.assertFalse(req["store"])
        self.assertEqual(req["tools"], [])
        with self.assertRaisesRegex(ValueError, "SUPPLEMENTARY_CONTEXT_SLOT_MISMATCH"):
            build_request(old,snapshot,instructions="事実のみ",supplementary_context=bundle)

    def test_missing_source_and_untrusted_host_are_not_invented(self):
        c = context()
        base = load_repository_sources(ROOT)
        d = copy.deepcopy(base)
        d["gold_position"] = None
        d["usdjpy_position"]["cftc"]["url"] = "https://spoof.example/fake"
        b = create_source_context(c,d)
        self.assertFalse(any(x["category"] in ("gold_position","usdjpy_position") for x in b["entries"]))
        self.assertIn("SOURCE_NOT_AVAILABLE",[x["reason"] for x in b["omissions"]])


if __name__ == "__main__":
    unittest.main()
