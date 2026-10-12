"""Explicitly fictional inputs; never inferred from the user's reference images."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from reporting.context import ReportContext
from reporting.snapshot import Market, MarketDataSnapshot
from reporting.infographic import SourceLock, REQUIRED_SECTIONS, build_spec
from reporting.morning_layout import MARKETS, SNAPSHOT_NAMES


def fixture():
    context = ReportContext.create('2026-10-06', '08:00', '2026-10-06T07:55:00+09:00', mode='historical')
    catalog = json.loads((ROOT/'config/market_data_sources.json').read_text(encoding='utf-8'))['symbols']
    policy = json.loads((ROOT/'config/market_data_validation.json').read_text(encoding='utf-8'))['symbols']
    prices = dict(zip(SNAPSHOT_NAMES, (4444.44, 88.88, 65432, 144.44, 1.2345, 88888.88)))
    changes = dict(zip(SNAPSHOT_NAMES, (12.34, -1.23, 0, .12, -.0012, 123.45)))
    pct = dict(zip(SNAPSHOT_NAMES, (.28, -1.36, 0, .08, -.10, .14)))
    markets = []
    for name, definition in catalog.items():
        if not definition.get('required'):
            continue
        bounds = policy.get(name, {})
        value = prices.get(name, (bounds.get('min', 1)+bounds.get('max', 100))/2)
        change = changes.get(name)
        source = definition['sources'][0]
        markets.append(Market(instrument=name, marketType=definition['marketType'], venue=None,
            contractMonth=None, priceValue=value, priceUnit=definition['unit'],
            changeValue=change, changePct=pct.get(name), direction='UNKNOWN' if change is None else 'UP' if change > 0 else 'DOWN' if change < 0 else 'FLAT',
            comparisonBasis='previous_close' if change is not None else '', asOf='2026-10-06T07:54:00+09:00',
            source=({'id':source['id'], 'url':source['url']},), status='VALID', unavailableReason=None,
            displayText=str(value)))
    snapshot = MarketDataSnapshot.capture(context, markets, '2026-10-06T07:55:30+09:00')
    source_sections = {heading: [] for heading in REQUIRED_SECTIONS}
    facts = []
    def add(heading, text, binding=None):
        ref = {'ref': f'f{len(facts)+1:03}'}
        fact = {'id':ref['ref'], 'text':text, 'source_section':heading}
        if binding:
            fact['snapshot_field'] = binding
        facts.append(fact); source_sections[heading].append(fact)
        return ref
    def s(heading, text):
        return add(heading, text)
    def number(heading, instrument, field, text):
        return add(heading, text, {'instrument':instrument, 'field':field})
    subtitle = s('今日の相場テーマ', '合成シナリオ：株式の反発と原油・金利の綱引きを検証する')
    cards = [{'number':i} for i in range(1,17)]
    cards[0].update(headline=s('総合判断', '株式は反発、警戒は継続'), paragraphs=[s('総合判断', 'これは描画試験用の架空データです。実市場の判断には使用できません。')])
    cards[0]['direction']=s('総合判断', '中立〜やや強気')
    cards[1]['items'] = [s('今日の主導市場', t) for t in ('先物の基準値と出来高', '原油とインフレ期待', '金利・為替の同時方向', '株式・暗号資産の強弱差')]
    cards[2]['paragraphs'] = [s('今日の相場テーマ', 'リスク回復とインフレ警戒が併存。値動きだけで資金移動を断定しない。'),s('材料と値動きの整合性', '材料と価格反応を区別し、原油から株式への影響を想定経路として監視する。')]
    cards[3]['items'] = [s('シナリオが崩れる条件', t) for t in ('WTI 95.55ドル超を警戒', '米長期金利の再上昇を警戒', 'OSE 62,222円割れを警戒')]
    cards[4]['timeline'] = [{'phase':p,'text':s('前回からの変化',t)} for p,t in zip(('開始前','開場','中盤','終盤','東京への引き継ぎ'),('供給改善観測で原油が軟化','株式に押し目買いが入る','銘柄ごとの材料で選別が進む','金利の上昇圧力を確認','先物と為替、出来高を照合する'))]
    cards[5]['table'] = {'columns':['指数','終値','前日比','騰落率'], 'change_columns':[2,3], 'rows':[[s('前回からの変化',v) for v in row] for row in [('NYダウ','50,123.45','+123.45','+0.25%'),('S&P500','7,234.56','-12.34','-0.17%'),('Nasdaq','25,345.67','±0.00','0.00%'),('Russell2000','2,345.67','+12.34','+0.53%'),('VIX','18.76','-0.54','-2.80%')]]}
    by_market = {m.instrument:m for m in markets}
    price_refs, time_refs = {}, {}
    rows = []
    for symbol, name in zip(MARKETS, SNAPSHOT_NAMES):
        m = by_market[name]
        price_refs[name] = number('主要6市場の見通し', name, 'priceValue', f'{m.priceValue:,.4f}' if name=='eurusd' else f'{m.priceValue:,.2f} {m.priceUnit}')
        time_refs[name] = number('主要6市場の見通し', name, 'asOf', m.asOf)
        rows.append([s('主要6市場の見通し',symbol),price_refs[name],number('主要6市場の見通し',name,'changePct',f'{m.changePct:+.2f}%'),time_refs[name]])
    cards[6]['table'] = {'columns':['市場','基準値','変化','基準日時'], 'change_columns':[2], 'rows':rows}
    cards[7]['table'] = {'columns':['指標','値・基準','時点'], 'change_columns':[], 'rows':[[s('金利',v) for v in row] for row in [('米長期金利','5.11%（架空値）','前営業日'),('日本長期金利','2.99%（架空値）','前営業日'),('日経VI','29.55（架空値）','前営業日'),('予想PER / EPS','18.22倍 / 3,591.22円','加重平均'),('PBR / 25日乖離','1.88倍 / +3.21%','前営業日'),('200日乖離 / 騰落レシオ','+12.34% / 92.55','前営業日')]]}
    cards[8]['flow'] = {'basis':'estimated', 'inflow':[s('クロスアセット資金フロー',t) for t in ('金：安全資産需要の候補','国債：選好回復の候補')], 'outflow':[s('クロスアセット資金フロー',t) for t in ('AI株：利益確定の候補','原油：リスク上乗せ縮小の候補')], 'evidence':s('クロスアセット資金フロー','市場反応からの推定。ETF確定フローは取得不能。実際の移動額は断定しない。')}
    cards[9]['chains'] = [{'basis':'hypothesis','nodes':[s('重要ニュース',t) for t in ('供給改善の観測','原油の下落圧力','インフレ期待と金利','株式・BTCの下支え')], 'evidence':s('重要ニュース','想定経路：報道と価格反応の因果は未確定。')}, {'basis':'hypothesis','nodes':[s('重要ニュース',t) for t in ('非常に長い合成ニュース見出し：供給網の改善観測と新たな地政学リスクが重なり市場ごとの反応が分かれた場合にも本文を省略せずすべて表示する試験','為替と長期金利を監視','株式の割引率に波及')], 'evidence':s('重要ニュース','想定経路：長文でもカードを縦に拡張する。')}]
    cards[9]['paragraphs'] = [s('今後のイベント','次回の経済統計・決算を確認。架空の時刻を実イベントとして公開しない。')]
    cards[10]['paragraphs'] = [s('需給・ポジション',t) for t in ('SQ通過後の先物と現物の強弱差を確認する。','最新建玉は取得不能。円ショート・金ロングの規模を推測しない。')]
    cards[11]['chains'] = [{'basis':'hypothesis','scenario':'main','nodes':[s('メインシナリオ',t) for t in ('原油が安定','金利が落ち着く','先物は基準値付近')], 'evidence':s('メインシナリオ','想定経路：確定予測ではない。')}, {'basis':'hypothesis','scenario':'upside','nodes':[s('代替シナリオ',t) for t in ('原油低下と株式高','金利の圧力が和らぐ','先物の強気条件を監視')], 'evidence':s('代替シナリオ','想定経路：上振れ条件を分けて監視する。')}, {'basis':'hypothesis','scenario':'downside','nodes':[s('代替シナリオ',t) for t in ('原油高と金利高','株式の重石','先物の弱気条件を監視')], 'evidence':s('代替シナリオ','想定経路：下振れ条件を分けて監視する。')}]
    cards[12]['paragraphs'] = [s('主要6市場の見通し','Gold WTI Nikkei 225 Futures (OSE) USD/JPY EUR/USD BTCUSD')]
    directions = ('中立〜やや強気','中立〜やや弱気','中立','中立〜ややドル高','中立〜やや弱気','中立〜やや強気')
    bulls = ('4,555ドル回復','92.22ドル超','66,666円回復','145.55円超','1.2555回復','90,000ドル定着')
    bears = ('4,333ドル割れ','85.55ドル割れ','62,222円割れ','142.22円割れ','1.2111割れ','86,000ドル割れ')
    cards[12]['markets'] = [{'symbol':symbol,'price':price_refs[name], 'asof':time_refs[name],
        'direction':s('主要6市場の見通し',direction), 'rationale':s('主要6市場の見通し',reason),
        'bull':s('主要6市場の見通し',bull),'bear':s('主要6市場の見通し',bear)}
        for symbol,name,direction,reason,bull,bear in zip(MARKETS,SNAPSHOT_NAMES,directions,
            ('金利と安全資産需要の綱引き','供給観測と地政学リスク','現物と先物の時点を区別','金利差とリスク選好','欧州材料とドルの方向','流動性とリスク選好'),bulls,bears)]
    cards[13]['paragraphs'] = [s('次時間帯への引き継ぎ',t) for t in ('東京時間は先物の出来高・板・スプレッドを確認。','時点の異なる価格を同時刻の値として混同しない。')]
    cards[14]['paragraphs'] = [s('シナリオが崩れる条件',t) for t in ('原油高・金利高・株式下落が重なれば仮説を見直す。','供給観測が確認されても全面的リスクオンとは断定しない。')]
    cards[15].update(conclusion=s('結論','回復と警戒が併存。数値と時刻を保ち、未取得情報を明示する。'),validation=[s('クロスチェック結果',t) for t in ('検証済み：合成fixtureの本文・snapshot・出典参照','取得不能：COMEX清算値・ETFフロー・最新建玉','公開不可：DRAFT / DEBUG_PREVIEW。実市場データではない。')])
    title = 'マーケットレポート｜2026/10/06 08:00'
    body = title+'\n'
    for heading, entries in source_sections.items():
        body += heading+'\n'
        for fact in entries:
            fact['start']=len(body); body += fact['text']; fact['end']=len(body); body += '\n'
    report = {'date':'2026-10-06','time':'08:00','title':title,'revision':1,'synthetic_fixture':True,
              'report_id':context.report_id,'snapshot_id':snapshot.snapshot_id,
              'fullText':body,'context':context.to_dict(),'snapshot':snapshot.to_dict()}
    lock = SourceLock.create(report)
    report['bodyHash'] = lock.sha256
    view = {'report_id':context.report_id,'time':'08:00','revision':1,'snapshot_id':snapshot.snapshot_id,
            'body_hash':lock.sha256,'synthetic_fixture':True,'header':{'subtitle':subtitle},'facts':facts,'cards':cards}
    return report, view


def formal_contract_fixture():
    """Mock-only formal contract compatibility; not a verified real report.

    Uses only snapshot prices as visible numbers because the legacy spec gate
    does not yet type arbitrary scenario thresholds. Never export as a real sample.
    """
    import re
    report, view = fixture()
    report['synthetic_fixture'] = False
    view['synthetic_fixture'] = False
    for fact in view['facts']:
        binding = fact.get('snapshot_field', {})
        if binding.get('field') in ('priceValue', 'asOf'):
            continue
        if binding:
            del fact['snapshot_field']
        fact['text'] = re.sub(r'[+±\-]?[\d,]+(?:\.\d+)?%?', '基準', fact['text'])
    snapshot = MarketDataSnapshot.capture(ReportContext(**report['context']),
        [Market(**{**m, 'changeValue':None, 'changePct':None, 'comparisonBasis':'', 'direction':'UNKNOWN'})
         for m in report['snapshot']['markets']], report['snapshot']['captured_at'])
    report['snapshot'] = snapshot.to_dict(); view['snapshot_id'] = snapshot.snapshot_id
    report['snapshot_id'] = snapshot.snapshot_id
    quote_line = 'Gold WTI Nikkei 225 Futures (OSE) USD/JPY EUR/USD BTCUSD: '+', '.join(str(m.priceValue) for m in snapshot.markets if m.instrument in SNAPSHOT_NAMES)
    fact = {'id':'formal-quote-provenance','text':quote_line,'source_section':'主要6市場の見通し'}
    view['facts'].append(fact); view['cards'][12]['paragraphs'].append({'ref':fact['id']})
    body = report['title']+'\n'
    for heading in REQUIRED_SECTIONS:
        body += heading+'\n'
        for fact in view['facts']:
            if fact['source_section'] == heading:
                fact['start']=len(body); body += fact['text']; fact['end']=len(body); body += '\n'
    report['fullText']=body; report['bodyHash']=SourceLock.create(report).sha256
    view['body_hash']=report['bodyHash']
    spec = build_spec(report)
    # Timestamps remain validated provenance metadata; visible projection uses
    # exact snapshot asOf and full-text offsets, never an invented timestamp.
    for panel in spec['panels']:
        panel['text'] = panel['text'].replace('2026-10-06T07:54:00+09:00', '')
    return report, view, spec


if __name__ == '__main__':
    target = Path(sys.argv[1]); target.mkdir(parents=True, exist_ok=True)
    report, view = fixture()
    for name, data in (('report.json',report),('view.json',view)):
        (target/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
