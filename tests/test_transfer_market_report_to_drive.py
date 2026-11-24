import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.reporting.delivery_spool import TransferReadback
from scripts.transfer_market_report_to_drive import local_spool_path, run


class WriterFixture:
    def __init__(self):
        self.saved = {}
        self.calls = []

    @classmethod
    def from_environment(cls, folder_id=None):
        return cls.instance

    def write_docs(self, key, payload):
        self.calls.append("DOCS_WRITE")
        self.saved["DOCS"] = ("fixture-doc", payload)
        return "fixture-doc"

    def write_png(self, key, payload):
        self.calls.append("PNG_WRITE")
        self.saved["PNG"] = ("fixture-png", payload)
        return "fixture-png"

    def readback(self, reference):
        self.calls.append("READBACK:" + reference)
        for kind, (saved_ref, payload) in self.saved.items():
            if saved_ref == reference:
                return TransferReadback(payload, {"fileId": reference, "kind": kind, "fixture": True})
        raise ValueError("fixture reference missing")

    def reconcile(self, key, payload):
        for _kind, (reference, saved_payload) in self.saved.items():
            if saved_payload == payload:
                self.calls.append("RECONCILE:" + reference)
                return reference
        return None


class TransferCommandTests(unittest.TestCase):
    def test_spool_path_must_be_local_temp_not_a_synced_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            accepted = local_spool_path(str(Path(temp) / "source.sqlite"))
            self.assertEqual(accepted, Path(temp).resolve() / "source.sqlite")
        with self.assertRaisesRegex(ValueError, "local non-synced app-data or temp directory"):
            local_spool_path(str(Path.cwd() / "synced" / "source.sqlite"))

    def test_command_can_resume_png_only_after_docs_checkpoint_is_saved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            body = root / "body.txt"
            png = root / "image.png"
            spool = root / "source.sqlite"
            body.write_bytes("TEST_ONLY report body".encode("utf-8"))
            png.write_bytes(b"\x89PNG\r\n\x1a\nTEST_ONLY")
            fixture = WriterFixture()
            WriterFixture.instance = fixture
            args = SimpleNamespace(report_id="2026-11-24_12-00", revision=1,
                spool=str(spool), folder_id="TEST_ONLY_FOLDER", body_file=str(body), png_file=None)
            with patch("scripts.transfer_market_report_to_drive.GoogleDriveReportWriter.from_environment",
                       side_effect=WriterFixture.from_environment):
                first, first_code = run(args)
                self.assertEqual(first["status"], "PARTIAL")
                self.assertEqual(first_code, 2)
                args.body_file = None
                args.png_file = str(png)
                second, second_code = run(args)
            self.assertEqual(second["status"], "COMPLETE")
            self.assertEqual(second_code, 0)
            self.assertEqual(fixture.calls.count("DOCS_WRITE"), 1)
            self.assertEqual(fixture.calls.count("PNG_WRITE"), 1)


if __name__ == "__main__":
    unittest.main()
