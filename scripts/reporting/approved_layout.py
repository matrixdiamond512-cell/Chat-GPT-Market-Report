"""Source-exact four-slot DRAFT adapter for the approved 16-panel layout.

Reuses the existing source/snapshot/spec gates and browser renderer. Extracted
numbers are transcription evidence, never an independent market snapshot.
No publication manifest, report revision, or source bodyHash is manufactured.
"""
from __future__ import annotations

import base64
from datetime import datetime
from decimal import Decimal
import hashlib
import html
import io
import json
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo

from .infographic import (ValidationFailure, SourceLock, report_text,
                         validate_market_data, validate_report, validate_spec)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(value):
    return hashlib.sha256(value).hexdigest()

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / 'templates/infographic/approved'
SLOTS = ('08:00', '12:00', '16:00', '21:00')
NUMBER = re.compile(r'[+\-−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?')
OUTLOOK_NAMES = ('金', 'WTI', '日経225先物', 'USD/JPY', 'EUR/USD', 'BTCUSD')
OUTLOOK_ICONS = ('gold', 'oil', 'japan', 'usa', 'europe', 'btc')


def fail(reason, details=None):
    raise ValidationFailure(reason, details)


def layout_config(reference):
    layout = json.loads((TEMPLATE / 'layout.json').read_text(encoding='utf-8'))
    if not Path(reference).is_file():
        fail('APPROVED_REFERENCE_NOT_FOUND')
    if sha(Path(reference).read_bytes()) != layout['reference_sha256']:
        fail('APPROVED_REFERENCE_HASH_MISMATCH')
    if [p['number'] for p in layout['panels']] != list(range(1, 17)):
        fail('APPROVED_PANEL_SEQUENCE')
    if layout['panels'][14]['title'] != '重要イベントスケジュール':
        fail('APPROVED_EVENT_PANEL_MISSING')
    return layout


def source_lines(report):
    body = report_text(report)
    day, slot = report.get('date'), report.get('time')
    if slot not in SLOTS or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day or ''):
        fail('APPROVED_SOURCE_SLOT_INVALID')
    expected_date = day.replace('-', '/')
    if (report.get('title') != body.splitlines()[0] or expected_date not in report['title']
            or not report['title'].endswith(slot)):
        fail('APPROVED_TITLE_BODY_SLOT_MISMATCH')
    lines, section, position = [], '', 0
    headings = []
    for raw in body.splitlines(keepends=True):
        value = raw.rstrip('\r\n')
        m = re.match(r'^(\d{1,2})[．.]\s*(.+)$', value)
        if m:
            section = m[2]
            headings.append(int(m[1]))
        elif value.strip() and value != report['title']:
            offset = 0
            for sentence in re.split(r'(?<=。)', value):
                if sentence:
                    index = re.match(r'^(NYダウ：|S&P500：|Nasdaq総合：|Russell2000：|日経225現物：)([^、。]+)(、(?:前日比)?[^（(]+)([（(][^）)]+[）)])(.*)$', sentence) if slot == '08:00' else None
                    pieces = list(zip(('label','price','change','percent','basis'),index.groups())) if index else [(None,sentence)]
                    for column, piece in pieces:
                        if piece:
                            lines.append({'id': f'l{len(lines)+1:04d}', 'text': piece,
                                          'start': position + offset, 'end': position + offset + len(piece),
                                          'source_line_start': position, 'source_line_text': value,
                                          'source_section': section or '原本冒頭', 'display_column': column})
                            offset += len(piece)
        position += len(raw)
    if headings != list(range(1, 17)):
        fail('APPROVED_SOURCE_SECTION_SEQUENCE', headings)
    return lines


def panel_for(line, slot):
    text, section = line['source_line_text'], line['source_section']
    if section == '原本冒頭':
        if '総合判断' in text:
            return 1
        return 16
    if 'テーマ' in section:
        return 3
    if '時系列' in section or '市場の動き' in section:
        if slot == '08:00' and 'NY' not in section:
            fail('APPROVED_TIMELINE_SLOT_MISMATCH')
        if slot in ('12:00', '16:00') and 'NY' in section:
            fail('APPROVED_TIMELINE_SLOT_MISMATCH')
        if slot == '21:00' and '東京前場' in section:
            fail('APPROVED_TIMELINE_SLOT_MISMATCH')
        return 5
    if '6市場' in section:
        return 13
    if '引き継ぎ' in section:
        return 14
    if 'イベント' in section:
        return 15
    if '崩れる条件' in section and '代替' not in section:
        return 4
    if 'シナリオ' in section or '代替' in section:
        return 12
    if '資金フロー' in section:
        return 9
    if '需給' in section or 'ポジション' in section:
        return 11
    if 'ニュース' in section or '整合性' in section or '主導市場' in section:
        return 10
    if '金利' in section or 'バリュエーション' in section:
        return 8
    if '市場データ' in section or '終値一覧' in section or 'データ取得' in section:
        if slot == '08:00' and re.match(r'^(NYダウ|S&P500|Nasdaq|Russell2000|日経225現物|CME日経)', text):
            return 6
        if slot == '08:00' and re.match(r'^(米10年|日本10年|日経225予想|日経225・25日|東証)', text):
            return 8
        return 7
    if 'からの変化' in section:
        return 14
    if '結論' in section or 'クロスチェック' in section:
        return 16
    fail('APPROVED_UNMAPPED_SOURCE_SECTION', section)


def numeric_registry(lines):
    rows = []
    for line in lines:
        text = line['text']
        for m in NUMBER.finditer(text):
            before, after = text[:m.start()], text[m.end():]
            label = re.split(r'[。／]', before)[-1].partition('：')[0].strip('・ ')
            # Preserve explicit context; do not guess missing trade basis or date.
            unit = re.match(r'^(ドル|円|[%％]|倍|ポイント|bp|枚|銘柄|万株|億円)', after)
            context = line['source_line_text']
            time = re.findall(r'\d{1,2}/\d{1,2}[^。]*?(?:終値|清算値|時点)|\d{1,2}:\d{2}(?:頃)?', context)
            bases = re.findall(r'(?:COMEX[^：。]*|大阪[^：。]*|\d+月限|日足終値|清算値|遅延参照値|現物|スポット|先物|参照値)', context)
            comparison = re.findall(r'[^。]*(?:前日比|前週末|比|との差)[^。]*', context)
            raw = str(Decimal(m[0].replace(',', '').replace('−', '-')))
            rows.append({'fact_id': f'n{len(rows)+1:05d}', 'line_id': line['id'],
                         'start': line['start'] + m.start(), 'end': line['start'] + m.end(),
                         'instrument': label or None, 'display_value': m[0], 'raw_value': raw,
                         'unit': unit[0] if unit else None, 'price_basis': ' / '.join(bases) or None,
                         'as_of': ' / '.join(time) or None,
                         'comparison_basis': ' / '.join(comparison) or None,
                         'change_value': None, 'change_pct': None,
                         'direction': 'UP' if m[0].startswith('+') else 'DOWN' if m[0].startswith(('-', '−')) else 'UNKNOWN',
                         'source_name': 'GitHub保存本文（独立市場データ未照合）',
                         'source_url': None, 'source_timestamp': None,
                         'body_excerpt': context, 'verification_status': 'SOURCE_TEXT_ONLY',
                         'missing_reason': 'typed snapshot/独立した商品・観測時点・出典との対応未確定。符号は転記値の符号であり予測方向ではない。'})
    return rows


def strict_preflight(report, spec=None):
    checks, reasons = {}, []
    for key, fn in (('market_data', validate_market_data), ('body', validate_report)):
        try:
            check = fn(report)
            checks[key] = check
            if check.get('status') != 'PASS':
                reasons.append(key.upper() + '_NOT_PASS')
        except (ValidationFailure, ValueError, KeyError, TypeError) as exc:
            reason = exc.reason if isinstance(exc, ValidationFailure) else 'INPUT_INVALID'
            checks[key] = {'status': 'FAIL', 'reason': reason}
            reasons.append(reason)
    lock = SourceLock.create(report)
    for key in ('revision', 'snapshot_id', 'bodyHash'):
        if not report.get(key):
            reasons.append('SOURCE_' + key.upper() + '_MISSING')
    if report.get('bodyHash') and report['bodyHash'] != lock.sha256:
        reasons.append('SOURCE_BODY_HASH_MISMATCH')
    if not spec:
        checks['spec'] = {'status': 'NOT_RUN', 'reason': 'INFOGRAPHIC_SPEC_NOT_PROVIDED'}
        reasons.append('INFOGRAPHIC_SPEC_NOT_PROVIDED')
    else:
        try:
            checks['spec'] = validate_spec(report, spec)
        except ValidationFailure as exc:
            checks['spec'] = {'status': 'FAIL', 'reason': exc.reason}
            reasons.append(exc.reason)
    return {'status': 'BLOCKED' if reasons else 'PASS', 'checks': checks,
            'reasons': list(dict.fromkeys(reasons)), 'publish_allowed': False,
            'publication_status': 'NOT_READY', 'external_publication': 'NOT_RUN'}


def event_time(event):
    if event.get('precision') != 'EXACT' or not event.get('sourceURL') or not event.get('confirmedAt'):
        return '時刻未確定'
    local = datetime.fromisoformat(event['localDateTime']).replace(tzinfo=ZoneInfo(event['timezone']))
    japan = local.astimezone(ZoneInfo('Asia/Tokyo'))
    if japan.strftime('%Y-%m-%d') != event['date'] or japan.strftime('%H:%M') != event['timeJST']:
        fail('APPROVED_EVENT_TIME_MISMATCH', event.get('event_id'))
    return japan.strftime('%H:%M')


def source_events(report, evidence=None):
    body = report_text(report)
    events = []
    definitions = (('BANK', r'(?:米(?:大手)?|大手)銀行決算', '米大手銀行決算'),
                   ('CPI', r'米(?:9月)?CPI', '米CPI'), ('PPI', r'米PPI', '米PPI'),
                   ('RETAIL', r'小売売上高', '米小売売上高'))
    for code, pattern, title in definitions:
        found = list(re.finditer(pattern, body))
        if not found:
            continue
        candidates = []
        for match in found:
            line_start = body.rfind('\n', 0, match.start()) + 1
            line_end = body.find('\n', match.end())
            line = body[line_start:line_end if line_end >= 0 else len(body)]
            prefix = body[max(line_start, match.start()-30):match.start()].split('。')[-1]
            suffix = body[match.end():match.end()+12]
            preceding = list(re.finditer(r'(\d{1,2})/(\d{1,2})', prefix))
            before = preceding[-1] if preceding and len(prefix[preceding[-1].end():]) <= 12 else None
            after = re.match(r'[（(](\d{1,2})/(\d{1,2})[）)]', suffix)
            dates = after or before
            if dates:
                candidates.append((f"{report['date'][:4]}-{int(dates[1]):02d}-{int(dates[2]):02d}", line))
        days = {day for day, _ in candidates}
        day = next(iter(days)) if len(days) == 1 else None
        line = candidates[0][1] if candidates else body[body.rfind('\n',0,found[0].start())+1:].split('\n')[0]
        if day is None and len(days) == 0:
            declared = [s for s in report.get('events', []) if isinstance(s, str) and re.search(pattern, s)]
            date_matches = [re.search(r'(\d{1,2})/(\d{1,2})', s) for s in declared]
            values = {f"{report['date'][:4]}-{int(m[1]):02d}-{int(m[2]):02d}" for m in date_matches if m}
            if len(values) == 1:
                day = next(iter(values))
        event = {'event_id': f'{code}-{day or report["date"]}', 'title': title, 'date': day,
                 'timeJST': None, 'precision': 'UNKNOWN', 'sourceURL': None,
                 'confirmedAt': None, 'importance': '原本未指定', 'affectedMarkets': [],
                 'body_excerpt': line, 'verification_status': 'SOURCE_TEXT_ONLY',
                 'note': '公式時刻未照合。予定の転記であり実績ではない。'}
        if evidence:
            matches = [e for e in evidence.get('events', []) if e['code'] == code and e['date'] == day]
            if matches:
                event.update(matches[0])
                event_time(event)
        events.append(event)
    return events


def build_projection(report, reference, *, event_evidence=None, spec=None):
    layout = layout_config(reference)
    lines = source_lines(report)
    panels = [{**p, 'line_ids': []} for p in layout['panels']]
    by_id = {l['id']: l for l in lines}
    for line in lines:
        panels[panel_for(line, report['time']) - 1]['line_ids'].append(line['id'])
    # Focus is a source-exact repeat of handover/material excerpts, never a summary rewrite.
    focus = [l['id'] for l in lines if '引き継ぎ' in l['source_section']] or panels[9]['line_ids']
    panels[1]['line_ids'] = focus[:4]
    if not panels[3]['line_ids']:
        panels[3]['line_ids'] = panels[11]['line_ids']
    market_lines = [by_id[f] for f in panels[12]['line_ids']]
    outlooks = []
    for name, icon in zip(OUTLOOK_NAMES, OUTLOOK_ICONS):
        aliases = ('金',) if name == '金' else ('大阪日経', '日経225先物') if name == '日経225先物' else (name,)
        matches = [l for l in market_lines if any(re.match(r'^' + re.escape(a) + r'[^：]{0,12}：', l['text']) for a in aliases)]
        if len(matches) != 1:
            fail('APPROVED_SIX_MARKETS_MISSING_OR_DUPLICATE', name)
        # Only label-specific lines may be repeated as the reference price; broad
        # mixed-instrument prose remains in panel 07, without inventing a quote.
        prices = [l['id'] for l in lines if l['id'] not in panels[12]['line_ids']
                  and panel_for(l, report['time']) in (6, 7)
                  and any(l['text'].lstrip('・').startswith(a) for a in
                          (('金', 'COMEX金', 'COMEX12月限') if name == '金' else
                           ('大阪日経', '大阪取引所日経', '日経225先物') if name == '日経225先物' else aliases))]
        outlooks.append({'name': name, 'icon': icon, 'line_id': matches[0]['id'],
                         'line_ids': [l['id'] for l in market_lines if l['source_line_start'] == matches[0]['source_line_start']],
                         'price_line_ids': prices})
    events = source_events(report, event_evidence)
    projection = {'artifact_type': 'DEBUG_PREVIEW', 'status': 'DRAFT',
                  'report_key': f"{report['date']}_{report['time'].replace(':','-')}",
                  'date': report['date'], 'time': report['time'], 'title': report['title'],
                  'source_observed_sha256': sha(report_text(report).encode('utf-8')),
                  'source_claimed_bodyHash': report.get('bodyHash'),
                  'source_revision': report.get('revision'),
                  'source_snapshot_id': report.get('snapshot_id'),
                  'source_report_status': report.get('report_status'),
                  'source_current_state': 'UNKNOWN',
                  'reference_sha256': layout['reference_sha256'],
                  'layout_sha256': sha(canonical(layout).encode()),
                  'lines': lines, 'panels': panels, 'outlooks': outlooks,
                  'numeric_registry': numeric_registry(lines), 'events': events,
                  'formal_preflight': strict_preflight(report, spec)}
    validate_projection(report, projection, reference)
    return projection


def validate_projection(report, view, reference):
    layout = layout_config(reference)
    if view.get('artifact_type') != 'DEBUG_PREVIEW' or view.get('status') != 'DRAFT':
        fail('APPROVED_PREVIEW_ONLY')
    if (view.get('source_observed_sha256') != sha(report_text(report).encode('utf-8'))
            or view.get('time') != report['time'] or view.get('title') != report['title']):
        fail('APPROVED_SOURCE_CHANGED')
    if view.get('reference_sha256') != layout['reference_sha256'] or view.get('layout_sha256') != sha(canonical(layout).encode()):
        fail('APPROVED_LAYOUT_CHANGED')
    if view['lines'] != source_lines(report):
        fail('APPROVED_SOURCE_LINE_MISMATCH')
    if view['numeric_registry'] != numeric_registry(view['lines']):
        fail('APPROVED_NUMERIC_REGISTRY_MISMATCH')
    expected = {l['id'] for l in view['lines']}
    used = set()
    for panel, target in zip(view['panels'], layout['panels']):
        if any(panel.get(k) != v for k,v in target.items()):
            fail('APPROVED_PANEL_LAYOUT_CHANGED')
        used.update(panel['line_ids'])
    if len(view['panels']) != 16 or used != expected:
        fail('APPROVED_SOURCE_COVERAGE')
    for line in view['lines']:
        if line['id'] not in view['panels'][panel_for(line, report['time'])-1]['line_ids']:
            fail('APPROVED_PANEL_SOURCE_MAPPING')
    if [m['name'] for m in view['outlooks']] != list(OUTLOOK_NAMES):
        fail('APPROVED_SIX_MARKETS')
    for event in view['events']:
        if event['body_excerpt'] not in report_text(report):
            fail('APPROVED_EVENT_OUTSIDE_SOURCE')
        event_time(event)
    return {'status': 'PASS', 'scope': 'SOURCE_TRANSCRIPTION_ONLY',
            'source_lines': len(expected), 'numeric_tokens': len(view['numeric_registry']),
            'publish_allowed': False}


def icon(name):
    return f'<svg class="source-icon" aria-hidden="true"><use href="#icon-{name}"/></svg>'


def render_html(report, view, reference):
    validation = validate_projection(report, view, reference)
    by_id = {l['id']: l for l in view['lines']}
    by_line = {}
    for num in view['numeric_registry']:
        by_line.setdefault(num['line_id'], []).append(num)

    def fact(fid):
        line = by_id[fid]
        text, pos, parts = line['text'], 0, []
        for num in by_line.get(fid, []):
            start, end = num['start'] - line['start'], num['end'] - line['start']
            parts.append(html.escape(text[pos:start]))
            cls = 'up' if num['direction'] == 'UP' else 'down' if num['direction'] == 'DOWN' else ''
            parts.append(f'<span class="numeric {cls}" data-numeric-id="{num["fact_id"]}">{html.escape(num["display_value"])}</span>')
            pos = end
        parts.append(html.escape(text[pos:]))
        return f'<span class="fact" data-fact-id="{fid}">{"".join(parts)}</span>'

    def groups(ids):
        grouped = []
        for fid in ids:
            if grouped and by_id[grouped[-1][0]]['source_line_start'] == by_id[fid]['source_line_start']:
                grouped[-1].append(fid)
            else:
                grouped.append([fid])
        return grouped

    def paragraph(ids):
        if isinstance(ids, str):
            ids = [ids]
        return '<p class="source-line"><small class="source-heading">' + html.escape(by_id[ids[0]]['source_section']) + '</small>' + ''.join(fact(fid) for fid in ids) + '</p>'

    def prose(ids):
        return ''.join(paragraph(group) for group in groups(ids))

    def market_direction(text):
        direction = text.partition('：')[2].partition('。')[0]
        if '弱気' in direction or '円高' in direction:
            return 'down', '↓'
        if '強気' in direction or 'ドル高' in direction:
            return 'up', '↑'
        return 'flat', '↔'

    cards = []
    for panel in view['panels']:
        no, ids = panel['number'], panel['line_ids']
        content = prose(ids)
        if no == 1:
            content = '<div class="lead"><div>' + icon('oil') + icon('gold') + '</div><div>' + content + '</div></div>'
        elif no == 2:
            content = '<ol class="focus">' + ''.join('<li>' + fact(fid) + '</li>' for fid in ids) + '</ol>'
        elif no == 3:
            content = '<div class="causal-row">' + icon('oil') + '<div>' + content + '</div></div>'
        elif no == 4:
            content = ''.join('<div class="warning">' + icon('warning') + paragraph(group) + '</div>' for group in groups(ids))
            content += '<div class="unknown">原本の条件を全文表示。3条件への分割・確定は未検証。</div>'
        elif no == 5:
            content = ''.join('<div class="timeline-row"><div>' + ''.join(fact(fid) for fid in group) + '</div></div>' for group in groups(ids))
        elif no in (6, 7):
            detailed = no == 6 and any(by_id[fid]['display_column'] for fid in ids)
            headings = '<th>指数</th><th>終値</th><th>前日比</th><th>騰落率</th>' if detailed else '<th class="label">市場 / 基準</th><th>原本値・変化・観測時刻（異時点を保持）</th>'
            content = '<table class="data-table"><thead><tr>' + headings + '</tr></thead><tbody>'
            for group in groups(ids):
                label = by_id[group[0]]['text'].lstrip('・').partition('：')[0]
                pictogram = 'japan' if '日経' in label else 'usa' if no == 6 else 'gold' if '金先物' in label or '金スポット' in label else 'oil' if 'WTI' in label or '原油' in label else 'europe' if 'EUR' in label else 'btc' if 'BTC' in label else 'usa'
                if detailed and any(by_id[fid]['display_column'] for fid in group):
                    content += '<tr>' + ''.join('<td>' + (icon(pictogram) if column == 'label' else '') + ''.join(fact(fid) for fid in group if by_id[fid]['display_column'] == column) + '</td>' for column in ('label','price','change','percent')) + '</tr>'
                    content += '<tr><td colspan="4" class="small">' + ''.join(fact(fid) for fid in group if by_id[fid]['display_column'] in ('basis',None)) + '</td></tr>'
                else:
                    content += '<tr><td' + (' colspan="4"' if detailed else '') + '>' + ('' if detailed else icon(pictogram) + html.escape(label[:35]) + '</td><td>') + ''.join(fact(fid) for fid in group) + '</td></tr>'
            content += '</tbody></table>'
        elif no == 8:
            content = '<div class="metrics">' + ''.join('<div class="metric">' + ''.join(fact(fid) for fid in group) + '</div>' for group in groups(ids)) + '</div>'
        elif no == 9:
            content = '<div class="flow-title"><span>資金流入の仮説</span><span>資金流出の仮説</span></div><div class="transfer" aria-hidden="true"><span class="arrow-in">←</span><span class="arrow-out">→</span></div>' + content + '<div class="flow-note">価格反応による推定。実測資金額ではない。</div>'
        elif no == 10:
            content = ''.join('<div class="causal-row">' + icon('oil' if any('原油' in by_id[fid]['text'] for fid in group) else 'japan') + '<div>' + ''.join(fact(fid) for fid in group) + '</div></div>' for group in groups(ids))
        elif no == 12:
            content = ''.join('<div class="scenario-row">' + ''.join(fact(fid) for fid in group) + '</div>' for group in groups(ids))
        elif no == 13:
            tiles = []
            mapped = set()
            for market in view['outlooks']:
                fid = market['line_id']
                mapped.update(market['line_ids'])
                cls, arrow = market_direction(by_id[fid]['text'])
                prices = ''.join('<div class="price-basis">' + fact(p) + '</div>' for p in market['price_line_ids'])
                tiles.append('<article class="market"><h3>' + icon(market['icon']) + html.escape(market['name']) + '</h3><div class="direction ' + cls + '">' + arrow + '</div><p>' + ''.join(fact(f) for f in market['line_ids']) + '</p>' + (prices or '<div class="missing">独立した基準値セルなし。原本の市場データ欄を参照。</div>') + '</article>')
            content = '<div class="market-grid">' + ''.join(tiles) + '</div>' + prose([fid for fid in ids if fid not in mapped])
        elif no == 15:
            content = '<div class="events-note">予定表。公式確認は生成時の追補で、原本作成時の確認ではありません。予想・実績は補完しません。</div><table class="data-table events"><thead><tr><th>日付 / 曜日</th><th>JST</th><th>イベント</th><th>重要度</th><th>影響市場</th><th>注意点</th></tr></thead><tbody>'
            for event in view['events']:
                day = event['date']
                label = day[5:] + ' (' + '月火水木金土日'[datetime.fromisoformat(day).weekday()] + ')' if day else '日付未確定'
                note = '公式予定時刻を追補確認' if event['precision'] == 'EXACT' else '一次資料の時刻照合未了'
                content += '<tr data-event-id="' + html.escape(event['event_id']) + '">' + ''.join('<td>' + html.escape(str(v)) + '</td>' for v in (label, event_time(event), event['title'], event['importance'], '・'.join(event['affectedMarkets']) or '原本未指定', note)) + '</tr>'
            content += '</tbody></table>' + prose(ids)
        if not ids and no != 15:
            content += '<div class="missing">この時刻の原本に対応データなし。別時刻の値では補完しません。</div>'
        title = panel['title']
        if no == 5 and view['time'] != '08:00':
            title = {'12:00': '東京前場の時系列', '16:00': '東京市場の時系列', '21:00': '欧州・NY開場前の時系列'}[view['time']]
        cards.append(f'<section class="card card-{no:02d} {panel["color"]}" data-card="{no:02d}" style="grid-column:{panel["start"]}/span {panel["span"]};grid-row:{panel["row"]}"><h2><b>{no:02d}</b>{html.escape(title)}</h2><div class="card-body">{content}</div></section>')
    # Only this text-free ornamental area is reused, per the supplied specification.
    from PIL import Image
    layout = layout_config(reference)
    with Image.open(reference) as image:
        if list(image.size) != layout['reference_size']:
            fail('APPROVED_REFERENCE_SIZE')
        stream = io.BytesIO()
        image.crop(tuple(layout['header_decoration_crop'])).save(stream, format='PNG')
    skyline = base64.b64encode(stream.getvalue()).decode('ascii')
    sprite = (ROOT / 'templates/infographic/0800/icons.svg').read_text(encoding='utf-8')
    css = (TEMPLATE / 'theme.css').read_text(encoding='utf-8')
    reasons = view['formal_preflight']['reasons']
    source_claim = '原文hash欠損' if not view['source_claimed_bodyHash'] else '原文hash一致' if view['source_claimed_bodyHash'] == view['source_observed_sha256'] else '原文hash不一致'
    historical = '撤回済みGitHub履歴・現在の原本として使用不可｜' if view['source_current_state'] == 'HISTORICAL_SOURCE_WITHDRAWN' else '現在の原本との対応は未確定｜' if view['source_current_state'] != 'CURRENT_GIT_SOURCE' else ''
    doc = '<!doctype html><html lang="ja"><meta charset="utf-8"><style>' + css + '</style><body>' + sprite + '<main id="report"><header><img class="skyline" alt="承認画像の文字を含まない東京夜景装飾" src="data:image/png;base64,' + skyline + '"><h1>' + html.escape(view['title']) + '</h1><div class="basis">原本の観測時刻・商品の区別を保持｜世界の流れを読む、次の一手を考える</div></header><div class="draft">DRAFT・未検証・公開不可｜' + historical + 'GitHub本文の転記一致を検査。市場snapshotの独立照合は未完了。</div><div class="cards">' + ''.join(cards) + '</div><footer>データ照合：本文文字・数値の転記検査のみ。' + source_claim + '。snapshot / revisionは原本の値のみ保持。<br>正式生成停止理由：' + html.escape(' / '.join(reasons) or '正式テンプレートと公開manifestの接続・受入未完了') + '<br>出典・商品・観測時点の詳細は原本とnumeric-registry.jsonを参照。DEBUG_PREVIEW。Drive / Portal公開はNOT_RUN。</footer></main></body></html>'
    contract = {'html_sha256': sha(doc.encode()), 'view_sha256': sha(canonical(view).encode()),
                'expected_text': {l['id']: l['text'] for l in view['lines']},
                'expected_numeric': {n['fact_id']: n['display_value'] for n in view['numeric_registry']},
                'layout_profile': 'APPROVED_16_PANEL', 'grid_columns': 60,
                'outlook_width_fraction': 40 / 60, 'output_basename': 'preview-' + view['report_key'],
                'validation': {**validation, 'artifact_type': 'DEBUG_PREVIEW'},
                'publication': {'publish_allowed': False, 'status': 'NOT_READY'}}
    return doc, contract


def render_command(args):
    report_path = args.report.resolve()
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes.decode('utf-8-sig'))
    evidence = json.loads(args.events.read_text(encoding='utf-8-sig')) if args.events else None
    spec = json.loads(args.spec.read_text(encoding='utf-8-sig')) if args.spec else None
    view = build_projection(report, args.reference, event_evidence=evidence, spec=spec)
    if not args.draft:
        fail('APPROVED_FORMAL_GENERATION_BLOCKED', view['formal_preflight'])
    out = args.output.resolve()
    # This producer has no authority to write canonical/publication assets.
    protected = ('reports', 'data', 'images', 'publication-receipts', 'publication-attempts', '.git', '.github')
    if out == ROOT or any(out == ROOT / p or (ROOT / p) in out.parents for p in protected):
        fail('APPROVED_PROTECTED_OUTPUT')
    if out.exists():
        fail('APPROVED_OUTPUT_ALREADY_EXISTS')
    try:
        relative = args.source_path or report_path.relative_to(ROOT).as_posix()
        if relative != f'reports/{report["date"]}_{report["time"].replace(":","-")}.json':
            fail('APPROVED_CANONICAL_SOURCE_PATH_MISMATCH')
        original = subprocess.run(['git', 'show', f'{args.source_ref}:{relative}'], cwd=ROOT,
                                  capture_output=True, check=True).stdout
        commit = subprocess.run(['git', 'rev-parse', args.source_ref], cwd=ROOT, capture_output=True, check=True).stdout.decode().strip()
        git_source = {'status': 'PASS', 'commit': commit, 'path': relative,
                      'url': f'https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/blob/{commit}/{relative}'}
    except (ValueError, subprocess.CalledProcessError) as exc:
        fail('APPROVED_GIT_SOURCE_NOT_VERIFIABLE', str(exc))
    if original.replace(b'\r\n', b'\n') != report_bytes.replace(b'\r\n', b'\n'):
        fail('APPROVED_GIT_SOURCE_MISMATCH')
    git_source.update({'git_blob_sha256': sha(original), 'comparison': 'EXACT_EXCEPT_JSON_CONTAINER_CRLF_LF'})
    current = subprocess.run(['git','show',f'HEAD:{relative}'],cwd=ROOT,capture_output=True)
    state = ('HISTORICAL_SOURCE_WITHDRAWN' if current.returncode else
             'CURRENT_GIT_SOURCE' if current.stdout.replace(b'\r\n',b'\n') == original.replace(b'\r\n',b'\n') else
             'HISTORICAL_SOURCE_CHANGED')
    view['source_current_state'] = state
    git_source['current_state'] = state
    if state != 'CURRENT_GIT_SOURCE':
        view['formal_preflight']['reasons'].append(state)
        view['formal_preflight']['status'] = 'BLOCKED'
    doc, contract = render_html(report, view, args.reference)
    out.mkdir(parents=True)
    def write(name, value):
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'report.html').write_text(doc, encoding='utf-8', newline='\n')
    (out / 'source-report.json').write_bytes(report_bytes)
    write('source-lock.json', {'git_source': git_source, 'source_file_sha256': sha(report_bytes),
                              'observed_body_sha256': view['source_observed_sha256'],
                              'claimed_bodyHash': report.get('bodyHash'), 'original_identity':
                              {k: report.get(k) for k in ('report_id','revision','snapshot_id','bodyHash')},
                              'scope': 'LOCAL_OBSERVATION_NOT_A_MANUFACTURED_SOURCE_IDENTITY'})
    write('panel-manifest.json', view)
    write('numeric-registry.json', view['numeric_registry'])
    write('events.json', view['events'])
    write('preflight.json', view['formal_preflight'])
    write('render-contract.json', contract)
    cmd = [args.node, str(ROOT / 'scripts/render_morning_png.js'), '--html', str(out / 'report.html'),
           '--contract', str(out / 'render-contract.json'), '--out', str(out / 'png')]
    if args.browser:
        cmd += ['--browser', args.browser]
    rendered = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    if rendered.returncode:
        write('render-failure.json', {'status': 'FAIL', 'reason': 'APPROVED_RENDERER_FAILED',
                                     'stderr': rendered.stderr, 'publish_allowed': False})
        fail('APPROVED_RENDERER_FAILED', rendered.stderr)
    return {'status': 'DRAFT', 'preview_status': 'PASS', 'artifact_type': 'DEBUG_PREVIEW',
            'source': git_source, 'formal_preflight': view['formal_preflight'],
            'output': str(out), 'publish_allowed': False, 'publication_manifest': 'NOT_CREATED'}
