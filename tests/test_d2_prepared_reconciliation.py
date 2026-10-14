"""Forensic replay tests: untrusted local evidence NEVER triggers regeneration."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.reporting.d2_offline_prepared_run import run_prepared_offline
from scripts.reporting.d2_prepared_reconciliation import reconcile_prepared_offline
from scripts.reporting.d2_private_store import LocalPrivateEvidenceStore
from scripts.reporting.d2_monthly_budget import MonthlySpendInputs
from test_shadow_worker_offline import fixture_context, fixture_snapshot
from test_d2_responses_contract import provider_fixture


@unittest.skipUnless(os.name == "posix", "POSIX local proof staging only")
class TestPreparedForensicReplay(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "private"
        self.store = LocalPrivateEvidenceStore(self.root)
        self.ctx = fixture_context()
        self.snapshot = fixture_snapshot(self.ctx)
        self.run_id = "e2e-test-run"
        self.attempt_id = "e2e-test-attempt"
        self.calls = 0
        self.count_bytes = b'{"object":"response.input_tokens","input_tokens":9000}\n'
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

    def model(self, _):
        self.calls += 1
        return json.dumps(provider_fixture(self.ctx, self.snapshot),
                          ensure_ascii=False, indent=2).encode("utf-8")

    def execute(self, response=None):
        return run_prepared_offline(
            self.ctx, self.snapshot, self.store,
            response if response is not None else self.model,
            raw_count_fixture=self.count_bytes,
            monthly_inputs=self.monthly,
            run_id=self.run_id, attempt_id=self.attempt_id,
        )

    def replay(self, **kwargs):
        return reconcile_prepared_offline(
            self.ctx, self.snapshot, LocalPrivateEvidenceStore(self.root),
            monthly_inputs=kwargs.pop("monthly_inputs", self.monthly),
            run_id=kwargs.pop("run_id", self.run_id),
            attempt_id=kwargs.pop("attempt_id", self.attempt_id),
            **kwargs
        )

    def location(self, suffix):
        return self.root / self.run_id / f"{self.attempt_id}-{suffix}.json"

    def claim(self):
        return self.root / f"slot-{self.ctx.report_id}-r{self.ctx.revision}" / "claim.json"

    def test_absent_prep_cannot_prove_no_execution(self):
        result = self.replay()
        self.assertEqual(result.status, "UNRESOLVED_NO_PREPARATION")
        self.assertEqual(
            result.reason, "ABSENCE_DOES_NOT_PROVE_NO_EXTERNAL_EXECUTION")
        self.assertFalse(result.retry_allowed or result.api_send_allowed)
        self.assertFalse(result.publication_allowed)

    def test_full_chain_matches_but_never_authenticates(self):
        self.execute()
        first = self.replay()
        self.assertEqual(first.status, "OFFLINE_CHAIN_CONSISTENT_UNATTESTED")
        self.assertTrue(all((first.count_present, first.preparation_present,
                             first.claim_present, first.raw_present,
                             first.result_present)))
        self.assertFalse(first.externally_attested)
        self.assertFalse(first.api_send_allowed)
        self.assertFalse(first.retry_allowed)
        self.assertFalse(first.publication_allowed)
        self.assertEqual(first, self.replay())
        self.assertEqual(self.calls, 1)

    def test_raw_count_only_interrupt_after_first_file(self):
        self.store.put_once(
            f"shadow/{self.run_id}/{self.attempt_id}-inputcount", self.count_bytes)
        result = self.replay()
        self.assertEqual(result.status, "INTERRUPTED_NEEDS_MANUAL_REVIEW")
        self.assertEqual(result.reason, "COUNT_RAW_ONLY_NO_PREPARATION")
        self.assertFalse(result.claim_present)
        self.assertFalse(result.retry_allowed)

    def test_prep_saved_before_claim_returns_manual_review(self):
        self.execute()
        for p in (self.claim(), self.location("raw"), self.location("result")):
            p.unlink()
        result = self.replay()
        self.assertEqual(result.status, "INTERRUPTED_NEEDS_MANUAL_REVIEW")
        self.assertEqual(result.reason, "PREPARATION_SAVED_WITHOUT_SLOT_CLAIM")

    def test_crash_after_claim_but_before_result(self):
        def crash(_):
            self.calls += 1
            raise RuntimeError("fixture crashed after claim")
        with self.assertRaises(RuntimeError):
            self.execute(crash)
        finding = self.replay()
        self.assertEqual(finding.status, "INTERRUPTED_NEEDS_MANUAL_REVIEW")
        self.assertEqual(finding.reason, "DOWNSTREAM_SLOT_CLAIM_PRESENT_WITHOUT_RESULT")
        self.assertTrue(finding.claim_present)
        self.assertEqual(self.calls, 1)

    def test_timeout_does_not_allow_auto_retry(self):
        def timeout(_):
            self.calls += 1
            raise TimeoutError("synthetic timeout")
        out = self.execute(timeout)
        self.assertEqual(out.execution.status, "UNKNOWN_FIXTURE_RESULT")
        finding = self.replay()
        self.assertEqual(finding.status, "INTERRUPTED_NEEDS_MANUAL_REVIEW")
        self.assertEqual(finding.reason, "DOWNSTREAM_TIMEOUT_UNKNOWN_NO_AUTOMATIC_RETRY")
        self.assertEqual(self.calls, 1)

    def test_downstream_blocked_is_never_promoted_to_success(self):
        self.execute(lambda _: b'{"status":"completed","output":[]}')
        finding = self.replay()
        self.assertEqual(finding.status, "OFFLINE_BLOCKED_RECORDED")
        self.assertFalse(finding.publication_allowed)

    def test_count_bytes_tampering_detected(self):
        self.execute()
        self.location("inputcount").write_bytes(
            b'{"object":"response.input_tokens","input_tokens":3}')
        finding = self.replay()
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "PREPARATION_REPLAY_MISMATCH")

    def test_preparation_hash_tamper_detected(self):
        self.execute()
        p = self.location("preparation")
        d = json.loads(p.read_text())
        d["create_request_sha256"] = "0" * 64
        p.write_text(json.dumps(d))
        finding = self.replay()
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "PREPARATION_REPLAY_MISMATCH")

    def test_preparation_monthly_total_tamper_detected(self):
        self.execute()
        p = self.location("preparation")
        d = json.loads(p.read_text())
        d["monthly_total_with_reservation_usd"] = "0.0"
        p.write_text(json.dumps(d))
        finding = self.replay()
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "PREPARATION_REPLAY_MISMATCH")

    def test_supplied_monthly_usage_has_changed(self):
        self.execute()
        different = replace(self.monthly, reported_month_spend_usd="0.81")
        finding = self.replay(monthly_inputs=different)
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "PREPARATION_REPLAY_MISMATCH")

    def test_equal_total_different_spent_and_pending_is_detected(self):
        self.execute()
        # Originally 0.80 spent + 0.20 pending. Still 1.00, yet different
        # underlying billing evidence. Aggregates alone missed this.
        changed = replace(self.monthly,
                          reported_month_spend_usd="0.79",
                          outstanding_reservations_usd="0.21")
        finding = self.replay(monthly_inputs=changed)
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "PREPARATION_REPLAY_MISMATCH")
        self.assertFalse(finding.retry_allowed)

    def test_nonbinding_hard_cap_change_is_detected(self):
        self.execute()
        # The effective minimum remains project=$1.50, so old checks on
        # effective cap / total would wrongly accept this changed evidence.
        changed = replace(self.monthly, org_hard_limit_usd="4.00")
        finding = self.replay(monthly_inputs=changed)
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "PREPARATION_REPLAY_MISMATCH")

    def test_nonbinding_approved_month_cap_change_is_detected(self):
        self.execute()
        changed = replace(self.monthly, approved_month_cap_usd="2.50")
        finding = self.replay(monthly_inputs=changed)
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "PREPARATION_REPLAY_MISMATCH")

    def test_preparation_monthly_input_hash_tampering_is_detected(self):
        self.execute()
        p = self.location("preparation")
        record = json.loads(p.read_text())
        record["monthly_inputs_sha256"] = "0" * 64
        p.write_text(json.dumps(record))
        finding = self.replay()
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "PREPARATION_REPLAY_MISMATCH")

    def test_obsolete_preparation_schema_rejected(self):
        self.execute()
        p = self.location("preparation")
        record = json.loads(p.read_text())
        record["schema"] = "d2-offline-preparation/v1"
        record.pop("monthly_inputs_sha256")
        p.write_text(json.dumps(record))
        finding = self.replay()
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "PREPARATION_CONTENT_INVALID")

    def test_supplied_monthly_hard_cap_now_invalid(self):
        self.execute()
        altered = replace(self.monthly, project_hard_limit_enabled=False)
        finding = self.replay(monthly_inputs=altered)
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "LOCAL_PREPARATION_UNSAFE_OR_UNREPLAYABLE")

    def test_prompt_changes_cannot_reuse_saved_count(self):
        self.execute()
        finding = self.replay(instructions="This is a new instruction.")
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "PREPARATION_REPLAY_MISMATCH")

    def test_missing_raw_count_even_when_prep_exists(self):
        self.execute()
        self.location("inputcount").unlink()
        finding = self.replay()
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "PREPARATION_MISSING_COUNT_RAW")

    def test_missing_preparation_with_downstream_is_orphaned(self):
        self.execute()
        self.location("preparation").unlink()
        finding = self.replay()
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "DOWNSTREAM_WITHOUT_PREPARATION_RECEIPT")

    def test_claim_changed_from_original_request(self):
        self.execute()
        p = self.claim()
        d = json.loads(p.read_text())
        d["request_sha256"] = "0" * 64
        p.write_text(json.dumps(d))
        finding = self.replay()
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertTrue(finding.reason.startswith("DOWNSTREAM_"))

    def test_duplicate_keys_and_invalid_utf8_are_never_accepted(self):
        for corrupt in (b'{"schema":1,"schema":2}', b'\xff'):
            with self.subTest(corrupt=corrupt):
                with tempfile.TemporaryDirectory() as d:
                    store = LocalPrivateEvidenceStore(Path(d) / "private")
                    store.put_once(
                        f"shadow/{self.run_id}/{self.attempt_id}-inputcount",
                        self.count_bytes)
                    store.put_once(
                        f"shadow/{self.run_id}/{self.attempt_id}-preparation",
                        corrupt)
                    x = reconcile_prepared_offline(
                        self.ctx, self.snapshot, store,
                        monthly_inputs=self.monthly, run_id=self.run_id,
                        attempt_id=self.attempt_id)
                    self.assertEqual(x.status, "INCONSISTENT_UNTRUSTED")
                    self.assertFalse(x.retry_allowed)

    def test_symlinked_preparation_is_not_followed(self):
        self.execute()
        p = self.location("preparation")
        p.unlink()
        p.symlink_to(self.location("inputcount"))
        finding = self.replay()
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "LOCAL_PREPARATION_UNSAFE_OR_UNREPLAYABLE")

    def test_other_run_cannot_steal_existing_slot_or_claim(self):
        self.execute()
        finding = self.replay(run_id="other-run", attempt_id="other-attempt")
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "DOWNSTREAM_EVIDENCE_WITHOUT_PREPARATION")

    def test_fully_readonly_and_no_additional_model_invocation(self):
        self.execute()
        all_files = [self.claim()] + [self.location(x) for x in (
            "inputcount", "preparation", "raw", "result")]
        before = [(p.stat().st_mtime_ns, p.read_bytes()) for p in all_files]
        result = self.replay()
        after = [(p.stat().st_mtime_ns, p.read_bytes()) for p in all_files]
        self.assertEqual(result.status, "OFFLINE_CHAIN_CONSISTENT_UNATTESTED")
        self.assertEqual(before, after)
        self.assertEqual(self.calls, 1)


if __name__ == "__main__":
    unittest.main()
