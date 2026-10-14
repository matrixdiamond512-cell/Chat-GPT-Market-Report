"""D2 numeric provenance regression: offline fixtures and no API access."""
from dataclasses import replace
import unittest

from scripts.reporting.d2_numeric_claims import (
    audit_numeric_claims, verified_source_bundle, NumericClaimBlocked,
    _non_claim_tokens,
)
from scripts.reporting.snapshot import MarketDataSnapshot
from scripts.reporting.shadow_worker import ShadowBlocked
from test_shadow_worker_offline import fixture_context, fixture_snapshot


class TestD2NumericClaims(unittest.TestCase):
    def setUp(self):
        self.context = fixture_context()
        self.snapshot = fixture_snapshot(self.context)
        self.gold = self.snapshot.markets[0]
        self.title = "マーケットレポート｜2026/10/15（木）16:00\n"

    def claim(self, body, literal, *, series="gold", field="priceValue",
              source_id=None, as_of=None):
        m = next(m for m in self.snapshot.markets if m.instrument == series)
        return {
            "start": body.index(literal, len(self.title)),
            "literal": literal, "series": series, "field": field,
            "source_id": source_id or m.source[0]["id"],
            "as_of": as_of or m.asOf,
        }

    def test_independent_source_bundle_binds_snapshot_id_cutoff_and_timestamp(self):
        b = verified_source_bundle(self.context, self.snapshot)
        self.assertEqual(b["snapshot_id"], self.snapshot.snapshot_id)
        self.assertEqual(b["cutoff"], self.context.data_cutoff)
        self.assertEqual(b["observations"][0]["as_of"], self.gold.asOf)
        self.assertEqual(b["observations"][0]["source"][0]["id"], self.gold.source[0]["id"])
        self.assertEqual(b["observations"][0]["priceValue"], self.gold.priceValue)

    def test_lexical_coverage_price_and_percentage_from_frozen_fields(self):
        gold = replace(self.gold, changePct=1.25, direction="UP",
                       comparisonBasis="previous_close")
        markets = (gold, *self.snapshot.markets[1:])
        self.snapshot = MarketDataSnapshot.capture(self.context, markets,
                                                  self.snapshot.captured_at)
        body = self.title + "gold: 100.0 USD/oz、gold変化率: +1.25%"
        claims = [self.claim(body, "100.0"), self.claim(
            body, "+1.25", field="changePct")]
        audit = audit_numeric_claims(self.context, self.snapshot, body, claims)
        self.assertEqual(audit.checked_claims, 2)
        self.assertEqual(audit.scanned_numbers, 2)
        self.assertFalse(audit.publication_allowed)

    def test_unapproved_number_rejected_even_if_prose_contains_known_price(self):
        body = self.title + "gold: 100.0 USD/oz、推測価格999.0"
        with self.assertRaisesRegex(NumericClaimBlocked, "NUMERIC_COVERAGE_INCOMPLETE"):
            audit_numeric_claims(self.context, self.snapshot, body,
                                 [self.claim(body, "100.0")])

    def test_numerical_value_and_source_references_are_not_self_authenticating(self):
        body = self.title + "gold: 999.0 USD/oz"
        with self.assertRaisesRegex(NumericClaimBlocked, "NUMERIC_VALUE_MISMATCH"):
            audit_numeric_claims(self.context, self.snapshot, body,
                                 [self.claim(body, "999.0")])
        body = self.title + "gold: 100.0 USD/oz"
        with self.assertRaisesRegex(NumericClaimBlocked, "NUMERIC_SOURCE_TIME_OR_ID_MISMATCH"):
            audit_numeric_claims(self.context, self.snapshot, body,
                                 [self.claim(body, "100.0", source_id="fake")])
        with self.assertRaisesRegex(NumericClaimBlocked, "NUMERIC_SOURCE_TIME_OR_ID_MISMATCH"):
            audit_numeric_claims(self.context, self.snapshot, body,
                                 [self.claim(body, "100.0",
                                             as_of="2026-10-15T16:01:00+09:00")])

    def test_duplicate_claim_cannot_hide_an_unexplained_number(self):
        body = self.title + "gold: 100.0 USD/oz, 777.0の統計"
        c = self.claim(body, "100.0")
        with self.assertRaisesRegex(NumericClaimBlocked, "NUMERIC_SPAN_UNKNOWN_OR_DUPLICATED"):
            audit_numeric_claims(self.context, self.snapshot, body, [c, dict(c)])

    def test_price_with_percent_suffix_is_forbidden(self):
        body = self.title + "gold: 100.0%"
        with self.assertRaisesRegex(NumericClaimBlocked, "NUMERIC_UNIT_CONFLICT"):
            audit_numeric_claims(self.context, self.snapshot, body,
                                 [self.claim(body, "100.0")])

    def test_date_metadata_not_arbitrarily_exempted_elsewhere(self):
        body = self.title + "gold: 100.0 USD/oz　発表は2026/10/15"
        with self.assertRaisesRegex(NumericClaimBlocked, "NUMERIC_COVERAGE_INCOMPLETE"):
            audit_numeric_claims(self.context, self.snapshot, body,
                                 [self.claim(body, "100.0")])

    def test_known_market_name_with_digits_is_metadata_but_other_numbers_arent(self):
        body = self.title + "nikkei225_futures_ose: 102.0 円"
        literals = [m.group(0) for m in _non_claim_tokens(body, self.context, self.snapshot)]
        self.assertEqual(literals, ["102.0"])
        self.assertEqual(audit_numeric_claims(self.context, self.snapshot, body,
                         [self.claim(body, "102.0", series="nikkei225_futures_ose")]).checked_claims, 1)

    def test_fullwidth_decimal_must_match_underlying_value(self):
        body = self.title + "gold: １００．０ USD/oz"
        audit = audit_numeric_claims(self.context, self.snapshot, body,
                                     [self.claim(body, "１００．０")])
        self.assertEqual(audit.checked_claims, 1)

    def test_signed_zero_semantics_cannot_be_lost(self):
        zero = replace(self.gold, priceValue=-0.0)
        self.snapshot = MarketDataSnapshot.capture(self.context,
            (zero, *self.snapshot.markets[1:]), self.snapshot.captured_at)
        body = self.title + "gold: 0.0 USD/oz"
        with self.assertRaisesRegex(NumericClaimBlocked, "NUMERIC_SIGNED_ZERO_MISMATCH"):
            audit_numeric_claims(self.context, self.snapshot, body,
                                 [self.claim(body, "0.0")])
        body = self.title + "gold: -0.0 USD/oz"
        self.assertEqual(audit_numeric_claims(self.context, self.snapshot, body,
                         [self.claim(body, "-0.0")]).checked_claims, 1)

    def test_stale_observation_blocks_all_claims(self):
        stale = replace(self.gold, status="STALE")
        self.snapshot = MarketDataSnapshot.capture(self.context,
            (stale, *self.snapshot.markets[1:]), self.snapshot.captured_at)
        body = self.title + "gold: 100.0 USD/oz"
        with self.assertRaisesRegex(ShadowBlocked, "MARKET_UNVERIFIED_OR_STALE"):
            audit_numeric_claims(self.context, self.snapshot, body,
                                 [self.claim(body, "100.0")])

    def test_unavailable_field_must_not_be_implicitly_invented(self):
        body = self.title + "gold: 100.0 USD/oz"
        with self.assertRaisesRegex(NumericClaimBlocked, "NUMERIC_SOURCE_VALUE_MISSING"):
            audit_numeric_claims(self.context, self.snapshot, body,
                                 [self.claim(body, "100.0", field="changeValue")])

    def test_unsupported_exponent_blocks_instead_of_reinterpreting(self):
        body = self.title + "gold: 1e-7 USD/oz"
        with self.assertRaisesRegex(NumericClaimBlocked, "NUMERIC_COVERAGE_INCOMPLETE"):
            audit_numeric_claims(self.context, self.snapshot, body, [])


if __name__ == "__main__":
    unittest.main()
