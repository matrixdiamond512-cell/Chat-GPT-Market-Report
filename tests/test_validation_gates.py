import dataclasses
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from reporting.context import ReportContext
from reporting.snapshot import MarketDataSnapshot
from reporting.report import ReportObject
from reporting.gates import Transaction, GateFailure, normalize
from validate_report_transaction import validate
from tests.transaction_fixture import objects, docs, png, manifest_tx, git, pages


class GateTests(unittest.TestCase):
    def begin(self):
        return Transaction.begin(*objects())

    def assert_gate(self, gate, operation):
        with self.assertRaises(GateFailure) as caught:
            operation()
        self.assertEqual(caught.exception.gate, gate)

    def ready_pages(self):
        tx = manifest_tx()
        return tx.verify_git(**git(tx)).verify_actions(commit_sha='a'*40, run_id='fixture-run', status='success')

    def test_drive_id_consistency(self):
        tx = self.begin()
        e = docs(tx.report); e['read_file_id'] = 'different-doc'
        self.assert_gate('G3', lambda: tx.verify_docs(**e))

    def test_full_text_punctuation_and_number_mismatch(self):
        tx = self.begin()
        for changed in (tx.report.full_text+'。', tx.report.full_text.replace('89.47', '08'), tx.report.full_text.replace('fixture本文。', 'fixture本文', 1)):
            e = docs(tx.report); e['read_text'] = changed
            self.assert_gate('G3', lambda: tx.verify_docs(**e))
        e = docs(tx.report); e['read_text'] = tx.report.full_text.replace('\n', '\r\n')[:-2]
        passed = tx.verify_docs(**e)
        self.assertTrue(passed.evidence['G3']['drive']['diff'])

    def test_missing_png_manifest_fail_git_pages_forbidden(self):
        tx = self.begin(); tx = tx.verify_docs(**docs(tx.report))
        e = png(tx); e['exists'] = False
        self.assert_gate('G4', lambda: tx.verify_png(**e))
        self.assert_gate('G5', lambda: tx.create_manifest('2026-10-01T21:03:00+09:00'))
        self.assertFalse(tx.can_register_git); self.assertFalse(tx.can_deploy_pages)
        self.assert_gate('G6', lambda: tx.verify_git(**git(tx)))
        self.assert_gate('G7', lambda: tx.verify_pages(**dict(pages(manifest_tx()))))

    def test_report_id_mismatch(self):
        c, s, r = objects()
        c2 = ReportContext.create('2026-09-30', '21:00', '2026-09-30T20:55:00+09:00', revision=2)
        self.assert_gate('G1', lambda: Transaction.begin(c2, s, r))
        tx = self.begin().verify_docs(**docs(r)); e = png(tx); e['report_id'] = '2026-09-30_21-00'
        self.assert_gate('G4', lambda: tx.verify_png(**e))

    def test_revision_rollback(self):
        tx = manifest_tx()
        for previous in (2, 3):
            e = git(tx); e['existing_revision'] = previous
            self.assert_gate('G6', lambda: tx.verify_git(**e))

    def test_canonical_index_mismatch(self):
        tx = manifest_tx()
        e = git(tx); e['index'] = dict(e['index'], snapshot_id='different')
        self.assert_gate('G6', lambda: tx.verify_git(**e))

    def test_latest_dashboard_mismatch(self):
        tx = manifest_tx()
        for name in ('latest', 'dashboard'):
            e = git(tx); e[name] = dict(e[name], revision=99)
            self.assert_gate('G6', lambda: tx.verify_git(**e))

    def test_numeric_direction_mismatch(self):
        c, s, r = objects()
        with self.assertRaises(ValueError):
            dataclasses.replace(s.markets[0], changeValue=-1, changePct=-1, direction='UP')

    def test_timezone_mismatch(self):
        tx = self.ready_pages()
        e = pages(tx); e['verified_at'] = '2026-10-01T21:05:00'
        with self.assertRaises(ValueError):
            tx.verify_pages(**e)

    def test_dom_gold_btc_08_reject(self):
        tx = self.ready_pages()
        for instrument in ('gold', 'btcusd'):
            e = pages(tx)
            row = next(r for r in e['rows'] if r['instrument'] == instrument)
            row['priceValue'] = 8; row['displayText'] = '08'
            self.assert_gate('G7', lambda: tx.verify_pages(**e))

    def test_loading_timeout_evidence_required(self):
        tx = self.ready_pages()
        e = pages(tx); e['loading_timeout']['error_visible'] = False
        self.assert_gate('G7', lambda: tx.verify_pages(**e))

    def test_mobile_table_evidence_required(self):
        tx = self.ready_pages()
        e = pages(tx); e['mobile']['body_overflow'] = True
        self.assert_gate('G7', lambda: tx.verify_pages(**e))

    def test_connected_g0_g8_receipt_only_after_dom(self):
        tx = manifest_tx()
        self.assertNotIn('receipt', tx.manifest)
        self.assertIsNone(tx.receipt)
        self.assert_gate('G8', tx.create_receipt)
        tx = self.ready_pages(); tx = tx.verify_pages(**pages(tx)); tx = tx.create_receipt()
        self.assertEqual(tx.passed, tuple('G'+str(i) for i in range(9)))
        self.assertEqual(tx.receipt['final_status'], 'VERIFIED')
        self.assertEqual(tx.receipt['manifest_id'], tx.manifest['manifest_id'])

    def test_read_only_entry_point_connects_existing_snapshot(self):
        import base64
        c, s, r = objects(); tx = self.begin(); p = png(tx); p['png_base64'] = base64.b64encode(p.pop('png_bytes')).decode()
        payload = {'execution_context': {'attempt_id': 'fixture-retry-2', 'execution_started_at': '2026-10-01T21:00:00+09:00'},
                   'context': c.to_dict(), 'snapshot': s.to_dict(), 'report': r.to_dict(), 'evidence': {'docs': docs(r), 'png': p, 'manifest_created_at': '2026-10-01T21:03:00+09:00'}}
        result = validate(json.loads(json.dumps(payload)))
        self.assertTrue(result['can_register_git']); self.assertFalse(result['can_deploy_pages'])
        self.assertIsNone(result['receipt'])

    def test_png_bytes_corruption_reject(self):
        tx = self.begin(); tx = tx.verify_docs(**docs(tx.report))
        e = png(tx); e['png_bytes'] = e['png_bytes'][:-5]
        self.assert_gate('G4', lambda: tx.verify_png(**e))

    def test_unresolved_target_cannot_pass_publication(self):
        c, s, r = objects()
        c2 = ReportContext.create('2026-10-02', '21:00', c.data_cutoff, revision=2, mode='recovery')
        s2 = MarketDataSnapshot.capture(c2, s.markets, s.captured_at)
        r2 = ReportObject.build(c2, s2, r.title, r.full_text)
        self.assert_gate('G2', lambda: Transaction.begin(c2, s2, r2))

    def test_required_heading_and_body_numeric_conflict(self):
        c, s, r = objects()
        for body in (r.full_text.replace('リスク管理\n', ''), r.full_text.replace('89.47', '08')):
            changed = ReportObject.build(c, s, r.title, body)
            self.assert_gate('G2', lambda: Transaction.begin(c, s, changed))

    def test_freshness_and_market_type_substitution(self):
        c, s, r = objects()
        for m in (dataclasses.replace(s.markets[0], asOf='2026-09-01T20:50:00+09:00'), dataclasses.replace(s.markets[0], marketType='SPOT')):
            changed = MarketDataSnapshot.capture(c, (m,)+s.markets[1:], s.captured_at)
            obj = ReportObject.build(c, changed, r.title, r.full_text)
            self.assert_gate('G1', lambda: Transaction.begin(c, changed, obj))

    def test_failed_or_different_commit_actions_cannot_authorize_pages(self):
        tx = manifest_tx(); tx = tx.verify_git(**git(tx))
        self.assertFalse(tx.can_deploy_pages)
        for sha, status in (('b'*40, 'success'), ('a'*40, 'failure')):
            self.assert_gate('ACTIONS', lambda: tx.verify_actions(commit_sha=sha, run_id='fixture', status=status))

    def test_same_revision_retry_requires_identical_existing_object(self):
        tx = manifest_tx(); e = git(tx); e['existing_revision'] = 2; e['existing_report'] = tx.report.to_dict()
        self.assertIn('G6', tx.verify_git(**e).passed)

    def test_display_08_cannot_hide_valid_numeric_price(self):
        c, s, r = objects()
        m = dataclasses.replace(s.markets[0], displayText='08')
        changed = MarketDataSnapshot.capture(c, (m,)+s.markets[1:], s.captured_at)
        obj = ReportObject.build(c, changed, r.title, r.full_text)
        self.assert_gate('G1', lambda: Transaction.begin(c, changed, obj))

    def test_failed_drive_compare_keeps_normalization_diffs(self):
        tx = self.begin(); e = docs(tx.report); e['read_text'] = tx.report.full_text+'。'
        with self.assertRaises(GateFailure) as failed:
            tx.verify_docs(**e)
        self.assertIn('comparison_diff', failed.exception.evidence)
        self.assertEqual(failed.exception.evidence['chat']['raw'], tx.report.full_text)

    def test_g1_runs_before_body_factory(self):
        c, s, r = objects(); calls = []
        def produce(ctx, snapshot):
            calls.append((ctx.report_id, snapshot.snapshot_id))
            return r.full_text
        prepared = Transaction.begin(c, s)
        self.assertTrue(prepared.can_generate_body)
        complete = prepared.generate_report(r.title, produce)
        self.assertEqual(len(calls), 1)
        self.assertEqual(complete.report.full_text, r.full_text)
        bad = dataclasses.replace(s.markets[0], asOf='2026-09-01T00:00:00+09:00')
        stale = MarketDataSnapshot.capture(c, (bad,)+s.markets[1:], s.captured_at)
        self.assert_gate('G1', lambda: Transaction.begin(c, stale).generate_report(r.title, produce))
        self.assertEqual(len(calls), 1)
