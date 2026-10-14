"""Read-only crash-recovery simulations; no HTTP, Cloud, paid API or writer."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.reporting.d2_private_store import LocalPrivateEvidenceStore
from scripts.reporting.d2_offline_pipeline import exercise_d2_offline
from scripts.reporting.d2_reconciliation import reconcile_d2_offline
from test_shadow_worker_offline import fixture_context, fixture_snapshot
from test_d2_responses_contract import provider_fixture


@unittest.skipUnless(os.name == "posix", "local POSIX staging only")
class TestD2ReadOnlyRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "private"
        self.store = LocalPrivateEvidenceStore(self.root)
        self.context = fixture_context()
        self.snapshot = fixture_snapshot(self.context)
        self.run = "run-fixture-one"
        self.attempt = "attempt-fixture-one"
        self.calls = 0

    def responder(self, request):
        self.calls += 1
        self.assertEqual(request["tools"], [])
        return json.dumps(provider_fixture(self.context, self.snapshot),
                          ensure_ascii=False, indent=2).encode("utf-8")

    def execute(self, fn=None):
        return exercise_d2_offline(
            self.context, self.snapshot, self.store,
            fn if fn is not None else self.responder,
            run_id=self.run, attempt_id=self.attempt,
        )

    def inspect(self):
        return reconcile_d2_offline(
            self.context, self.snapshot, LocalPrivateEvidenceStore(self.root),
            run_id=self.run, attempt_id=self.attempt,
        )

    def rewrite(self, key, body):
        path = self.root / key
        assert path.is_file(), key
        path.write_bytes(body)

    def result_key(self):
        return f"{self.run}/{self.attempt}-result.json"

    def raw_key(self):
        return f"{self.run}/{self.attempt}-raw.json"

    def claim_key(self):
        return f"slot-{self.context.report_id}-r{self.context.revision}/claim.json"

    def test_no_claim_never_authorizes_new_execution(self):
        finding = self.inspect()
        self.assertEqual(finding.status, "UNRESOLVED_NO_CLAIM")
        self.assertEqual(finding.reason, "CANNOT_PROVE_NO_PRIOR_EXECUTION")
        self.assertFalse(finding.retry_allowed)
        self.assertFalse(finding.api_send_allowed)
        self.assertFalse(finding.publication_allowed)
        self.assertEqual(self.calls, 0)

    def test_readonly_replay_of_valid_fixture_still_cannot_publish(self):
        self.execute()
        first = self.inspect()
        second = self.inspect()
        self.assertEqual(first, second)
        self.assertEqual(first.status, "OFFLINE_CONSISTENT_UNATTESTED")
        self.assertEqual(first.reason, "LOCAL_REPLAY_MATCHES_NO_PROVIDER_ATTESTATION")
        self.assertEqual((first.slot_claim_present, first.raw_present,
                          first.result_present), (True, True, True))
        self.assertFalse(first.retry_allowed or first.publication_allowed)
        self.assertEqual(self.calls, 1)

    def test_timeout_preserves_unknown_state(self):
        def timeout(_):
            self.calls += 1
            raise TimeoutError("simulated")
        self.execute(timeout)
        x = self.inspect()
        self.assertEqual(x.status, "INTERRUPTED_NEEDS_MANUAL_REVIEW")
        self.assertEqual(x.reason, "TIMEOUT_UNKNOWN_NO_AUTOMATIC_RETRY")
        self.assertEqual((x.slot_claim_present, x.raw_present,
                          x.result_present), (True, False, True))
        self.assertEqual(self.calls, 1)

    def test_unexpected_worker_crash_after_claim_is_not_retried(self):
        def crash(_):
            self.calls += 1
            raise RuntimeError("process crashed after slot claimed")
        with self.assertRaisesRegex(RuntimeError, "process crashed"):
            self.execute(crash)
        x = self.inspect()
        self.assertEqual(x.status, "INTERRUPTED_NEEDS_MANUAL_REVIEW")
        self.assertEqual(x.reason, "SLOT_CLAIM_PRESENT_WITHOUT_RESULT")
        self.assertFalse(x.retry_allowed)
        self.assertEqual(self.calls, 1)

    def test_crash_after_raw_evidence_before_result(self):
        def crash(_):
            self.calls += 1
            raise RuntimeError("simulated")
        with self.assertRaises(RuntimeError):
            self.execute(crash)
        self.store.put_once(f"shadow/{self.run}/{self.attempt}-raw",
                            self.responder({"tools": []}))
        x = self.inspect()
        self.assertEqual(x.status, "INTERRUPTED_NEEDS_MANUAL_REVIEW")
        self.assertEqual(x.reason, "RAW_PRESENT_WITHOUT_RESULT")
        self.assertTrue(x.raw_present)
        self.assertFalse(x.result_present)
        self.assertFalse(x.retry_allowed)

    def test_known_blocked_result_never_upgraded_from_saved_raw(self):
        raw = provider_fixture(self.context, self.snapshot)
        obj = json.loads(raw["output"][0]["content"][0]["text"])
        obj["numeric_claims"] = []
        raw["output"][0]["content"][0]["text"] = json.dumps(obj)
        self.execute(lambda _: json.dumps(raw).encode("utf8"))
        x = self.inspect()
        self.assertEqual(x.status, "OFFLINE_BLOCKED_RECORDED")
        self.assertFalse(x.publication_allowed)
        self.assertTrue(x.raw_present)

    def test_raw_tampering_is_detected_as_inconsistency(self):
        self.execute()
        self.rewrite(self.raw_key(), b'{"wrong":"data"}')
        x = self.inspect()
        self.assertEqual(x.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(x.reason, "RAW_DIGEST_OR_ID_MISMATCH")

    def test_slot_claim_tampering_is_detected(self):
        self.execute()
        data = json.loads((self.root / self.claim_key()).read_text())
        data["run_id"] = "other-run"
        self.rewrite(self.claim_key(), json.dumps(data).encode())
        x = self.inspect()
        self.assertEqual(x.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(x.reason, "SLOT_CLAIM_CONTENT_INVALID")

    def test_results_with_forged_success_status_are_not_trusted(self):
        def timeout(_):
            raise TimeoutError()
        self.execute(timeout)
        path = self.root / self.result_key()
        data = json.loads(path.read_text())
        data["status"] = "OFFLINE_FIXTURE_VALIDATED"
        self.rewrite(self.result_key(), json.dumps(data).encode())
        x = self.inspect()
        self.assertEqual(x.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(x.reason, "RAW_OBJECT_MISSING")

    def test_claim_budget_quote_tampering_is_rejected(self):
        self.execute()
        path = self.root / self.claim_key()
        record = json.loads(path.read_text())
        record["max_input_tokens"] = 8000
        self.rewrite(self.claim_key(), json.dumps(record).encode())
        finding = self.inspect()
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "SLOT_CLAIM_CONTENT_INVALID")
        self.assertFalse(finding.retry_allowed)

    def test_result_budget_cap_tampering_is_rejected(self):
        self.execute()
        path = self.root / self.result_key()
        record = json.loads(path.read_text())
        record["max_model_cost_usd"] = "9.99"
        self.rewrite(self.result_key(), json.dumps(record).encode())
        finding = self.inspect()
        self.assertEqual(finding.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(finding.reason, "RUN_RESULT_CONTENT_INVALID")
        self.assertFalse(finding.publication_allowed)

    def test_producer_over_token_cap_is_blocked_even_when_hashes_match(self):
        result = exercise_d2_offline(
            self.context, self.snapshot, self.store, self.responder,
            run_id=self.run, attempt_id=self.attempt, max_input_tokens=11999)
        self.assertEqual(result.status, "OFFLINE_BLOCKED")
        self.assertEqual(result.reason, "ACTUAL_TOKEN_CAP_EXCEEDED")
        finding = self.inspect()
        self.assertEqual(finding.status, "OFFLINE_BLOCKED_RECORDED")
        self.assertFalse(finding.retry_allowed)
        self.assertFalse(finding.publication_allowed)

    def test_evidence_result_hash_mismatch_detected(self):
        self.execute()
        path = self.root / self.result_key()
        data = json.loads(path.read_text())
        data["body_sha256"] = "0" * 64
        self.rewrite(self.result_key(), json.dumps(data).encode())
        x = self.inspect()
        self.assertEqual(x.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(x.reason, "VALIDATED_DIGEST_MISMATCH")

    def test_malformed_json_or_duplicate_key_fails_closed(self):
        self.execute()
        self.rewrite(self.result_key(), b'{"schema":1,"schema":2}')
        x = self.inspect()
        self.assertEqual(x.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(x.reason, "LOCAL_EVIDENCE_MALFORMED_OR_UNSAFE")

    def test_orphaned_raw_evidence_cannot_establish_slot(self):
        self.store.put_once(f"shadow/{self.run}/{self.attempt}-raw", b'{"ok":true}')
        x = self.inspect()
        self.assertEqual(x.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(x.reason, "ORPHANED_EVIDENCE_NO_SLOT_CLAIM")
        self.assertFalse(x.retry_allowed)

    def test_symlinked_run_directory_blocks_diagnostics(self):
        (self.root / self.run).symlink_to(Path(self.temp.name), target_is_directory=True)
        x = self.inspect()
        self.assertEqual(x.status, "INCONSISTENT_UNTRUSTED")
        self.assertEqual(x.reason, "LOCAL_EVIDENCE_MALFORMED_OR_UNSAFE")

    def test_inspection_does_not_change_any_saved_files(self):
        self.execute()
        paths = [self.root / self.claim_key(), self.root / self.raw_key(),
                 self.root / self.result_key()]
        before = [(p.stat().st_mtime_ns, p.read_bytes()) for p in paths]
        self.inspect()
        after = [(p.stat().st_mtime_ns, p.read_bytes()) for p in paths]
        self.assertEqual(before, after)

    def test_untrusted_size_limit_cannot_be_overridden_by_bad_value(self):
        self.execute()
        with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_SIZE_LIMIT_INVALID"):
            self.store.read_for_diagnostics(
                f"shadow/{self.run}/{self.attempt}-raw", max_bytes=0)
        with self.assertRaisesRegex(ValueError, "DIAGNOSTIC_BYTES_EXCEED_LIMIT"):
            self.store.read_for_diagnostics(
                f"shadow/{self.run}/{self.attempt}-raw", max_bytes=1)


if __name__ == "__main__":
    unittest.main()
