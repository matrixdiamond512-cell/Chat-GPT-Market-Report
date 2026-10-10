"""Fail-closed validation for report-bound infographic specifications and evidence."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from typing import Any

from .report import canonical_heading
from .snapshot import MarketDataSnapshot

STATUSES = ('PASS', 'WATCH', 'FAIL', 'NOT_RUN', 'NOT_APPLICABLE')
REQUIRED_SECTIONS = (
    '総合判断', '今日の相場テーマ', '前回からの変化', '材料と値動きの整合性',
    '今日の主導市場', '重要ニュース', '金利', 'クロスアセット資金フロー',
    '需給・ポジション', '今後のイベント', '主要6市場の見通し', 'メインシナリオ',
    '代替シナリオ', 'シナリオが崩れる条件', '次時間帯への引き継ぎ', '結論', 'クロスチェック結果',
)
MARKETS = ('Gold', 'WTI', 'Nikkei 225 Futures (OSE)', 'USD/JPY', 'EUR/USD', 'BTCUSD')
TIMELINES = {
    '08:00': ('開始前', '開場', '中盤', '終盤', '東京への引き継ぎ'),
    '12:00': ('08:00時点', '09:00寄り付き', '09:30前後', '10:00〜11:00', '11:30前引け', '12:00時点の判断'),
    '16:00': ('12:00', '12:30後場寄り', '13:00〜14:00', '15:00前後', '大引け', '16:00判断'),
    '21:00': ('欧州市場', 'EUR/USD', '欧州債券', 'US Treasury', 'US equity futures', 'OSE Nikkei night session', 'USD/JPY', 'Gold', 'WTI', 'BTCUSD'),
}
_INFOGRAPHIC_0800_CONTENT_CONTRACT = json.loads(
    (Path(__file__).resolve().parents[2] / 'config' / 'infographic_0800_content_contract_v1.json')
    .read_text(encoding='utf-8')
)
_NUMBER = re.compile(r'(?<![\w])[-+]?\d[\d,]*(?:\.\d+)?%?')
_BANNED = {
    'line_chart': 'DECORATIVE_CHART_DETECTED', 'bar_chart': 'DECORATIVE_CHART_DETECTED',
    'pie_chart': 'DECORATIVE_CHART_DETECTED', 'decorative_chart': 'DECORATIVE_CHART_DETECTED',
    'gauge': 'UNSUPPORTED_VISUAL_ELEMENT', 'meter': 'UNSUPPORTED_VISUAL_ELEMENT',
    'waveform': 'UNSUPPORTED_VISUAL_ELEMENT', 'invented_price_chart': 'UNSUPPORTED_VISUAL_ELEMENT',
    'candlesticks': 'UNSUPPORTED_VISUAL_ELEMENT', 'people': 'UNSUPPORTED_VISUAL_ELEMENT',
    'trader_illustration': 'UNSUPPORTED_VISUAL_ELEMENT',
}


class ValidationFailure(ValueError):
    def __init__(self, reason: str, details: Any = None):
        self.reason = reason
        self.details = details
        super().__init__(reason)


def validate_market_data(report: dict) -> dict:
    """Run the existing immutable G0/G1 market snapshot checks before body use."""
    context_payload = report.get('context') or report.get('report_context')
    snapshot_payload = report.get('snapshot') or report.get('marketDataSnapshot') or report.get('market_data_snapshot')
    if not isinstance(context_payload, dict) or not isinstance(snapshot_payload, dict):
        raise ValidationFailure('MARKET_DATA_SNAPSHOT_NOT_FOUND')
    try:
        from .context import ReportContext
        from .snapshot import MarketDataSnapshot
        from .gates import Transaction, GateFailure
        context = ReportContext(**context_payload)
        if context.report_id != identity(report):
            raise ValidationFailure('REPORT_ID_MISMATCH')
        snapshot = MarketDataSnapshot.restore(snapshot_payload)
        transaction = Transaction.begin(context, snapshot)
    except ValidationFailure:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        raise ValidationFailure('MARKET_DATA_VALIDATION_FAILED', str(exc)) from exc
    status = 'PASS' if all(market.status == 'VALID' for market in snapshot.markets) else 'WATCH'
    return {'status': status, 'report_id': context.report_id, 'snapshot_id': snapshot.snapshot_id,
            'validated_gates': list(transaction.passed), 'captured_at': snapshot.captured_at}


def report_text(report: dict) -> str:
    text = report.get('fullText') or report.get('full_text') or report.get('rawText') or report.get('body')
    if not isinstance(text, str) or not text.strip():
        raise ValidationFailure('EMPTY_REPORT_BODY')
    return text


def identity(report: dict) -> str:
    day, slot = report.get('date') or report.get('report_date'), report.get('time') or report.get('report_time')
    if not isinstance(day, str) or not isinstance(slot, str) or slot not in TIMELINES:
        raise ValidationFailure('INVALID_REPORT_IDENTITY')
    rid = f'{day}_{slot.replace(":", "-")}'
    if report.get('report_id') and report['report_id'] != rid:
        raise ValidationFailure('REPORT_ID_MISMATCH')
    return rid


@dataclass(frozen=True)
class SourceLock:
    report_id: str
    title: str
    sha256: str
    locked: bool = True

    @classmethod
    def create(cls, report: dict) -> 'SourceLock':
        text = report_text(report)
        return cls(identity(report), str(report.get('title') or ''), hashlib.sha256(text.encode('utf-8')).hexdigest())

    def verify(self, report: dict) -> None:
        if not self.locked or identity(report) != self.report_id:
            raise ValidationFailure('SOURCE_LOCK_MISMATCH')
        actual = hashlib.sha256(report_text(report).encode('utf-8')).hexdigest()
        if actual != self.sha256 or str(report.get('title') or '') != self.title:
            raise ValidationFailure('SOURCE_CHANGED_AFTER_LOCK')


def _headings(text: str) -> set[str]:
    recognized = set()
    required_titles = set(REQUIRED_SECTIONS) | {
        '重要イベント', '今日の重要イベント', '今日のイベント', '今後の重要イベント', '個別市場見通し',
        '主要6市場の短期見通し', '6市場の見通し', '上振れシナリオ', '下振れシナリオ',
        'ブレイク条件', '12:00への引き継ぎ', '16:00への引き継ぎ', '21:00への引き継ぎ',
        '08:00への引き継ぎ', 'クロスチェック結果',
    }
    for line in text.replace('\r\n', '\n').splitlines():
        canonical = canonical_heading(line)
        if canonical:
            recognized.add(canonical)
        cleaned = re.sub(r'^\s*#{1,6}\s*', '', line).strip()
        cleaned = re.sub(r'^【(.*)】$', r'\1', cleaned)
        cleaned = re.sub(r'^\d{1,2}[．.、)]\s*', '', cleaned).strip()
        if cleaned in required_titles:
            recognized.add(cleaned)
    return recognized


def _report_sections(text: str) -> list[dict]:
    known = _headings(text)
    sections = []
    current = None
    for line in text.replace('\r\n', '\n').splitlines():
        canonical = canonical_heading(line)
        cleaned = re.sub(r'^\s*#{1,6}\s*', '', line).strip()
        cleaned = re.sub(r'^【(.*)】$', r'\1', cleaned)
        cleaned = re.sub(r'^\d{1,2}[．.、)]\s*', '', cleaned).strip()
        heading = cleaned if cleaned in known else canonical
        if heading:
            if current:
                sections.append(current)
            current = {'heading': heading, 'original_heading': line, 'lines': []}
        elif current is not None:
            current['lines'].append(line)
    if current:
        sections.append(current)
    return sections


def validate_report(report: dict) -> dict:
    rid = identity(report)
    text = report_text(report)
    if not report.get('title'):
        raise ValidationFailure('MISSING_REPORT_TITLE')
    title = str(report.get('title'))
    title_date = str(report.get('date') or report.get('report_date')).replace('-', '/')
    title_time = str(report.get('time') or report.get('report_time'))
    if title_date not in title or title_time not in title:
        raise ValidationFailure('REPORT_TITLE_IDENTITY_MISMATCH')
    sections = _headings(text)
    aliases = {
        '総合判断': ('総合判断',), '材料と値動きの整合性': ('材料と値動きの整合性',),
        '今日の主導市場': ('今日の主導市場',), '金利': ('金利', '米国債', '日本国債'),
        '今後のイベント': ('今後のイベント', '重要イベント', '今日の重要イベント'),
        '主要6市場の見通し': ('主要6市場の見通し', '個別市場見通し', '6市場の見通し'),
        'メインシナリオ': ('メインシナリオ', 'シナリオ'), '代替シナリオ': ('代替シナリオ', '上振れシナリオ', '下振れシナリオ'),
        'シナリオが崩れる条件': ('シナリオが崩れる条件', 'ブレイク条件'),
        '次時間帯への引き継ぎ': ('次時間帯への引き継ぎ', '12:00への引き継ぎ', '16:00への引き継ぎ', '21:00への引き継ぎ', '08:00への引き継ぎ'),
    }
    missing = []
    for required in REQUIRED_SECTIONS:
        options = aliases.get(required, (required,))
        if not any(option in sections for option in options):
            missing.append(required)
    lower = text.lower()
    missing_markets = [m for m in MARKETS if m.lower() not in lower and not ({'Gold': '金', 'Nikkei 225 Futures (OSE)': '日経225先物'}.get(m, '') in text)]
    if missing_markets:
        missing.append('markets:' + ','.join(missing_markets))
    if missing:
        raise ValidationFailure('MISSING_REQUIRED_REPORT_SECTION', missing)
    return {'status': 'PASS', 'report_id': rid, 'body_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(), 'sections': sorted(sections)}


def _numeric_tokens(value: str):
    value = re.sub(r'Nikkei\s+225\s+Futures\s*\(OSE\)', 'Nikkei Futures OSE', value, flags=re.IGNORECASE)
    for found in _NUMBER.findall(value):
        token = found.replace(',', '').removesuffix('%')
        try:
            yield Decimal(token).normalize()
        except InvalidOperation:
            continue


def _text(value):
    ignored = {'timestamp', 'source_section', 'unit', 'instrument', 'report_id', 'source_sha256'}
    def collect(item, key=''):
        if key in ignored:
            return []
        if isinstance(item, dict):
            return [text for k, v in item.items() for text in collect(v, str(k))]
        if isinstance(item, (list, tuple)):
            return [text for v in item for text in collect(v, key)]
        return [str(item)] if isinstance(item, (str, int, float, Decimal)) and not isinstance(item, bool) else []
    return '\n'.join(collect(value))


def _display_text(panels):
    ignored = {'title', 'timestamp', 'source_section', 'unit', 'instrument', 'report_id', 'source_sha256'}
    def collect(item, key=''):
        if key in ignored:
            return []
        if isinstance(item, dict):
            return [text for k, v in item.items() for text in collect(v, str(k))]
        if isinstance(item, (list, tuple)):
            return [text for v in item for text in collect(v, key)]
        if isinstance(item, (str, int, float, Decimal)) and not isinstance(item, bool):
            return [str(item)]
        return []
    return '\n'.join(collect(panels))


def _direction(value):
    normalized = str(value).upper()
    return {'上昇': 'UP', '上': 'UP', '↑': 'UP', '下降': 'DOWN', '下落': 'DOWN', '下': 'DOWN', '↓': 'DOWN', '横ばい': 'FLAT'}.get(normalized, normalized)


def _instrument_aliases(instrument):
    aliases = {'Nikkei225': ('nikkei', '日経225', '日経平均'), 'Gold': ('gold', '金'), 'WTI': ('wti', '原油'),
               'USDJPY': ('usdjpy', 'usd/jpy', 'ドル円'), 'EURUSD': ('eurusd', 'eur/usd', 'ユーロドル'),
               'BTCUSD': ('btcusd', 'bitcoin', 'ビットコイン')}
    return aliases.get(str(instrument), (str(instrument).lower(),))


def validate_0800_source_generation_contract(report: dict, spec: dict) -> None:
    if (report.get('time') or report.get('report_time')) == '08:00' and spec.get('required_source_fact_contract') != _INFOGRAPHIC_0800_CONTENT_CONTRACT:
        raise ValidationFailure('08_SOURCE_GENERATION_CONTRACT_MISSING_OR_CHANGED')


def validate_spec(report: dict, spec: dict, source_lock: dict | None = None) -> dict:
    market_data_result = validate_market_data(report)
    if market_data_result['status'] != 'PASS':
        raise ValidationFailure('MARKET_DATA_NOT_PASS', {'status': market_data_result['status']})
    if spec.get('snapshot_id') != market_data_result['snapshot_id']:
        raise ValidationFailure('SNAPSHOT_ID_MISMATCH')
    lock = SourceLock(**source_lock) if source_lock else SourceLock.create(report)
    lock.verify(report)
    report_result = validate_report(report)
    rid = report_result['report_id']
    if spec.get('report_id') != rid:
        raise ValidationFailure('REPORT_ID_MISMATCH')
    if spec.get('title') != report.get('title') or spec.get('date') != (report.get('date') or report.get('report_date')):
        raise ValidationFailure('REPORT_TITLE_IDENTITY_MISMATCH')
    if spec.get('source_sha256') and spec['source_sha256'] != lock.sha256:
        raise ValidationFailure('SOURCE_LOCK_MISMATCH')
    if spec.get('source_locked') is not True:
        raise ValidationFailure('SOURCE_NOT_LOCKED')
    validate_0800_source_generation_contract(report, spec)
    slot = rid[-5:].replace('-', ':')
    if spec.get('time') and spec['time'] != slot:
        raise ValidationFailure('REPORT_TIME_MISMATCH')
    panels = spec.get('panels')
    if not isinstance(panels, list) or not panels:
        raise ValidationFailure('MISSING_REQUIRED_SECTION')
    violations = []
    panel_titles = [str(panel.get('title', '')) for panel in panels if isinstance(panel, dict)]
    all_panel_text = _text(panels)
    section_aliases = {
        '主要6市場の見通し': ('主要6市場の見通し', '個別市場見通し', '6市場の見通し'),
        'メインシナリオ': ('メインシナリオ', 'シナリオ'),
        '代替シナリオ': ('代替シナリオ', '上振れシナリオ', '下振れシナリオ'),
        'シナリオが崩れる条件': ('シナリオが崩れる条件', 'ブレイク条件'),
        '今後のイベント': ('今後のイベント', '重要イベント', '今日の重要イベント'),
        '次時間帯への引き継ぎ': ('次時間帯への引き継ぎ', 'への引き継ぎ'),
    }
    missing_panels = [required for required in REQUIRED_SECTIONS
                      if not any(alias in title for alias in section_aliases.get(required, (required,)) for title in panel_titles)]
    if missing_panels:
        violations.append('MISSING_REQUIRED_SECTION')
    missing_market_panels = [market for market in MARKETS
                             if market.lower() not in all_panel_text.lower()
                             and not ({'Gold': '金', 'Nikkei 225 Futures (OSE)': '日経225先物'}.get(market, '') in all_panel_text)]
    if missing_market_panels:
        violations.append('MISSING_REQUIRED_SECTION')
    for panel in panels:
        if not isinstance(panel, dict) or not panel.get('title'):
            violations.append('MISSING_REQUIRED_SECTION')
            continue
        for key, reason in _BANNED.items():
            if panel.get(key) is True:
                violations.append(reason)
        if panel.get('type') in ('line_chart', 'bar_chart', 'pie_chart', 'gauge', 'meter', 'chart_3d', 'price_chart', 'candlestick'):
            violations.append('DECORATIVE_CHART_DETECTED' if 'chart' in panel.get('type', '') else 'UNSUPPORTED_VISUAL_ELEMENT')
    slot_timeline = spec.get('timeline')
    if slot_timeline is not None and tuple(slot_timeline) != TIMELINES[slot]:
        violations.append('INVALID_TIMELINE')
    if slot_timeline is None:
        violations.append('INVALID_TIMELINE')
    if any(spec.get(key) is not False for key in ('allow_charts', 'allow_gauges', 'allow_people')):
        violations.append('UNSUPPORTED_VISUAL_ELEMENT')
    visible = all_panel_text
    foreign_ids = re.findall(r'\d{4}-\d{2}-\d{2}_(?:08|12|16|21)-00', visible)
    if any(other != rid for other in foreign_ids):
        violations.append('TIME_SLOT_CONTAMINATION')
    if slot == '12:00' and any(term in visible for term in ('昨夜のNY市場の時系列', 'NY市場時系列', '米国市場の開始前→開場')):
        violations.append('TIME_SLOT_CONTAMINATION')
    if slot == '12:00' and any(term in visible for term in ('16:00終値', '21:00 NY', '21:00 NY市場', '大引け')):
        violations.append('TIME_SLOT_CONTAMINATION')
    if slot == '16:00' and any(term in visible for term in ('09:00寄り付き', '09:30前後', '11:30前引け')):
        violations.append('TIME_SLOT_CONTAMINATION')
    source_numbers = set(_numeric_tokens(report_text(report)))
    spec_numbers = set(_numeric_tokens(_display_text(panels)))
    annotated_numbers = set()
    source_sections = _headings(report_text(report))
    market_data = MarketDataSnapshot.restore(report.get('snapshot') or report.get('marketDataSnapshot') or report.get('market_data_snapshot'))
    market_by_name = {market.instrument: market for market in market_data.markets}
    if not spec_numbers <= source_numbers:
        violations.append('NUMBER_NOT_FOUND_IN_SOURCE')
    for panel in panels:
        for number in panel.get('numbers', []) if isinstance(panel, dict) else []:
            if not isinstance(number, dict) or 'value' not in number or not all(number.get(k) for k in ('unit', 'timestamp', 'source_section', 'instrument')):
                violations.append('NUMBER_PROVENANCE_MISSING')
                continue
            try:
                parsed = set(_numeric_tokens(str(number['value'])))
                annotated_numbers.update(parsed)
                source_instrument_lines = [line for line in report_text(report).splitlines()
                                           if any(alias.lower() in line.lower() for alias in _instrument_aliases(number['instrument']))]
                if source_instrument_lines and parsed and not any(parsed <= set(_numeric_tokens(line)) for line in source_instrument_lines):
                    violations.append('NUMERIC_DRIFT')
                if not parsed or not parsed <= source_numbers:
                    if source_instrument_lines and parsed and not any(parsed <= set(_numeric_tokens(line)) for line in source_instrument_lines):
                        violations.append('NUMERIC_DRIFT')
                    else:
                        violations.append('NUMBER_NOT_FOUND_IN_SOURCE')
                if number['source_section'] not in source_sections:
                    violations.append('NUMBER_PROVENANCE_MISSING')
                source_market = market_by_name.get(number['instrument'])
                if source_market is None:
                    source_market = next((market for instrument, market in market_by_name.items()
                                          if any(alias.lower() in instrument.lower() for alias in _instrument_aliases(number['instrument']))), None)
                if source_market is None:
                    violations.append('NUMBER_PROVENANCE_MISSING')
                if source_market is not None and (number['unit'] != source_market.priceUnit or number['timestamp'] != source_market.asOf):
                    violations.append('NUMBER_PROVENANCE_MISSING')
                if source_market is not None and source_market.priceValue is not None:
                    if parsed != set(_numeric_tokens(str(source_market.priceValue))):
                        violations.append('NUMERIC_DRIFT')
            except (InvalidOperation, TypeError):
                violations.append('NUMBER_NOT_FOUND_IN_SOURCE')
    if not spec_numbers <= annotated_numbers:
        violations.append('NUMBER_PROVENANCE_MISSING')
    for panel in panels:
        if isinstance(panel, dict):
            for comparison in panel.get('comparisons', []):
                try:
                    expected = 'UP' if Decimal(str(comparison['current'])) > Decimal(str(comparison['previous'])) else 'DOWN' if Decimal(str(comparison['current'])) < Decimal(str(comparison['previous'])) else 'FLAT'
                    if _direction(comparison.get('direction')) != expected:
                        violations.append('DIRECTION_MISMATCH')
                except (KeyError, InvalidOperation, TypeError):
                    violations.append('DIRECTION_MISMATCH')
    if violations:
        # Keep the first deterministic machine-readable failure and all observed reasons.
        unique = list(dict.fromkeys(violations))
        priority = ('SOURCE_CHANGED_AFTER_LOCK', 'TIME_SLOT_CONTAMINATION', 'INVALID_TIMELINE', 'NUMERIC_DRIFT',
                    'DIRECTION_MISMATCH', 'DECORATIVE_CHART_DETECTED', 'UNSUPPORTED_VISUAL_ELEMENT',
                    'NUMBER_NOT_FOUND_IN_SOURCE')
        primary = next((reason for reason in priority if reason in unique), unique[0])
        raise ValidationFailure(primary, unique)
    return {'status': 'PASS', 'report_id': rid, 'source_sha256': lock.sha256, 'snapshot_id': market_data_result['snapshot_id'], 'required_sections': len(panels), 'number_count': len(spec_numbers), 'timeline': list(slot_timeline or ()), 'image_generation': 'READY_FOR_IMAGE_GENERATION'}


def build_spec(report: dict) -> dict:
    validated = validate_report(report)
    market_data_result = validate_market_data(report)
    if market_data_result['status'] != 'PASS':
        raise ValidationFailure('MARKET_DATA_NOT_PASS', {'status': market_data_result['status']})
    slot = report.get('time') or report.get('report_time')
    lock = SourceLock.create(report)
    existing = _headings(report_text(report))
    parsed_sections = _report_sections(report_text(report))
    panels = [{'title': str(section['original_heading']).strip('# 【】 '),
               'type': 'text_panel', 'text': '\n'.join(section['lines']), 'numbers': []}
              for section in parsed_sections]
    for market in MarketDataSnapshot.restore(report.get('snapshot') or report.get('marketDataSnapshot') or report.get('market_data_snapshot')).markets:
        if market.priceValue is None:
            continue
        matching = next((section for section in parsed_sections
                        if any(Decimal(str(market.priceValue)) == value for line in section['lines'] for value in _numeric_tokens(line))), None)
        if matching is not None:
            observations = [value for value in (market.priceValue, market.changeValue, market.changePct)
                            if value is not None and any(Decimal(str(value)) == token for line in matching['lines'] for token in _numeric_tokens(line))]
            panels.append({'title': market.instrument, 'type': 'numeric_card', 'text': market.displayText,
                           'numbers': [{'instrument': market.instrument, 'value': str(value), 'unit': market.priceUnit,
                                        'timestamp': market.asOf, 'source_section': matching['heading']} for value in observations]})
    result = {'report_id': lock.report_id, 'title': report.get('title'), 'date': report.get('date') or report.get('report_date'),
            'time': slot, 'source_sha256': lock.sha256, 'snapshot_id': market_data_result['snapshot_id'], 'source_locked': True, 'layout': 'high_information_grid',
            'allow_charts': False, 'allow_gauges': False, 'allow_people': False,
            'timeline': list(TIMELINES[slot]), 'source_sections': sorted(existing), 'panels': panels,
            'generation_prompt': ('NO decorative charts. NO line charts. NO gauges. NO invented price graphs. NO people. '
                                  'Use tables, text panels, arrows, icons and color-coded information blocks.'),
            'status': 'DRAFT', 'market_data_validation': market_data_result, 'report_validation': validated}
    if slot == '08:00':
        result['required_source_fact_contract'] = _INFOGRAPHIC_0800_CONTENT_CONTRACT
    return result


def build_generation_prompt(report: dict, spec: dict) -> str:
    """Only validated structured specs can be turned into an image prompt."""
    validate_spec(report, spec)
    prompt_payload = {'report_id': spec['report_id'], 'title': spec.get('title'), 'layout': spec.get('layout'),
                      'timeline': spec.get('timeline'), 'panels': spec.get('panels')}
    if spec.get('time') == '08:00':
        prompt_payload['required_source_fact_contract'] = spec['required_source_fact_contract']
    payload = json.dumps(prompt_payload, ensure_ascii=False, separators=(',', ':'))
    return ('NO decorative charts. NO line charts. NO bar charts. NO pie charts. NO gauges. '
            'NO invented price graphs. NO candlesticks. NO people. Use tables, text panels, arrows, icons and color-coded information blocks. '
            'Use only the exact source-bound values in this validated JSON; do not round, infer, or add data.\n' + payload)


_VISION_ATTESTATION_FIELDS = (
    'schema', 'status', 'provider', 'review_id', 'report_id', 'title', 'source_sha256',
    'image_sha256', 'source_document_id', 'drive_image_file_id', 'reviewed_at', 'checks',
)


def vision_attestation_payload(review: dict) -> str:
    """Stable cross-runtime payload for an authenticated Vision review."""
    if not isinstance(review, dict) or any(field not in review for field in _VISION_ATTESTATION_FIELDS):
        raise ValidationFailure('VISION_ATTESTATION_INVALID', 'required signed fields are missing')
    lines = [f'{field}={json.dumps(review[field], ensure_ascii=False, sort_keys=True, separators=(",", ":"))}'
             for field in _VISION_ATTESTATION_FIELDS]
    return '\n'.join(lines)


def validate_image(report: dict, spec: dict, image_path: str, vision_review: dict | None) -> dict:
    validate_spec(report, spec)
    if not image_path:
        raise ValidationFailure('IMAGE_NOT_FOUND')
    from pathlib import Path
    path = Path(image_path)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValidationFailure('IMAGE_NOT_FOUND')
    if path.suffix.lower() not in ('.png', '.jpg', '.jpeg'):
        raise ValidationFailure('UNSUPPORTED_IMAGE_FORMAT')
    content = path.read_bytes()
    if path.suffix.lower() == '.png':
        from .gates import GateFailure, validate_png
        try:
            validate_png(content)
        except GateFailure as exc:
            raise ValidationFailure('INVALID_IMAGE_BYTES', str(exc)) from exc
    elif not content.startswith(b'\xff\xd8\xff') or not content.endswith(b'\xff\xd9'):
        raise ValidationFailure('INVALID_IMAGE_BYTES')
    if not vision_review:
        raise ValidationFailure('VISION_REVIEW_NOT_PROVIDED', {'status': 'NOT_RUN'})
    if (vision_review.get('report_id') != identity(report)
            or vision_review.get('source_sha256') != spec.get('source_sha256')
            or vision_review.get('image_sha256') != hashlib.sha256(content).hexdigest()):
        raise ValidationFailure('VISION_REVIEW_IDENTITY_MISMATCH')
    required = ('decorative_charts', 'gauges', 'invented_charts', 'people', 'title_correct', 'date_correct', 'time_correct',
                'required_sections_present', 'timeline_correct', 'numbers_match', 'text_overflow', 'headings_match', 'major_typos')
    checks = vision_review.get('checks', {})
    missing = [name for name in required if name not in checks]
    if missing:
        raise ValidationFailure('VISION_REVIEW_INCOMPLETE', missing)
    non_boolean = [name for name in required if not isinstance(checks[name], bool)]
    if non_boolean:
        raise ValidationFailure('VISION_REVIEW_INCOMPLETE', {'non_boolean_checks': non_boolean})
    violations = []
    for name in ('decorative_charts',):
        if checks[name] is True:
            violations.append('DECORATIVE_CHART_DETECTED')
    for name in ('gauges', 'invented_charts', 'people'):
        if checks[name] is True:
            violations.append('UNSUPPORTED_VISUAL_ELEMENT')
    for name in ('title_correct', 'date_correct', 'time_correct', 'required_sections_present', 'timeline_correct', 'numbers_match', 'headings_match'):
        if checks[name] is not True:
            violations.append({'title_correct': 'IMAGE_TITLE_MISMATCH', 'date_correct': 'IMAGE_DATE_MISMATCH', 'time_correct': 'IMAGE_TIME_MISMATCH', 'required_sections_present': 'MISSING_REQUIRED_SECTION', 'timeline_correct': 'INVALID_TIMELINE', 'numbers_match': 'NUMERIC_DRIFT', 'headings_match': 'HEADING_BODY_MISMATCH'}[name])
    if checks['text_overflow'] is True:
        violations.append('TEXT_OVERFLOW')
    if checks['major_typos'] is True:
        violations.append('MAJOR_TYPO_DETECTED')
    if violations:
        raise ValidationFailure(violations[0], list(dict.fromkeys(violations)))
    warnings = vision_review.get('warnings', [])
    secret = os.environ.get('MARKET_REPORT_VISION_HMAC_KEY', '')
    trusted_provider = os.environ.get('MARKET_REPORT_TRUSTED_VISION_PROVIDER', '')
    if not secret or not trusted_provider:
        # A syntactically valid caller claim remains WATCH until a trust root is configured.
        return {'status': 'WATCH', 'artifact_state': 'VALIDATING', 'image_sha256': hashlib.sha256(content).hexdigest(),
                'vision_review_id': vision_review.get('review_id'), 'review_claim_valid': True, 'warnings': warnings,
                'failure_reason': 'VISION_PROVIDER_NOT_CONFIGURED'}
    if len(secret.encode('utf-8')) < 32:
        raise ValidationFailure('VISION_ATTESTATION_KEY_INVALID', 'HMAC key must contain at least 32 UTF-8 bytes')
    expected_identity = {
        'schema': 'market-report-vision-review/v1',
        'status': 'VERIFIED',
        'provider': trusted_provider,
        'report_id': identity(report),
        'title': report.get('title'),
        'source_sha256': spec.get('source_sha256'),
        'image_sha256': hashlib.sha256(content).hexdigest(),
        'source_document_id': (report.get('sourceDocument') or {}).get('id'),
    }
    if any(vision_review.get(key) != expected for key, expected in expected_identity.items()):
        raise ValidationFailure('VISION_REVIEW_IDENTITY_MISMATCH')
    if not vision_review.get('review_id') or not vision_review.get('drive_image_file_id') or not vision_review.get('reviewed_at'):
        raise ValidationFailure('VISION_ATTESTATION_INVALID', 'review/document/image identity is incomplete')
    try:
        payload = vision_attestation_payload(vision_review).encode('utf-8')
    except ValidationFailure:
        raise
    expected_signature = hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(str(vision_review.get('signature', '')), expected_signature):
        raise ValidationFailure('VISION_ATTESTATION_INVALID', 'HMAC signature mismatch')
    return {'status': 'PASS', 'artifact_state': 'VERIFIED', 'image_sha256': hashlib.sha256(content).hexdigest(),
            'vision_review_id': vision_review.get('review_id'), 'provider': trusted_provider,
            'review_claim_valid': True, 'authenticated_attestation': True, 'warnings': warnings}


def completion_gate(stages: dict[str, str]) -> str:
    required = ('market_data', 'report_body', 'infographic', 'google_docs', 'drive_image', 'github', 'receipt', 'portal')
    if any(stages.get(stage) != 'PASS' for stage in required):
        return 'INCOMPLETE'
    return 'COMPLETE'


def validate_publication_evidence(report: dict, evidence: dict, *, image_sha256: str) -> dict:
    """Check readback evidence structure and identity links, not the external observation itself."""
    rid = identity(report)
    body = report_text(report)
    body_sha = hashlib.sha256(body.encode('utf-8')).hexdigest()
    title = str(report.get('title') or '')
    required = ('google_docs', 'drive_image', 'github', 'receipt', 'portal')
    if not isinstance(evidence, dict):
        raise ValidationFailure('PUBLICATION_EVIDENCE_INVALID')
    docs = evidence.get('google_docs', {})
    if (docs.get('status') != 'PASS' or not docs.get('file_id') or docs.get('file_id') != docs.get('read_file_id')
            or docs.get('report_id') != rid or docs.get('title') != title or docs.get('body_sha256') != body_sha
            or not isinstance(docs.get('read_text'), str) or docs['read_text'] != body):
        raise ValidationFailure('GOOGLE_DOC_READBACK_FAILED')
    drive = evidence.get('drive_image', {})
    if (drive.get('status') != 'PASS' or not drive.get('file_id') or drive.get('file_id') != drive.get('read_file_id')
            or drive.get('report_id') != rid or drive.get('filename') != f'マーケットレポート_{rid}.png'
            or drive.get('mime_type') != 'image/png' or not drive.get('folder_id')
            or drive.get('sha256') != image_sha256 or drive.get('read_sha256') != image_sha256):
        raise ValidationFailure('DRIVE_IMAGE_READBACK_FAILED')
    github = evidence.get('github', {})
    commit = github.get('commit_sha', '')
    if (github.get('status') != 'PASS' or not re.fullmatch(r'[0-9a-f]{40}', str(commit))
            or github.get('report_path') != f'reports/{rid}.json' or github.get('report_id') != rid
            or github.get('body_sha256') != body_sha):
        raise ValidationFailure('GITHUB_REGISTRATION_FAILED')
    receipt = evidence.get('receipt', {})
    if (receipt.get('status') != 'PASS' or not receipt.get('receipt_id') or not receipt.get('manifest_id')
            or receipt.get('report_id') != rid or receipt.get('git_commit_sha') != commit
            or receipt.get('final_status') != 'VERIFIED'):
        raise ValidationFailure('PUBLICATION_RECEIPT_FAILED')
    portal = evidence.get('portal', {})
    if (portal.get('status') != 'PASS' or not portal.get('url') or portal.get('report_id') != rid
            or portal.get('latest_report_id') != rid or portal.get('title') != title
            or portal.get('date') != (report.get('date') or report.get('report_date'))
            or portal.get('time') != (report.get('time') or report.get('report_time'))
            or portal.get('body_sha256') != body_sha):
        raise ValidationFailure('PORTAL_READBACK_FAILED')
    return {'status': 'STRUCTURE_PASS', 'report_id': rid, 'git_commit_sha': commit, 'receipt_id': receipt['receipt_id'], 'portal_url': portal['url'], 'readbacks': list(required),
            'external_observation_verified': False}


def result(status: str, reason: str | None = None, details=None):
    return {'status': status, 'failure_reason': reason, 'details': details}
