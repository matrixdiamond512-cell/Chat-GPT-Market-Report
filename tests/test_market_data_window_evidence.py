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

    def test_main_readback_that_crosses_slot_deadline_is_blocked(self):
        with (
            mock.patch("scripts.persist_report_slot_evidence.require_before_slot", side_effect=[None, ValueError("late")]) as cutoff,
            mock.patch.object(window, "ROOT", self.root),
            mock.patch.object(window, "verify_main_file", return_value=self.evidence.read_bytes()),
        ):
            with self.assertRaisesRegex(ValueError, "late"):
                window.verify_main_evidence(self.evidence, date(2026, 10, 16), "08:00")
        self.assertEqual(cutoff.call_count, 2)

    def test_missing_main_evidence_is_recorded_as_a_machine_readable_block(self):
        audit = self.root / "acquisition.jsonl"
        missing = self.root / "data" / "report-evidence" / "2026-10-16_12-00-r1.json"
        with mock.patch.object(window, "ROOT", self.root), mock.patch.object(window, "git_commit_push") as commit, mock.patch.dict(
            window.os.environ,
            {"GITHUB_RUN_ID": "123", "GITHUB_REPOSITORY": "owner/repo", "GITHUB_SERVER_URL": "https://github.com"},
            clear=False,
        ), mock.patch.object(window, "verify_main_audit_record", return_value=True) as verify_audit:
            window.record_evidence_readback(
                audit,
                date(2026, 10, 16),
                "12:00",
                missing,
                "BLOCKED_PRE_DRAFT_EVIDENCE_MISSING",
                "No eligible acquisition before cutoff.",
            )

        rows = window.read_audit(audit)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["evidenceStatus"], "BLOCKED_PRE_DRAFT_EVIDENCE_MISSING")
        self.assertEqual(rows[0]["reason"], "No eligible acquisition before cutoff.")
        self.assertEqual(rows[0]["actionsUrl"], "https://github.com/owner/repo/actions/runs/123")
        commit.assert_called_once()
        verify_audit.assert_called_once_with(audit, rows[0])

    def test_readback_audit_records_state_transitions_without_old_status_suppression(self):
        audit = self.root / "data" / "market" / "acquisition_runs.jsonl"
        audit.parent.mkdir(parents=True)
        with (
            mock.patch.object(window, "ROOT", self.root),
            mock.patch.object(window, "git_commit_push"),
            mock.patch.object(window, "verify_main_audit_record", return_value=True),
        ):
            window.record_evidence_readback(audit, date(2026, 10, 16), "08:00", self.evidence, "VERIFIED_ON_MAIN")
            window.record_evidence_readback(audit, date(2026, 10, 16), "08:00", self.evidence, "BLOCKED", "later mismatch")
            window.record_evidence_readback(audit, date(2026, 10, 16), "08:00", self.evidence, "VERIFIED_ON_MAIN")

        self.assertEqual(
            [row["evidenceStatus"] for row in window.read_audit(audit)],
            ["VERIFIED_ON_MAIN", "BLOCKED", "VERIFIED_ON_MAIN"],
        )

    def test_commit_stages_evidence_without_assuming_directory_exists(self):
        with mock.patch.object(window, "ROOT", self.root), mock.patch.object(window, "run") as run, mock.patch.object(
            window.subprocess, "run", return_value=SimpleNamespace(returncode=0)
        ):
            self.assertFalse(window.git_commit_push("audit only"))
        self.assertEqual(run.call_args_list[0].args[0], ["git", "add", "data/market", "data/dashboard.json"])
        self.assertEqual(run.call_args_list[-1].args[0], ["git", "push"])

    def test_commit_stages_only_the_evidence_path_that_passed_local_validation(self):
        with mock.patch.object(window, "ROOT", self.root), mock.patch.object(window, "run") as run, mock.patch.object(
            window.subprocess, "run", return_value=SimpleNamespace(returncode=1)
        ):
            window.git_commit_push("freeze slot", evidence_path=self.evidence)
        self.assertEqual(
            run.call_args_list[0].args[0],
            ["git", "add", "data/market", "data/dashboard.json", "data/report-evidence/2026-10-16_08-00-r1.json"],
        )

    def test_successful_acquisition_freezes_before_commit_then_checks_main(self):
        self.evidence.unlink()
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
                "08:00", date(2026, 10, 16), "07:35", "test", audit, "full", 0,
                freeze_evidence=True,
            )

        freeze.assert_called_once_with(date(2026, 10, 16), "08:00")
        append.assert_called_once()
        commit.assert_called_once_with(
            "Record 08:00 market data attempt 07:35",
            evidence_path=self.evidence,
        )
        verify.assert_called_once_with(self.evidence, date(2026, 10, 16), "08:00")
        readback_audit.assert_called_once_with(audit, date(2026, 10, 16), "08:00", self.evidence, "VERIFIED_ON_MAIN")
        self.assertEqual(result["acquisitionStatus"], "verified")
        self.assertEqual(result["evidenceStatus"], "VERIFIED_ON_MAIN")
        self.assertEqual(result["evidenceReadback"], "PASS")

    def test_existing_candidate_is_reused_without_rebuilding_from_newer_market_data(self):
        audit = self.root / "acquisition.jsonl"
        original = self.evidence.read_bytes()
        payload = {"overallStatus": "verified", "acquisition": {"targetedSymbols": ["USDJPY"]}}
        with (
            mock.patch.object(window, "ROOT", self.root),
            mock.patch.object(window, "run"),
            mock.patch.object(window, "load_json", return_value=payload),
            mock.patch.object(window, "sheets_pull_status", return_value=("pull_importdata", "ok")),
            mock.patch.object(window, "freeze_slot_evidence") as freeze,
            mock.patch.object(window, "append_audit"),
            mock.patch.object(window, "git_commit_push"),
            mock.patch.object(window, "verify_main_evidence", return_value=True),
            mock.patch.object(window, "record_evidence_readback", return_value=True),
        ):
            result = window.perform_attempt(
                "08:00", date(2026, 10, 16), "07:35", "test", audit, "full", 0,
                freeze_evidence=True,
            )

        freeze.assert_not_called()
        self.assertEqual(self.evidence.read_bytes(), original)
        self.assertEqual(result["evidenceStatus"], "VERIFIED_ON_MAIN")

    def test_freeze_failure_keeps_acquisition_audit_but_blocks_evidence(self):
        self.evidence.unlink()
        audit = self.root / "acquisition.jsonl"
        payload = {"overallStatus": "verified", "acquisition": {"targetedSymbols": ["USDJPY"]}}
        with (
            mock.patch.object(window, "ROOT", self.root),
            mock.patch.object(window, "run"),
            mock.patch.object(window, "load_json", return_value=payload),
            mock.patch.object(window, "sheets_pull_status", return_value=("pull_importdata", "ok")),
            mock.patch.object(window, "freeze_slot_evidence", side_effect=ValueError("stale source")),
            mock.patch.object(window, "append_audit") as append,
            mock.patch.object(window, "git_commit_push") as commit,
        ):
            result = window.perform_attempt(
                "08:00", date(2026, 10, 16), "07:35", "test", audit, "full", 0,
                freeze_evidence=True,
            )

        append.assert_called_once()
        self.assertEqual(append.call_args.args[1]["acquisitionStatus"], "verified")
        self.assertEqual(append.call_args.args[1]["evidenceStatus"], "BLOCKED_FREEZE")
        commit.assert_called_once()
        self.assertEqual(result["outcome"], "verified")
        self.assertEqual(result["evidenceReadback"], "BLOCKED")

    def test_push_failure_keeps_separate_acquisition_state_and_blocks_report(self):
        self.evidence.unlink()
        audit = self.root / "acquisition.jsonl"
        payload = {"overallStatus": "verified", "acquisition": {"targetedSymbols": ["USDJPY"]}}
        with (
            mock.patch.object(window, "ROOT", self.root),
            mock.patch.object(window, "run"),
            mock.patch.object(window, "load_json", return_value=payload),
            mock.patch.object(window, "sheets_pull_status", return_value=("pull_importdata", "ok")),
            mock.patch.object(window, "freeze_slot_evidence", return_value=self.evidence),
            mock.patch.object(window, "append_audit") as append,
            mock.patch.object(window, "git_commit_push", side_effect=OSError("push rejected")),
            mock.patch.object(window, "verify_main_evidence") as verify,
        ):
            result = window.perform_attempt(
                "08:00", date(2026, 10, 16), "07:35", "test", audit, "full", 0,
                freeze_evidence=True,
            )

        self.assertEqual(append.call_count, 2)
        self.assertEqual(append.call_args_list[0].args[1]["acquisitionStatus"], "verified")
        self.assertEqual(append.call_args_list[1].args[1]["evidenceStatus"], "BLOCKED_GIT_PUSH")
        verify.assert_not_called()
        self.assertEqual(result["evidenceStatus"], "BLOCKED_GIT_PUSH")
        self.assertEqual(result["evidenceReadback"], "BLOCKED")

    def test_audit_push_failure_does_not_relabel_already_verified_evidence(self):
        audit = self.root / "acquisition.jsonl"
        payload = {"overallStatus": "verified", "acquisition": {"targetedSymbols": ["USDJPY"]}}
        with (
            mock.patch.object(window, "ROOT", self.root),
            mock.patch.object(window, "run"),
            mock.patch.object(window, "load_json", return_value=payload),
            mock.patch.object(window, "sheets_pull_status", return_value=("pull_importdata", "ok")),
            mock.patch.object(window, "append_audit") as append,
            mock.patch.object(window, "git_commit_push", side_effect=OSError("push rejected")),
        ):
            result = window.perform_attempt(
                "08:00", date(2026, 10, 16), "07:35", "test", audit, "full", 0,
                freeze_evidence=False,
            )

        self.assertEqual(result["evidenceStatus"], "ALREADY_VERIFIED_ON_MAIN")
        self.assertEqual(result["auditStatus"], "BLOCKED_GIT_PUSH")
        failure = append.call_args_list[-1].args[1]
        self.assertEqual(failure["evidenceStatus"], "ALREADY_VERIFIED_ON_MAIN")
        self.assertEqual(failure["auditStatus"], "BLOCKED_GIT_PUSH")

    def test_readback_failure_blocks_after_preserving_successful_acquisition_audit(self):
        self.evidence.unlink()
        audit = self.root / "acquisition.jsonl"
        payload = {"overallStatus": "verified", "acquisition": {"targetedSymbols": ["USDJPY"]}}
        with (
            mock.patch.object(window, "ROOT", self.root),
            mock.patch.object(window, "run"),
            mock.patch.object(window, "load_json", return_value=payload),
            mock.patch.object(window, "sheets_pull_status", return_value=("pull_importdata", "ok")),
            mock.patch.object(window, "freeze_slot_evidence", return_value=self.evidence),
            mock.patch.object(window, "append_audit") as append,
            mock.patch.object(window, "git_commit_push"),
            mock.patch.object(window, "verify_main_evidence", side_effect=RuntimeError("mismatch")),
            mock.patch.object(window, "record_evidence_readback") as readback,
        ):
            result = window.perform_attempt(
                "08:00", date(2026, 10, 16), "07:35", "test", audit, "full", 0,
                freeze_evidence=True,
            )

        append.assert_called_once()
        self.assertEqual(append.call_args.args[1]["acquisitionStatus"], "verified")
        readback.assert_called_once_with(audit, date(2026, 10, 16), "08:00", self.evidence, "BLOCKED", "RuntimeError: mismatch")
        self.assertEqual(result["evidenceStatus"], "BLOCKED_MAIN_READBACK")
        self.assertEqual(result["evidenceReadback"], "BLOCKED")

    def test_report_ready_requires_both_current_acquisition_and_main_evidence(self):
        self.assertFalse(window.report_ready(False, False))
        self.assertFalse(window.report_ready(True, False))
        self.assertFalse(window.report_ready(False, True))
        self.assertTrue(window.report_ready(True, True))


if __name__ == "__main__":
    unittest.main()
