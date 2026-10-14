import copy
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from reporting.approved_layout import (build_projection, event_time, render_html,
                                       source_events, strict_preflight, validate_projection, panel_for)
from reporting.infographic import ValidationFailure, validate_market_data

REFERENCE = ROOT / 'docs/examples/approved-infographic/approved-reference.png'
EVIDENCE = json.loads((ROOT / 'templates/infographic/approved/events-2026-10-13.json').read_text(encoding='utf-8'))


def report(slot='08-00'):
    return json.loads((ROOT / f'docs/examples/approved-infographic/review-20261014-withdrawal-aware/2026-10-13_{slot}/source-report.json').read_text(encoding='utf-8-sig'))


class ApprovedLayoutTests(unittest.TestCase):
    def setUp(self):
        self.report = report()
        self.view = build_projection(self.report, REFERENCE, event_evidence=EVIDENCE)

    def reject(self, mutate, reason):
        view = copy.deepcopy(self.view)
        mutate(view)
        with self.assertRaisesRegex(ValidationFailure, reason):
            validate_projection(self.report, view, REFERENCE)

    def test_risk_indicators_are_placed_with_rates_while_primary_markets_stay_together(self):
        for instrument in ('vix', 'nikkei_vi', 'fear_greed', 'crypto_fear_greed'):
            with self.subTest(instrument=instrument):
                line = {'source_line_text': f'{instrument} | 20 | pt', 'source_section': '主要市場データ'}
                self.assertEqual(panel_for(line, '16:00'), 8)
        for instrument in ('gold', 'wti', 'nikkei225_futures_ose', 'usdjpy', 'eurusd', 'btcusd'):
            with self.subTest(instrument=instrument):
                line = {'source_line_text': f'{instrument} | 100 | unit', 'source_section': '主要市場データ'}
                self.assertEqual(panel_for(line, '16:00'), 7)

    def test_four_real_sources_keep_all_nonheading_characters_and_all_numeric_occurrences(self):
        for slot in ('08-00','12-00','16-00','21-00'):
            with self.subTest(slot=slot):
                source = report(slot)
                before = copy.deepcopy(source)
                view = build_projection(source, REFERENCE, event_evidence=EVIDENCE)
                body = source['fullText']
                for line in view['lines']:
                    self.assertEqual(body[line['start']:line['end']], line['text'])
                # Check character coverage independently, including punctuation.
                covered = {i for line in view['lines'] for i in range(line['start'],line['end'])}
                offset = 0
                for raw in body.splitlines(keepends=True):
                    if raw.strip() and raw.rstrip('\r\n') != source['title'] and not __import__('re').match(r'^\d+[．.]', raw):
                        self.assertTrue(all(offset+i in covered for i,c in enumerate(raw) if c not in '\r\n'))
                    offset += len(raw)
                for numeric in view['numeric_registry']:
                    self.assertEqual(body[numeric['start']:numeric['end']], numeric['display_value'])
                    self.assertEqual(numeric['verification_status'], 'SOURCE_TEXT_ONLY')
                self.assertEqual(source, before)
                self.assertEqual(view['formal_preflight']['status'], 'BLOCKED')
                self.assertFalse(view['formal_preflight']['publish_allowed'])

    def test_one_digit_numeric_error_rejected(self):
        self.reject(lambda v: v['numeric_registry'][10].update(display_value='999'), 'NUMERIC_REGISTRY_MISMATCH')

    def test_change_sign_error_rejected(self):
        self.reject(lambda v: v['numeric_registry'][10].update(direction='DOWN'), 'NUMERIC_REGISTRY_MISMATCH')

    def test_contract_month_confusion_rejected(self):
        self.reject(lambda v: v['numeric_registry'][10].update(price_basis='COMEX6月限'), 'NUMERIC_REGISTRY_MISMATCH')

    def test_source_text_changed_after_lock_rejected(self):
        changed = copy.deepcopy(self.report)
        changed['fullText'] = changed['fullText'].replace('51,850.55','51,850.56')
        with self.assertRaisesRegex(ValidationFailure, 'SOURCE_CHANGED'):
            validate_projection(changed, self.view, REFERENCE)

    def test_other_slot_timeline_rejected(self):
        changed = copy.deepcopy(self.report)
        changed['fullText'] = changed['fullText'].replace('昨夜NY市場の時系列','東京前場の時系列')
        with self.assertRaisesRegex(ValidationFailure, 'TIMELINE_SLOT_MISMATCH'):
            build_projection(changed, REFERENCE)

    def test_panel_15_removed_rejected(self):
        self.reject(lambda v: v['panels'].pop(14), 'PANEL_LAYOUT_CHANGED|SOURCE_COVERAGE')

    def test_source_line_removed_rejected(self):
        self.reject(lambda v: v['panels'][6]['line_ids'].clear(), 'SOURCE_COVERAGE|PANEL_SOURCE_MAPPING')

    def test_approved_reference_missing_rejected(self):
        with self.assertRaisesRegex(ValidationFailure, 'REFERENCE_NOT_FOUND'):
            build_projection(self.report, ROOT / 'does-not-exist.png')

    def test_other_reference_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            ref = Path(directory) / 'other.png'
            ref.write_bytes(b'an unapproved image')
            with self.assertRaisesRegex(ValidationFailure, 'REFERENCE_HASH_MISMATCH'):
                build_projection(self.report, ref)

    def test_cpi_one_hour_shift_rejected(self):
        evidence = copy.deepcopy(EVIDENCE)
        evidence['events'][0]['timeJST'] = '22:30'
        with self.assertRaisesRegex(ValidationFailure, 'EVENT_TIME_MISMATCH'):
            build_projection(self.report, REFERENCE, event_evidence=evidence)

    def test_dst_uses_event_date_in_summer_and_winter(self):
        summer = copy.deepcopy(EVIDENCE['events'][0])
        self.assertEqual(event_time(summer), '21:30')
        summer.update(date='2026-12-10', localDateTime='2026-12-10T08:30:00', timeJST='22:30')
        self.assertEqual(event_time(summer), '22:30')

    def test_unconfirmed_event_never_gets_claimed_exact_time(self):
        event = {'precision':'EXACT', 'timeJST':'21:30', 'sourceURL':None, 'confirmedAt':None}
        self.assertEqual(event_time(event), '時刻未確定')

    def test_event_dates_do_not_take_unrelated_boj_meeting_or_first_date_on_line(self):
        for slot in ('08-00','12-00','16-00','21-00'):
            events = source_events(report(slot))
            self.assertEqual([e['date'] for e in events], ['2026-10-13','2026-10-14','2026-10-15','2026-10-15'])

    def test_missing_source_identity_stays_missing_and_draft_not_ready(self):
        self.assertIsNone(self.view['source_revision'])
        self.assertIsNone(self.view['source_snapshot_id'])
        self.assertIsNone(self.view['source_claimed_bodyHash'])
        self.assertEqual(self.view['status'],'DRAFT')
        self.assertEqual(self.view['formal_preflight']['publication_status'],'NOT_READY')
        with self.assertRaisesRegex(ValidationFailure,'MARKET_DATA_SNAPSHOT_NOT_FOUND'):
            validate_market_data(self.report)

    def test_formal_marker_cannot_be_forged(self):
        self.reject(lambda v:v.update(status='APPROVED',artifact_type='FORMAL'), 'PREVIEW_ONLY')

    def test_source_body_hash_mismatch_is_a_formal_block(self):
        changed = report('16-00')
        changed['bodyHash'] = '0' * 64
        self.assertIn('SOURCE_BODY_HASH_MISMATCH',strict_preflight(changed)['reasons'])

    def test_transcription_contract_does_not_claim_market_validation(self):
        doc, contract = render_html(self.report,self.view,REFERENCE)
        self.assertEqual(contract['validation']['scope'],'SOURCE_TRANSCRIPTION_ONLY')
        self.assertEqual(contract['validation']['artifact_type'],'DEBUG_PREVIEW')
        self.assertFalse(contract['publication']['publish_allowed'])
        self.assertIn('DRAFT・未検証・公開不可',doc)
        self.assertEqual(len(contract['expected_numeric']),len(self.view['numeric_registry']))

    def test_cli_without_draft_stops_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / 'formal'
            result = subprocess.run([sys.executable,str(ROOT/'scripts/market_report.py'), 'render-infographic',
                                     '--report',str(ROOT/'docs/examples/approved-infographic/review-20261014-withdrawal-aware/2026-10-13_08-00/source-report.json'),
                                     '--reference',str(REFERENCE),'--output',str(dest)],
                                    capture_output=True,text=True,encoding='utf-8')
            self.assertNotEqual(result.returncode,0)
            self.assertIn('FORMAL_GENERATION_BLOCKED',result.stdout)
            self.assertFalse(dest.exists())


if __name__ == '__main__':
    unittest.main()
