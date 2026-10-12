"""Fail-closed boundary tests for G2 issuer → formal projection."""
import unittest
from morning_fixture import fixture, formal_contract_fixture
from scripts.validate_morning_issue_projection import validate_issuance_projection
from reporting.infographic import ValidationFailure

class IssuanceProjectionTests(unittest.TestCase):
    def test_rejects_missing_g2_evidence(self):
        report, view, spec = formal_contract_fixture()
        with self.assertRaises(ValidationFailure) as e:
            validate_issuance_projection(report, view, spec)
        self.assertEqual(e.exception.reason, "G2_ISSUANCE_EVIDENCE_REQUIRED")

    def test_rejects_synthetic_even_if_claiming_g2(self):
        report, view = fixture()
        report["evidence_stage"] = "G2_DRAFT_NOT_SAVED"
        report["validated_gates"] = ["G0", "G1", "G2"]
        with self.assertRaises(ValidationFailure) as e:
            validate_issuance_projection(report, view, {})
        self.assertEqual(e.exception.reason, "SYNTHETIC_PROJECTION_NOT_FORMAL")

    def test_g2_label_does_not_bypass_preflight(self):
        report, view, spec = formal_contract_fixture()
        report["evidence_stage"] = "G2_DRAFT_NOT_SAVED"
        report["validated_gates"] = ["G0", "G1", "G2"]
        report.pop("bodyHash")
        with self.assertRaises(ValidationFailure) as e:
            validate_issuance_projection(report, view, spec)
        self.assertEqual(e.exception.reason, "ISSUANCE_PREFLIGHT_BLOCKED")

    def test_forged_g2_marker_cannot_bypass_transaction_recheck(self):
        report, view, spec = formal_contract_fixture()
        report["evidence_stage"] = "G2_DRAFT_NOT_SAVED"
        report["validated_gates"] = ["G0", "G1", "G2"]
        # This mock fixture has not actually passed canonical G2 report-section checks.
        with self.assertRaises(ValidationFailure) as error:
            validate_issuance_projection(report, view, spec)
        self.assertEqual(error.exception.reason, "G2_EVIDENCE_RECHECK_FAILED")

    def test_g2_label_does_not_bypass_canonical_spec(self):
        report, view, spec = formal_contract_fixture()
        report["evidence_stage"] = "G2_DRAFT_NOT_SAVED"
        report["validated_gates"] = ["G0", "G1", "G2"]
        with self.assertRaises(ValidationFailure) as e:
            validate_issuance_projection(report, view, {})
        self.assertNotEqual(e.exception.reason, "G2_ISSUANCE_EVIDENCE_REQUIRED")

if __name__ == "__main__":
    unittest.main()
