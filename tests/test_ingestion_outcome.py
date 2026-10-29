import unittest

from scripts.reporting.ingestion_outcome import format_ingestion_status_lines


class IngestionOutcomeTests(unittest.TestCase):
    def test_archive_only_import_does_not_claim_publication(self):
        key = ("2026-10-30", "08:00")
        lines = format_ingestion_status_lines(
            {key: ({"report_status": "SOURCE_ARCHIVED"}, None)},
            {},
        )
        joined = "\n".join(lines)
        self.assertIn("CANONICAL_SOURCE_INGESTION_COMPLETE", joined)
        self.assertIn("SOURCE_ARCHIVED_ONLY", joined)
        self.assertIn("formal publication not established", joined)
        self.assertNotIn("PUBLICATION_COMPLETE", joined)
        self.assertNotIn("PUBLISHED", joined)

    def test_docs_receipt_does_not_claim_pages_publication(self):
        key = ("2026-10-30", "12:00")
        lines = format_ingestion_status_lines(
            {key: ({"report_status": "DOC_READBACK_PASS"}, {"status": "DOC_READBACK_PASS"})},
            {},
        )
        joined = "\n".join(lines)
        self.assertIn("DOC_READBACK_RECEIPT_RECORDED", joined)
        self.assertIn("Pages deployment/public readback not verified", joined)
        self.assertNotIn("PUBLICATION_COMPLETE", joined)

    def test_unknown_receipt_pairing_is_not_upgraded(self):
        key = ("2026-10-30", "16:00")
        lines = format_ingestion_status_lines(
            {key: ({"report_status": "SOURCE_ARCHIVED"}, {"status": "DOC_READBACK_PASS"})},
            {},
        )
        joined = "\n".join(lines)
        self.assertIn("CANONICAL_INGESTION_STATUS_UNKNOWN", joined)
        self.assertNotIn("DOC_READBACK_RECEIPT_RECORDED", joined)

    def test_archive_promotion_is_not_pages_publication(self):
        key = ("2026-10-30", "21:00")
        lines = format_ingestion_status_lines(
            {},
            {key: ({"report_status": "DOC_READBACK_PASS"}, {"status": "DOC_READBACK_PASS"})},
        )
        joined = "\n".join(lines)
        self.assertIn("ARCHIVED_SOURCE_PROMOTED_TO_CANONICAL", joined)
        self.assertIn("Pages deployment/public readback not verified", joined)


if __name__ == "__main__":
    unittest.main()