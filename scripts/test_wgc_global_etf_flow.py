#!/usr/bin/env python3
"""WGC global ETF flow must never be confused with European regional flow."""
from __future__ import annotations

import unittest

from enrich_gold_etf_flow import parse_wgc_global_monthly_flow_usd_billion


class GlobalGoldEtfFlowsTests(unittest.TestCase):
    def test_september_2026_global_10bn_before_or_after_europe_3point6bn(self):
        global_sentence = "Global gold ETFs attracted US$10bn in September, lifting Q3 inflows to a record US$31bn."
        europe_sentence = "European gold ETFs saw inflows of US$3.6bn in September."
        self.assertEqual(
            parse_wgc_global_monthly_flow_usd_billion(europe_sentence + " " + global_sentence), 10.0
        )
        self.assertEqual(
            parse_wgc_global_monthly_flow_usd_billion(global_sentence + " " + europe_sentence), 10.0
        )

    def test_regional_only_or_ambiguous_page_remains_unknown(self):
        self.assertIsNone(parse_wgc_global_monthly_flow_usd_billion("European gold ETFs saw inflows of US$3.6bn."))
        self.assertIsNone(parse_wgc_global_monthly_flow_usd_billion("Gold ETF inflows of US$3.6bn."))

    def test_explicit_global_outflows_sign(self):
        self.assertEqual(
            parse_wgc_global_monthly_flow_usd_billion(
                "Global gold ETFs recorded net outflows of US$2.4bn in April."
            ), -2.4
        )

    def test_explicit_global_positive_inflows(self):
        self.assertEqual(
            parse_wgc_global_monthly_flow_usd_billion("Global gold ETFs saw inflows of US$18bn in August."), 18.0
        )


if __name__ == "__main__":
    unittest.main()
