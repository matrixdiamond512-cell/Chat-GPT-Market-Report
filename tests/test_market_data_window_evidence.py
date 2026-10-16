from datetime import date
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from scripts import run_market_data_window as window


class MarketDataWindowEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.evidence = self.root / "data" / "report-evidence" / "2026-10-16_08-00-r1.json"
        self.evidence.parent.mkdir(parents=True)
        self.evidence.write_bytes(b'{"evidenceId":"fixed"}\n')

    def tearDown(self):
        self.temp.cleanup()

    def test_freeze_uses_explicit_slot_and_live_cutoff_guard(self):
        with mock.patch.object(window, "ROOT", self.root), mock.patch(
            "scripts.persist_report_slot_evidence.persist_slot_evidence",
            return_value=(self.evidence, True),
        ) as persist:
            result = window.freeze_slot_evidence(date(2026, 10, 16), "08:00")

        self.assertEqual(result, self.evidence)
        persist.assert_called_once_with(
            "2026-10-16",
            "08:00",
            self.root / "data" / "market" / "latest.json",
            self.root / "data" / "report-evidence",
            max_age_minutes=15,
            require_live_before_slot=True,
        )

    def test_main_readback_compares_exact_remote_bytes(self):
        remote = SimpleNamespace(stdout=self.evidence.read_bytes())
        with mock.patch.object(window, "ROOT", self.root), mock.patch.object(window, "run") as run, mock.patch.object(
            window.subprocess, "run", return_value=remote
        ) as git_show:
            self.assertTrue(window.verify_main_evidence(self.evidence))

        run.assert_called_once_with(["git", "fetch", "origin", "main"], check=True)
        git_show.assert_called_once_with(
            ["git", "show", "origin/main:data/report-evidence/2026-10-16_08-00-r1.json"],
            cwd=self.root,
            check=True,
            capture_output=True,
            env=mock.ANY,
        )

    def test_main_readback_mismatch_blocks(self):
        with mock.patch.object(window, "ROOT", self.root), mock.patch.object(window, "run"), mock.patch.object(
            window.subprocess, "run", return_value=SimpleNamespace(stdout=b"different")
        ):
            with self.assertRaisesRegex(RuntimeError, "BLOCKED_MAIN_EVIDENCE_READBACK_MISMATCH"):
                window.verify_main_evidence(self.evidence)

    def test_commit_stages_evidence_without_assuming_directory_exists(self):
        with mock.patch.object(window, "ROOT", self.root), mock.patch.object(window, "run") as run, mock.patch.object(
            window.subprocess, "run", return_value=SimpleNamespace(returncode=0)
        ):
            self.assertFalse(window.git_commit_push("audit only"))
        run.assert_called_once_with(
            ["git", "add", "data/market", "data/dashboard.json", "data/report-evidence"],
            check=True,
        )

    def test_successful_acquisition_freezes_before_commit_then_checks_main(self):
        audit = self.root / "acquisition.jsonl"
        payload = {"overallStatus": "verified", "acquisition": {"targetedSymbols": ["USDJPY"]}}
        with (
            mock.patch.object(window, "ROOT", self.root),
            mock.patch.object(window, "run"),
            mock.patch.object(window, "load_json", return_value=payload),
            mock.patch.object(window, "sheets_pull_status", return_value=("pull_importdata", "ok")),
            mock.patch.object(window, "freeze_slot_evidence", return_value=self.evidence) as freeze,
            mock.patch.object(window, "append_audit") as append,
            mock.patch.object(window, "git_commit_push") as commit,
            mock.patch.object(window, "verify_main_evidence", return_value=True) as verify,
            mock.patch.object(window, "record_evidence_readback") as readback_audit,
        ):
            result = window.perform_attempt(
                "08:00", date(2026, 10, 16), "07:55", "test", audit, "full", 0,
                freeze_evidence=True,
            )

        freeze.assert_called_once_with(date(2026, 10, 16), "08:00")
        append.assert_called_once()
        commit.assert_called_once()
        verify.assert_called_once_with(self.evidence)
        readback_audit.assert_called_once_with(audit, date(2026, 10, 16), "08:00", self.evidence, "VERIFIED_ON_MAIN")
        self.assertEqual(result["evidenceStatus"], "LOCAL_FROZEN")
        self.assertEqual(result["evidenceReadback"], "PASS")


if __name__ == "__main__":
    unittest.main()
