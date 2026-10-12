"""Regression suite for the infographic safety contract (TEST 01–12)."""
import json
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
import dataclasses
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from reporting.infographic import (  # noqa: E402
    SourceLock, TIMELINES, ValidationFailure, build_spec, completion_gate,
    validate_0800_source_generation_contract, validate_image, validate_market_data,
    validate_publication_evidence, validate_report, validate_spec,
    vision_attestation_payload,
)
from reporting.context import ReportContext  # noqa: E402
from reporting.snapshot import Market, MarketDataSnapshot  # noqa: E402


def sample(slot='12:00'):
    body = """総合判断
判断は中立。
今日の相場テーマ
金利と為替を確認する。
前回からの変化
日経225は70,683.98。
材料と値動きの整合性
前回70,000から上昇。
今日の主導市場
債券。
重要ニュース
ニュースなし。
金利
米10年金利。
クロスアセット資金フロー
ドルから金。
需給・ポジション
ポジションは中立。
今後のイベント
雇用統計。
主要6市場の見通し
Gold WTI Nikkei 225 Futures (OSE) USD/JPY EUR/USD BTCUSD
メインシナリオ
高値圏。
代替シナリオ
上昇継続。
シナリオが崩れる条件
金利上昇。
次時間帯への引き継ぎ
次の時間を確認。
結論
慎重。
クロスチェック結果
確認済み。
70,683.98
"""
    context = ReportContext.create('2026-10-06', slot, f'2026-10-06T{slot}:00+09:00', mode='historical')
    source_config = json.loads((Path(__file__).resolve().parents[1]/'config/market_data_sources.json').read_text(encoding='utf-8'))['symbols']
    policy = json.loads((Path(__file__).resolve().parents[1]/'config/market_data_validation.json').read_text(encoding='utf-8'))
    target_hour, target_minute = (int(part) for part in slot.split(':'))
    target = target_hour*60+target_minute
    cutoff = target-5
    cutoff_time = f'{cutoff//60:02}:{cutoff%60:02}'
    context = ReportContext.create('2026-10-06', slot, f'2026-10-06T{cutoff_time}:00+09:00', mode='historical')
    quote_minute = cutoff-1
    quote_time = f'{quote_minute//60:02}:{quote_minute%60:02}'
    markets = []
    for name, definition in source_config.items():
        if not definition.get('required'):
            continue
        bounds = policy['symbols'].get(name, {})
        low, high = bounds.get('min', 1), bounds.get('max', 100)
        price = 70683.98 if name == 'nikkei225_futures_ose' else (low+high)/2
        source = definition['sources'][0]
        markets.append(Market(instrument=name, marketType=definition['marketType'], venue=None, contractMonth=None,
                              priceValue=price, priceUnit=definition['unit'], changeValue=None, changePct=None,
                              direction='UNKNOWN', comparisonBasis='', asOf=f'2026-10-06T{quote_time}:00+09:00',
                              source=({'id': source['id'], 'url': source['url']},), status='VALID',
                              unavailableReason=None, displayText=str(price)))
    snapshot = MarketDataSnapshot.capture(context, markets, f'2026-10-06T{cutoff_time}:30+09:00')
    return {'date': '2026-10-06', 'time': slot, 'title': f'マーケットレポート｜2026/10/06 {slot}', 'fullText': body,
            'sourceDocument': {'id': 'doc-fixture-1'},
            'context': context.to_dict(), 'snapshot': snapshot.to_dict()}


def spec(report=None, slot='12:00'):
    report = report or sample(slot)
    rid = f"{report['date']}_{report['time'].replace(':', '-')}"
    panels = [{'title': section, 'type': 'text_panel', 'text': '' if section != '主要6市場の見通し' else 'Gold WTI Nikkei 225 Futures (OSE) USD/JPY EUR/USD BTCUSD', 'numbers': []}
              for section in ('総合判断', '今日の相場テーマ', '前回からの変化', '材料と値動きの整合性', '今日の主導市場', '重要ニュース', '金利', 'クロスアセット資金フロー', '需給・ポジション', '今後のイベント', '主要6市場の見通し', 'メインシナリオ', '代替シナリオ', 'シナリオが崩れる条件', '次時間帯への引き継ぎ', '結論', 'クロスチェック結果')]
    panels[2]['text'] = '70,683.98 日経225'
    source_market = next(market for market in report['snapshot']['markets'] if market['instrument'] == 'nikkei225_futures_ose')
    panels.append({'title': 'Nikkei225', 'type': 'numeric_card', 'text': '',
            'numbers': [{'instrument': source_market['instrument'], 'value': '70,683.98', 'unit': source_market['priceUnit'],
                                'timestamp': source_market['asOf'], 'source_section': '前回からの変化'}]})
    return {'report_id': rid, 'title': report['title'], 'date': report['date'], 'time': report['time'], 'snapshot_id': report['snapshot']['snapshot_id'],
            'source_sha256': SourceLock.create(report).sha256, 'source_locked': True,
            'timeline': list(TIMELINES[report['time']]), 'allow_charts': False, 'allow_gauges': False, 'allow_people': False,
            'panels': panels}


def vision(report, candidate, image_bytes, **changes):
    checks = {key: False for key in ('decorative_charts', 'gauges', 'invented_charts', 'people', 'text_overflow', 'major_typos')}
    checks.update({key: True for key in ('title_correct', 'date_correct', 'time_correct', 'required_sections_present', 'timeline_correct', 'numbers_match', 'headings_match')})
    checks.update(changes)
    return {'review_id': 'vision-fixture-1', 'report_id': f"{report['date']}_{report['time'].replace(':', '-')}" ,
            'source_sha256': candidate['source_sha256'], 'image_sha256': hashlib.sha256(image_bytes).hexdigest(), 'checks': checks}


class InfographicRegressionTests(unittest.TestCase):
    def fails(self, reason, fn):
        with self.assertRaises(ValidationFailure) as exc:
            fn()
        self.assertEqual(exc.exception.reason, reason)

    def test_01_multiple_report_slots_in_one_infographic_fail(self):
        report = sample()
        candidate = spec(report)
        candidate['panels'][0]['text'] += ' 2026-10-06_16-00 2026-10-06_21-00'
        self.fails('TIME_SLOT_CONTAMINATION', lambda: validate_spec(report, candidate))

    def test_02_1200_ny_timeline_contamination_fails(self):
        report = sample()
        candidate = spec(report)
        candidate['panels'][0]['text'] = '昨夜のNY市場の時系列'
        self.fails('TIME_SLOT_CONTAMINATION', lambda: validate_spec(report, candidate))

    def test_03_decorative_line_chart_fails(self):
        report = sample(); candidate = spec(report)
        candidate['panels'][0]['type'] = 'line_chart'
        self.fails('DECORATIVE_CHART_DETECTED', lambda: validate_spec(report, candidate))

    def test_04_one_digit_numeric_drift_fails(self):
        report = sample(); candidate = spec(report)
        candidate['panels'][0]['text'] = '70,687.98'
        candidate['panels'][-1]['numbers'][0]['value'] = '70,687.98'
        self.fails('NUMERIC_DRIFT', lambda: validate_spec(report, candidate))

    def test_05_missing_body_blocks_spec_generation(self):
        self.fails('EMPTY_REPORT_BODY', lambda: build_spec({'date': '2026-10-06', 'time': '12:00', 'title': 't'}))

    def test_heading_mention_does_not_replace_required_section(self):
        report = sample().copy()
        report['fullText'] = report['fullText'].replace('今日の相場テーマ\n金利と為替を確認する。\n', '判断文に今日の相場テーマと書かれているだけ。\n')
        self.fails('MISSING_REQUIRED_REPORT_SECTION', lambda: validate_report(report))

    def test_spec_builder_preserves_main_and_alternative_scenario_sections(self):
        titles = [panel['title'] for panel in build_spec(sample())['panels']]
        self.assertIn('メインシナリオ', titles)
        self.assertIn('代替シナリオ', titles)

    def test_0800_spec_carries_fixed_sixteen_zone_source_generation_contract(self):
        report = sample('08:00')
        candidate = build_spec(report)
        contract = candidate['required_source_fact_contract']
        self.assertEqual('market-report-0800-infographic-facts-v1', contract['contract_id'])
        self.assertEqual(16, len(contract['zones']))
        validate_0800_source_generation_contract(report, candidate)
        candidate.pop('required_source_fact_contract')
        with self.assertRaises(ValidationFailure) as caught:
            validate_0800_source_generation_contract(report, candidate)
        self.assertEqual('08_SOURCE_GENERATION_CONTRACT_MISSING_OR_CHANGED', caught.exception.reason)

    def test_06_empty_docs_readback_fails_existing_gate(self):
        from tests.test_validation_gates import docs, objects
        from reporting.gates import Transaction
        context, snapshot, report = objects()
        tx = Transaction.begin(context, snapshot).attach_report(report)
        evidence = docs(report); evidence['read_text'] = ''
        with self.assertRaises(ValueError):
            tx.verify_docs(**evidence)

    def test_07_docs_body_mismatch_fails_existing_gate(self):
        from tests.test_validation_gates import docs, objects
        from reporting.gates import Transaction
        context, snapshot, report = objects()
        tx = Transaction.begin(context, snapshot).attach_report(report)
        evidence = docs(report); evidence['read_text'] += '改変'
        with self.assertRaises(ValueError):
            tx.verify_docs(**evidence)

    def test_08_portal_readback_before_complete_is_incomplete(self):
        stages = {name: 'PASS' for name in ('market_data', 'report_body', 'infographic', 'google_docs', 'drive_image', 'github', 'receipt', 'portal')}
        stages['portal'] = 'NOT_RUN'
        self.assertEqual(completion_gate(stages), 'INCOMPLETE')

    def test_09_missing_receipt_before_complete_is_incomplete(self):
        stages = {name: 'PASS' for name in ('market_data', 'report_body', 'infographic', 'google_docs', 'drive_image', 'github', 'receipt', 'portal')}
        stages['receipt'] = 'NOT_RUN'
        self.assertEqual(completion_gate(stages), 'INCOMPLETE')

    def test_10_invented_numeric_value_fails(self):
        report = sample(); candidate = spec(report)
        candidate['panels'][0]['text'] += ' 98765.43'
        self.fails('NUMBER_NOT_FOUND_IN_SOURCE', lambda: validate_spec(report, candidate))

    def test_11_1600_wrong_timeline_fails(self):
        report = sample('16:00'); candidate = spec(report)
        candidate['timeline'] = list(TIMELINES['12:00'])
        self.fails('INVALID_TIMELINE', lambda: validate_spec(report, candidate))

    def test_12_generated_image_ignoring_prompt_fails_post_validation(self):
        report = sample(); candidate = spec(report)
        from tests.transaction_fixture import png_bytes
        png = png_bytes()
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/'render.png'; image.write_bytes(png)
            self.fails('DECORATIVE_CHART_DETECTED', lambda: validate_image(report, candidate, str(image), vision(report, candidate, png, decorative_charts=True)))

    def test_source_lock_detects_changed_body_after_lock(self):
        report = sample(); lock = SourceLock.create(report)
        changed = dict(report, fullText=report['fullText']+'\n追記')
        self.fails('SOURCE_CHANGED_AFTER_LOCK', lambda: lock.verify(changed))

    def test_unavailable_image_vision_result_is_not_run(self):
        report = sample(); candidate = spec(report)
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/'render.png'
            from tests.transaction_fixture import png_bytes
            image_bytes = png_bytes(); image.write_bytes(image_bytes)
            self.fails('VISION_REVIEW_NOT_PROVIDED', lambda: validate_image(report, candidate, str(image), None))

    def test_direction_derived_from_prices(self):
        report = sample(); candidate = spec(report)
        candidate['panels'][0]['comparisons'] = [{'instrument': 'Nikkei225', 'previous': 70000, 'current': 70683.98, 'direction': 'DOWN'}]
        self.fails('DIRECTION_MISMATCH', lambda: validate_spec(report, candidate))

    def test_unavailable_market_snapshot_is_watch_and_blocks_generation(self):
        report = sample()
        original = MarketDataSnapshot.restore(report['snapshot'])
        first = dataclasses.replace(original.markets[0], priceValue=None, asOf=None, source=(), status='UNAVAILABLE',
                                    unavailableReason='fixture unavailable', displayText='取得不能', direction='UNKNOWN')
        changed_snapshot = MarketDataSnapshot.capture(ReportContext(**report['context']), (first,)+original.markets[1:], original.captured_at)
        report['snapshot'] = changed_snapshot.to_dict()
        self.assertEqual(validate_market_data(report)['status'], 'WATCH')
        self.fails('MARKET_DATA_NOT_PASS', lambda: build_spec(report))

    def test_publication_requires_identity_bound_readbacks(self):
        report = sample(); rid = '2026-10-06_12-00'
        body_sha = hashlib.sha256(report['fullText'].encode('utf-8')).hexdigest()
        image_sha = 'a'*64
        evidence = {
            'google_docs': {'status': 'PASS', 'file_id': 'doc1', 'read_file_id': 'doc1', 'report_id': rid,
                            'title': report['title'], 'body_sha256': body_sha, 'read_text': report['fullText']},
            'drive_image': {'status': 'PASS', 'file_id': 'png1', 'read_file_id': 'png1', 'report_id': rid,
                            'filename': f'マーケットレポート_{rid}.png', 'mime_type': 'image/png', 'folder_id': 'folder1',
                            'sha256': image_sha, 'read_sha256': image_sha},
            'github': {'status': 'PASS', 'commit_sha': 'b'*40, 'report_path': f'reports/{rid}.json', 'report_id': rid, 'body_sha256': body_sha},
            'receipt': {'status': 'PASS', 'receipt_id': 'r1', 'manifest_id': 'm1', 'report_id': rid, 'git_commit_sha': 'b'*40, 'final_status': 'VERIFIED'},
            'portal': {'status': 'PASS', 'url': 'https://example.test/report', 'report_id': rid, 'latest_report_id': rid,
                       'title': report['title'], 'date': report['date'], 'time': report['time'], 'body_sha256': body_sha},
        }
        validated = validate_publication_evidence(report, evidence, image_sha256=image_sha)
        self.assertEqual(validated['status'], 'STRUCTURE_PASS')
        self.assertFalse(validated['external_observation_verified'])
        evidence['portal']['latest_report_id'] = '2026-10-06_16-00'
        self.fails('PORTAL_READBACK_FAILED', lambda: validate_publication_evidence(report, evidence, image_sha256=image_sha))

    def test_manual_vision_claim_cannot_mark_image_verified(self):
        report = sample(); candidate = spec(report)
        from tests.transaction_fixture import png_bytes
        png = png_bytes()
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/'render.png'; image.write_bytes(png)
            result = validate_image(report, candidate, str(image), vision(report, candidate, png))
        self.assertEqual(result['status'], 'WATCH')
        self.assertEqual(result['artifact_state'], 'VALIDATING')

    def test_signed_vision_attestation_is_bound_to_report_and_image(self):
        report = sample(); candidate = spec(report)
        from tests.transaction_fixture import png_bytes
        png = png_bytes()
        review = vision(report, candidate, png)
        review.update({'schema': 'market-report-vision-review/v1', 'status': 'VERIFIED',
                       'provider': 'trusted-fixture-provider', 'title': report['title'],
                       'source_document_id': report['sourceDocument']['id'],
                       'drive_image_file_id': 'drive-fixture-image-1', 'reviewed_at': '2026-10-07T00:00:00Z'})
        secret = secrets.token_urlsafe(48)
        review['signature'] = hmac.new(secret.encode(), vision_attestation_payload(review).encode(), hashlib.sha256).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/'render.png'; image.write_bytes(png)
            with patch.dict(os.environ, {'MARKET_REPORT_VISION_HMAC_KEY': secret,
                                         'MARKET_REPORT_TRUSTED_VISION_PROVIDER': 'trusted-fixture-provider'}):
                result = validate_image(report, candidate, str(image), review)
                self.assertEqual(result['status'], 'PASS')
                review['image_sha256'] = '0' * 64
                self.fails('VISION_REVIEW_IDENTITY_MISMATCH', lambda: validate_image(report, candidate, str(image), review))

    def test_short_vision_attestation_key_is_rejected(self):
        report = sample(); candidate = spec(report)
        from tests.transaction_fixture import png_bytes
        png = png_bytes(); review = vision(report, candidate, png)
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/'render.png'; image.write_bytes(png)
            with patch.dict(os.environ, {'MARKET_REPORT_VISION_HMAC_KEY': 'too-short',
                                         'MARKET_REPORT_TRUSTED_VISION_PROVIDER': 'trusted-fixture-provider'}):
                self.fails('VISION_ATTESTATION_KEY_INVALID', lambda: validate_image(report, candidate, str(image), review))

    def test_shared_vision_attestation_contract_fixture(self):
        fixture = json.loads((Path(__file__).parent/'fixtures/vision_attestation_contract.json').read_text(encoding='utf-8'))
        review = dict(fixture['review'])
        payload = vision_attestation_payload(review)
        self.assertEqual(payload, fixture['payload'])
        ephemeral_key = secrets.token_bytes(48)
        review['signature'] = hmac.new(ephemeral_key, payload.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(len(review['signature']), 64)


if __name__ == '__main__':
    unittest.main()
