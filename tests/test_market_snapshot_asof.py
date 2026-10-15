"""Regression gates for PR #94: no future knowledge in a Tokyo 16:00 report."""
import copy
import unittest

from scripts.market_snapshot_asof import AsOfProjectionError, project_snapshot_asof
from scripts.build_personal_market_report import render_report, report_counts, report_sheet_row


CUTOFF = "2026-10-13T16:00:00+09:00"


class SnapshotCutoffTests(unittest.TestCase):
    def _payload(self):
        return {
            "snapshotId": "archive-20261015",
            "generatedAt": "2026-10-15T08:46:03Z",
            "reportDate": "2026-10-12〜2026-10-14",
            "markets": {
                "dow": {"value": 51850.55, "displayValue": "51850.55", "unit": "pt",
                        "asOf": "2026-10-12", "fetchedAt": "2026-10-13T03:00:00Z",
                        "verificationStatus": "verified", "sourceId": "us_index", "sourceName": "US verified close"},
                "nikkei225_cash": {"value": 67777.52, "asOf": "2026-10-13",
                         "fetchedAt": "2026-10-14T08:14:11Z",
                         "verificationStatus": "verified", "sourceName": "Later official query"},
                "nikkei_vi": {"value": 30.41, "asOf": "2026-10-13",
                         "fetchedAt": "2026-10-13T07:14:45Z",
                         "verificationStatus": "verified", "sourceName": "Official VI profile"},
                "btcusd": {"value": 81574.32, "asOf": "2026-10-14",
                         "fetchedAt": "2026-10-15T08:46:03Z",
                         "verificationStatus": "verified", "sourceName": "BTC UTC daily"},
                "usdjpy": {"value": 157.76, "asOf": "2026-10-14",
                         "fetchedAt": "2026-10-15T08:46:03Z", "changePercent": 9.0,
                         "verificationStatus": "reference_only", "referenceOnly": True},
                "nikkei225_per": {"value": 17.31, "asOf": "2026-10-13",
                         "fetchedAt": "2026-10-13T06:50:00Z",
                         "verificationStatus": "verified"},
                "nikkei225_pbr": {"value": 1.89, "asOf": "2026-10-13",
                         "fetchedAt": "2026-10-13T06:50:00Z",
                         "seriesBasis": "weighted_average", "verificationStatus": "verified"},
                "tse_prime_advancers": {"value": 1140, "asOf": "2026-10-13",
                         "fetchedAt": "2026-10-13T06:50:00Z",
                         "marketSegment": "Japan all equities", "verificationStatus": "verified"},
                "wti": {"value": 91.85, "asOf": "2026-10-09",
                         "fetchedAt": "2026-10-11T17:48:43Z",
                         "verificationStatus": "reference_only", "referenceOnly": True,
                         "sourceName": "Continuous NYMEX bar"},
            },
            "news": [{"title": "Known early", "publishedAt": "2026-10-13T00:00:00Z"},
                     {"title": "Post-cutoff", "publishedAt": "2026-10-13T08:00:00Z"}],
        }

    def test_cutoff_filters_future_and_late_acquired_quotes_without_mutating_archive(self):
        source = self._payload()
        original = copy.deepcopy(source)
        output = project_snapshot_asof(source, CUTOFF)
        self.assertEqual(source, original)
        self.assertEqual(output["markets"]["dow"]["value"], 51850.55)
        self.assertEqual(output["markets"]["nikkei_vi"]["value"], 30.41)
        self.assertIsNone(output["markets"]["nikkei225_cash"]["value"])
        self.assertIsNone(output["markets"]["btcusd"]["value"])
        self.assertIsNone(output["markets"]["usdjpy"]["value"])
        self.assertNotIn("changePercent", output["markets"]["usdjpy"])
        self.assertEqual(output["asOfExcludedCount"], 5)
        self.assertEqual(len(output["news"]), 1)
        self.assertEqual(output["news"][0]["title"], "Known early")
        report = render_report(output)
        for forbidden in ("81574.32", "157.76", "67777.52", "Post-cutoff"):
            self.assertNotIn(forbidden, report)

    def test_basis_and_scope_are_required_before_promotion(self):
        source = self._payload()
        output = project_snapshot_asof(source, CUTOFF)
        self.assertIsNone(output["markets"]["nikkei225_per"]["value"])
        self.assertEqual(output["markets"]["nikkei225_pbr"]["value"], 1.89)
        self.assertFalse(output["markets"]["nikkei225_pbr"]["productionEligible"])
        self.assertIsNone(output["markets"]["tse_prime_advancers"]["value"])

    def test_old_later_retrieval_requires_dated_publication_proof(self):
        source = self._payload()
        cash = source["markets"]["nikkei225_cash"]
        cash.update({"publishedAt": "2026-10-13T06:45:00Z",
                     "finalizedAt": "2026-10-13T06:30:00Z",
                     "publicationEvidenceUrl": "https://example.org/dated-archive",
                     "publicationEvidence": "Dated public timestamp for exact official cash series"})
        result = project_snapshot_asof(source, CUTOFF)
        self.assertEqual(result["markets"]["nikkei225_cash"]["value"], 67777.52)
        cash["publishedAt"] = "2026-10-13T06:20:00Z"
        premature = project_snapshot_asof(source, CUTOFF)
        self.assertIsNone(premature["markets"]["nikkei225_cash"]["value"])
        cash["publishedAt"] = "2026-10-13T08:30:00Z"
        blocked = project_snapshot_asof(source, CUTOFF)
        self.assertIsNone(blocked["markets"]["nikkei225_cash"]["value"])

    def test_cutoff_checks_explicit_daily_boundary_and_strict_timestamp(self):
        source = self._payload()
        source["markets"]["dow"]["finalizedAt"] = "2026-10-13T08:00:00Z"
        result = project_snapshot_asof(source, CUTOFF)
        self.assertIsNone(result["markets"]["dow"]["value"])
        with self.assertRaises(AsOfProjectionError):
            project_snapshot_asof(source, "2026-10-13T16:00:00")

    def test_future_timestamp_on_same_calendar_day_is_excluded(self):
        source = self._payload()
        source["markets"]["dow"]["asOf"] = "2026-10-13T17:00:00+09:00"
        result = project_snapshot_asof(source, CUTOFF)
        self.assertIsNone(result["markets"]["dow"]["value"])

    def test_historical_verified_quotes_are_never_production_candidates(self):
        result = project_snapshot_asof(self._payload(), CUTOFF)
        self.assertEqual(result["markets"]["dow"]["verificationStatus"], "verified")
        self.assertFalse(result["markets"]["dow"]["productionEligible"])

    def test_reference_before_cutoff_is_not_production_eligible(self):
        output = project_snapshot_asof(self._payload(), CUTOFF)
        self.assertEqual(output["markets"]["wti"]["value"], 91.85)
        self.assertEqual(output["markets"]["wti"]["verificationStatus"], "reference_only")
        self.assertFalse(output["markets"]["wti"]["productionEligible"])

    def test_asof_row_id_is_deterministic_and_independent_of_generation_time(self):
        original = self._payload()
        result = project_snapshot_asof(original, CUTOFF)
        repeated = project_snapshot_asof({**original, "generatedAt": "2026-10-16T09:00:00Z"}, CUTOFF)
        self.assertEqual(result["snapshotId"], repeated["snapshotId"])
        body = render_report(result)
        same_body = render_report(repeated)
        self.assertNotEqual(body, same_body)  # archival generation time is explicitly displayed
        self.assertNotEqual(report_sheet_row(result, body)[0], report_sheet_row(repeated, same_body)[0])
        self.assertEqual(report_counts(result)[0], 3)


if __name__ == "__main__":
    unittest.main()
