"""Regression gates for PR #94: no future knowledge in a Tokyo 16:00 report."""
import copy
import hashlib
import json
import unittest

from scripts.market_snapshot_asof import (
    AsOfProjectionError, build_asof_artifacts, project_snapshot_asof,
)
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
                        "finalizedAt": "2026-10-12T20:00:00Z",
                        "verificationStatus": "verified", "sourceId": "us_index", "sourceName": "US verified close"},
                "nikkei225_cash": {"value": 67777.52, "asOf": "2026-10-13",
                         "fetchedAt": "2026-10-14T08:14:11Z",
                         "finalizedAt": "2026-10-13T06:30:00Z",
                         "verificationStatus": "verified", "sourceName": "Later official query"},
                "nikkei_vi": {"value": 30.41, "asOf": "2026-10-13",
                         "fetchedAt": "2026-10-13T07:14:45Z",
                         "finalizedAt": "2026-10-13T06:30:00Z",
                         "verificationStatus": "verified", "sourceName": "Official VI profile"},
                "btcusd": {"value": 81574.32, "asOf": "2026-10-14",
                         "fetchedAt": "2026-10-15T08:46:03Z",
                         "verificationStatus": "verified", "sourceName": "BTC UTC daily"},
                "usdjpy": {"value": 157.76, "asOf": "2026-10-14",
                         "fetchedAt": "2026-10-15T08:46:03Z", "changePercent": 9.0,
                         "changeText": "急騰", "direction": "up",
                         "analysisText": "対象時刻後の相場反応",
                         "verificationStatus": "reference_only", "referenceOnly": True},
                "nikkei225_per": {"value": 17.31, "asOf": "2026-10-13",
                         "fetchedAt": "2026-10-13T06:50:00Z",
                         "verificationStatus": "verified"},
                "nikkei225_pbr": {"value": 1.89, "asOf": "2026-10-13",
                         "fetchedAt": "2026-10-13T06:50:00Z",
                         "finalizedAt": "2026-10-13T06:30:00Z",
                         "seriesBasis": "weighted_average", "verificationStatus": "verified"},
                "tse_prime_advancers": {"value": 1140, "asOf": "2026-10-13",
                         "fetchedAt": "2026-10-13T06:50:00Z",
                         "marketSegment": "Japan all equities", "verificationStatus": "verified"},
                "wti": {"value": 91.85, "asOf": "2026-10-09",
                         "fetchedAt": "2026-10-11T17:48:43Z",
                         "finalizedAt": "2026-10-09T22:00:00Z",
                         "verificationStatus": "reference_only", "referenceOnly": True,
                         "sourceName": "Continuous NYMEX bar"},
            },
            "news": [{"title": "Known early", "publishedAt": "2026-10-13T00:00:00Z",
                      "fetchedAt": "2026-10-13T00:30:00Z"},
                     {"title": "Post-cutoff", "publishedAt": "2026-10-13T08:00:00Z"},
                     {"title": "Later update", "publishedAt": "2026-10-13T00:00:00Z",
                      "updatedAt": "2026-10-13T08:00:00Z"}],
            "timelineEvidence": [{
                "時間帯": "寄り付き", "observedAt": "2026-10-13T07:01:00Z",
                "fetchedAt": "2026-10-13T08:00:00Z", "出来事": "later event",
            }],
        }

    def test_cutoff_filters_future_and_late_acquired_quotes_without_mutating_archive(self):
        source = self._payload()
        original = copy.deepcopy(source)
        output = project_snapshot_asof(source, CUTOFF)
        self.assertEqual(source, original)
        self.assertEqual(output["markets"]["dow"]["value"], 51850.55)
        self.assertIsNone(output["markets"]["nikkei_vi"]["value"])
        self.assertIsNone(output["markets"]["nikkei225_cash"]["value"])
        self.assertIsNone(output["markets"]["btcusd"]["value"])
        self.assertIsNone(output["markets"]["usdjpy"]["value"])
        self.assertNotIn("changePercent", output["markets"]["usdjpy"])
        self.assertNotIn("changeText", output["markets"]["usdjpy"])
        self.assertNotIn("direction", output["markets"]["usdjpy"])
        self.assertNotIn("analysisText", output["markets"]["usdjpy"])
        self.assertEqual(output["asOfExcludedCount"], 25)
        self.assertEqual(len(output["news"]), 1)
        self.assertEqual(output["news"][0]["title"], "Known early")
        self.assertEqual(output["timelineEvidence"], [])
        report = render_report(output)
        for forbidden in ("81574.32", "157.76", "67777.52", "30.41", "Post-cutoff"):
            self.assertNotIn(forbidden, report)

    def test_basis_and_scope_are_required_before_promotion(self):
        source = self._payload()
        output = project_snapshot_asof(source, CUTOFF)
        self.assertIsNone(output["markets"]["nikkei225_per"]["value"])
        self.assertEqual(output["markets"]["nikkei225_pbr"]["value"], 1.89)
        self.assertFalse(output["markets"]["nikkei225_pbr"]["productionEligible"])
        self.assertIsNone(output["markets"]["tse_prime_advancers"]["value"])

    def test_wrong_valuation_basis_is_not_used_in_weighted_average_field(self):
        source = self._payload()
        source["markets"]["nikkei225_pbr"]["seriesBasis"] = "index_basis"
        projected = project_snapshot_asof(source, CUTOFF)
        self.assertIsNone(projected["markets"]["nikkei225_pbr"]["value"])

    def test_old_later_retrieval_requires_dated_publication_proof(self):
        source = self._payload()
        cash = source["markets"]["nikkei225_cash"]
        cash.update({"publishedAt": "2026-10-13T06:45:00Z", "sourceSeriesId": "NIKKEI225-CASH-D",
                     "publicationEvidenceUrl": "https://example.org/dated-archive"})
        proof = {"sourceSeriesId": "NIKKEI225-CASH-D", "originalId": "archive-record-20261013-1600",
                 "publishedAt": "2026-10-13T06:45:00Z", "observedValue": cash["value"],
                 "originalContent": json.dumps({"id": "archive-record-20261013-1600",
                                                "series": "NIKKEI225-CASH-D", "value": cash["value"]},
                                               sort_keys=True)}
        proof["sha256"] = hashlib.sha256(proof["originalContent"].encode("utf-8")).hexdigest()
        cash["publicationEvidence"] = proof
        result = project_snapshot_asof(source, CUTOFF)
        self.assertEqual(result["markets"]["nikkei225_cash"]["value"], 67777.52)
        cash["publishedAt"] = "2026-10-13T06:20:00Z"
        premature = project_snapshot_asof(source, CUTOFF)
        self.assertIsNone(premature["markets"]["nikkei225_cash"]["value"])
        cash["publishedAt"] = "2026-10-13T08:30:00Z"
        blocked = project_snapshot_asof(source, CUTOFF)
        self.assertIsNone(blocked["markets"]["nikkei225_cash"]["value"])

    def test_later_fetch_proof_must_match_series_value_and_original_hash(self):
        source = self._payload()
        cash = source["markets"]["nikkei225_cash"]
        cash.update({"publishedAt": "2026-10-13T06:45:00Z", "sourceSeriesId": "NIKKEI225-CASH-D",
                     "publicationEvidenceUrl": "https://example.org/dated-archive"})
        original = json.dumps({"id": "archive-record-1", "series": "NIKKEI225-CASH-D",
                               "value": cash["value"]}, sort_keys=True)
        proof = {"sourceSeriesId": "NIKKEI225-CASH-D", "originalId": "archive-record-1",
                 "publishedAt": "2026-10-13T06:45:00Z", "observedValue": cash["value"],
                 "originalContent": original,
                 "sha256": hashlib.sha256(original.encode("utf-8")).hexdigest()}
        cash["publicationEvidence"] = proof
        self.assertEqual(project_snapshot_asof(source, CUTOFF)["markets"]["nikkei225_cash"]["value"], 67777.52)
        for field, bad_value in (("sourceSeriesId", "OTHER-SERIES"),
                                 ("observedValue", 1.0), ("sha256", "0" * 64)):
            invalid = copy.deepcopy(source)
            invalid["markets"]["nikkei225_cash"]["publicationEvidence"][field] = bad_value
            self.assertIsNone(project_snapshot_asof(invalid, CUTOFF)["markets"]["nikkei225_cash"]["value"])

    def test_date_only_daily_value_requires_a_market_close_timestamp(self):
        source = self._payload()
        source["markets"]["dow"].pop("finalizedAt")
        result = project_snapshot_asof(source, CUTOFF)
        self.assertIsNone(result["markets"]["dow"]["value"])

    def test_intraday_delayed_capture_before_cutoff_is_reference_only(self):
        observation = {
            "value": 68570, "asOf": "2026-10-12", "fetchedAt": "2026-10-12T15:08:30Z",
            "sourceId": "tradingview_mcp_cme_niy1_", "verificationStatus": "reference_only",
            "referenceOnly": True, "freshnessStatus": "intraday_delayed",
            "quoteUpdateMode": "delayed_streaming_600", "marketType": "futures_cme",
        }
        payload = {"markets": {"nikkei225_futures_cme_yen": observation}}

        projected = project_snapshot_asof(payload, "2026-10-13T16:00:00+09:00")
        market = projected["markets"]["nikkei225_futures_cme_yen"]
        self.assertEqual(market["value"], 68570)
        self.assertEqual(market["verificationStatus"], "reference_only")
        self.assertFalse(market["productionEligible"])

        observation["fetchedAt"] = "2026-10-13T08:00:00Z"
        after_cutoff = project_snapshot_asof(payload, "2026-10-13T16:00:00+09:00")
        self.assertIsNone(after_cutoff["markets"]["nikkei225_futures_cme_yen"]["value"])

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
        changed_evidence = copy.deepcopy(original)
        changed_evidence["markets"]["dow"]["sourceSeriesId"] = "different-series"
        changed_evidence["markets"]["dow"]["evidenceHash"] = "a" * 64
        self.assertNotEqual(result["snapshotId"], project_snapshot_asof(changed_evidence, CUTOFF)["snapshotId"])
        body = render_report(result)
        same_body = render_report(repeated)
        self.assertNotEqual(body, same_body)  # archival generation time is explicitly displayed
        self.assertNotEqual(report_sheet_row(result, body)[0], report_sheet_row(repeated, same_body)[0])
        self.assertEqual(report_counts(result)[0], 2)

    def test_formal_artifacts_account_for_28_fields_and_hash_reproducibly(self):
        payload = self._payload()
        archive_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        snapshot, evidence, body = build_asof_artifacts(
            payload, CUTOFF, archive_hash, "2026-10-15T10:00:00Z")
        repeated, repeated_evidence, repeated_body = build_asof_artifacts(
            payload, CUTOFF, archive_hash, "2026-10-16T10:00:00Z")
        self.assertEqual(len(evidence["items"]), 28)
        self.assertEqual(sum(evidence["classificationCounts"].values()), 28)
        self.assertEqual(evidence["classificationCounts"], {
            "VERIFIED_AS_OF": 2, "REFERENCE_AS_OF": 1, "UNAVAILABLE_AS_OF": 25,
        })
        self.assertTrue(all(item["productionEligible"] is False for item in evidence["items"]))
        self.assertFalse(snapshot["productionEligible"])
        self.assertEqual(snapshot["snapshotId"], repeated["snapshotId"])
        self.assertEqual(snapshot["snapshotSha256"], repeated["snapshotSha256"])
        self.assertEqual(snapshot["analysisSha256"], repeated["analysisSha256"])
        self.assertNotEqual(snapshot["reportSha256"], repeated["reportSha256"])
        self.assertEqual(evidence["evidenceLedgerSha256"], repeated_evidence["evidenceLedgerSha256"])
        self.assertNotIn("81574.32", body)
        self.assertNotIn("157.76", body)
        self.assertNotIn("対象時刻後の相場反応", body)


if __name__ == "__main__":
    unittest.main()


