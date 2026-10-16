"""08:00-only, source-bound display projection. No acquisition or publication writes."""
from __future__ import annotations

from decimal import Decimal
import hashlib
import html
import json
from pathlib import Path
import re

from .infographic import (ValidationFailure, SourceLock, validate_market_data,
                         validate_report, validate_spec, report_text, _numeric_tokens,
                         _display_text, _headings)
from .report import canonical_heading

ROOT = Path(__file__).resolve().parents[2]
TITLES = ('総合判断', '今日の焦点', '相場テーマ', '重要3条件', 'NY市場の時系列',
          'NY主要指数', '主要市場データ', '金利・ボラティリティ・日本株評価',
          'クロスアセット資金フロー', 'ニュース・材料と波及', '需給・ポジション、SQ/MSQ',
          'シナリオの因果関係', '6市場の短期見通し', '次の時間帯への引き継ぎ',
          'リスク管理・崩れる条件', '結論・データ検証')
MARKETS = ('XAU/USD', 'WTI', 'Nikkei225 OSE', 'USD/JPY', 'EUR/USD', 'BTCUSD')
ICONS = ('gold', 'oil', 'japan', 'usa', 'europe', 'btc')
DISPLAY_MARKETS = ('金（XAU/USD）', 'WTI原油', '日経225先物（大阪取引所）', 'USD/JPY', 'EUR/USD', 'BTCUSD')
SNAPSHOT_NAMES = ('gold', 'wti', 'nikkei225_futures_ose', 'usdjpy', 'eurusd', 'btcusd')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def fail(reason):
    raise ValidationFailure(reason)


def refs(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'ref':
                yield child
            else:
                yield from refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from refs(child)


def validate_projection(report, view, *, fixture=False, spec=None):
    if report.get('time') != '08:00' or view.get('time') != '08:00':
        fail('MORNING_SLOT_ONLY')
    synthetic = report.get('synthetic_fixture') is True
    if synthetic != fixture or view.get('synthetic_fixture') is not synthetic:
        fail('FIXTURE_MODE_MISMATCH')
    # Existing functions are called unchanged. Synthetic mode cannot become formal.
    market_check = validate_market_data(report)
    body_check = validate_report(report)
    if market_check['status'] != 'PASS':
        fail('MARKET_DATA_NOT_PASS')
    if not fixture:
        if not isinstance(spec, dict):
            fail('CANONICAL_SPEC_REQUIRED')
        validate_spec(report, spec)
    lock = SourceLock.create(report)
    context = report.get('context') or report.get('report_context')
    revision = report.get('revision')
    if type(revision) is not int or revision < 1 or context.get('revision') != revision:
        fail('MORNING_REVISION_MISMATCH')
    expected = {'report_id': lock.report_id, 'body_hash': lock.sha256,
                'snapshot_id': market_check['snapshot_id'], 'revision': revision}
    if any(view.get(key) != val for key, val in expected.items()):
        fail('MORNING_IDENTITY_MISMATCH')
    if not fixture and report.get('bodyHash') != lock.sha256:
        fail('SOURCE_LOCK_MISMATCH')
    if not fixture and (report.get('snapshot_id') or report.get('snapshotId')) != market_check['snapshot_id']:
        fail('MORNING_REPORT_SNAPSHOT_ID_MISSING_OR_MISMATCH')
    cards = view.get('cards')
    if not isinstance(cards, list) or [c.get('number') for c in cards] != list(range(1, 17)):
        fail('MORNING_CARD_SEQUENCE')
    required_shapes = {1:('headline','direction'),2:('items',),3:('paragraphs',),4:('items',),
                       5:('timeline',),6:('table',),7:('table',),8:('table',),9:('flow',),
                       10:('chains',),11:('paragraphs',),12:('chains',),13:('markets',),
                       14:('paragraphs',),15:('paragraphs',),16:('conclusion','validation')}
    if any(not card.get(key) for card in cards for key in required_shapes[card['number']]):
        fail('MORNING_REQUIRED_CARD_CONTENT')
    facts = view.get('facts')
    if not isinstance(facts, list) or not facts:
        fail('MORNING_FACTS_MISSING')
    by_id = {f['id']: f for f in facts}
    if len(by_id) != len(facts):
        fail('MORNING_DUPLICATE_FACT')
    body = report_text(report)
    headings = _headings(body)
    source_ranges = []
    active, position = set(), 0
    for line in body.splitlines(keepends=True):
        clean = re.sub(r'^\s*#{1,6}\s*', '', line).strip(' \r\n【】')
        clean = re.sub(r'^\d{1,2}[．.、)]\s*', '', clean)
        canonical_title = canonical_heading(line)
        if clean in headings or canonical_title:
            active = {v for v in (clean, canonical_title) if v}
        else:
            source_ranges.append((position, position + len(line), active))
        position += len(line)
    covered = set()
    snapshot = report.get('snapshot') or report.get('marketDataSnapshot') or report.get('market_data_snapshot')
    by_market = {m['instrument']: m for m in snapshot['markets']}
    spec_text = _display_text(spec['panels']) if not fixture else ''
    for fact in facts:
        start, end = fact.get('start'), fact.get('end')
        if (type(start) is not int or type(end) is not int or start < 0 or end <= start or end > len(body)
                or body[start:end] != fact.get('text') or fact.get('source_section') not in _headings(body)):
            fail('MORNING_FACT_SOURCE_MISMATCH')
        if not any(a <= start and end <= b and fact['source_section'] in names for a,b,names in source_ranges):
            fail('MORNING_FACT_SECTION_MISMATCH')
        # A formal projection cannot add text/numbers outside the unchanged validated spec.
        is_timestamp = (fact.get('snapshot_field') or {}).get('field') == 'asOf'
        if not fixture and not is_timestamp and fact['text'] not in spec_text:
            fail('MORNING_FACT_OUTSIDE_VALIDATED_SPEC')
        covered.update(range(start, end))
        if fact.get('snapshot_field'):
            binding = fact['snapshot_field']
            market = by_market.get(binding.get('instrument'))
            if not market or binding.get('field') not in ('priceValue', 'changeValue', 'changePct', 'asOf'):
                fail('MORNING_SNAPSHOT_BINDING_INVALID')
            raw = market[binding['field']]
            if raw is None:
                fail('MORNING_UNAVAILABLE_NUMERIC_BINDING')
            if binding['field'] == 'asOf':
                if fact['text'] != raw:
                    fail('MORNING_TIMESTAMP_DRIFT')
            elif list(_numeric_tokens(fact['text'])) != [Decimal(str(raw)).normalize()]:
                fail('NUMERIC_DRIFT')
    # Every original non-heading character must be displayed; no arbitrary fact subset.
    position = 0
    for line in body.splitlines(keepends=True):
        clean = re.sub(r'^\s*#{1,6}\s*', '', line).strip(' \r\n【】')
        clean = re.sub(r'^\d{1,2}[．.、)]\s*', '', clean)
        if clean not in headings and not canonical_heading(line) and clean != report['title']:
            if any(position + i not in covered for i, char in enumerate(line) if not char.isspace()):
                fail('MORNING_SOURCE_CONTENT_OMITTED')
        position += len(line)
    used = list(refs(cards)) + list(refs(view.get('header', {})))
    if set(used) != set(by_id):
        fail('MORNING_FACT_COVERAGE')
    focus = cards[1].get('items', [])
    conditions = cards[3].get('items', [])
    if len(focus) != 4 or len(conditions) != 3:
        fail('MORNING_FOCUS_CONDITION_COUNT')
    if not cards[0].get('direction') or cards[0]['direction'].get('ref') not in by_id:
        fail('MORNING_JUDGMENT_DIRECTION_MISSING')
    direction_class(by_id[cards[0]['direction']['ref']]['text'])
    timeline = cards[4].get('timeline', [])
    if [r.get('phase') for r in timeline] != ['開始前', '開場', '中盤', '終盤', '東京への引き継ぎ']:
        fail('INVALID_TIMELINE')
    outlooks = cards[12].get('markets', [])
    if [m.get('symbol') for m in outlooks] != list(MARKETS):
        fail('MORNING_SIX_MARKETS')
    for market, name in zip(outlooks, SNAPSHOT_NAMES):
        for field in ('price', 'asof', 'direction', 'rationale', 'bull', 'bear'):
            if not isinstance(market.get(field), dict) or market[field].get('ref') not in by_id:
                fail('MORNING_MARKET_FIELD_MISSING')
        for key, field in (('price', 'priceValue'), ('asof', 'asOf')):
            binding = by_id[market[key]['ref']].get('snapshot_field')
            if binding != {'instrument': name, 'field': field}:
                fail('MORNING_MARKET_BINDING_MISMATCH')
        direction_class(by_id[market['direction']['ref']]['text'])
    for flow in (cards[8].get('flow'),):
        if not isinstance(flow, dict) or flow.get('basis') not in ('estimated', 'measured'):
            fail('MORNING_FLOW_BASIS_MISSING')
        if not flow.get('inflow') or not flow.get('outflow'):
            fail('MORNING_FLOW_ASSETS_MISSING')
        evidence = by_id[flow['evidence']['ref']]['text']
        if flow['basis'] == 'estimated' and '市場反応からの推定' not in evidence:
            fail('MORNING_FLOW_ESTIMATE_UNLABELLED')
        if flow['basis'] == 'measured' and '実測' not in evidence:
            fail('MORNING_FLOW_MEASUREMENT_UNLABELLED')
    for card in cards:
        if card.get('table'):
            table = card['table']
            columns = {6: ['指数', '終値', '前日比', '騰落率'],
                       7: ['市場', '基準値', '変化', '基準日時'],
                       8: ['指標', '値・基準', '時点']}
            if table.get('columns') != columns.get(card['number']):
                fail('MORNING_TABLE_COLUMNS')
            if not table.get('rows') or any(len(row) != len(table['columns']) for row in table['rows']):
                fail('MORNING_TABLE_SHAPE')
            if table.get('change_columns', []) != {6: [2, 3], 7: [2], 8: []}.get(card['number']):
                fail('MORNING_TABLE_COLOR_COLUMNS')
        for chain in card.get('chains', []):
            if chain.get('basis') not in ('confirmed', 'hypothesis') or len(chain.get('nodes', [])) < 2:
                fail('MORNING_CAUSAL_BASIS_MISSING')
            evidence = by_id[chain['evidence']['ref']]['text']
            if ('想定経路' if chain['basis'] == 'hypothesis' else '確認済み') not in evidence:
                fail('MORNING_CAUSAL_LABEL_MISSING')
    if [chain.get('scenario') for chain in cards[11]['chains']] != ['main','upside','downside']:
        fail('MORNING_SCENARIO_PATHS')
    return {'status': 'PASS', **expected, 'required_fact_ids': sorted(by_id),
            'artifact_type': 'DEBUG_PREVIEW' if fixture else 'FORMAL_INFOGRAPHIC',
            'canonical_spec_validation': 'NOT_APPLICABLE_SYNTHETIC' if fixture else 'PASS',
            'market_data_validation': market_check, 'report_validation': body_check}


def direction_class(text):
    if text in ('上昇', '強気', 'やや強気', '中立〜やや強気', '中立〜ややドル高'):
        return 'up', '↑'
    if text in ('下落', '弱気', 'やや弱気', '中立〜やや弱気'):
        return 'down', '↓'
    if text == '方向未判定':
        return 'flat', '?'
    if text in ('横ばい', '中立'):
        return 'flat', '↔'
    fail('MORNING_DIRECTION_UNSUPPORTED')


def change_class(text):
    values = list(_numeric_tokens(text.replace('−', '-')))
    return 'up' if values and values[0] > 0 else 'down' if values and values[0] < 0 else 'flat'


def render_html(report, view, *, fixture=False, spec=None):
    validation = validate_projection(report, view, fixture=fixture, spec=spec)
    facts = {f['id']: f for f in view['facts']}
    def text(ref):
        return facts[ref['ref']]['text']
    def display(ref, cls=''):
        return '<span class="fact '+cls+'" data-fact-id="'+html.escape(ref['ref'], quote=True)+'">'+html.escape(text(ref))+'</span>'
    def icon(name):
        return f'<svg class="icon" aria-hidden="true"><use href="#icon-{name}"/></svg>'
    sections = []
    for card in view['cards']:
        number = card['number']
        content = ''
        if card.get('headline'):
            style, arrow = direction_class(text(card['direction']))
            content += '<div class="headline '+style+'"><b class="judgment-arrow">'+arrow+'</b>'+display(card['headline'])+'</div><p>'+display(card['direction'])+'</p>'
        if card.get('items'):
            content += '<ol class="numbered">'+''.join('<li>'+display(item)+'</li>' for item in card['items'])+'</ol>'
        for ref in card.get('paragraphs', []):
            if number == 13:
                content += '<div class="market-list-source">'+display(ref)+'</div>'
            else:
                content += '<p>'+display(ref)+'</p>'
        if card.get('timeline'):
            content += '<div class="timeline">'+''.join('<div><b>'+row['phase']+'</b>'+display(row['text'])+'</div>' for row in card['timeline'])+'</div>'
        if card.get('table'):
            table = card['table']
            if number == 7:
                content += '<div class="market-data">'
                for row in table['rows']:
                    label, price, change, asof = (text(ref) for ref in row)
                    glyph = ('usa' if 'USA' in label else 'japan' if 'Nikkei' in label else
                             'gold' if 'XAU' in label else 'oil' if 'WTI' in label else
                             'europe' if 'EUR' in label else 'btc' if 'BTC' in label else '')
                    marker = icon(glyph) if glyph else ''
                    content += '<div class="market-data-row"><div class="market-data-name">'+marker+display(row[0])+'</div><div class="market-data-values"><strong>'+display(row[1])+'</strong><span class="'+change_class(change)+'">'+display(row[2])+'</span><small class="asof">基準時点：'+display(row[3])+'</small></div></div>'
                content += '</div>'
                table = None
            if table:
                content += '<table><thead><tr>'+''.join('<th>'+html.escape(col)+'</th>' for col in table['columns'])+'</tr></thead><tbody>'
                for row in table['rows']:
                    cells = []
                    for i, ref in enumerate(row):
                        marker = ''
                        if i == 0 and number == 6:
                            label = text(ref)
                            glyph = ('usa' if any(name in label for name in ('NYダウ','S&P','Nasdaq','Russell','VIX')) else
                                     'japan' if any(name in label for name in ('日経','TOPIX','OSE','CME')) else '')
                            marker = icon(glyph) if glyph else ''
                        cells.append('<td>'+marker+display(ref, change_class(text(ref)) if i in table.get('change_columns', []) else '')+'</td>')
                    content += '<tr>'+''.join(cells)+'</tr>'
                content += '</tbody></table>'
        if card.get('flow'):
            flow = card['flow']
            def flow_item(ref):
                label = text(ref)
                glyph = ('gold' if '金' in label else 'oil' if '原油' in label else
                         'bank' if '国債' in label else 'trend' if '株' in label else 'btc' if 'BTC' in label else 'trend')
                return '<p>'+icon(glyph).replace('class="icon"','class="icon flow-item-icon"')+display(ref)+'</p>'
            flow_label = '実測フロー' if flow['basis'] == 'measured' else '推定フロー'
            content += '<div class="flow"><div class="inflow"><h3>資金流入が示唆される資産</h3>'+''.join(flow_item(r) for r in flow['inflow'])+'</div><div class="transfer '+flow['basis']+'"><b>'+flow_label+'</b><span class="flow-arrows"><i>→</i><i>←</i></span></div><div class="outflow"><h3>資金の重石・流出候補</h3>'+''.join(flow_item(r) for r in flow['outflow'])+'</div></div><p class="evidence">'+display(flow['evidence'])+'</p>'
        for chain in card.get('chains', []):
            if chain.get('scenario'):
                label = {
                    'main_scenario': 'メインシナリオ',
                    'alternative_scenario': '代替シナリオ',
                    'invalidation_trigger': '崩れる条件',
                }.get(chain.get('scenario_role'))
                label = label or {'main':'メイン','upside':'上振れ','downside':'下振れ'}[chain['scenario']]
                content += '<h3>'+label+'</h3>'
            content += '<div class="chain '+chain['basis']+'">'+('<span class="causal-arrow">→</span>'.join('<div class="'+('long' if len(text(ref)) > 40 else '')+'">'+display(ref)+'</div>' for ref in chain['nodes']))+'</div><p class="evidence">'+display(chain['evidence'])+'</p>'
        if card.get('markets'):
            content += '<div class="market-grid">'
            for market, glyph, label in zip(card['markets'], ICONS, DISPLAY_MARKETS):
                style, arrow = direction_class(text(market['direction']))
                content += '<article class="market"><h3>'+icon(glyph)+label+'</h3><p class="price">'+display(market['price'])+'</p><p class="asof">'+display(market['asof'])+'</p><div class="direction '+style+'"><b>'+arrow+'</b>'+display(market['direction'])+'</div>'
                for field, label in (('rationale', '判断根拠'), ('bull', '強気条件'), ('bear', '弱気条件')):
                    content += '<p class="condition"><strong>'+label+'</strong>'+display(market[field])+'</p>'
                content += '</article>'
            content += '</div><p class="evidence">方向表示は価格の予測方向・監視条件です。</p>'
        if card.get('conclusion'):
            content += '<div class="final-summary"><h3>最終結論</h3>'+display(card['conclusion'])+'</div><div class="validation"><h3>データ検証・公開状態</h3>'+''.join('<p>'+display(r)+'</p>' for r in card['validation'])+'</div>'
        heading_icon = icon({4:'warning',8:'bank',14:'clock',15:'warning'}.get(number)) if number in (4,8,14,15) else ''
        sections.append(f'<section class="card card-{number:02}" data-card="{number:02}"><h2><b>{number:02}</b> {heading_icon}{TITLES[number-1]}</h2><div class="card-body">{content}</div></section>')
    css = (ROOT/'templates/infographic/0800/theme.css').read_text(encoding='utf-8')
    svg = (ROOT/'templates/infographic/0800/icons.svg').read_text(encoding='utf-8')
    report_date = report['title'].split('｜', 1)[-1]
    header = '<header><div class="brandline"><div class="brand">マーケットレポート</div><div class="report-title">'+html.escape(report_date)+'</div></div><div class="brand-aside">世界の流れを読む<br>次の一手を考える</div><div class="subtitle">'+display(view['header']['subtitle'])+'</div><div class="basis">作成基準：日本時間 08:00</div>'
    if fixture:
        header += '<div class="draft">DRAFT / 合成データ・公開不可</div>'
    header += '</header>'
    document = '<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+html.escape(report['title'])+'</title><style>'+css+'</style><body>'+svg+'<main id="report">'+header+'<div class="cards">'+''.join(sections)+'</div><footer>上昇 ↑ ／ 下落 ↓ ／ 中立 ↔　・　流入＝緑 ／ 流出＝赤　・　破線＝推定/想定</footer></main></body></html>'
    expected = {key: fact['text'] for key, fact in facts.items()}
    return document, {'validation': validation, 'expected_text': expected,
                      'view_sha256': sha(canonical(view).encode()), 'html_sha256': sha(document.encode())}


def build_manifest(report, view, png_bytes, render_receipt, drive_file_id, drive_readback_bytes,
                   png_filename, *, fixture=False, spec=None):
    """Assemble the existing consumer contract after renderer and byte readback checks.

    No Drive/Git writes. Callers supply bytes actually read from the pinned Drive ID.
    Local CLI readback files prove byte compatibility, not external file provenance.
    """
    document, expected = render_html(report, view, fixture=fixture, spec=spec)
    from .gates import validate_png
    validate_png(png_bytes)
    if not drive_file_id or drive_readback_bytes != png_bytes:
        fail('MORNING_DRIVE_READBACK_MISMATCH')
    if (render_receipt.get('status') != 'PASS' or render_receipt.get('html_sha256') != expected['html_sha256']
            or render_receipt.get('view_sha256') != expected['view_sha256']
            or render_receipt.get('png_sha256') != sha(png_bytes)
            or render_receipt.get('rendered_fact_ids') != expected['validation']['required_fact_ids']
            or render_receipt.get('numeric_validation') != 'PASS'
            or render_receipt.get('renderer_status') != 'PASS'):
        fail('MORNING_RENDER_RECEIPT_MISMATCH')
    if render_receipt.get('artifact_type') != expected['validation']['artifact_type']:
        fail('MORNING_RENDER_ARTIFACT_TYPE_MISMATCH')
    identity = expected['validation']
    if not fixture and png_filename != f"マーケットレポート_{identity['report_id']}.png":
        fail('MORNING_PNG_FILENAME_MISMATCH')
    manifest = {key: identity[key] for key in ('report_id', 'revision', 'snapshot_id', 'body_hash', 'artifact_type')}
    manifest.update(status='DRAFT' if fixture else 'READY_FOR_PUBLICATION', debug_preview=fixture,
                    drive_file_id=drive_file_id, png_filename=png_filename, png_sha256=sha(png_bytes),
                    required_fact_ids=identity['required_fact_ids'],
                    rendered_fact_ids=render_receipt['rendered_fact_ids'], missing_fact_ids=[],
                    numeric_validation='PASS', renderer_status='PASS', vision_status='NOT_RUN')
    manifest['manifest_id'] = 'morning-'+sha(canonical(manifest).encode())
    manifest['manifest_hash'] = sha(canonical(manifest).encode())
    return manifest
