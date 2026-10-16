"""Formal evidence handoff regression tests; fictional test values only."""
import copy
import unittest
from morning_fixture import fixture
from scripts.bind_morning_report_evidence import assemble
from reporting.infographic import ValidationFailure

class EvidenceHandoffTests(unittest.TestCase):
    def setUp(self):
        complete, self.view = fixture()
        self.context = complete["context"]
        self.snapshot = complete["snapshot"]
        self.report = {key: value for key, value in complete.items()
                       if key not in ("context", "snapshot", "report_id", "revision",
                                      "snapshot_id")}
        # Synthetic inputs test the identity contract, not formal acceptance.
        self.report.pop("synthetic_fixture", None)

    def test_valid_envelope_retains_original_text(self):
        result = assemble(self.report, self.context, self.snapshot)
        self.assertEqual(result["fullText"], self.report["fullText"])
        self.assertEqual(result["snapshot_id"], self.snapshot["snapshot_id"])
        self.assertEqual(result["revision"], self.context["revision"])

    def test_missing_original_hash_is_blocked(self):
        self.report.pop("bodyHash")
        with self.assertRaises(ValidationFailure) as error:
            assemble(self.report, self.context, self.snapshot)
        self.assertEqual(error.exception.reason, "ORIGINAL_BODY_HASH_REQUIRED")

    def test_reconstructed_report_is_blocked(self):
        self.report["source_note"] = "CHAT_TRANSCRIPT_RECONSTRUCTED_NOT_VERBATIM"
        with self.assertRaises(ValidationFailure) as result:
            assemble(self.report, self.context, self.snapshot)
        self.assertEqual(result.exception.reason, "ORIGINAL_REPORT_NOT_VERIFIED")

    def test_wrong_context_date_is_blocked(self):
        self.context["report_date"] = "2026-10-07"
        with self.assertRaises(ValidationFailure):
            assemble(self.report, self.context, self.snapshot)

    def test_changed_body_hash_is_blocked(self):
        self.report["bodyHash"] = "unrelated"
        with self.assertRaises(ValidationFailure) as result:
            assemble(self.report, self.context, self.snapshot)
        self.assertEqual(result.exception.reason, "ORIGINAL_BODY_HASH_MISMATCH")

    def test_changed_snapshot_is_blocked(self):
        self.snapshot["snapshot_id"] = "snapshot-forged"
        with self.assertRaises(ValidationFailure):
            assemble(self.report, self.context, self.snapshot)

    def test_snapshot_price_tampering_is_blocked(self):
        # Keep the original snapshot_id but alter a price.
        # Restore must reject the content-addressed identity.
        self.snapshot["markets"][0]["priceValue"] = 999999
        with self.assertRaises(ValidationFailure) as error:
            assemble(self.report, self.context, self.snapshot)
        self.assertEqual(error.exception.reason, "SNAPSHOT_CONTEXT_INVALID")

    def test_snapshot_cutoff_tampering_is_blocked(self):
        self.snapshot["data_cutoff"] = "2026-10-06T07:50:00+09:00"
        with self.assertRaises(ValidationFailure) as error:
            assemble(self.report, self.context, self.snapshot)
        self.assertEqual(error.exception.reason, "SNAPSHOT_CONTEXT_INVALID")

    def test_existing_binding_cannot_be_overwritten(self):
        self.report["context"] = {"report_id":"unexpected"}
        with self.assertRaises(ValidationFailure) as result:
            assemble(self.report, self.context, self.snapshot)
        self.assertEqual(result.exception.reason, "REPORT_ALREADY_HAS_BOUND_EVIDENCE")

if __name__ == "__main__":
    unittest.main()
