import unittest

from scripts.reporting.publication_status import (
    InfographicStatus,
    ReportStatus,
    publication_status,
)


class IndependentPublicationStatusTests(unittest.TestCase):
    def test_report_pass_and_infographic_ready(self):
        result = publication_status(report_validation_passed=True, infographic_result="READY")
        self.assertEqual((result.report_status, result.infographic_status), (ReportStatus.PUBLISHED, InfographicStatus.READY))

    def test_missing_fact_keeps_report_published(self):
        result = publication_status(report_validation_passed=True)
        self.assertEqual((result.report_status, result.infographic_status), (ReportStatus.PUBLISHED, InfographicStatus.NOT_READY))

    def test_renderer_failure_keeps_report_published(self):
        result = publication_status(report_validation_passed=True, infographic_result="FAILED_VALIDATION")
        self.assertEqual((result.report_status, result.infographic_status), (ReportStatus.PUBLISHED, InfographicStatus.FAILED_VALIDATION))

    def test_vision_not_run_does_not_block_ready(self):
        # Optional Vision/OCR is intentionally not part of the status resolver.
        result = publication_status(report_validation_passed=True, infographic_result="READY")
        self.assertEqual(result.report_status, ReportStatus.PUBLISHED)
        self.assertEqual(result.infographic_status, InfographicStatus.READY)

    def test_report_failure_blocks_and_does_not_publish_infographic(self):
        result = publication_status(report_validation_passed=False, infographic_result="READY")
        self.assertEqual((result.report_status, result.infographic_status), (ReportStatus.BLOCKED, InfographicStatus.NOT_READY))

    def test_unknown_infographic_status_is_rejected(self):
        with self.assertRaises(ValueError):
            publication_status(report_validation_passed=True, infographic_result="DEBUG_PREVIEW")


if __name__ == "__main__":
    unittest.main()
