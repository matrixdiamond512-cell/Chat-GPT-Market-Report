import hashlib
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.reporting.slot_recovery_contract import (
    ContractError,
    DocsReadback,
    claim_trigger_attempt,
    freeze_g2_writer_input,
    sign_trigger_request,
    verify_docs_readback,
    DocsSaveEvidence,
    purge_expired_private_diagnostics,
    save_frozen_g2_and_readback,
    verify_pre_slot_trigger,
    write_private_diagnostic,
)

from scripts.reporting.pre_slot_execution import PrivateFileEvidenceStore, execute_test_only_capture, run_existing_live_pipeline

SECRET = b"fixture-secret-for-contract-tests-0123456789"
NOW = datetime.fromisoformat("2026-10-19T07:47:10+09:00")


def trigger(**overrides):
    payload = {
        "schemaVersion": "market-report-pre-slot-trigger/v1",
        "attemptId": "sched-20261019-074700-a",
        "reportDate": "2026-10-19",
        "reportSlot": "08:00",
        "scheduledAt": "2026-10-19T07:47:00+09:00",
        "triggeredAt": "2026-10-19T07:47:04+09:00",
        "triggerSource": "external_direct_runner",
        "executionMode": "TEST_ONLY",
    }
    payload.update(overrides)
    return payload


class PreSlotTriggerTests(unittest.TestCase):
    def accept(self, payload, now=NOW):
        return verify_pre_slot_trigger(payload, sign_trigger_request(payload, SECRET), SECRET, now=now)

    def test_omitted_now_uses_aware_utc_clock(self):
        from scripts.reporting import slot_recovery_contract as contract

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return NOW.astimezone(tz) if tz is not None else NOW.replace(tzinfo=None)

        payload = trigger()
        with patch.object(contract, "datetime", FixedDateTime):
            result = verify_pre_slot_trigger(payload, sign_trigger_request(payload, SECRET), SECRET)
        self.assertEqual(result.execution_mode, "TEST_ONLY")

    def test_accepts_signed_direct_pre_slot_test_request(self):
        result = self.accept(trigger())
        self.assertEqual(result.idempotency_key,
                         "2026-10-19_08-00:sched-20261019-074700-a")
        self.assertEqual(result.start_lag_seconds, 4)
        self.assertEqual(result.execution_mode, "TEST_ONLY")


    def test_delay_policy_cannot_be_relaxed_by_caller(self):
        payload = trigger()
        signature = sign_trigger_request(payload, SECRET)
        with self.assertRaisesRegex(ContractError, "TRIGGER_DELAY_POLICY_INVALID"):
            verify_pre_slot_trigger(payload, signature, SECRET, now=NOW, max_delay_seconds=600)

    def test_rejects_bad_signature_and_short_secret(self):
        payload = trigger()
        with self.assertRaisesRegex(ContractError, "TRIGGER_SIGNATURE_INVALID"):
            verify_pre_slot_trigger(payload, "0" * 64, SECRET, now=NOW)
        with self.assertRaisesRegex(ContractError, "TRIGGER_SECRET_TOO_SHORT"):
            verify_pre_slot_trigger(payload, sign_trigger_request(payload, SECRET), b"short", now=NOW)

    def test_rejects_late_slot_or_delayed_runner_start(self):
        payload = trigger(triggeredAt="2026-10-19T08:00:01+09:00")
        with self.assertRaisesRegex(ContractError, "TRIGGER_AFTER_SLOT_CUTOFF"):
            self.accept(payload, datetime.fromisoformat("2026-10-19T08:00:02+09:00"))
        payload = trigger(scheduledAt="2026-10-19T07:47:00+09:00",
                          triggeredAt="2026-10-19T07:49:00+09:00")
        with self.assertRaisesRegex(ContractError, "TRIGGER_START_DELAY_EXCEEDED"):
            self.accept(payload, datetime.fromisoformat("2026-10-19T07:49:05+09:00"))

    def test_rejects_wrong_slot_wrong_date_and_github_dispatch_source(self):
        for changes, expected in [
            ({"reportSlot": "12:00"}, "TRIGGER_SLOT_OUT_OF_SCOPE"),
            ({"reportDate": "2026-10-17"}, "TRIGGER_REPORT_DATE_NOT_SCHEDULED"),
            ({"triggerSource": "github_workflow_dispatch"}, "TRIGGER_SOURCE_NOT_DIRECT"),
        ]:
            payload = trigger(**changes)
            with self.subTest(expected=expected), self.assertRaisesRegex(ContractError, expected):
                self.accept(payload)


    def test_exact_trigger_retry_is_noop_and_replay_conflict_fails(self):
        verified = self.accept(trigger())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            root.mkdir()
            ledger = Path(temp) / "private" / "attempt.json"
            self.assertTrue(claim_trigger_attempt(ledger, verified, repository_root=root))
            self.assertFalse(claim_trigger_attempt(ledger, verified, repository_root=root))
            alternate = self.accept(trigger(triggeredAt="2026-10-19T07:47:05+09:00"))
            with self.assertRaisesRegex(ContractError, "TRIGGER_REPLAY_CONFLICT"):
                claim_trigger_attempt(ledger, alternate, repository_root=root)
            with self.assertRaisesRegex(ContractError, "TRIGGER_LEDGER_MUST_BE_PRIVATE"):
                claim_trigger_attempt(root / "ledger.json", verified, repository_root=root)

    def test_rejects_missing_fields_naive_and_stale_trigger(self):
        payload = trigger()
        del payload["attemptId"]
        with self.assertRaisesRegex(ContractError, "TRIGGER_FIELDS_MISSING"):
            self.accept(payload)
        payload = trigger(scheduledAt="2026-10-19T07:47:00")
        with self.assertRaisesRegex(ContractError, "SCHEDULED_AT_NAIVE"):
            self.accept(payload)
        with self.assertRaisesRegex(ContractError, "TRIGGER_REQUEST_STALE"):
            self.accept(trigger(), datetime.fromisoformat("2026-10-19T07:49:00+09:00"))


class G2DocsHandoffTests(unittest.TestCase):
    def setUp(self):
        self.body = "# Summary\n\nMain text\n"
        self.pinned = freeze_g2_writer_input(
            report_id="2026-10-19_08-00", revision=1, report_date="2026-10-19",
            report_slot="08:00", run_id="TEST_ONLY:run-1", full_text=self.body,
            body_hash=hashlib.sha256(self.body.encode()).hexdigest(),
            frozen_at="2026-10-19T07:50:00+09:00",
        )

    def test_freezes_exact_body_and_rejects_altered_hash_or_identity(self):
        self.assertEqual(self.pinned.body_hash, hashlib.sha256(self.body.encode()).hexdigest())
        self.assertEqual(self.pinned.full_text, self.body)
        with self.assertRaisesRegex(ContractError, "G2_BODY_HASH_MISMATCH"):
            freeze_g2_writer_input(report_id="2026-10-19_08-00", revision=1,
                report_date="2026-10-19", report_slot="08:00", run_id="r",
                full_text=self.body, body_hash="0" * 64,
                frozen_at="2026-10-19T07:50:00+09:00")
        with self.assertRaisesRegex(ContractError, "G2_REPORT_IDENTITY_MISMATCH"):
            freeze_g2_writer_input(report_id="2026-10-20_08-00", revision=1,
                report_date="2026-10-19", report_slot="08:00", run_id="r",
                full_text=self.body, frozen_at="2026-10-19T07:50:00+09:00")

    def test_exact_docs_readback_passes_and_records_identity(self):
        receipt = DocsSaveEvidence(
            run_id=self.pinned.run_id, report_id=self.pinned.report_id,
            revision=self.pinned.revision, document_id="doc-1",
            document_revision_id="rev-7", body_hash=self.pinned.body_hash,
            saved_at="2026-10-19T07:51:00+09:00")
        checked = verify_docs_readback(self.pinned, receipt,
            DocsReadback("doc-1", "rev-7", self.body),
            required_sections=("# Summary",), checked_at="2026-10-19T08:01:00+09:00")
        self.assertEqual(checked.status, "PASS")
        self.assertEqual(checked.diagnostic["documentRevisionId"], "rev-7")
        self.assertEqual(checked.diagnostic["readbackBodyHash"], self.pinned.body_hash)

    def test_mismatch_captures_safe_diagnostic_without_report_body(self):
        changed = "# Summary\n\nAltered text\n"
        receipt = DocsSaveEvidence(
            run_id=self.pinned.run_id, report_id=self.pinned.report_id,
            revision=self.pinned.revision, document_id="doc-1",
            document_revision_id="rev-8", body_hash=self.pinned.body_hash,
            saved_at="2026-10-19T07:51:00+09:00")
        checked = verify_docs_readback(self.pinned, receipt,
            DocsReadback("doc-1", "rev-8", changed),
            required_sections=("# Summary", "## Missing section"),
            writer_stage="DOCS_READBACK", checked_at="2026-10-19T08:01:00+09:00")
        self.assertEqual(checked.status, "FAIL")
        self.assertIn("DOCS_BODY_HASH_MISMATCH", checked.reasons)
        self.assertIn("DOCS_REQUIRED_SECTIONS_MISSING", checked.reasons)
        self.assertEqual(checked.diagnostic["firstDiffOffset"], 11)
        self.assertIn("## Missing section", checked.diagnostic["missingSections"])
        encoded = json.dumps(checked.diagnostic)
        self.assertNotIn(self.body, encoded)
        self.assertNotIn(changed, encoded)

    def test_missing_readback_identifiers_fail_closed(self):
        receipt = DocsSaveEvidence(
            run_id=self.pinned.run_id, report_id=self.pinned.report_id,
            revision=self.pinned.revision, document_id="doc-1",
            document_revision_id="rev-7", body_hash=self.pinned.body_hash,
            saved_at="2026-10-19T07:51:00+09:00")
        checked = verify_docs_readback(self.pinned, receipt,
            DocsReadback("", "", self.body),
            checked_at="2026-10-19T08:01:00+09:00")
        self.assertEqual(checked.status, "FAIL")
        self.assertIn("DOCS_DOCUMENT_ID_MISSING", checked.reasons)
        self.assertIn("DOCS_REVISION_ID_MISSING", checked.reasons)

    def test_readback_must_match_same_run_saved_document_revision(self):
        receipt = DocsSaveEvidence(
            run_id=self.pinned.run_id, report_id=self.pinned.report_id,
            revision=self.pinned.revision, document_id="doc-1",
            document_revision_id="rev-7", body_hash=self.pinned.body_hash,
            saved_at="2026-10-19T07:51:00+09:00")
        wrong_id = verify_docs_readback(self.pinned, receipt,
            DocsReadback("other-doc", "rev-7", self.body),
            checked_at="2026-10-19T08:01:00+09:00")
        self.assertIn("DOCS_DOCUMENT_ID_DOES_NOT_MATCH_SAVE", wrong_id.reasons)
        wrong_rev = verify_docs_readback(self.pinned, receipt,
            DocsReadback("doc-1", "rev-8", self.body),
            checked_at="2026-10-19T08:01:00+09:00")
        self.assertIn("DOCS_REVISION_DOES_NOT_MATCH_SAVE", wrong_rev.reasons)

    def test_frozen_body_is_only_writer_input_and_precedes_save(self):
        class FakeDocsWriter:
            def __init__(self, body):
                self.body = body
                self.kwargs = None
            def save(self, **kwargs):
                self.kwargs = kwargs
                return DocsSaveEvidence(
                    run_id=kwargs["run_id"], report_id=kwargs["report_id"],
                    revision=kwargs["revision"], document_id="doc-frozen",
                    document_revision_id="rev-frozen", body_hash=kwargs["body_hash"],
                    saved_at="2026-10-19T07:51:00+09:00")
            def readback(self, *, document_id):
                return DocsReadback(document_id, "rev-frozen", self.body)

        writer = FakeDocsWriter(self.pinned.full_text)
        receipt, readback, result = save_frozen_g2_and_readback(
            self.pinned, writer, required_sections=("# Summary",),
            checked_at="2026-10-19T08:01:00+09:00")
        self.assertEqual(result.status, "PASS")
        self.assertEqual(set(writer.kwargs), {"full_text", "body_hash", "run_id", "report_id", "revision"})
        self.assertEqual(writer.kwargs["full_text"], self.pinned.full_text)
        self.assertEqual(readback.document_id, receipt.document_id)

    def test_save_before_freeze_fails(self):
        receipt = DocsSaveEvidence(
            run_id=self.pinned.run_id, report_id=self.pinned.report_id,
            revision=self.pinned.revision, document_id="doc-1",
            document_revision_id="rev-7", body_hash=self.pinned.body_hash,
            saved_at="2026-10-19T07:49:00+09:00")
        checked = verify_docs_readback(self.pinned, receipt,
            DocsReadback("doc-1", "rev-7", self.body),
            checked_at="2026-10-19T08:01:00+09:00")
        self.assertIn("G2_NOT_FROZEN_BEFORE_DOCS_SAVE", checked.reasons)

    def test_private_diagnostic_refuses_public_path_and_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            root.mkdir()
            outside = Path(temp) / "private"
            receipt = DocsSaveEvidence(
                run_id=self.pinned.run_id, report_id=self.pinned.report_id,
                revision=self.pinned.revision, document_id="doc-1",
                document_revision_id="rev-8", body_hash=self.pinned.body_hash,
                saved_at="2026-10-19T07:51:00+09:00")
            checked = verify_docs_readback(self.pinned, receipt,
                DocsReadback("doc-1", "rev-8", self.body + "changed"),
                checked_at="2026-10-19T08:01:00+09:00")
            with self.assertRaisesRegex(ContractError, "DIAGNOSTIC_PATH_MUST_BE_PRIVATE"):
                write_private_diagnostic(root / "diagnostic.json", checked.diagnostic,
                                         repository_root=root)
            path = write_private_diagnostic(outside / "diagnostic.json", checked.diagnostic,
                                            repository_root=root, retention_days=14)
            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(stored["expiresAt"], "2026-11-02T08:01:00+09:00")
            self.assertNotIn("fullText", stored)
            self.assertEqual(purge_expired_private_diagnostics(
                outside, repository_root=root,
                now=datetime.fromisoformat("2026-11-02T08:00:59+09:00")), ())
            removed = purge_expired_private_diagnostics(
                outside, repository_root=root,
                now=datetime.fromisoformat("2026-11-02T08:01:00+09:00"))
            self.assertEqual(removed, ("diagnostic.json",))
            self.assertFalse(path.exists())
            path = write_private_diagnostic(outside / "diagnostic.json", checked.diagnostic,
                                            repository_root=root)
            with self.assertRaisesRegex(ContractError, "DIAGNOSTIC_ALREADY_EXISTS"):
                write_private_diagnostic(path, checked.diagnostic, repository_root=root)
            with self.assertRaisesRegex(ContractError, "DIAGNOSTIC_RETENTION_MUST_BE_14_DAYS"):
                write_private_diagnostic(outside / "other.json", checked.diagnostic,
                                         repository_root=root, retention_days=30)


class PreSlotExecutionTests(unittest.TestCase):
    def market_bytes(self, generated_at):
        payload = {
            "generatedAt": generated_at,
            "reportDate": "2026-10-19",
            "reportSlot": "08:00",
            "overallStatus": "verified",
            "markets": {
                "USDJPY": {
                    "id": "USDJPY", "marketType": "FX", "unit": "JPY",
                    "value": 157.8, "change": 0.0, "changePercent": 0.0,
                    "comparisonBasis": "previous_close",
                    "asOf": generated_at, "sourceId": "fixture-usdjpy",
                    "sourceUrl": "https://fixture.invalid/usdjpy",
                    "verificationStatus": "verified", "freshnessStatus": "fresh",
                    "displayValue": "157.8",
                }
            },
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def test_0747_0753_0757_test_only_capture_freeze_and_readback(self):
        for clock in ("07:47", "07:53", "07:57"):
            with self.subTest(clock=clock), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "repo"
                root.mkdir()
                private = Path(temp) / "private"
                store = PrivateFileEvidenceStore(private / "evidence", repository_root=root)
                minute = int(clock.split(":")[1])
                base = f"2026-10-19T{clock}"
                scheduled = f"{base}:00+09:00"
                trigger_time = f"{base}:04+09:00"
                now = datetime.fromisoformat(f"{base}:10+09:00")
                generated = f"{base}:05+09:00"
                payload = trigger(
                    attemptId=f"runner-20261019-{minute:02d}00-test",
                    scheduledAt=scheduled, triggeredAt=trigger_time)
                result = execute_test_only_capture(
                    payload=payload, signature=sign_trigger_request(payload, SECRET),
                    secret=SECRET, acquisition=lambda _: self.market_bytes(generated),
                    store=store, attempt_ledger=private / "ledger" / f"{minute}.json",
                    repository_root=root, now=now)
                self.assertEqual(result["status"], "PASS_TEST_ONLY")
                self.assertEqual(result["readback"], "PASS_EXACT_BYTES")
                self.assertEqual(result["mainReadback"], "NOT_RUN_TEST_ONLY_PRIVATE_STORE")
                self.assertEqual(result["reportId"], "2026-10-19_08-00")
                self.assertEqual(len(result["sourceHash"]), 64)
                self.assertEqual(result["capturedAt"], generated)

    def test_test_capture_rejects_tampered_signature_late_or_stale_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            root.mkdir()
            store = PrivateFileEvidenceStore(Path(temp) / "private" / "evidence", repository_root=root)
            payload = trigger()
            kwargs = dict(
                payload=payload, signature="0" * 64, secret=SECRET,
                acquisition=lambda _: self.market_bytes("2026-10-19T07:47:05+09:00"),
                store=store, attempt_ledger=Path(temp) / "private" / "ledger.json",
                repository_root=root, now=NOW)
            with self.assertRaisesRegex(ContractError, "TRIGGER_SIGNATURE_INVALID"):
                execute_test_only_capture(**kwargs)
            payload = trigger(scheduledAt="2026-10-19T07:47:00+09:00",
                              triggeredAt="2026-10-19T08:00:01+09:00")
            kwargs["payload"] = payload
            kwargs["signature"] = sign_trigger_request(payload, SECRET)
            kwargs["now"] = datetime.fromisoformat("2026-10-19T08:00:02+09:00")
            with self.assertRaisesRegex(ContractError, "TRIGGER_AFTER_SLOT_CUTOFF"):
                execute_test_only_capture(**kwargs)
            payload = trigger()
            kwargs["payload"] = payload
            kwargs["signature"] = sign_trigger_request(payload, SECRET)
            kwargs["now"] = NOW
            kwargs["acquisition"] = lambda _: self.market_bytes("2026-10-19T07:30:00+09:00")
            with self.assertRaisesRegex(ValueError, "allowed pre-draft cutoff window"):
                execute_test_only_capture(**kwargs)

    def test_live_main_write_path_is_disabled_by_default(self):
        payload = trigger(executionMode="LIVE")
        verified = verify_pre_slot_trigger(
            payload, sign_trigger_request(payload, SECRET), SECRET, now=NOW)
        with self.assertRaisesRegex(ContractError, "LIVE_MAIN_EVIDENCE_WRITE_NOT_ENABLED"):
            run_existing_live_pipeline(
                trigger=verified, now=NOW, audit_path=Path("test-audit.json"))

    def test_test_capture_detects_evidence_readback_tampering(self):
        class TamperedStore:
            def __init__(self, inner):
                self.inner = inner
                self.evidence_id = None
            def put_if_absent(self, evidence_id, encoded):
                self.evidence_id = evidence_id
                self.inner.put_if_absent(evidence_id, encoded)
            def read(self, evidence_id):
                return self.inner.read(evidence_id) + b" "

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            root.mkdir()
            private = Path(temp) / "private"
            payload = trigger()
            with self.assertRaisesRegex(ContractError, "EVIDENCE_READBACK_MISMATCH"):
                execute_test_only_capture(
                    payload=payload, signature=sign_trigger_request(payload, SECRET),
                    secret=SECRET, acquisition=lambda _: self.market_bytes("2026-10-19T07:47:05+09:00"),
                    store=TamperedStore(PrivateFileEvidenceStore(private / "evidence", repository_root=root)),
                    attempt_ledger=private / "ledger.json", repository_root=root, now=NOW)



if __name__ == "__main__":
    unittest.main()
