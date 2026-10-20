"""Offline-only report continuity contracts; no production adapters or CLI.

A real ingress must verify OIDC issuer, audience and authorized service account
before trusting the scheduler header. A timestamp alone is never authentication.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from threading import Lock
from typing import Callable, Protocol

from scripts.resolve_market_report_slot import ReportIdentity


@dataclass(frozen=True)
class StoredObject:
    data: bytes
    generation: int
    committed_at: datetime


class EvidenceStore(Protocol):
    def create(self, key: str, data: bytes) -> StoredObject:
        """Atomic create-only: production contract is ifGenerationMatch=0.

        Raise FileExistsError on existing key, including races. The timestamp
        must be storage-server metadata, never a client supplied clock.
        """
        ...

    def read(self, key: str) -> StoredObject: ...


class FakeStorage:
    """Thread-safe fixture backend. Not cloud evidence or publication proof."""
    def __init__(self, clock: Callable[[], datetime]):
        self.clock = clock
        self._objects: dict[str, StoredObject] = {}
        self._lock = Lock()

    def create(self, key: str, data: bytes) -> StoredObject:
        with self._lock:
            if key in self._objects:
                raise FileExistsError(key)
            obj = StoredObject(bytes(data), len(self._objects) + 1, self.clock())
            self._objects[key] = obj
            return obj

    def read(self, key: str) -> StoredObject:
        with self._lock:
            return self._objects[key]


def readiness(identity: ReportIdentity, *, now: datetime,
              snapshot_at: datetime | None, acquisition_valid: bool,
              evidence_valid: bool, draft_input_valid: bool) -> dict:
    if now.tzinfo is None or (snapshot_at is not None and snapshot_at.tzinfo is None):
        raise ValueError("Timezone required")
    acquisition = bool(acquisition_valid and snapshot_at is not None
                       and timedelta(0) <= now - snapshot_at <= timedelta(minutes=15)
                       and timedelta(0) <= identity.target - snapshot_at <= timedelta(minutes=15))
    return {"acquisitionReady": acquisition,
            "evidenceReady": bool(evidence_valid and now < identity.target and acquisition),
            "draftAllowed": bool(draft_input_valid),
            "publicationEligible": False, "chatStatus": "UNKNOWN"}


class EvidenceWriter:
    def __init__(self, store: EvidenceStore, clock: Callable[[], datetime]):
        self.store, self.clock = store, clock

    def write(self, identity: ReportIdentity, data: bytes) -> dict:
        key = f"shadow/{identity.report_id}/evidence"
        digest = sha256(data).hexdigest()
        if self.clock() >= identity.target:
            return {"status": "BLOCKED", "reason": "EXPIRED"}
        try:
            created = self.store.create(key, data)
            status = "CREATED"
        except FileExistsError:
            created = self.store.read(key)
            status = "NO_OP" if created.data == data else "CONFLICT"
        readback = self.store.read(key)
        if (readback != created or sha256(readback.data).hexdigest() != digest
                or readback.generation <= 0):
            return {"status": "CONFLICT"}
        if readback.committed_at >= identity.target or self.clock() >= identity.target:
            return {"status": "BLOCKED", "reason": "CUTOFF_CROSSED"}
        return {"status": status, "generation": readback.generation,
                "sha256": digest, "committedAt": readback.committed_at.isoformat()}


class JobCoordinator:
    """Retry from immutable persisted stages; no production writes supported."""
    def __init__(self, writer: EvidenceWriter, *, enabled: bool = False):
        self.writer, self.enabled = writer, enabled

    def run(self, identity: ReportIdentity, data: bytes) -> dict:
        if not self.enabled:
            return {"status": "DISABLED", "publicationEligible": False}
        result = self.writer.write(identity, data)
        # Stage records are create-only too. On retry, reconcile evidence first.
        if result["status"] in {"CREATED", "NO_OP"}:
            key = f"shadow/{identity.report_id}/stages/evidence-readback/{result['sha256']}"
            try:
                self.writer.store.create(key, result["sha256"].encode("ascii"))
            except FileExistsError:
                if self.writer.store.read(key).data != result["sha256"].encode("ascii"):
                    return {"status": "CONFLICT", "publicationEligible": False}
        return {**result, "publicationEligible": False, "chatStatus": "UNKNOWN"}
