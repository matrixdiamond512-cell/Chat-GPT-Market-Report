"""Build a conspicuously unverified, review-only preview from saved 08:00 text.

This path intentionally does not create a report view, snapshot, or publication
manifest. It is solely for design review when the source report is unverified.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf-8-sig'))
    if report.get('time') != '08:00' or report.get('report_status') != 'RECONSTRUCTED_UNVERIFIED':
        raise SystemExit('Review builder accepts only the explicitly unverified saved 08:00 report')
    if report.get('snapshot') or report.get('snapshot_id') or report.get('snapshotId'):
        raise SystemExit('Review builder refuses report data that carries a snapshot identity')
    body = report.get('fullText', '')
    if not body or '2026/10/12' not in body:
        raise SystemExit('Expected saved 2026/10/12 fullText is missing')
    sections = {}
    current = 'header'
    for line in body.splitlines():
        match = re.match(r'^(\d{1,2})．(.+)$', line)
        if match:
            current = match.group(1)
            sections.setdefault(current, {'title': match.group(2), 'lines': []})
        elif current != 'header' and line.strip():
            sections[current]['lines'].append(line)
    if set(sections) != {str(n) for n in range(1, 19)}:
        raise SystemExit('Saved body does not contain all 18 expected numbered sections')

    cards = [
        ('総合判断', [('judgment', [next(line for line in body.splitlines() if line.startswith('総合判断：'))[5:]])]),
        ('今日の焦点', [('focus', sections['5']['lines'])]),
        ('相場テーマ', [('theme', sections['1']['lines'])]),
        ('重要3条件', [('risk', sections['15']['lines'])]),
        ('NY市場の時系列', [('timeline', sections['4']['lines'])]),
        ('NY主要指数・前営業日終値', [('index', sections['3']['lines'][:1])]),
        ('主要市場データ（時点を区別）', [('market-data', sections['3']['lines'][1:])]),
        ('金利・ボラティリティ・日本株評価', [('rates', sections['7']['lines'] + sections['8']['lines'])]),
        ('クロスアセット資金フロー', [('flow', sections['9']['lines'])]),
        ('ニュース・材料と波及', [('causal', sections['6']['lines'] + sections['11']['lines'])]),
        ('需給・ポジション、SQ/MSQ', [('position', sections['10']['lines'])]),
        ('シナリオ', [('scenario', sections['13']['lines'] + sections['14']['lines'])]),
        ('6市場の短期見通し', [('markets', sections['12']['lines'])]),
        ('次の時間帯への引き継ぎ', [('handoff', sections['16']['lines'])]),
        ('結論・リスク管理', [('conclusion', sections['17']['lines'])]),
        ('データ取得・クロスチェック', [('validation', sections['2']['lines'] + sections['18']['lines'])]),
    ]
    fact_text = {}
    serial = 1

    def fact(value, cls=''):
        nonlocal serial
        fid = f'u{serial:03d}'
        serial += 1
        fact_text[fid] = value
        return f'<span class="fact {cls}" data-fact-id="{fid}">{html.escape(value)}</span>'

    def content(card_no, group, lines):
        if card_no == 1:
            return '<div class="judgment"><b>↗</b>'+''.join('<p>'+fact(line)+'</p>' for line in lines)+'</div>'
        if card_no == 2:
            items = []
            for line in lines:
                pieces = [piece for piece in re.findall(r'[^。]+。?', line) if piece]
                items.extend('<li>'+fact(piece)+'</li>' for piece in pieces)
            return '<ol class="focus-list">'+''.join(items)+'</ol>'
        if card_no == 13:
            source = ' '.join(lines)
            entries = [part.strip() for part in re.findall(r'[^。]+。?', source) if part.strip()]
            if len(entries) != 6:
                raise SystemExit(f'Expected six market outlook items, found {len(entries)}')
            tiles = []
            for item in entries:
                cls = 'up' if ('強気' in item or 'ドル高' in item) else 'flat'
                arrow = '↑' if cls == 'up' else '↔'
                label = item.partition('：')[0]
                tiles.append('<article class="market"><h3>'+html.escape(label)+'</h3><p class="direction '+cls+'"><b>'+arrow+'</b>'+fact(item)+'</p></article>')
            return '<div class="market-grid">'+''.join(tiles)+'</div>'
        if card_no == 5:
            parts = []
            for line in lines:
                for segment in re.split(r'(?<=[。])', line):
                    if segment.strip():
                        label, sep, value = segment.partition('：')
                        if sep:
                            parts.append('<div class="timeline-row"><b>'+html.escape(label)+'</b>'+fact(value.strip())+'</div>')
                        else:
                            parts.append('<div class="timeline-row">'+fact(segment)+'</div>')
            return '<div class="timeline">'+''.join(parts)+'</div>'
        if card_no in (6, 7):
            if card_no == 6:
                index_items = []
                for line in lines:
                    parts = re.split(r'(?<=）)、', line.rstrip('。'))
                    for part in parts:
                        if part.strip():
                            cls = 'up' if '+' in part else 'down' if '-' in part else 'flat'
                            index_items.append('<div class="index-row"><b>🇺🇸</b><span class="'+cls+'">'+fact(part, 'data-line')+'</span></div>')
                return '<div class="index-table">'+''.join(index_items)+'</div>'
            return '<div class="data-list">'+''.join('<div class="data-row">'+fact(line, 'data-line')+'</div>' for line in lines if line.strip())+'</div>'
        if card_no == 8:
            rows = []
            for line in lines:
                parts = [part.strip() for part in line.split('、') if part.strip()]
                rows.extend('<div class="metric-row">'+fact(part + ('、' if i < len(parts)-1 else ''), 'data-line')+'</div>' for i, part in enumerate(parts))
            return '<div class="metric-table">'+''.join(rows)+'</div>'
        if card_no == 9:
            return '<div class="flow-review"><div class="inflow"><h3>市場で観測された動き</h3>'+''.join('<p>'+fact(line)+'</p>' for line in lines)+'</div><div class="transfer">⇄<b>資金フローの確定データなし</b></div></div>'
        if card_no == 10:
            return ''.join('<div class="causal-sentence"><b>→</b>'+fact(line)+'</div>' for line in lines)
        if card_no == 4:
            return '<div class="warning-list">'+''.join('<p><b>!</b>'+fact(line)+'</p>' for line in lines)+'</div>'
        return ''.join('<p>'+fact(line)+'</p>' for line in lines if line.strip())

    rendered = []
    for number, (title, groups) in enumerate(cards, 1):
        body_html = ''.join(content(number, kind, lines) for kind, lines in groups)
        rendered.append(f'<section class="card card-{number:02d}" data-card="{number:02d}"><h2><b>{number:02d}</b> {html.escape(title)}</h2><div class="card-body">{body_html}</div></section>')
    doc = f'''<!doctype html><html lang="ja"><meta charset="utf-8"><style>
{(Path(__file__).resolve().parents[1] / 'templates/infographic/0800/theme.css').read_text(encoding='utf-8')}
.review-banner{{margin:6px;padding:6px 10px;border:3px solid #9d122c;border-radius:6px;background:#fff2c7;color:#76132a;font-size:20px;font-weight:950;text-align:center}}
.review-banner small{{display:block;font-size:15px;font-weight:800}}
.card-body{{font-size:16px;line-height:1.18}} .card-body p{{margin:5px 0}}
.data-list{{display:grid;gap:3px}} .data-row{{padding:4px;border:1px solid #b7d8f2;background:#f3faff;border-radius:4px}}
.timeline{{display:grid;grid-template-rows:repeat(5,minmax(0,1fr));gap:4px;height:100%}} .timeline-row{{display:grid;grid-template-columns:75px 1fr;gap:5px;align-items:center;padding:4px;background:#f0f8ff;border-radius:4px}}
.timeline-row b{{padding:5px;background:#0757bc;color:#fff;border-radius:3px;text-align:center}}
.flow-review{{display:grid;grid-template-columns:1fr 65px;align-items:center;gap:5px}} .flow-review .inflow{{padding:6px;border-color:#087abd;background:#f0f8ff}}
.flow-review .transfer{{font-size:35px}} .flow-review .transfer b{{font-size:11px}}
.warning-list p{{display:flex;gap:6px;align-items:center;padding:5px;background:#fff0f2;border:1px solid #ed8697;border-radius:4px;font-weight:850}}
.warning-list p>b{{display:grid;place-items:center;flex:0 0 28px;height:28px;border-radius:50%;background:#d80c37;color:#fff;font-size:22px}}
.judgment{{display:grid;grid-template-columns:53px 1fr;gap:4px;align-items:center;font-size:19px;font-weight:900;line-height:1.14}}
.judgment>b{{color:#ed174b;font-size:58px;line-height:.9;text-align:center;text-shadow:1px 2px #f9bfd0}}
.focus-list{{display:grid;gap:4px;list-style:none;counter-reset:focus;padding:0;margin:0}}
.focus-list li{{counter-increment:focus;display:grid;grid-template-columns:28px 1fr;gap:4px;align-items:start;padding:3px 0;font-weight:800}}
.focus-list li:before{{content:counter(focus);display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:linear-gradient(145deg,#08b9f4,#0757bc);color:#fff;font-size:17px;font-weight:950}}
.index-table{{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:repeat(2,minmax(0,1fr));gap:3px;height:100%}}
.index-row{{display:grid;grid-template-columns:27px 1fr;align-items:center;min-height:42px;padding:3px;border:1px solid #9dcaf1;background:linear-gradient(90deg,#e6f7ff,#fff);border-radius:4px;font-weight:850;font-size:15px;line-height:1.08}}
.index-row>b{{font-size:20px}} .metric-table{{display:grid;gap:3px}}
.metric-row{{padding:4px 5px;border-left:4px solid #099d9c;background:#effbfa;font-weight:760;line-height:1.13}}
.card-07 .data-list{{height:100%;grid-template-rows:repeat(5,minmax(0,1fr))}}
.card-14 .card-body:before{{content:'◷';float:left;display:grid;place-items:center;width:50px;height:54px;margin:0 8px 3px 0;color:#0875cf;font-size:52px;font-weight:950;line-height:1}}
.card-15 .card-body:before{{display:grid}}
.card-16 .card-body:before{{content:'💡';float:left;display:grid;place-items:center;width:43px;height:46px;margin:0 7px 3px 0;font-size:35px}}
.card-12 .card-body p{{padding:7px 5px;margin:4px 0;border-bottom:1px solid #e7aeb8;font-weight:780}}
.market-grid{{grid-template-columns:repeat(6,minmax(0,1fr))}} .market{{min-height:100px}} .market h3{{font-size:16px}}
.market .direction{{align-items:flex-start;font-size:16px;line-height:1.12}} .market .direction b{{font-size:38px;flex:none}}
.market .fact{{overflow-wrap:anywhere}} .card-13{{grid-column:1 / span 9;grid-row:4}}
.card-14{{grid-column:10 / span 3;grid-row:4}} .card-15{{grid-column:1 / span 6;grid-row:5}} .card-16{{grid-column:7 / span 6;grid-row:5}}
.card-15 .card-body:before{{display:none}}
.card{{display:flex;flex-direction:column}} .card-body{{flex:1}}
.card-05{{grid-column:1 / span 4;grid-row:2}} .card-06{{grid-column:5 / span 4;grid-row:2}} .card-07{{grid-column:9 / span 4;grid-row:2}}
.card-08{{grid-column:1 / span 3;grid-row:3}} .card-09{{grid-column:4 / span 3;grid-row:3}} .card-10{{grid-column:7 / span 3;grid-row:3}} .card-11{{grid-column:10 / span 3;grid-row:3}}
.card-12{{grid-column:1 / span 3;grid-row:4}} .card-13{{grid-column:4 / span 9;grid-row:4}}
.card-14{{grid-column:1 / span 4;grid-row:5}} .card-15{{grid-column:5 / span 4;grid-row:5}} .card-16{{grid-column:9 / span 4;grid-row:5}}
.causal-sentence{{display:grid;grid-template-columns:27px 1fr;gap:4px;align-items:start;padding:6px 4px;margin:4px 0;border-bottom:1px solid #b9d9f2;font-weight:750;line-height:1.18}}
.causal-sentence>b{{display:grid;place-items:center;border-radius:50%;background:#ed4c08;color:#fff;width:25px;height:25px;font-size:18px}}
.card-01{{grid-column:1 / span 3;grid-row:1}} .card-02{{grid-column:4 / span 3;grid-row:1}} .card-03{{grid-column:7 / span 3;grid-row:1}} .card-04{{grid-column:10 / span 3;grid-row:1}}
.card-05{{grid-column:1 / span 4;grid-row:2}} .card-06{{grid-column:5 / span 4;grid-row:2}} .card-07{{grid-column:9 / span 4;grid-row:2}}
.card-08{{grid-column:1 / span 3;grid-row:3}} .card-09{{grid-column:4 / span 3;grid-row:3}} .card-10{{grid-column:7 / span 3;grid-row:3}} .card-11{{grid-column:10 / span 3;grid-row:3}} .card-12{{grid-column:1 / span 3;grid-row:4}}
header:before{{opacity:.04}} .brand-aside{{display:none}} .draft{{background:#ffd52a}}
.cards{{align-items:start}}
.card{{display:block}} .card-body{{flex:initial}}
.card-05{{grid-column:1 / span 6;grid-row:2}} .card-06{{grid-column:7 / span 6;grid-row:2}}
.card-07{{grid-column:1 / span 6;grid-row:3}} .card-08{{grid-column:7 / span 6;grid-row:3}}
.card-09{{grid-column:1 / span 3;grid-row:4}} .card-10{{grid-column:4 / span 3;grid-row:4}} .card-11{{grid-column:7 / span 3;grid-row:4}} .card-12{{grid-column:10 / span 3;grid-row:4}}
.card-13{{grid-column:1 / span 12;grid-row:5}}
.card-14{{grid-column:1 / span 4;grid-row:6}} .card-15{{grid-column:5 / span 4;grid-row:6}} .card-16{{grid-column:9 / span 4;grid-row:6}}
.card-14 .card-body:before{{width:36px;height:34px;margin-right:5px;font-size:32px}}
.card-14 .card-body:before,.card-15 .card-body:before,.card-16 .card-body:before{{display:none}}
.card-14 h2:after{{content:'◷';margin-left:auto;color:#e5f4ff;font-size:22px}}
.card-15 h2:after{{content:'⚠';margin-left:auto;color:#fff;font-size:20px}}
.card-16 h2:after{{content:'💡';margin-left:auto;font-size:19px}}
.card-16 .card-body{{display:block}}
</style><body><main id="report"><header><div class="brandline"><span class="brand">マーケットレポート</span><span class="report-title">2026/10/12（月）08:00</span></div><div class="subtitle">米国株反発 × 高金利・原油高｜日本はスポーツの日・OSE先物は祝日取引</div><div class="draft">未検証・公開不可｜保存済み10/12本文によるデザイン確認用</div><div class="basis">正式snapshot未照合</div></header><div class="review-banner">未検証の保存本文を使用したデザインレビュー用プレビュー<small>数値・記述は正式確認前です。公開・投資判断には使用できません。snapshot未取得のため正式生成ではありません。</small></div><div class="cards">{''.join(rendered)}</div><footer>出典欄・照合状況：保存済み本文より描画｜本文再構成・照合未了｜正式レポートおよび公開manifestを生成しないレビュー資料</footer></main></body></html>'''
    out = args.output
    if out.exists():
        raise SystemExit(f'Output already exists: {out}')
    out.mkdir(parents=True)
    (out / 'report.html').write_text(doc, encoding='utf-8', newline='\n')
    contract = {'html_sha256': hashlib.sha256(doc.encode()).hexdigest(), 'view_sha256': 'UNVERIFIED_REVIEW_ONLY',
                'expected_text': fact_text, 'validation': {'status': 'PASS', 'artifact_type': 'UNVERIFIED_CONTENT_REVIEW'}}
    (out / 'render-contract.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (out / 'README.md').write_text('# 未検証・公開不可の08:00デザインレビュー\n\n保存済み10/12 `fullText` をカードへ再配置した目視レビュー用です。入力本文は `RECONSTRUCTED_UNVERIFIED` で、snapshot照合はありません。正式レポート、公開用manifest、公開ステータスは生成しません。\n', encoding='utf-8')
    print(json.dumps({'status':'REVIEW_PREVIEW_ONLY','cards':16,'facts':len(fact_text),'unverified':True,'publication_manifest':'NOT_CREATED'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
