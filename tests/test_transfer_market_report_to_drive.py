import tempfile
from contextlib import nullcontext
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.reporting.delivery_spool import DeliverySpool, TransferReadback
from scripts.transfer_market_report_to_drive import default_spool_path, local_spool_path, run


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

    def transfer_guard(self, key, payload):
        return nullcontext()


class TransferCommandTests(unittest.TestCase):
    def test_default_spool_uses_persistent_local_appdata(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict("os.environ", {
            "MARKET_REPORT_SPOOL_PATH": "", "LOCALAPPDATA": temp,
        }, clear=False):
            self.assertEqual(Path(default_spool_path()),
                             Path(temp) / "MarketReportDelivery" / "delivery-spool.sqlite3")

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

    def test_auth_failure_happens_after_both_sources_are_spooled(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            body = root / "body.txt"
            png = root / "image.png"
            spool_path = root / "source.sqlite"
            body.write_bytes(b"TEST_ONLY auth failure body")
            png.write_bytes(b"\x89PNG\r\n\x1a\nTEST_ONLY image")
            args = SimpleNamespace(report_id="2026-11-24_12-00", revision=2,
                spool=str(spool_path), folder_id="TEST_ONLY_FOLDER",
                body_file=str(body), png_file=str(png))

            def auth_failure(folder_id=None):
                saved = DeliverySpool(spool_path)
                self.assertEqual(saved.inspect(args.report_id, args.revision, "DOCS")["payload"], body.read_bytes())
                self.assertEqual(saved.inspect(args.report_id, args.revision, "PNG")["payload"], png.read_bytes())
                raise RuntimeError("TEST_ONLY authentication unavailable")

            with patch("scripts.transfer_market_report_to_drive.GoogleDriveReportWriter.from_environment",
                       side_effect=auth_failure):
                result, code = run(args)
            self.assertEqual(code, 1)
            self.assertEqual(result["lanes"], {"DOCS": "PERSISTED", "PNG": "PERSISTED"})
            self.assertEqual(result["attemptOutcomes"]["DOCS"], "BLOCKED:RuntimeError")
            self.assertEqual(result["attemptOutcomes"]["PNG"], "BLOCKED:RuntimeError")

    def test_docs_interruption_can_resume_both_persisted_sources_after_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            body = root / "body.txt"
            png = root / "image.png"
            spool_path = root / "source.sqlite"
            body.write_bytes(b"TEST_ONLY interrupted body")
            png.write_bytes(b"\x89PNG\r\n\x1a\nTEST_ONLY interrupted image")
            fixture = WriterFixture()
            WriterFixture.instance = fixture
            args = SimpleNamespace(report_id="2026-11-24_12-00", revision=3,
                spool=str(spool_path), folder_id="TEST_ONLY_FOLDER",
                body_file=str(body), png_file=str(png))

            def docs_create_then_lose_response(key, payload):
                fixture.saved["DOCS"] = ("fixture-doc", payload)
                raise KeyboardInterrupt("TEST_ONLY simulated process stop after Drive create")

            fixture.write_docs = docs_create_then_lose_response
            with patch("scripts.transfer_market_report_to_drive.GoogleDriveReportWriter.from_environment",
                       side_effect=WriterFixture.from_environment):
                with self.assertRaises(KeyboardInterrupt):
                    run(args)
                reopened = DeliverySpool(spool_path)
                self.assertEqual(reopened.inspect(args.report_id, args.revision, "DOCS")["state"], "WRITING")
                self.assertEqual(reopened.inspect(args.report_id, args.revision, "PNG")["state"], "PERSISTED")
                args.body_file = None
                args.png_file = None
                fixture.write_docs = WriterFixture.write_docs.__get__(fixture, WriterFixture)
                second, second_code = run(args)
            self.assertEqual(second_code, 0)
            self.assertEqual(second["status"], "COMPLETE")
            self.assertEqual(reopened.inspect(args.report_id, args.revision, "DOCS")["payload"], body.read_bytes())
            self.assertEqual(reopened.inspect(args.report_id, args.revision, "PNG")["payload"], png.read_bytes())

    def test_network_response_loss_keeps_sources_and_retry_reconciles_without_duplicate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            body = root / "body.txt"
            png = root / "image.png"
            spool_path = root / "source.sqlite"
            body.write_bytes(b"TEST_ONLY network interrupted body")
            png.write_bytes(b"\x89PNG\r\n\x1a\nTEST_ONLY network interrupted image")
            fixture = WriterFixture()
            WriterFixture.instance = fixture
            args = SimpleNamespace(report_id="2026-11-24_12-00", revision=4,
                spool=str(spool_path), folder_id="TEST_ONLY_FOLDER",
                body_file=str(body), png_file=str(png))

            def docs_create_then_timeout(key, payload):
                fixture.saved["DOCS"] = ("fixture-doc", payload)
                raise OSError("TEST_ONLY response lost")

            fixture.write_docs = docs_create_then_timeout
            with patch("scripts.transfer_market_report_to_drive.GoogleDriveReportWriter.from_environment",
                       side_effect=WriterFixture.from_environment):
                first, first_code = run(args)
                self.assertEqual(first_code, 2)
                spool = DeliverySpool(spool_path)
                self.assertEqual(spool.inspect(args.report_id, args.revision, "DOCS")["state"], "UNKNOWN")
                self.assertEqual(spool.inspect(args.report_id, args.revision, "PNG")["payload"], png.read_bytes())
                self.assertEqual(spool.inspect(args.report_id, args.revision, "DOCS")["payload"], body.read_bytes())
                args.body_file = None
                args.png_file = None
                fixture.write_docs = WriterFixture.write_docs.__get__(fixture, WriterFixture)
                second, second_code = run(args)
            self.assertEqual(second_code, 0)
            self.assertEqual(second["status"], "COMPLETE")
            self.assertEqual(fixture.calls.count("DOCS_WRITE"), 0)
            self.assertEqual(fixture.calls.count("PNG_WRITE"), 1)
            self.assertEqual(fixture.calls.count("RECONCILE:fixture-doc"), 1)


if __name__ == "__main__":
    unittest.main()
