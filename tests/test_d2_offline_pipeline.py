"""Offline D2 integration tests: no SDK, keys, paid API or public writers."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.reporting.d2_offline_pipeline import (
    exercise_d2_offline, OfflineD2Blocked,
)
from scripts.reporting.d2_private_store import LocalPrivateEvidenceStore
from scripts.reporting.snapshot import MarketDataSnapshot
from test_shadow_worker_offline import fixture_context, fixture_snapshot, fixture_market, REQUIRED_SIX
from test_d2_responses_contract import provider_fixture


@unittest.skipUnless(os.name == "posix", "POSIX staging test only")
class TestD2OfflineIntegrated(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "private"
        self.store = LocalPrivateEvidenceStore(self.root)
        self.context = fixture_context()
        self.snapshot = fixture_snapshot(self.context)
        self.invocations = 0

    def fixture(self, request):
        self.invocations += 1
        self.assertEqual(request["tools"], [])
        self.assertFalse(request["store"])
        self.assertEqual(request["tool_choice"], "none")
        return json.dumps(provider_fixture(self.context, self.snapshot),
                          ensure_ascii=False, indent=2).encode("utf-8")

    def run_once(self, responder=None, **kwargs):
        return exercise_d2_offline(
            self.context, self.snapshot, self.store,
            responder if responder is not None else self.fixture,
            run_id=kwargs.pop("run_id", "run-fixture-one"),
            attempt_id=kwargs.pop("attempt_id", "attempt-fixture-one"),
            **kwargs)

    def test_one_offline_attempt_preserves_byte_exact_raw_evidence(self):
        result = self.run_once()
        self.assertEqual(result.status, "OFFLINE_FIXTURE_VALIDATED")
        self.assertIsNone(result.reason)
        self.assertFalse(result.api_send_allowed)
        self.assertFalse(result.publishable)
        self.assertEqual(self.invocations, 1)
        actual = self.store.read_verified(result.response_receipt)
        self.assertTrue(actual.startswith(b'{\n  "id"'))
        self.assertEqual(result.response_receipt.byte_length, len(actual))
        record = json.loads(self.store.read_verified(result.result_receipt))
        self.assertEqual(record["raw_response_sha256"],
                         result.response_receipt.content_sha256)
        self.assertEqual(record["status"], result.status)
        self.assertIsNotNone(record["body_sha256"])
        self.assertIsNotNone(record["numeric_audit_bundle_sha256"])
        self.assertFalse(record["publication_allowed"])
        self.assertFalse(record["api_send_allowed"])
        self.assertEqual(LocalPrivateEvidenceStore(self.root).read_verified(
            result.result_receipt), self.store.read_verified(result.result_receipt))

    def test_duplicate_slot_different_run_and_restart_never_resend(self):
        result = self.run_once()
        self.assertEqual(result.status, "OFFLINE_FIXTURE_VALIDATED")
        reopened = LocalPrivateEvidenceStore(self.root)
        def forbidden(_):
            self.fail("no duplicate fixture invocation")
        with self.assertRaisesRegex(OfflineD2Blocked, "SLOT_ALREADY_CLAIMED"):
            exercise_d2_offline(self.context, self.snapshot, reopened, forbidden,
                                run_id="second-run", attempt_id="second-attempt")
        self.assertEqual(self.invocations, 1)

    def test_timeout_unknown_is_preserved_and_never_retried(self):
        def timeout(_):
            self.invocations += 1
            raise TimeoutError("fixture transport uncertainty")
        first = self.run_once(timeout)
        self.assertEqual(first.status, "UNKNOWN_FIXTURE_RESULT")
        self.assertEqual(first.reason, "UNKNOWN_RESULT_NO_RETRY")
        self.assertIsNone(first.response_receipt)
        record = json.loads(self.store.read_verified(first.result_receipt))
        self.assertEqual(record["status"], "UNKNOWN_FIXTURE_RESULT")
        with self.assertRaisesRegex(OfflineD2Blocked, "SLOT_ALREADY_CLAIMED"):
            self.run_once(self.fixture, run_id="retry-run", attempt_id="retry-attempt")
        self.assertEqual(self.invocations, 1)

    def test_invalid_model_output_is_saved_as_blocked_not_success(self):
        raw = provider_fixture(self.context, self.snapshot)
        o = json.loads(raw["output"][0]["content"][0]["text"])
        o["numeric_claims"].pop()
        raw["output"][0]["content"][0]["text"] = json.dumps(o)
        wire = json.dumps(raw).encode("utf-8")
        r = self.run_once(lambda _: wire)
        self.assertEqual(r.status, "OFFLINE_BLOCKED")
        self.assertIn("NUMERIC_CLAIM_AUDIT_BLOCKED", r.reason)
        self.assertEqual(self.store.read_verified(r.response_receipt), wire)
        record = json.loads(self.store.read_verified(r.result_receipt))
        self.assertFalse(record["publication_allowed"])
        self.assertIsNone(record["body_sha256"])

    def test_invalid_utf8_and_non_json_are_blocked_after_raw_storage(self):
        for payload in (b'{', b'\xff'):
            with self.subTest(payload=payload):
                with tempfile.TemporaryDirectory() as root:
                    store = LocalPrivateEvidenceStore(Path(root) / "private")
                    r = exercise_d2_offline(
                        self.context, self.snapshot, store, lambda _: payload,
                        run_id="broken-run", attempt_id="bad-attempt")
                    self.assertEqual(r.status, "OFFLINE_BLOCKED")
                    self.assertIsNotNone(r.response_receipt)
                    self.assertEqual(store.read_verified(r.response_receipt), payload)

    def test_cost_ceiling_blocks_without_publishing(self):
        r = self.run_once(max_model_cost_usd="0.000001")
        self.assertEqual(r.status, "OFFLINE_BLOCKED")
        self.assertEqual(r.reason, "SIMULATED_BUDGET_EXCEEDED")
        self.assertIsNotNone(r.response_receipt)
        self.assertFalse(r.publishable)

    def test_missing_frozen_data_blocks_before_claim_and_response(self):
        markets = tuple(fixture_market(x, i) for i, x in enumerate(REQUIRED_SIX[:-1]))
        self.snapshot = fixture_snapshot(self.context, markets=markets)
        with self.assertRaises(Exception):
            self.run_once(lambda _: self.fail("invalid snapshot must never hit responder"))
        self.assertFalse(self.root.joinpath(
            f"slot-{self.context.report_id}-r{self.context.revision}").exists())

    def test_bad_run_id_or_limit_rejected_before_response(self):
        for kwargs in (
            {"run_id": "../escape"}, {"attempt_id": "x/y"},
            {"max_model_cost_usd": "nan"}, {"max_model_cost_usd": "-1"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(OfflineD2Blocked):
                self.run_once(**kwargs)
        self.assertEqual(self.invocations, 0)

    def test_empty_bytes_fail_closed_with_result_receipt(self):
        r = self.run_once(lambda _: b"")
        self.assertEqual(r.status, "OFFLINE_BLOCKED")
        self.assertEqual(r.reason, "RAW_FIXTURE_BYTES_REQUIRED")
        self.assertIsNone(r.response_receipt)
        self.assertFalse(r.publishable)

    def test_raw_bytes_hash_differs_from_reformatted_object(self):
        result = self.run_once()
        wire = self.store.read_verified(result.response_receipt)
        parsed = json.loads(wire)
        compact = json.dumps(parsed, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")
        self.assertNotEqual(compact, wire)


if __name__ == "__main__":
    unittest.main()
