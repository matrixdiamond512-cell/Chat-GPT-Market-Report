"""Offline-first durable source and independent Docs/PNG transfer checkpoints.

No Google/GitHub adapter or trigger is configured here. Transfer readback is
not formal publication, image quality, or Pages acceptance evidence.
"""
from contextlib import contextmanager, nullcontext
import hashlib
import re
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class TransferReadback:
    payload: bytes
    metadata: dict


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


class DeliverySpool:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS artifacts (report_id TEXT, revision INTEGER, kind TEXT, payload BLOB NOT NULL, sha256 TEXT NOT NULL, state TEXT NOT NULL, reference TEXT, readback_metadata TEXT, PRIMARY KEY(report_id,revision,kind))")
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, report_id TEXT, revision INTEGER, kind TEXT, state TEXT, observed_at TEXT)")
            columns = {row["name"] for row in db.execute("PRAGMA table_info(artifacts)")}
            if "readback_metadata" not in columns:
                db.execute("ALTER TABLE artifacts ADD COLUMN readback_metadata TEXT")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _event(self, db, report_id, revision, kind, state):
        db.execute("INSERT INTO events(report_id,revision,kind,state,observed_at) VALUES(?,?,?,?,?)", (report_id, revision, kind, state, datetime.now(timezone.utc).isoformat()))

    def persist(self, report_id, revision, kind, payload):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}_(?:08|12|16|21)-00", report_id) or type(revision) is not int or revision < 1 or kind not in {"DOCS", "PNG"}:
            raise ValueError("invalid report identity or transfer kind")
        if not isinstance(payload, bytes) or not payload:
            raise ValueError("nonempty original bytes required")
        if kind == "DOCS":
            payload.decode("utf-8")
        elif not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("PNG signature missing (quality is still unverified)")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            body = db.execute("SELECT 1 FROM artifacts WHERE report_id=? AND revision=? AND kind='DOCS'", (report_id, revision)).fetchone()
            if kind == "PNG" and not body:
                raise ValueError("persist original body before PNG")
            old = db.execute("SELECT * FROM artifacts WHERE report_id=? AND revision=? AND kind=?", (report_id, revision, kind)).fetchone()
            if old:
                if bytes(old["payload"]) != payload or old["sha256"] != digest(payload):
                    raise ValueError("same revision cannot overwrite original bytes")
                return old["sha256"]
            db.execute("INSERT INTO artifacts(report_id,revision,kind,payload,sha256,state,reference,readback_metadata) VALUES(?,?,?,?,?,'PERSISTED',NULL,NULL)", (report_id, revision, kind, payload, digest(payload)))
            self._event(db, report_id, revision, kind, "PERSISTED")
        return digest(payload)

    def inspect(self, report_id, revision, kind):
        with self.connect() as db:
            row = db.execute("SELECT * FROM artifacts WHERE report_id=? AND revision=? AND kind=?", (report_id, revision, kind)).fetchone()
            if row is None:
                raise ValueError("original artifact not persisted")
            result = dict(row)
            if digest(bytes(result["payload"])) != result["sha256"]:
                raise ValueError("persisted original hash mismatch")
            if result.get("readback_metadata"):
                result["readback_metadata"] = json.loads(result["readback_metadata"])
            return result

    def _state(self, identity, state, reference=None, readback_metadata=None):
        encoded_metadata = json.dumps(readback_metadata, ensure_ascii=False, sort_keys=True) if readback_metadata is not None else None
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE artifacts SET state=?,reference=COALESCE(?,reference),readback_metadata=COALESCE(?,readback_metadata) WHERE report_id=? AND revision=? AND kind=?", (state, reference, encoded_metadata, *identity))
            self._event(db, *identity, state)

    def transfer(self, report_id, revision, kind, *, write, readback, reconcile=None, guard=None):
        """Run one lane under an optional provider-wide guard.

        The guard spans reconciliation, provider create, checkpoint persistence,
        and full readback. Local SQLite claims alone cannot coordinate separate
        machines, so real remote writers must supply their shared guard.
        """
        artifact = self.inspect(report_id, revision, kind)
        body = self.inspect(report_id, revision, "DOCS")
        key = {"reportId": report_id, "revision": revision, "bodyHash": body["sha256"],
               "artifactHash": artifact["sha256"], "kind": kind}
        payload = bytes(artifact["payload"])
        with guard(key, payload) if guard is not None else nullcontext():
            return self._transfer_locked(report_id, revision, kind, write=write,
                                         readback=readback, reconcile=reconcile)

    def _transfer_locked(self, report_id, revision, kind, *, write, readback, reconcile=None):
        """Only invoked adapters have side effects. Retrying a saved reference
        performs readback only. A provider lookup can resolve an ambiguous write
        without creating a duplicate; absence never authorizes a second write.
        Callbacks receive stable identity/hashes for provider deduplication.
        """
        identity = (report_id, revision, kind)
        artifact = self.inspect(*identity)
        if artifact["state"] == "WRITE_READBACK_VERIFIED":
            return artifact["reference"]
        if artifact["state"] in {"WRITING", "UNKNOWN"}:
            if reconcile is None:
                raise ValueError("ambiguous/in-progress write; provider reconciliation is required")
            body = self.inspect(report_id, revision, "DOCS")
            key = {"reportId": report_id, "revision": revision, "bodyHash": body["sha256"], "artifactHash": artifact["sha256"], "kind": kind}
            reference = reconcile(key, bytes(artifact["payload"]))
            if not isinstance(reference, str) or not reference:
                raise ValueError("ambiguous write not found; original remains blocked and will not be recreated")
            self._state(identity, "SAVED", reference)
            artifact = self.inspect(*identity)
        reference = artifact["reference"]
        if not reference:
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                claimed = db.execute("UPDATE artifacts SET state='WRITING' WHERE report_id=? AND revision=? AND kind=? AND state='PERSISTED'", identity).rowcount
                if claimed != 1:
                    raise ValueError("another attempt claimed this artifact")
                self._event(db, *identity, "WRITING")
            body = self.inspect(report_id, revision, "DOCS")
            key = {"reportId": report_id, "revision": revision, "bodyHash": body["sha256"], "artifactHash": artifact["sha256"], "kind": kind}
            try:
                reference = write(key, bytes(artifact["payload"]))
                if not isinstance(reference, str) or not reference:
                    raise ValueError("writer did not return a durable reference")
            except Exception as exc:
                self._state(identity, "PERSISTED" if getattr(exc, "definitely_not_created", False) else "UNKNOWN")
                raise
            self._state(identity, "SAVED", reference)
        try:
            observed = readback(reference)
            if isinstance(observed, TransferReadback):
                observed_payload = observed.payload
                observed_metadata = observed.metadata
            else:
                observed_payload = observed
                observed_metadata = None
            if not isinstance(observed_payload, bytes) or observed_payload != bytes(artifact["payload"]):
                raise ValueError("whole original byte readback mismatch")
        except Exception:
            self._state(identity, "READBACK_FAILED", reference)
            raise
        self._state(identity, "WRITE_READBACK_VERIFIED", reference, observed_metadata)
        return reference

    def delivery_status(self, report_id, revision):
        """Report transfer completeness only; this is not publication or QA."""
        with self.connect() as db:
            rows = db.execute("SELECT kind,state FROM artifacts WHERE report_id=? AND revision=?", (report_id, revision)).fetchall()
        states = {row["kind"]: row["state"] for row in rows}
        verified = sum(state == "WRITE_READBACK_VERIFIED" for state in states.values())
        if all(states.get(kind) == "WRITE_READBACK_VERIFIED" for kind in ("DOCS", "PNG")):
            status = "COMPLETE"
        elif verified:
            status = "PARTIAL"
        elif any(state in {"WRITING", "UNKNOWN"} for state in states.values()):
            status = "UNKNOWN"
        elif any(state == "READBACK_FAILED" for state in states.values()):
            status = "FAILED"
        else:
            status = "PENDING"
        return {"reportId": report_id, "revision": revision, "status": status, "lanes": states,
                "uncertainLanes": [kind for kind, state in states.items() if state in {"WRITING", "UNKNOWN"}],
                "formalPublication": "NOT_ASSESSED", "imageQuality": "NOT_ASSESSED"}
