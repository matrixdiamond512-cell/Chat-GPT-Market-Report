import base64
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from reporting.context import ReportContext
from reporting.snapshot import MarketDataSnapshot, plain
from reporting.report import ReportObject, adapt_legacy
from reporting.gates import GateFailure, normalize
from reporting.publisher import DryRunPublisher, FixtureStore, FixtureStop, PublisherError, Identity, ROOT
from tests.transaction_fixture import objects, png_bytes
from tests.publisher_fixture import NOW, payload, publication


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)/'publisher-fixture-test'
        self.store = FixtureStore(self.directory)
        self.publisher = DryRunPublisher(self.store)
        self.context, self.snapshot, self.report = objects()
        self.image = png_bytes()

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def run_fixture(self, **kwargs):
        return self.publisher.run(self.context, self.snapshot, self.report, self.image, now=NOW, **kwargs)

    @property
    def key(self):
        return Identity(self.report.report_id, self.report.revision, self.report.snapshot_id,
                        hashlib.sha256(self.report.full_text.encode()).hexdigest()).transaction_id

    def reopen(self):
        self.store.close()
        self.store = FixtureStore(self.directory)
        self.publisher = DryRunPublisher(self.store)

    def complete(self):
        registered = self.run_fixture()
        return self.run_fixture(publication=publication(registered, self.report))

    def test_duplicate_doc_prevention(self):
        self.run_fixture(); self.reopen(); self.run_fixture()
        self.assertEqual(self.store.counts()['doc'], 1)

    def test_same_file_id_readback(self):
        with self.assertRaises(GateFailure):
            self.run_fixture(faults={'doc_readback': {'file_id': 'different'}})
        self.assertEqual(self.store.journal(self.key)['checkpoint'], 'DOC_SAVED')
        self.assertEqual(self.store.counts(), {'doc': 1})

    def test_body_mismatch_stop(self):
        with self.assertRaises(GateFailure):
            self.run_fixture(faults={'doc_readback': {'full_text': self.report.full_text+'。'}})
        self.assertEqual(self.store.journal(self.key)['state'], 'FAILED')
        self.assertIn('comparison_diff', self.store.journal(self.key)['failure_evidence'])
        self.assertEqual(self.store.counts(), {'doc': 1})

    def test_normalization_allowed(self):
        altered = self.report.full_text.replace('\n', '\r\n')[:-2]
        result = self.run_fixture(faults={'doc_readback': {'full_text': altered}})
        self.assertEqual(result['state'], 'GIT_REGISTERED')
        self.assertEqual(normalize(altered), normalize(self.report.full_text))

    def test_normalization_forbidden(self):
        for suffix in ('。', '\n', ' ', '08'):
            with self.subTest(suffix=suffix):
                text = self.report.full_text+suffix
                self.assertNotEqual(normalize(text), normalize(self.report.full_text))
        with self.assertRaises(GateFailure):
            self.run_fixture(faults={'doc_readback': {'full_text': self.report.full_text.replace('89.47', '89.48')}})

    def test_missing_png_stop(self):
        with self.assertRaises(GateFailure):
            self.run_fixture(faults={'png_exists': False})
        self.assertEqual(self.store.counts(), {'doc': 1, 'png': 1})
        self.assertIsNone(self.store.journal(self.key)['manifest'])

    def test_wrong_png_report_id_stop(self):
        with self.assertRaises(GateFailure):
            self.run_fixture(faults={'png_readback': {'report_id': '2026-10-01_16-00'}})
        self.assertNotIn('git', self.store.counts())

    def test_retry_after_docs(self):
        self.retry_checkpoint('DOC_SAVED', {'doc': 1})

    def test_retry_after_png(self):
        self.retry_checkpoint('PNG_SAVED', {'doc': 1, 'png': 1})

    def test_retry_after_manifest(self):
        self.retry_checkpoint('MANIFEST_READY', {'doc': 1, 'png': 1, 'manifest': 1})

    def retry_checkpoint(self, checkpoint, counts):
        with self.assertRaises(FixtureStop):
            self.run_fixture(stop_after=checkpoint)
        self.assertEqual(self.store.counts(), counts)
        self.assertEqual(self.store.journal(self.key)['state'], checkpoint)
        self.reopen()
        result = self.complete()
        self.assertEqual(result['state'], 'VERIFIED')
        self.assertEqual(self.store.counts(), dict(doc=1, png=1, manifest=1, git=1, receipt=1))

    def test_lost_git_response_recovery(self):
        with self.assertRaises(PublisherError) as exc:
            self.run_fixture(faults={'response_lost': 'git'})
        self.assertEqual(exc.exception.state, 'UNKNOWN')
        journal = self.store.journal(self.key)
        self.assertEqual(journal['checkpoint'], 'MANIFEST_READY')
        self.assertEqual(journal['pending_action'], self.key+':git')
        sha = self.store.find(self.key+':git')['payload']['git_commit_sha']
        self.reopen()
        result = self.complete()
        self.assertEqual(result['git_commit_sha'], sha)
        self.assertEqual(self.store.counts()['git'], 1)

    def test_retry_before_receipt(self):
        registered = self.run_fixture()
        observed = publication(registered, self.report)
        with self.assertRaises(FixtureStop):
            self.run_fixture(publication=observed, stop_after='BEFORE_RECEIPT')
        self.assertEqual(self.store.journal(self.key)['state'], 'PUBLISHED')
        self.assertNotIn('receipt', self.store.counts())
        self.reopen()
        result = self.run_fixture(publication=observed)
        self.assertEqual(result['state'], 'VERIFIED')
        self.assertEqual(self.store.counts()['receipt'], 1)

    def test_duplicate_manifest_prevention(self):
        a = self.run_fixture(); b = self.run_fixture()
        self.assertEqual(a['manifest'], b['manifest'])
        self.assertEqual(self.store.counts()['manifest'], 1)
        with self.assertRaises(TypeError):
            a['manifest']['revision'] = 3

    def test_duplicate_receipt_prevention(self):
        a = self.complete(); self.reopen(); b = self.complete()
        self.assertEqual(a['receipt'], b['receipt'])
        self.assertTrue(a['receipt']['receipt_id'].startswith('receipt-'))
        self.assertEqual(self.store.counts()['receipt'], 1)

    def test_double_execution_creates_one_of_each(self):
        self.complete(); self.reopen(); self.complete()
        self.assertEqual(self.store.counts(), dict(doc=1, png=1, manifest=1, git=1, receipt=1))

    def test_stale_revision_reject(self):
        self.run_fixture()
        c = dataclasses.replace(self.context, revision=1)
        s = MarketDataSnapshot.capture(c, self.snapshot.markets, self.snapshot.captured_at)
        r = ReportObject.build(c, s, self.report.title, self.report.full_text)
        with self.assertRaisesRegex(PublisherError, 'stale'):
            self.publisher.run(c, s, r, self.image, now=NOW)
        self.assertEqual(self.store.counts()['git'], 1)

    def test_changed_snapshot_reject(self):
        self.run_fixture()
        s = MarketDataSnapshot.capture(self.context, self.snapshot.markets, '2026-10-01T20:53:00+09:00')
        r = ReportObject.build(self.context, s, self.report.title, self.report.full_text)
        with self.assertRaisesRegex(PublisherError, 'changed snapshot/bodyHash'):
            self.publisher.run(self.context, s, r, self.image, now=NOW)
        self.assertEqual(self.store.counts()['doc'], 1)

    def test_changed_body_hash_reject(self):
        self.run_fixture()
        r = ReportObject.build(self.context, self.snapshot, self.report.title, self.report.full_text+'。')
        with self.assertRaisesRegex(PublisherError, 'changed snapshot/bodyHash'):
            self.publisher.run(self.context, self.snapshot, r, self.image, now=NOW)
        self.assertEqual(self.store.counts()['doc'], 1)

    def test_invalid_png_bytes_stop(self):
        self.image = b'\x89PNG\r\n\x1a\n'
        with self.assertRaises(GateFailure):
            self.run_fixture()
        self.assertNotIn('manifest', self.store.counts())

    def test_wrong_png_revision_snapshot_body_and_file_id(self):
        # Each fault uses a separate fixture, so a prior terminal failure cannot
        # mask an identity rejection at G4.
        for field, value in (('revision', 1), ('snapshot_id', 'wrong'), ('body_hash', '0'*64), ('file_id', 'different')):
            with self.subTest(field=field):
                store = FixtureStore(Path(self.temp.name)/('publisher-fixture-'+field))
                try:
                    with self.assertRaises(GateFailure):
                        DryRunPublisher(store).run(self.context, self.snapshot, self.report, self.image, now=NOW,
                                                  faults={'png_readback': {field: value}})
                    self.assertNotIn('git', store.counts())
                finally:
                    store.close()

    def test_no_receipt_before_publication(self):
        result = self.run_fixture()
        self.assertEqual(result['state'], 'GIT_REGISTERED')
        self.assertIsNone(result['receipt'])
        self.assertFalse(result['production_connected'])
        self.assertFalse(result['deploy_allowed'])

    def test_failed_dom_stops_receipt(self):
        registered = self.run_fixture(); observed = publication(registered, self.report)
        observed['pages']['full_text'] += '。'
        with self.assertRaises(GateFailure):
            self.run_fixture(publication=observed)
        self.assertNotIn('receipt', self.store.counts())

    def test_failed_actions_stops_receipt(self):
        registered = self.run_fixture(); observed = publication(registered, self.report)
        observed['actions']['status'] = 'failure'
        with self.assertRaises(GateFailure):
            self.run_fixture(publication=observed)
        self.assertNotIn('receipt', self.store.counts())

    def test_unknown_lookup_never_recommits(self):
        with self.assertRaises(PublisherError):
            self.run_fixture(faults={'response_lost': 'git'})
        with self.assertRaises(PublisherError) as exc:
            self.run_fixture(faults={'lookup_unknown': 'git'})
        self.assertEqual(exc.exception.state, 'UNKNOWN')
        self.assertEqual(self.store.counts()['git'], 1)
        self.assertEqual(self.run_fixture()['state'], 'GIT_REGISTERED')

    def test_corrupt_git_content_requires_review(self):
        with self.assertRaises(PublisherError):
            self.run_fixture(faults={'response_lost': 'git'})
        record = self.store.find(self.key+':git')['payload']
        record['git_commit_sha'] = '0'*40
        self.store.db.execute('UPDATE effects SET payload=? WHERE action_id=?', (json.dumps(record), self.key+':git'))
        with self.assertRaisesRegex(PublisherError, 'reconciliation mismatch'):
            self.run_fixture()
        self.assertEqual(self.store.journal(self.key)['state'], 'NEEDS_REVIEW')
        self.assertEqual(self.store.counts()['git'], 1)

    def test_lost_doc_png_manifest_receipt_responses(self):
        for kind in ('doc', 'png', 'manifest', 'receipt'):
            with self.subTest(kind=kind):
                store = FixtureStore(Path(self.temp.name)/('publisher-fixture-lost-'+kind))
                runner = DryRunPublisher(store)
                try:
                    observed = None
                    if kind == 'receipt':
                        result = runner.run(self.context, self.snapshot, self.report, self.image, now=NOW)
                        observed = publication(result, self.report)
                    with self.assertRaises(PublisherError) as exc:
                        runner.run(self.context, self.snapshot, self.report, self.image, now=NOW,
                                   publication=observed, faults={'response_lost': kind})
                    self.assertEqual(exc.exception.state, 'UNKNOWN')
                    result = runner.run(self.context, self.snapshot, self.report, self.image, now=NOW, publication=observed)
                    self.assertEqual(result['state'], 'VERIFIED' if kind == 'receipt' else 'GIT_REGISTERED')
                    self.assertEqual(store.counts()[kind], 1)
                finally:
                    store.close()

    def test_protected_slot_read_only(self):
        source = ROOT/'reports/2026-10-02_21-00.json'
        before = source.read_bytes()
        legacy = adapt_legacy(json.loads(before))
        self.assertEqual(legacy.canonicalIdentity, 'UNRESOLVED')
        c = ReportContext.create('2026-10-02', '21:00', '2026-10-02T20:55:00+09:00', revision=1)
        s = MarketDataSnapshot.capture(c, self.snapshot.markets, '2026-10-02T20:54:00+09:00')
        with self.assertRaisesRegex(PublisherError, 'protected slot'):
            self.publisher.run(c, s, legacy.report, self.image, now=NOW)
        self.assertEqual(self.store.counts(), {})
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(hashlib.sha256(before).hexdigest(), '54c2ca7aa962e7a37c3691236d0e01a6fcdedc2def7a326ce6bdb271872dcfa3')

    def test_fixture_destination_safety(self):
        for directory in (ROOT/'publisher-fixture-disallowed', ROOT/'reports', Path(self.temp.name)/'production'):
            with self.assertRaises(ValueError):
                FixtureStore(directory)
        foreign = Path(self.temp.name)/'publisher-fixture-foreign'
        foreign.mkdir(); (foreign/'existing').write_text('do not touch')
        with self.assertRaises(ValueError):
            FixtureStore(foreign)

    def test_concurrent_runner_rejected(self):
        other = FixtureStore(self.directory)
        try:
            with self.store.exclusive():
                with self.assertRaisesRegex(PublisherError, 'runner holds'):
                    DryRunPublisher(other).run(self.context, self.snapshot, self.report, self.image, now=NOW)
            self.assertEqual(self.store.counts(), {})
        finally:
            other.close()

    def test_terminal_failure_requires_review(self):
        with self.assertRaises(GateFailure):
            self.run_fixture(faults={'png_exists': False})
        with self.assertRaisesRegex(PublisherError, 'reviewed recovery'):
            self.run_fixture()
        self.assertEqual(self.store.counts(), {'doc': 1, 'png': 1})

    def test_manifest_tampering_rejected(self):
        with self.assertRaises(FixtureStop):
            self.run_fixture(stop_after='MANIFEST_READY')
        row = self.store.journal(self.key); altered = dict(row['manifest'], drive_file_id='other')
        self.store.update(self.key, manifest=altered)
        with self.assertRaisesRegex(PublisherError, 'Manifest journal'):
            self.run_fixture()
        self.assertNotIn('git', self.store.counts())

    def test_cli_process_restart_recovery(self):
        fixture = Path(self.temp.name)/'input.json'
        fixture.write_text(json.dumps(payload(), ensure_ascii=False), encoding='utf-8')
        directory = Path(self.temp.name)/'publisher-fixture-process'
        command = [sys.executable, '-B', str(ROOT/'scripts/publish_report_dry_run.py'), str(fixture), '--dry-run', '--fixture-dir', str(directory)]
        env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
        stopped = subprocess.run(command+['--lose-response', 'git'], capture_output=True, text=True, encoding='utf-8', env=env)
        self.assertEqual(stopped.returncode, 1, stopped.stderr)
        self.assertEqual(json.loads(stopped.stdout)['state'], 'UNKNOWN')
        restarted = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', env=env)
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        result = json.loads(restarted.stdout)
        self.assertEqual(result['state'], 'GIT_REGISTERED')
        self.assertEqual(result['effect_counts']['git'], 1)
        self.assertIsNone(result['receipt'])

    def test_unknown_after_registered_restores_checkpoint(self):
        original = self.run_fixture()
        with self.assertRaises(PublisherError):
            self.run_fixture(faults={'lookup_unknown': 'git'})
        self.assertEqual(self.store.journal(self.key)['checkpoint'], 'GIT_REGISTERED')
        self.reopen()
        recovered = self.run_fixture()
        self.assertEqual(recovered['state'], 'GIT_REGISTERED')
        self.assertEqual(recovered['git_commit_sha'], original['git_commit_sha'])
        self.assertEqual(self.store.counts()['git'], 1)

    def test_unknown_after_verified_restores_checkpoint(self):
        original = self.complete()
        with self.assertRaises(PublisherError):
            self.run_fixture(publication=publication(original, self.report), faults={'lookup_unknown': 'receipt'})
        recovered = self.complete()
        self.assertEqual(recovered['state'], 'VERIFIED')
        self.assertEqual(recovered['receipt'], original['receipt'])
        self.assertEqual(self.store.counts()['receipt'], 1)

    def test_missing_saved_effect_cannot_be_recreated(self):
        self.run_fixture()
        self.store.db.execute('DELETE FROM effects WHERE action_id=?', (self.key+':doc',))
        with self.assertRaisesRegex(PublisherError, 'missing doc effect'):
            self.run_fixture()
        self.assertNotIn('doc', self.store.counts())
        self.assertEqual(self.store.journal(self.key)['state'], 'NEEDS_REVIEW')

    def test_missing_manifest_journal_stops_git(self):
        with self.assertRaises(FixtureStop):
            self.run_fixture(stop_after='MANIFEST_READY')
        self.store.update(self.key, manifest=None, manifest_hash=None)
        with self.assertRaisesRegex(PublisherError, 'Manifest journal missing'):
            self.run_fixture()
        self.assertNotIn('git', self.store.counts())

    def test_changed_png_bytes_reject_same_identity(self):
        self.run_fixture()
        self.image += b'extra'
        with self.assertRaisesRegex(PublisherError, 'frozen input/PNG'):
            self.run_fixture()
        self.assertEqual(self.store.counts()['png'], 1)

    def test_new_revision_and_lower_retry(self):
        self.run_fixture()
        c = dataclasses.replace(self.context, revision=3)
        s = MarketDataSnapshot.capture(c, self.snapshot.markets, self.snapshot.captured_at)
        r = ReportObject.build(c, s, self.report.title, self.report.full_text)
        result = self.publisher.run(c, s, r, self.image, now=NOW)
        self.assertEqual(result['state'], 'GIT_REGISTERED')
        self.assertEqual(self.store.counts()['doc'], 2)
        with self.assertRaisesRegex(PublisherError, 'stale'):
            self.run_fixture()

    def test_retry_timestamp_does_not_change_manifest(self):
        original = self.run_fixture()
        result = self.publisher.run(self.context, self.snapshot, self.report, self.image,
                                    now='2026-10-06T12:00:00+09:00')
        self.assertEqual(result['manifest'], original['manifest'])
        self.assertEqual(result['git_commit_sha'], original['git_commit_sha'])

    def test_complete_state_sequence_and_no_external_calls(self):
        with patch('socket.socket', side_effect=AssertionError('network forbidden')), patch('subprocess.Popen', side_effect=AssertionError('Git executable forbidden')):
            result = self.complete()
        self.assertEqual([e['state'] for e in result['events']],
                         ['WAITING', 'DOC_SAVED', 'DOC_VERIFIED', 'PNG_SAVED', 'PNG_VERIFIED',
                          'MANIFEST_READY', 'GIT_REGISTERED', 'PUBLISHED', 'VERIFIED'])
        self.assertEqual(result['manifest']['status'], 'READY_FOR_PUBLICATION')
        self.assertEqual(result['receipt']['manifest_hash'], result['manifest_hash'])

    def test_invalid_publication_evidence_cannot_issue_receipt(self):
        result = self.run_fixture()
        observed = publication(result, self.report)
        observed['simulation'] = False
        with self.assertRaisesRegex(PublisherError, 'explicitly simulated'):
            self.run_fixture(publication=observed)
        self.assertNotIn('receipt', self.store.counts())

    def test_receipt_restart_uses_persisted_observations(self):
        registered = self.run_fixture()
        with self.assertRaises(FixtureStop):
            self.run_fixture(publication=publication(registered, self.report), stop_after='BEFORE_RECEIPT')
        self.reopen()
        result = self.run_fixture()
        self.assertEqual(result['state'], 'VERIFIED')
        self.assertEqual(self.store.counts()['receipt'], 1)

    def test_changed_verified_observations_require_review(self):
        result = self.complete()
        observed = publication(result, self.report)
        observed['pages']['verified_at'] = '2026-10-01T21:06:00+09:00'
        with self.assertRaisesRegex(PublisherError, 'publication evidence changed'):
            self.run_fixture(publication=observed)
        self.assertEqual(self.store.counts()['receipt'], 1)

    def test_receipt_journal_tampering_without_new_observations_rejected(self):
        result = self.complete()
        altered = dict(plain(result['receipt']), portal_url='https://wrong.test')
        self.store.update(self.key, receipt=altered)
        with self.assertRaisesRegex(PublisherError, 'Receipt journal mismatch'):
            self.run_fixture()
        self.assertEqual(self.store.counts()['receipt'], 1)


if __name__ == '__main__':
    unittest.main()
