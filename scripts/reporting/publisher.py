"""Phase E offline Publisher. No production adapter, network or Git executable.

SQLite models fixture effects separately from durable checkpoints. An exclusive
SQLite lock serializes fixture runners; a process crash releases it. Every effect
has a stable action ID, and uncertain effects are reconciled before retry.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import base64
import hashlib
import json
from pathlib import Path
import sqlite3

from .context import ReportContext, aware
from .snapshot import MarketDataSnapshot, digest, freeze, plain
from .report import ReportObject
from .gates import Transaction, GateFailure, body_hash, UNRESOLVED


STATES = ('WAITING', 'DOC_SAVED', 'DOC_VERIFIED', 'PNG_SAVED', 'PNG_VERIFIED',
          'MANIFEST_READY', 'GIT_REGISTERED', 'PUBLISHED', 'VERIFIED',
          'FAILED', 'UNKNOWN', 'NEEDS_REVIEW')
MARKER = 'PHASE_E_OFFLINE_FIXTURE_V1\n'
ROOT = Path(__file__).resolve().parents[2]


class PublisherError(ValueError):
    def __init__(self, state, reason):
        self.state = state
        super().__init__(reason)


class FixtureStop(RuntimeError):
    """Deliberate interruption; durable effects/checkpoints survive restart."""


def canonical(value):
    return json.dumps(plain(value), ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True)
class Identity:
    report_id: str
    revision: int
    snapshot_id: str
    body_hash: str

    @property
    def transaction_id(self):
        return 'transaction-'+digest(self)


class FixtureStore:
    """Only writes to a named, marked fixture directory outside the repository.

    This is a simulation backend, not a Drive client or Git repository. SHA fields
    identify simulated content records and are explicitly labelled in outputs.
    """
    def __init__(self, directory):
        self.root = Path(directory).resolve()
        if not self.root.name.startswith('publisher-fixture-') or self.root.is_relative_to(ROOT):
            raise ValueError('fixture directory must be named publisher-fixture-* outside the repository')
        self.root.mkdir(parents=True, exist_ok=True)
        marker = self.root/'OFFLINE_FIXTURE.txt'
        if marker.exists():
            if marker.read_text(encoding='utf-8') != MARKER:
                raise ValueError('invalid fixture marker')
        else:
            if any(self.root.iterdir()):
                raise ValueError('refuse unmarked nonempty directory')
            with marker.open('x', encoding='utf-8', newline='') as output:
                output.write(MARKER)
        self.db = sqlite3.connect(self.root/'state.sqlite', timeout=0, isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS transactions (
                report_id TEXT, revision INTEGER, transaction_id TEXT UNIQUE,
                envelope TEXT, envelope_hash TEXT, state TEXT, checkpoint TEXT,
                created_at TEXT, pending_action TEXT, error TEXT, events TEXT,
                manifest TEXT, manifest_hash TEXT, receipt TEXT, git_commit_sha TEXT,
                failure_evidence TEXT, publication_evidence TEXT,
                PRIMARY KEY(report_id, revision));
            CREATE TABLE IF NOT EXISTS effects (
                action_id TEXT PRIMARY KEY, kind TEXT, payload TEXT);
        ''')
        for field in ('failure_evidence', 'publication_evidence'):
            if field not in {column[1] for column in self.db.execute('PRAGMA table_info(transactions)')}:
                self.db.execute('ALTER TABLE transactions ADD COLUMN '+field+' TEXT')
        self.db.row_factory = sqlite3.Row
        self.lock_db = sqlite3.connect(self.root/'runner-lock.sqlite', timeout=0, isolation_level=None)
        self.lock_db.execute('CREATE TABLE IF NOT EXISTS lock_marker (value TEXT)')

    def close(self):
        self.db.close()
        self.lock_db.close()

    @contextmanager
    def exclusive(self):
        try:
            self.lock_db.execute('BEGIN IMMEDIATE')
        except sqlite3.OperationalError as exc:
            raise PublisherError('WAITING', 'another fixture runner holds the lock') from exc
        try:
            yield
        finally:
            self.lock_db.execute('ROLLBACK')

    def journal(self, transaction_id):
        row = self.db.execute('SELECT * FROM transactions WHERE transaction_id=?', (transaction_id,)).fetchone()
        if row is None:
            return None
        value = dict(row)
        for field in ('envelope', 'events', 'manifest', 'receipt', 'failure_evidence', 'publication_evidence'):
            value[field] = json.loads(value[field]) if value[field] is not None else None
        return value

    def update(self, transaction_id, **values):
        columns = {'state', 'checkpoint', 'pending_action', 'error', 'events',
                   'manifest', 'manifest_hash', 'receipt', 'git_commit_sha', 'failure_evidence', 'publication_evidence'}
        if not set(values) <= columns:
            raise ValueError('unsupported journal field')
        encoded = {k: canonical(v) if k in ('events', 'manifest', 'receipt', 'failure_evidence', 'publication_evidence') and v is not None else v for k, v in values.items()}
        self.db.execute('UPDATE transactions SET '+','.join(k+'=?' for k in encoded)+' WHERE transaction_id=?',
                        (*encoded.values(), transaction_id))

    def find(self, action_id):
        row = self.db.execute('SELECT kind,payload FROM effects WHERE action_id=?', (action_id,)).fetchone()
        return None if row is None else {'kind': row['kind'], 'payload': json.loads(row['payload'])}

    def put_once(self, action_id, kind, payload):
        existing = self.find(action_id)
        if existing is not None:
            if existing != {'kind': kind, 'payload': plain(payload)}:
                raise PublisherError('NEEDS_REVIEW', kind+' existing content differs; no overwrite')
            return existing['payload']
        self.db.execute('INSERT INTO effects VALUES (?,?,?)', (action_id, kind, canonical(payload)))
        return plain(payload)

    def counts(self):
        return {row['kind']: row['n'] for row in self.db.execute('SELECT kind,count(*) n FROM effects GROUP BY kind')}


class DryRunPublisher:
    """Offline orchestration over G0–G8, with pinned effects and recovery.

    A real adapter cannot be injected. Fixture publication evidence is supplied
    separately; default execution stops at GIT_REGISTERED, before any receipt.
    """
    def __init__(self, store):
        if type(store) is not FixtureStore:
            raise TypeError('only the concrete offline FixtureStore is supported')
        self.store = store

    def _transition(self, key, state, **values):
        row = self.store.journal(key)
        events = row['events']+[{'state': state, 'at': row['created_at']}]
        checkpoint = state if state not in ('FAILED', 'UNKNOWN', 'NEEDS_REVIEW') else row['checkpoint']
        self.store.update(key, state=state, checkpoint=checkpoint, events=events, error=None, **values)

    def _effect(self, key, kind, payload, faults):
        action = key+':'+kind
        # Persist intent before effect. UNKNOWN remains until lookup is decisive.
        self.store.update(key, pending_action=action)
        if faults.get('lookup_unknown') == kind:
            raise PublisherError('UNKNOWN', kind+' reconciliation inconclusive; do not retry effect')
        found = self.store.find(action)
        if found is not None:
            if found != {'kind': kind, 'payload': plain(payload)}:
                raise PublisherError('NEEDS_REVIEW', kind+' SHA/content reconciliation mismatch')
            result = found['payload']
        else:
            result = self.store.put_once(action, kind, payload)
            if faults.get('response_lost') == kind:
                raise PublisherError('UNKNOWN', kind+' response lost; reconcile stored action before retry')
        self.store.update(key, pending_action=None)
        return result

    def _claim(self, context, snapshot, report, png_bytes, now):
        identity = Identity(context.report_id, context.revision, snapshot.snapshot_id, body_hash(report.full_text))
        envelope = {'context': context.to_dict(), 'snapshot': snapshot.to_dict(), 'report': report.to_dict(),
                    'png_base64': base64.b64encode(png_bytes).decode('ascii')}
        key = identity.transaction_id
        same = self.store.db.execute('SELECT transaction_id FROM transactions WHERE report_id=? AND revision=?',
                                     (context.report_id, context.revision)).fetchone()
        newest = self.store.db.execute('SELECT max(revision) FROM transactions WHERE report_id=?', (context.report_id,)).fetchone()[0]
        if newest is not None and context.revision < newest:
            raise PublisherError('NEEDS_REVIEW', 'stale revision rejected')
        if same is not None and same['transaction_id'] != key:
            raise PublisherError('NEEDS_REVIEW', 'same revision changed snapshot/bodyHash rejected')
        existing = self.store.journal(key)
        if existing:
            if existing['envelope_hash'] != digest(envelope) or existing['envelope'] != envelope:
                raise PublisherError('NEEDS_REVIEW', 'frozen input/PNG content changed')
            return key, existing
        self.store.db.execute('''INSERT INTO transactions
            (report_id,revision,transaction_id,envelope,envelope_hash,state,checkpoint,created_at,events)
            VALUES (?,?,?,?,?,'WAITING','WAITING',?,?)''',
            (context.report_id, context.revision, key, canonical(envelope), digest(envelope), now,
             canonical([{'state': 'WAITING', 'at': now}])))
        return key, self.store.journal(key)

    def run(self, context, snapshot, report, png_bytes, *, now, publication=None, stop_after=None, faults=None):
        """Faults are explicit simulation inputs, never enabled by live config."""
        aware(now)
        if not isinstance(png_bytes, bytes):
            raise ValueError('PNG bytes required')
        if context.report_id in UNRESOLVED or report.report_id in UNRESOLVED:
            raise PublisherError('NEEDS_REVIEW', 'protected slot is read-only; neither OLD nor NEW can be selected')
        faults = faults or {}
        if stop_after not in (None, 'DOC_SAVED', 'PNG_SAVED', 'MANIFEST_READY', 'BEFORE_RECEIPT'):
            raise ValueError('unsupported stop fixture')
        with self.store.exclusive():
            # G0–G2 validation precedes every effect, including first claim.
            tx = Transaction.begin(context, snapshot, report)
            key, row = self._claim(context, snapshot, report, png_bytes, now)
            try:
                return self._run(key, row, tx, png_bytes, publication, stop_after, faults)
            except FixtureStop:
                raise
            except (PublisherError, GateFailure, ValueError, KeyError, TypeError) as exc:
                state = getattr(exc, 'state', 'FAILED')
                self._transition(key, state)
                self.store.update(key, error=str(exc), failure_evidence=getattr(exc, 'evidence', None))
                raise

    def _run(self, key, row, tx, png_bytes, publication, stop_after, faults):
        self._validate_checkpoint(key, row)
        if row['state'] in ('FAILED', 'NEEDS_REVIEW'):
            raise PublisherError('NEEDS_REVIEW', 'terminal failure requires explicit reviewed recovery/new revision')
        completed = row['checkpoint']
        created_at = row['created_at']
        if row['publication_evidence'] is not None:
            if publication is not None and publication != row['publication_evidence']:
                raise PublisherError('NEEDS_REVIEW', 'verified publication evidence changed; no duplicate Receipt')
            publication = row['publication_evidence']
        doc_id = 'fixture-doc-'+digest({'transaction': key})[:24]
        doc = {'file_id': doc_id, 'report_id': tx.report.report_id, 'revision': tx.report.revision,
               'snapshot_id': tx.snapshot.snapshot_id, 'body_hash': body_hash(tx.report.full_text),
               'full_text': tx.report.full_text, 'drive_url': 'https://docs.google.com/document/d/'+doc_id+'/edit'}
        saved = self._effect(key, 'doc', doc, faults)
        if STATES.index(completed) < STATES.index('DOC_SAVED'):
            self._transition(key, 'DOC_SAVED')
            if stop_after == 'DOC_SAVED':
                raise FixtureStop('stopped after Docs save')
        # Read by the saved ID, never by title. Re-read exact pinned effect on retry.
        read = dict(self.store.find(key+':doc')['payload'])
        read.update(faults.get('doc_readback', {}))
        if any(read.get(k) != doc[k] for k in ('report_id', 'revision', 'snapshot_id', 'body_hash')):
            raise PublisherError('NEEDS_REVIEW', 'Doc metadata identity mismatch')
        tx = tx.verify_docs(chat_text=tx.report.full_text, saved_file_id=saved['file_id'], read_file_id=read['file_id'],
                            drive_url=read['drive_url'], read_text=read['full_text'], read_at=created_at, read_success=True)
        if STATES.index(completed) < STATES.index('DOC_VERIFIED'):
            self._transition(key, 'DOC_VERIFIED')
        png_id = 'fixture-png-'+digest({'transaction': key})[:24]
        image = {'file_id': png_id, 'report_id': tx.report.report_id, 'revision': tx.report.revision,
                 'snapshot_id': tx.snapshot.snapshot_id, 'body_hash': body_hash(tx.report.full_text),
                 'filename': 'マーケットレポート_'+tx.report.report_id+'.png',
                 'png_base64': base64.b64encode(png_bytes).decode('ascii')}
        saved_png = self._effect(key, 'png', image, faults)
        if STATES.index(completed) < STATES.index('PNG_SAVED'):
            self._transition(key, 'PNG_SAVED')
            if stop_after == 'PNG_SAVED':
                raise FixtureStop('stopped after PNG save')
        read_png = dict(self.store.find(key+':png')['payload'])
        read_png.update(faults.get('png_readback', {}))
        tx = tx.verify_png(png_bytes=base64.b64decode(read_png['png_base64'], validate=True),
                           file_id=saved_png['file_id'], read_file_id=read_png['file_id'], filename=read_png['filename'],
                           exists=faults.get('png_exists', True), read_at=created_at, report_id=read_png['report_id'],
                           revision=read_png['revision'], snapshot_id=read_png['snapshot_id'], body_hash_value=read_png['body_hash'])
        if tx.evidence['G4']['png_hash'] != hashlib.sha256(png_bytes).hexdigest():
            raise PublisherError('NEEDS_REVIEW', 'pinned PNG bytes changed')
        if STATES.index(completed) < STATES.index('PNG_VERIFIED'):
            self._transition(key, 'PNG_VERIFIED')
        tx = tx.create_manifest(created_at)
        manifest = self._effect(key, 'manifest', tx.manifest, faults)
        if row['manifest'] is not None and (row['manifest'] != manifest or row['manifest_hash'] != digest(manifest)):
            raise PublisherError('NEEDS_REVIEW', 'immutable Manifest journal mismatch')
        if STATES.index(completed) < STATES.index('MANIFEST_READY'):
            self._transition(key, 'MANIFEST_READY', manifest=manifest, manifest_hash=digest(manifest))
            if stop_after == 'MANIFEST_READY':
                raise FixtureStop('stopped after Manifest creation')
        # Bundle is pinned by Manifest, not fetched or selected again. No Phase F
        # production projection: G6 receives exact ReportObject fixture copies.
        bundle = {'manifest': manifest, 'manifest_hash': digest(manifest), 'report': tx.report.to_dict(),
                  'doc': saved, 'png': saved_png}
        bundle_hash = digest(bundle)
        commit = {'manifest_id': manifest['manifest_id'], 'manifest_hash': digest(manifest),
                  'bundle_hash': bundle_hash, 'bundle': bundle,
                  'git_commit_sha': hashlib.sha1(('offline-fixture-git:'+bundle_hash).encode()).hexdigest(),
                  'simulation': True}
        registration = self._effect(key, 'git', commit, faults)
        if row['git_commit_sha'] is not None and row['git_commit_sha'] != registration['git_commit_sha']:
            raise PublisherError('NEEDS_REVIEW', 'Git SHA differs from checkpoint')
        expected = tx.report.to_dict()
        tx = tx.verify_git(canonical=expected, index=expected, latest=expected, dashboard=expected,
                           existing_revision=tx.report.revision, existing_report=expected,
                           commit_sha=registration['git_commit_sha'])
        if STATES.index(completed) < STATES.index('GIT_REGISTERED'):
            self._transition(key, 'GIT_REGISTERED', git_commit_sha=registration['git_commit_sha'])
        if publication is None:
            # All saved artifacts were reconciled above. If a read/reconciliation
            # failed after an already-complete checkpoint, restore that state;
            # never leave a recovered transaction labelled UNKNOWN.
            if self.store.journal(key)['state'] == 'UNKNOWN':
                self._transition(key, completed)
            return self.result(key, tx)
        # These are supplied fixture observations, never a deploy operation.
        if publication.get('simulation') is not True:
            raise PublisherError('NEEDS_REVIEW', 'only explicitly simulated publication evidence accepted')
        tx = tx.verify_actions(**publication['actions'])
        tx = tx.verify_pages(**publication['pages'])
        if STATES.index(completed) < STATES.index('PUBLISHED'):
            self._transition(key, 'PUBLISHED', publication_evidence=publication)
        if stop_after == 'BEFORE_RECEIPT' and completed != 'VERIFIED':
            raise FixtureStop('stopped before Receipt')
        tx = tx.create_receipt()
        receipt = dict(plain(tx.receipt), receipt_id='receipt-'+digest(tx.receipt))
        receipt = self._effect(key, 'receipt', receipt, faults)
        if row['receipt'] is not None and row['receipt'] != receipt:
            raise PublisherError('NEEDS_REVIEW', 'immutable Receipt journal mismatch')
        if completed != 'VERIFIED' or self.store.journal(key)['state'] == 'UNKNOWN':
            self._transition(key, 'VERIFIED', receipt=receipt)
        return self.result(key, tx)

    def _validate_checkpoint(self, key, row):
        checkpoint = row['checkpoint']
        if checkpoint not in STATES[:9] or row['state'] not in STATES:
            raise PublisherError('NEEDS_REVIEW', 'invalid journal state/checkpoint')
        if row['state'] not in ('UNKNOWN', 'FAILED', 'NEEDS_REVIEW') and row['state'] != checkpoint:
            raise PublisherError('NEEDS_REVIEW', 'journal state/checkpoint inconsistent')
        level = STATES.index(checkpoint)
        for kind, state in (('doc', 'DOC_SAVED'), ('png', 'PNG_SAVED'), ('manifest', 'MANIFEST_READY'),
                            ('git', 'GIT_REGISTERED'), ('receipt', 'VERIFIED')):
            if level >= STATES.index(state) and self.store.find(key+':'+kind) is None:
                raise PublisherError('NEEDS_REVIEW', 'checkpoint claims missing '+kind+' effect; no recreation')
        if level >= STATES.index('MANIFEST_READY') and (row['manifest'] is None or row['manifest_hash'] != digest(row['manifest'])):
            raise PublisherError('NEEDS_REVIEW', 'immutable Manifest journal missing/hash mismatch')
        if level >= STATES.index('GIT_REGISTERED') and not row['git_commit_sha']:
            raise PublisherError('NEEDS_REVIEW', 'Git checkpoint missing SHA')
        if level >= STATES.index('PUBLISHED') and row['publication_evidence'] is None:
            raise PublisherError('NEEDS_REVIEW', 'published checkpoint missing observation evidence')
        if level >= STATES.index('VERIFIED') and row['receipt'] is None:
            raise PublisherError('NEEDS_REVIEW', 'verified checkpoint missing Receipt')
        if level >= STATES.index('VERIFIED') and self.store.find(key+':receipt')['payload'] != row['receipt']:
            raise PublisherError('NEEDS_REVIEW', 'immutable Receipt journal mismatch')
        if row['pending_action'] is not None and row['pending_action'] not in {key+':'+kind for kind in ('doc', 'png', 'manifest', 'git', 'receipt')}:
            raise PublisherError('NEEDS_REVIEW', 'pending action identity mismatch')

    def result(self, key, tx=None):
        row = self.store.journal(key)
        identity = row['envelope']['report']
        return {'mode': 'OFFLINE_DRY_RUN', 'simulation': True, 'transaction_id': key,
                'state': row['state'], 'checkpoint': row['checkpoint'], 'pending_action': row['pending_action'],
                'report_id': row['report_id'], 'revision': row['revision'], 'snapshot_id': identity['snapshot_id'],
                'body_hash': body_hash(identity['full_text']), 'manifest': freeze(row['manifest']) if row['manifest'] else None,
                'manifest_hash': row['manifest_hash'], 'git_commit_sha': row['git_commit_sha'],
                'receipt': freeze(row['receipt']) if row['receipt'] else None, 'effect_counts': self.store.counts(),
                'passed': tx.passed if tx else (), 'error': row['error'], 'events': row['events'],
                'failure_evidence': row['failure_evidence'],
                'production_connected': False, 'push_allowed': False, 'deploy_allowed': False}
