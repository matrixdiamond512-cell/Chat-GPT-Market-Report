#!/usr/bin/env python3
"""Add verified Nikkei 225 option Put/Call turnover when JPX exposes it."""
from __future__ import annotations
import csv,json,re
from datetime import datetime
from pathlib import Path
import update_nikkei225_supply_demand as u
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/nikkei225-supply-demand.json'

def latest_summary_url():
    xs=[url for url,_ in u.links(u.URLS['futures']) if re.search(r'trade_summary_per_underlying\.csv(?:\?|$)',url,re.I)]
    return xs[0] if xs else None

def parse_summary(url:str):
    rows=list(csv.reader(u.decode(u.get(url).content).splitlines()))
    if not rows: raise ValueError('empty trade summary')
    for r in rows[1:]:
        if len(r)<12: continue
        code=u.txt(r[3]).upper()
        pname=' '.join(u.txt(x) for x in r[:5])
        if code!='NK225E' and not re.search(r'Nikkei\s*225\s*Options|日経\s*225\s*オプション',pname,re.I):
            continue
        put=u.n(r[7]); call=u.n(r[9]); total=u.n(r[5]); ds=u.txt(r[11])
        if put is None or call is None: continue
        asof=None
        try: asof=datetime.strptime(ds,'%Y%m%d').date().isoformat()
        except: pass
        return {'putVolume':int(round(put)),'callVolume':int(round(call)),'totalVolume':int(round(total)) if total is not None else None,'putCallRatio':put/call if call not in (None,0) else None,'asOfDate':asof,'productCode':code or 'NK225E'}
    return None

def main():
    d=json.loads(OUT.read_text(encoding='utf-8')); prev=d.get('options') or {}
    base={'sourceName':'JPX 日経225オプション','sourceUrl':'https://www.jpx.co.jp/markets/derivatives/option-price/','comment':'SQ日程、Put/Call、IVは別々に鮮度管理します。取得できない指標は推測しません。'}
    out={**prev,**base}
    try:
        url=latest_summary_url()
        if not url: raise ValueError('JPX当日取引総括CSVが見つかりません')
        x=parse_summary(url)
        if x:
            out.update(x); out['summarySourceFileUrl']=url; out['putCallStatus']='verified'
        else:
            out['putVolume']=None; out['callVolume']=None; out['putCallRatio']=None
            out['putCallStatus']='unavailable'
            out['putCallReason']='現在のJPX当日取引総括CSVには日経225指数オプション（NK225E）の行がないため取得不能'
        if u.n(out.get('iv')) is None:
            out['iv']=None; out['ivChange']=None; out['ivStatus']='unavailable'
            out['ivReason']='JPX理論価格等情報の専用取得処理を実装するまで取得不能'
        out['status']='verified' if out.get('putCallStatus')=='verified' else ('calculated' if out.get('nextSqDate') else 'unavailable')
        out.pop('error',None); out['fetchedAt']=u.now()
    except Exception as exc:
        out['putVolume']=None; out['callVolume']=None; out['putCallRatio']=None
        out['putCallStatus']='unavailable'; out['putCallReason']=f'取得不能（{type(exc).__name__}: {exc}）'
        out['ivStatus']='unavailable'; out['ivReason']='取得不能（理論価格等情報の専用取得処理待ち）'
        out['status']='calculated' if out.get('nextSqDate') else 'unavailable'; out['fetchedAt']=u.now()
    d['options']=out
    assess=u.assessment(d.get('futures') or {},d.get('arbitrage') or {},d.get('options') or {},d.get('foreignInvestors') or {})
    ratio=u.n(out.get('putCallRatio'))
    if ratio is not None:
        assess['options']='Put優勢・ヘッジ警戒' if ratio>=1.2 else 'Call優勢' if ratio<=0.8 else '中立'
        assess['reason']=f"短期先物={assess.get('shortTerm')}、裁定={assess.get('arbitrage')}、オプション={assess.get('options')}（出来高P/C={ratio:.2f}）、海外投資家={assess.get('foreign')}。各データの鮮度を分離して判定。"
    else:
        assess['options']='SQ日程のみ確認済み'
    d['assessment']=assess
    keys=('spot','futures','sessions','arbitrage','options','participantFlow','foreignInvestors','participantOpenInterest','shortSelling','margin')
    statuses={k:(d.get(k) or {}).get('status','unavailable') for k in keys}
    verified=sum(v=='verified' for v in statuses.values()); calculated=sum(v=='calculated' for v in statuses.values())
    d['sourceStatus']=f'{verified}確認済み + {calculated}計算済み / 10主要セクション（内部欠損は個別表示）'
    d.setdefault('diagnostics',{})['statuses']=statuses
    d['diagnostics']['optionParser']='JPX daily summary probe for NK225E; no fabrication when index-option row is absent'
    d['generatedAt']=u.now()
    OUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'options':d['options'],'sourceStatus':d['sourceStatus']},ensure_ascii=False))
if __name__=='__main__': main()
