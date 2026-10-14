"""D2 offline pre-generation safety chain; all calls are synthetic."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.reporting.d2_offline_prepared_run import (
    run_prepared_offline, PreparedOfflineBlocked
)
from scripts.reporting.d2_private_store import LocalPrivateEvidenceStore
from test_shadow_worker_offline import fixture_context, fixture_snapshot
from test_d2_responses_contract import provider_fixture
from scripts.reporting.d2_monthly_budget import MonthlySpendInputs, monthly_inputs_sha256


@unittest.skipUnless(os.name == "posix", "POSIX private staging only")
class TestD2PreparedOfflineRun(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "safe"
        self.store = LocalPrivateEvidenceStore(self.root)
        self.ctx = fixture_context()
        self.snapshot = fixture_snapshot(self.ctx)
        self.calls = 0
        self.count = b'{"object":"response.input_tokens","input_tokens":9000}\n'
        self.monthly = MonthlySpendInputs(
            report_id=self.ctx.report_id,
            month_jst=self.ctx.report_date[:7],
            reported_month_spend_usd="0.80",
            outstanding_reservations_usd="0.20",
            approved_month_cap_usd="2.00",
            project_hard_limit_usd="1.50",
            org_hard_limit_usd="3.00",
            project_hard_limit_enabled=True,
            org_hard_limit_enabled=True,
        )

    def responder(self, request):
        self.calls += 1
        self.assertEqual(request["tools"], [])
        self.assertFalse(request["store"])
        return json.dumps(provider_fixture(self.ctx, self.snapshot),
                          ensure_ascii=False, indent=2).encode("utf8")

    def execute(self, **kwargs):
        return run_prepared_offline(
            self.ctx, self.snapshot, self.store, self.responder,
            raw_count_fixture=kwargs.pop("raw_count_fixture", self.count),
            monthly_inputs=kwargs.pop("monthly_inputs", self.monthly),
            run_id=kwargs.pop("run_id", "prepared-run"),
            attempt_id=kwargs.pop("attempt_id", "prepared-attempt"),
            **kwargs,
        )

    def no_claim(self):
        path = self.root / f"slot-{self.ctx.report_id}-r{self.ctx.revision}"
        self.assertFalse(path.exists())
        self.assertEqual(self.calls, 0)

    def test_successful_synthetic_chain_does_not_authorize_any_send(self):
        outcome = self.execute()
        self.assertEqual(outcome.execution.status, "OFFLINE_FIXTURE_VALIDATED")
        self.assertEqual(self.calls, 1)
        self.assertFalse(outcome.api_send_allowed)
        self.assertFalse(outcome.publication_allowed)
        self.assertFalse(outcome.execution.publishable)
        self.assertFalse(outcome.execution.api_send_allowed)
        prep = json.loads(self.store.read_verified(outcome.preparation_receipt))
        claim = json.loads(self.store.read_verified(outcome.execution.claim_receipt))
        self.assertEqual(prep["create_request_sha256"], claim["request_sha256"])
        self.assertEqual(prep["counted_input_tokens"], 9000)
        self.assertEqual(prep["max_input_tokens"], 12000)
        self.assertEqual(prep["monthly_total_with_reservation_usd"], "1.027")
        self.assertEqual(prep["monthly_effective_cap_usd"], "1.50")
        self.assertEqual(prep["schema"], "d2-offline-preparation/v2")
        self.assertEqual(prep["monthly_inputs_sha256"],
                         monthly_inputs_sha256(self.monthly))
        self.assertEqual(len(prep["monthly_inputs_sha256"]), 64)
        self.assertEqual(prep["count_evidence_kind"],
                         "SYNTHETIC_FIXTURE_NOT_AUTHENTICATED")
        self.assertEqual(prep["billing_evidence_kind"],
                         "SYNTHETIC_VALUES_NOT_AUTHENTICATED")
        self.assertEqual(
            self.store.read_verified(outcome.count_receipt), self.count)
        self.assertFalse(prep["api_send_allowed"])
        self.assertFalse(prep["publication_allowed"])

    def test_monthly_full_field_digest_catches_equal_sum_inputs(self):
        # Only the local commitment changes, not total monthly amount.
        changed = replace(self.monthly,
                          reported_month_spend_usd="0.79",
                          outstanding_reservations_usd="0.21")
        self.assertNotEqual(monthly_inputs_sha256(self.monthly),
                            monthly_inputs_sha256(changed))
        first = self.execute()
        prep = json.loads(self.store.read_verified(first.preparation_receipt))
        self.assertEqual(prep["monthly_inputs_sha256"],
                         monthly_inputs_sha256(self.monthly))

    def test_count_over_cap_fails_before_claim_and_fixture(self):
        bad = b'{"object":"response.input_tokens","input_tokens":12001}'
        with self.assertRaisesRegex(PreparedOfflineBlocked,
                                    "MODEL_INPUT_TOKEN_CAP_EXCEEDED"):
            self.execute(raw_count_fixture=bad)
        self.no_claim()

    def test_count_duplicate_json_field_fails_before_claim(self):
        with self.assertRaises(PreparedOfflineBlocked):
            self.execute(raw_count_fixture=b'{"input_tokens":1,"input_tokens":2}')
        self.no_claim()

    def test_count_spoofing_integers_rejected_before_claim(self):
        for bad in (True, "9000", None, -1):
            with self.subTest(bad=bad), self.assertRaises(PreparedOfflineBlocked):
                self.execute(raw_count_fixture=json.dumps({
                    "object": "response.input_tokens", "input_tokens": bad,
                }).encode())
        self.no_claim()

    def test_monthly_cap_breach_fails_before_claim(self):
        policy = replace(self.monthly, project_hard_limit_usd="1.00")
        with self.assertRaisesRegex(PreparedOfflineBlocked,
                                    "MONTHLY_BUDGET_RESERVATION_OVER_LIMIT"):
            self.execute(monthly_inputs=policy)
        self.no_claim()

    def test_monthly_hard_limit_not_enabled_rejected_before_claim(self):
        policy = replace(self.monthly, org_hard_limit_enabled=False)
        with self.assertRaisesRegex(PreparedOfflineBlocked,
                                    "BOTH_HARD_SPEND_LIMITS_REQUIRED"):
            self.execute(monthly_inputs=policy)
        self.no_claim()

    def test_report_id_other_slot_same_month_is_rejected(self):
        policy = replace(self.monthly, report_id="2026-10-15_12-00")
        with self.assertRaisesRegex(PreparedOfflineBlocked,
                                    "MONTHLY_REPORT_ID_MISMATCH"):
            self.execute(monthly_inputs=policy)
        self.no_claim()

    def test_changed_instructions_require_fresh_count_preparation(self):
        first = self.execute(instructions="Immutable snapshot only.")
        self.assertEqual(first.execution.status, "OFFLINE_FIXTURE_VALIDATED")
        prep = json.loads(self.store.read_verified(first.preparation_receipt))
        another = tempfile.TemporaryDirectory()
        self.addCleanup(another.cleanup)
        self.store = LocalPrivateEvidenceStore(Path(another.name) / "safe")
        second = self.execute(instructions="A distinct prompt.")
        prep2 = json.loads(self.store.read_verified(second.preparation_receipt))
        self.assertNotEqual(prep["create_request_sha256"],
                            prep2["create_request_sha256"])
        self.assertNotEqual(prep["count_request_sha256"],
                            prep2["count_request_sha256"])
        self.assertEqual(self.calls, 2)

    def test_duplicate_run_or_slot_cannot_invoke_second_responder(self):
        first = self.execute()
        self.assertEqual(first.execution.status, "OFFLINE_FIXTURE_VALIDATED")
        with self.assertRaisesRegex(PreparedOfflineBlocked,
                                    "PREPARATION_STORAGE_BLOCKED"):
            self.execute()
        self.assertEqual(self.calls, 1)
        with self.assertRaises(Exception):
            self.execute(run_id="other-run", attempt_id="other-attempt")
        self.assertEqual(self.calls, 1)

    def test_timeout_keeps_preparation_and_claim_locked(self):
        def timeout(_):
            self.calls += 1
            raise TimeoutError("unknown")
        result = run_prepared_offline(
            self.ctx, self.snapshot, self.store, timeout,
            raw_count_fixture=self.count, monthly_inputs=self.monthly,
            run_id="run-timeout", attempt_id="attempt-timeout",
        )
        self.assertEqual(result.execution.status, "UNKNOWN_FIXTURE_RESULT")
        self.assertFalse(result.publication_allowed)
        with self.assertRaises(PreparedOfflineBlocked):
            self.execute(run_id="run-timeout", attempt_id="attempt-timeout")
        self.assertEqual(self.calls, 1)

    def test_bad_output_is_blocked_even_when_prerequisites_pass(self):
        def bad_response(_):
            self.calls += 1
            return b'{"status":"completed","output":[]}'
        result = run_prepared_offline(
            self.ctx, self.snapshot, self.store, bad_response,
            raw_count_fixture=self.count, monthly_inputs=self.monthly,
            run_id="bad-output", attempt_id="bad-attempt",
        )
        self.assertEqual(result.execution.status, "OFFLINE_BLOCKED")
        self.assertFalse(result.publication_allowed)
        self.assertEqual(self.calls, 1)

    def test_no_approved_budget_for_count_is_not_bypassed(self):
        with self.assertRaisesRegex(PreparedOfflineBlocked,
                                    "COUNT_WORST_CASE_BUDGET_EXCEEDED"):
            self.execute(max_model_cost_usd="0.001")
        self.no_claim()

    def test_persisted_preparation_bytes_not_rewritten_on_reinspection(self):
        result = self.execute()
        p = self.root / "prepared-run/prepared-attempt-preparation.json"
        original = p.read_bytes()
        receipt = result.preparation_receipt
        reopened = LocalPrivateEvidenceStore(self.root)
        self.assertEqual(reopened.read_verified(receipt), original)
        self.assertEqual(p.read_bytes(), original)
        self.assertEqual(self.calls, 1)

    def test_invalid_raw_count_type_rejected_before_any_generation(self):
        with self.assertRaisesRegex(PreparedOfflineBlocked,
                                    "SYNTHETIC_COUNT_BYTES_REQUIRED"):
            self.execute(raw_count_fixture={"input_tokens": 9})
        self.no_claim()

    def test_no_external_io_dependency_in_composition_module(self):
        import ast
        from scripts.reporting import d2_offline_prepared_run
        roots=set()
        for n in ast.walk(ast.parse(Path(d2_offline_prepared_run.__file__).read_text())):
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
