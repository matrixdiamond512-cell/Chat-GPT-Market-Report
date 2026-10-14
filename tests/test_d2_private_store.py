"""Offline-only POSIX filesystem adapter tests; fixture bytes, no API/network."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest

from scripts.reporting.d2_private_store import (
    LocalPrivateEvidenceStore, EvidenceReceipt, PrivateEvidenceError, REPO_ROOT
)


@unittest.skipUnless(os.name == "posix", "POSIX-only staging adapter")
class TestLocalPrivateEvidenceStore(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "evidence"
        self.store = LocalPrivateEvidenceStore(self.root)
        self.object_id = "shadow/test-run/test-attempt"
        self.body = b'{"schema":"test","status":"BLOCKED","public_writes":0}'

    def test_immutable_storage_and_restart_readback(self):
        receipt = self.store.put_once(self.object_id, self.body)
        self.assertEqual(receipt.contract, "d2-local-private-evidence/v1")
        self.assertEqual(receipt.byte_length, len(self.body))
        self.assertEqual(receipt.content_sha256, hashlib.sha256(self.body).hexdigest())
        self.assertEqual(LocalPrivateEvidenceStore(self.root).read_verified(receipt), self.body)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.root/"test-run").stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.root/"test-run"/"test-attempt.json").stat().st_mode), 0o600)

    def test_duplicate_run_attempt_is_never_overwritten_even_for_same_bytes(self):
        self.store.put_once(self.object_id, self.body)
        for content in (self.body, self.body + b"changed"):
            with self.assertRaisesRegex(PrivateEvidenceError, "STORAGE_OBJECT_ALREADY_EXISTS"):
                LocalPrivateEvidenceStore(self.root).put_once(self.object_id, content)
        self.assertEqual((self.root/"test-run"/"test-attempt.json").read_bytes(), self.body)

    def test_byte_tampering_is_detected_after_restart(self):
        receipt = self.store.put_once(self.object_id, self.body)
        (self.root/"test-run"/"test-attempt.json").write_bytes(b'{}')
        with self.assertRaisesRegex(PrivateEvidenceError, "PRIVATE_READBACK_MISMATCH"):
            LocalPrivateEvidenceStore(self.root).read_verified(receipt)

    def test_forged_receipt_cannot_validate_altered_evidence(self):
        receipt = self.store.put_once(self.object_id, self.body)
        with self.assertRaisesRegex(PrivateEvidenceError, "PRIVATE_READBACK_MISMATCH"):
            self.store.read_verified(replace(receipt, content_sha256="0"*64))
        with self.assertRaisesRegex(PrivateEvidenceError, "RECEIPT_INVALID"):
            self.store.read_verified(replace(receipt, contract="production-proof"))
        self.assertIsInstance(receipt, EvidenceReceipt)

    def test_traversal_and_malformed_object_ids_fail_closed(self):
        for item in (
            "", "reports/run/attempt", "shadow/../bad", "shadow/run/../../x",
            "shadow/run/try.json", "shadow/run/at tempt",
            r"shadow/run\\evil/attempt", "/shadow/run/attempt", "shadow/run",
        ):
            with self.subTest(item=item):
                with self.assertRaisesRegex(PrivateEvidenceError, "OBJECT_ID_INVALID"):
                    self.store.put_once(item, self.body)

    def test_symlinked_files_and_run_directories_rejected(self):
        receipt = self.store.put_once(self.object_id, self.body)
        path = self.root/"test-run"/"test-attempt.json"
        path.unlink()
        path.symlink_to(Path(self.temp.name)/"outside.json")
        with self.assertRaisesRegex(PrivateEvidenceError, "EVIDENCE_MISSING_OR_UNSAFE"):
            self.store.read_verified(receipt)
        (self.root/"evil").symlink_to(Path(self.temp.name), target_is_directory=True)
        with self.assertRaisesRegex(PrivateEvidenceError, "RUN_DIRECTORY_INVALID"):
            self.store.put_once("shadow/evil/attempt", self.body)

    def test_unsafe_permissions_or_hardlinks_rejected(self):
        receipt = self.store.put_once(self.object_id, self.body)
        path = self.root/"test-run"/"test-attempt.json"
        os.chmod(path, 0o644)
        with self.assertRaisesRegex(PrivateEvidenceError, "PRIVATE_FILE_PERMISSIONS_INVALID"):
            self.store.read_verified(receipt)
        os.chmod(path, 0o600)
        os.link(path, self.root/"test-run"/"hardlink")
        with self.assertRaisesRegex(PrivateEvidenceError, "PRIVATE_FILE_PERMISSIONS_INVALID"):
            self.store.read_verified(receipt)

    def test_unsafe_root_or_run_permissions_rejected(self):
        os.chmod(self.root, 0o755)
        with self.assertRaisesRegex(PrivateEvidenceError, "PRIVATE_DIRECTORY_PERMISSIONS_INVALID"):
            LocalPrivateEvidenceStore(self.root)
        os.chmod(self.root, 0o700)
        self.store.put_once(self.object_id, self.body)
        os.chmod(self.root/"test-run", 0o755)
        receipt = EvidenceReceipt(self.object_id, hashlib.sha256(self.body).hexdigest(), len(self.body))
        with self.assertRaisesRegex(PrivateEvidenceError, "PRIVATE_DIRECTORY_PERMISSIONS_INVALID"):
            self.store.read_verified(receipt)

    def test_store_rejects_repo_tree_relative_root_and_root_symlink(self):
        with self.assertRaisesRegex(PrivateEvidenceError, "PRIVATE_ROOT_INVALID"):
            LocalPrivateEvidenceStore("relative/path")
        with self.assertRaisesRegex(PrivateEvidenceError, "PRIVATE_ROOT_INVALID"):
            LocalPrivateEvidenceStore(REPO_ROOT/"should-not-be-created")
        link = Path(self.temp.name)/"link"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(PrivateEvidenceError, "PRIVATE_ROOT_INVALID"):
            LocalPrivateEvidenceStore(link)

    def test_byte_exact_preservation_including_unusual_utf8(self):
        arbitrary = b'{"raw":"\\u2605"}\n'
        receipt = self.store.put_once(self.object_id, arbitrary)
        self.assertEqual(self.store.read_verified(receipt), arbitrary)
        self.assertNotEqual(receipt.content_sha256, hashlib.sha256('{"raw":"★"}\n'.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    unittest.main()
