"""Synthetic monthly math and hard-limit selection: no billing API / send."""
from dataclasses import replace
import unittest

from scripts.reporting.d2_monthly_budget import (
    MonthlySpendInputs, review_monthly_budget, BudgetReviewBlocked,
)
from scripts.reporting.d2_responses_contract import build_request
from scripts.reporting.d2_token_count_contract import build_count_plan
from test_shadow_worker_offline import fixture_context, fixture_snapshot


class TestD2MonthlyBudget(unittest.TestCase):
    def setUp(self):
        ctx = fixture_context()
        req = build_request(ctx, fixture_snapshot(ctx), instructions="Frozen sources only.")
        self.plan = build_count_plan(req)
        self.policy = MonthlySpendInputs(
            report_id="2026-10-15_16-00",
            month_jst="2026-10",
            reported_month_spend_usd="0.80",
            outstanding_reservations_usd="0.20",
            approved_month_cap_usd="2.00",
            project_hard_limit_usd="1.50",
            org_hard_limit_usd="3.00",
            project_hard_limit_enabled=True,
            org_hard_limit_enabled=True,
        )

    def test_monthly_math_considers_reservations_and_strictest_cap(self):
        outcome = review_monthly_budget(self.plan, self.policy)
        self.assertEqual(outcome.strictest_cap_usd, "1.50")
        self.assertEqual(outcome.total_with_proposed_reservation_usd, "1.027")
        self.assertEqual(outcome.remaining_after_reservation_usd, "0.473")
        self.assertFalse(outcome.external_billing_attested)
        self.assertFalse(outcome.send_allowed)
        self.assertFalse(outcome.publication_allowed)

    def test_real_billing_can_never_be_attested_by_json_fixture(self):
        for limit in ("2.00", "999.00"):
            result = review_monthly_budget(self.plan,
                replace(self.policy, approved_month_cap_usd=limit))
            self.assertFalse(result.send_allowed)
            self.assertEqual(result.status, "OFFLINE_MONTHLY_ARITHMETIC_PASS_NOT_ATTESTED")

    def test_user_cap_also_applies_even_when_project_hard_limit_high(self):
        policy = replace(self.policy, approved_month_cap_usd="1.01",
                         project_hard_limit_usd="50.00",
                         org_hard_limit_usd="50.00")
        with self.assertRaisesRegex(
                BudgetReviewBlocked, "MONTHLY_BUDGET_RESERVATION_OVER_LIMIT"):
            review_monthly_budget(self.plan, policy)

    def test_spent_plus_pending_and_max_model_cost_cannot_exceed_limit(self):
        for field, value in (
            ("reported_month_spend_usd", "1.48"),
            ("outstanding_reservations_usd", "0.48"),
            ("project_hard_limit_usd", "0.90"),
            ("org_hard_limit_usd", "0.50"),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(
                    BudgetReviewBlocked, "MONTHLY_BUDGET_RESERVATION_OVER_LIMIT"):
                review_monthly_budget(self.plan, replace(self.policy, **{field:value}))

    def test_equality_with_limit_is_math_pass_only(self):
        x = review_monthly_budget(self.plan,
            replace(self.policy, project_hard_limit_usd="1.027"))
        self.assertEqual(x.remaining_after_reservation_usd, "0.000")
        self.assertFalse(x.send_allowed)

    def test_alert_only_or_missing_hard_limit_is_blocked(self):
        for field in ("project_hard_limit_enabled", "org_hard_limit_enabled"):
            for value in (False, None, "yes"):
                with self.subTest(field=field, value=value), self.assertRaisesRegex(
                        BudgetReviewBlocked, "BOTH_HARD_SPEND_LIMITS_REQUIRED"):
                    review_monthly_budget(self.plan,
                                          replace(self.policy, **{field:value}))

    def test_cross_month_report_is_blocked(self):
        for args in (
            {"month_jst":"2026-11"},
            {"report_id":"2026-11-02_16-00"},
        ):
            with self.subTest(args=args), self.assertRaisesRegex(
                    BudgetReviewBlocked, "BILLING_MONTH_MISMATCH"):
                review_monthly_budget(self.plan, replace(self.policy, **args))

    def test_invalid_report_day_and_wrong_slot_block(self):
        for report_id in ("2026-13-15_16-00", "2026-10-15_18-00",
                          "2026-10-15_16-01", "today"):
            with self.subTest(report_id=report_id), self.assertRaises(BudgetReviewBlocked):
                review_monthly_budget(self.plan,
                                      replace(self.policy, report_id=report_id))

    def test_false_currency_or_precision_blocks(self):
        for field in (
            "reported_month_spend_usd", "outstanding_reservations_usd",
            "approved_month_cap_usd", "project_hard_limit_usd",
            "org_hard_limit_usd"
        ):
            for value in ("nan", "-1", "1e5", 1.0, True, "01.00", "1.000000001"):
                with self.subTest(field=field, value=value), self.assertRaises(BudgetReviewBlocked):
                    review_monthly_budget(self.plan,
                                          replace(self.policy, **{field:value}))

    def test_zero_hard_limit_and_user_cap_never_enable_send(self):
        for field in ("approved_month_cap_usd",
                      "project_hard_limit_usd", "org_hard_limit_usd"):
            with self.subTest(field=field), self.assertRaises(BudgetReviewBlocked):
                review_monthly_budget(self.plan, replace(self.policy, **{field:"0"}))

    def test_budget_review_has_no_network_or_payment_mutation(self):
        import ast
        from pathlib import Path
        from scripts.reporting import d2_monthly_budget
        roots=set()
        for n in ast.walk(ast.parse(Path(d2_monthly_budget.__file__).read_text())):
            if isinstance(n, ast.Import):
                roots.update(x.name.split(".")[0] for x in n.names)
            if isinstance(n, ast.ImportFrom) and n.module:
                roots.add(n.module.split(".")[0])
        self.assertFalse(roots & {
            "openai", "requests", "urllib", "httpx", "socket",
            "googleapiclient", "subprocess"
        })


if __name__ == "__main__":
    unittest.main()
