"""D2 private evidence store prototype for *offline* POSIX staging only.

This is a local disk adapter, not production IAM, encryption at rest, a
distributed run lock, a network client, or an authorization to send API
requests. Configure the root on an independently encrypted/private volume
outside the repository. Never place API keys or market reports in CI artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat


REPO_ROOT = Path(__file__).resolve().parents[2]
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")


class PrivateEvidenceError(ValueError):
    """Fail closed: untrusted path, content, permissions or readback."""


@dataclass(frozen=True)
class EvidenceReceipt:
    object_id: str
    content_sha256: str
    byte_length: int
    # Not a production proof, object generation or provider attestation.
    contract: str = "d2-local-private-evidence/v1"


def _reject(message: str):
    raise PrivateEvidenceError(message)


def _object_parts(object_id: str) -> tuple[str, str]:
    if not isinstance(object_id, str):
        _reject("OBJECT_ID_INVALID")
    parts = object_id.split("/")
    if len(parts) != 3 or parts[0] != "shadow":
        _reject("OBJECT_ID_INVALID")
    if not all(IDENTIFIER.fullmatch(x) for x in parts[1:]):
        _reject("OBJECT_ID_INVALID")
    return parts[1], parts[2]


def _private_dir(fd: int):
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        _reject("PRIVATE_DIRECTORY_PERMISSIONS_INVALID")


def _private_file(fd: int):
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077 or info.st_nlink != 1):
        _reject("PRIVATE_FILE_PERMISSIONS_INVALID")


class LocalPrivateEvidenceStore:
    """Immutable, O_EXCL/O_NOFOLLOW object writes, independent disk readback.

    Linux/POSIX only. This does not replace external encryption, IAM, object
    versioning, operational backup, or cross-machine attempt/slot locking.
    """

    def __init__(self, root: str | Path):
        if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
            _reject("POSIX_PRIVATE_STORE_REQUIRED")
        p = Path(root)
        if not p.is_absolute() or p.is_symlink():
            _reject("PRIVATE_ROOT_INVALID")
        # Resolve path traversal and symlinked ancestors before checking
        # for repository-backed storage. Never store evidence in the worktree.
        canonical = p.resolve(strict=False)
        if canonical == REPO_ROOT or REPO_ROOT in canonical.parents:
            _reject("PRIVATE_ROOT_INVALID")
        if not p.exists():
            try:
                p.mkdir(mode=0o700)
            except OSError as exc:
                raise PrivateEvidenceError("PRIVATE_ROOT_CREATE_FAILED") from exc
        # Avoid canonicalizing a symlink: no redirect into repo or other storage.
        if p.is_symlink():
            _reject("PRIVATE_ROOT_INVALID")
        self.root = p
        with self._open_root():
            pass

    def _open_root(self):
        try:
            fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                _private_dir(fd)
            except BaseException:
                os.close(fd)
                raise
        except OSError as exc:
            raise PrivateEvidenceError("PRIVATE_ROOT_OPEN_FAILED") from exc
        return _FD(fd)

    def _run_directory(self, root_fd: int, run: str, create: bool) -> "_FD":
        if create:
            try:
                os.mkdir(run, mode=0o700, dir_fd=root_fd)
            except FileExistsError:
                pass
            except OSError as exc:
                raise PrivateEvidenceError("RUN_DIRECTORY_CREATE_FAILED") from exc
        try:
            fd = os.open(run, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                         dir_fd=root_fd)
            try:
                _private_dir(fd)
            except BaseException:
                os.close(fd)
                raise
        except OSError as exc:
            raise PrivateEvidenceError("RUN_DIRECTORY_INVALID") from exc
        return _FD(fd)

    def put_once(self, object_id: str, content: bytes) -> EvidenceReceipt:
        run, attempt = _object_parts(object_id)
        if type(content) is not bytes:
            _reject("EVIDENCE_NOT_BYTES")
        if not content:
            _reject("EMPTY_EVIDENCE_REJECTED")
        filename = attempt + ".json"
        with self._open_root() as root_fd:
            with self._run_directory(root_fd, run, create=True) as run_fd:
                try:
                    fd = os.open(filename,
                                 os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=run_fd)
                except FileExistsError as exc:
                    raise PrivateEvidenceError("STORAGE_OBJECT_ALREADY_EXISTS") from exc
                except OSError as exc:
                    raise PrivateEvidenceError("PRIVATE_FILE_CREATE_FAILED") from exc
                try:
                    _private_file(fd)
                    with os.fdopen(fd, "wb", closefd=False) as stream:
                        stream.write(content)
                        stream.flush()
                        os.fsync(fd)
                finally:
                    os.close(fd)
                os.fsync(run_fd)
                receipt = EvidenceReceipt(
                    object_id, hashlib.sha256(content).hexdigest(), len(content))
        # Read through a newly opened descriptor, not the write buffer.
        if self.read_verified(receipt) != content:
            _reject("PRIVATE_READBACK_MISMATCH")
        return receipt

    def read_verified(self, receipt: EvidenceReceipt) -> bytes:
        if not isinstance(receipt, EvidenceReceipt) or (
                receipt.contract != "d2-local-private-evidence/v1"):
            _reject("RECEIPT_INVALID")
        run, attempt = _object_parts(receipt.object_id)
        with self._open_root() as root_fd:
            with self._run_directory(root_fd, run, create=False) as run_fd:
                try:
                    fd = os.open(attempt + ".json",
                                 os.O_RDONLY | os.O_NOFOLLOW, dir_fd=run_fd)
                except OSError as exc:
                    raise PrivateEvidenceError("EVIDENCE_MISSING_OR_UNSAFE") from exc
                try:
                    _private_file(fd)
                    with os.fdopen(fd, "rb", closefd=False) as stream:
                        data = stream.read()
                finally:
                    os.close(fd)
        if (len(data) != receipt.byte_length or
                hashlib.sha256(data).hexdigest() != receipt.content_sha256):
            _reject("PRIVATE_READBACK_MISMATCH")
        return data


class _FD:
    """Close file descriptors even if a check or read fails."""

    def __init__(self, fd: int):
        self.fd = fd

    def __enter__(self):
        return self.fd

    def __exit__(self, _type, _value, _tb):
        os.close(self.fd)
