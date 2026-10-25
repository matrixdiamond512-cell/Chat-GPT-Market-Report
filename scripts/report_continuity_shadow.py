"""Immutable report continuity contracts for isolated shadow evidence."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from threading import Lock
from typing import Callable, Protocol

from scripts.resolve_market_report_slot import ReportIdentity

SCHEDULER_ATTEMPTS = (3, 7, 13)


@dataclass(frozen=True)
class StoredObject:
    data: bytes
    generation: int
    committed_at: datetime


class EvidenceStore(Protocol):
    def create(self, key: str, data: bytes) -> StoredObject:
        """Atomic create-only (GCS ifGenerationMatch=0), including races."""
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


def evidence_key(identity: ReportIdentity, attempt_minutes: int | None = None) -> str:
    if attempt_minutes is None:
        return f"shadow/{identity.report_id}/evidence"
    if type(attempt_minutes) is not int or attempt_minutes not in SCHEDULER_ATTEMPTS:
        raise ValueError("INVALID_SCHEDULER_ATTEMPT")
    return f"shadow/{identity.report_id}/attempts/t-{attempt_minutes}/evidence"


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

    def write(self, identity: ReportIdentity, data: bytes,
              *, attempt_minutes: int | None = None) -> dict:
        key = evidence_key(identity, attempt_minutes)
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
        result = {"status": status, "generation": readback.generation,
                  "sha256": digest, "committedAt": readback.committed_at.isoformat()}
        if attempt_minutes is not None:
            result["attemptMinutes"] = attempt_minutes
        return result


class JobCoordinator:
    """Reconcile per-attempt immutable evidence and readback stages."""
    def __init__(self, writer: EvidenceWriter, *, enabled: bool = False):
        self.writer, self.enabled = writer, enabled

    def run(self, identity: ReportIdentity, data: bytes,
            *, attempt_minutes: int | None = None) -> dict:
        if not self.enabled:
            return {"status": "DISABLED", "publicationEligible": False, "chatStatus": "UNKNOWN"}
        result = self.writer.write(identity, data, attempt_minutes=attempt_minutes)
        # A distinct allowed attempt has its own create-only evidence key. Retries
        # of one attempt reconcile only that key and never replace another attempt.
        if result["status"] in {"CREATED", "NO_OP"}:
            if attempt_minutes is None:
                stage_prefix = f"shadow/{identity.report_id}/"
            else:
                stage_prefix = f"shadow/{identity.report_id}/attempts/t-{attempt_minutes}/"
            key = f"{stage_prefix}stages/evidence-readback/{result['sha256']}"
            expected = result["sha256"].encode("ascii")
            if self.writer.clock() >= identity.target:
                return {"status": "BLOCKED", "reason": "STAGE_CUTOFF_CROSSED",
                        "publicationEligible": False, "chatStatus": "UNKNOWN"}
            try:
                stage = self.writer.store.create(key, expected)
            except FileExistsError:
                stage = self.writer.store.read(key)
            readback = self.writer.store.read(key)
            if readback != stage or readback.data != expected or readback.generation <= 0:
                return {"status": "CONFLICT", "publicationEligible": False,
                        "chatStatus": "UNKNOWN"}
            if readback.committed_at >= identity.target or self.writer.clock() >= identity.target:
                return {"status": "BLOCKED", "reason": "STAGE_CUTOFF_CROSSED",
                        "publicationEligible": False, "chatStatus": "UNKNOWN"}
        return {**result, "publicationEligible": False, "chatStatus": "UNKNOWN"}
