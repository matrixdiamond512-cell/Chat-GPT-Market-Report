"""Offline-first durable source and independent Docs/PNG transfer checkpoints.

No Google/GitHub adapter or trigger is configured here. Transfer readback is
not formal publication, image quality, or Pages acceptance evidence.
"""
from contextlib import contextmanager
import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


class DeliverySpool:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS artifacts (report_id TEXT, revision INTEGER, kind TEXT, payload BLOB NOT NULL, sha256 TEXT NOT NULL, state TEXT NOT NULL, reference TEXT, PRIMARY KEY(report_id,revision,kind))")
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, report_id TEXT, revision INTEGER, kind TEXT, state TEXT, observed_at TEXT)")

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
            db.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,'PERSISTED',NULL)", (report_id, revision, kind, payload, digest(payload)))
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
            return result

    def _state(self, identity, state, reference=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE artifacts SET state=?,reference=COALESCE(?,reference) WHERE report_id=? AND revision=? AND kind=?", (state, reference, *identity))
            self._event(db, *identity, state)

    def transfer(self, report_id, revision, kind, *, write, readback):
        """Only invoked adapters have side effects. Retrying a saved reference
        performs readback only; ambiguous writes require operator reconciliation.
        A callback receives the stable identity/hashes for provider idempotency.
        """
        identity = (report_id, revision, kind)
        artifact = self.inspect(*identity)
        if artifact["state"] == "WRITE_READBACK_VERIFIED":
            return artifact["reference"]
        if artifact["state"] in {"WRITING", "UNKNOWN"}:
            raise ValueError("ambiguous/in-progress write; reconcile before retry")
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
            except Exception:
                self._state(identity, "UNKNOWN")
                raise
            self._state(identity, "SAVED", reference)
        try:
            observed = readback(reference)
            if not isinstance(observed, bytes) or observed != bytes(artifact["payload"]):
                raise ValueError("whole original byte readback mismatch")
        except Exception:
            self._state(identity, "READBACK_FAILED", reference)
            raise
        self._state(identity, "WRITE_READBACK_VERIFIED", reference)
        return reference
