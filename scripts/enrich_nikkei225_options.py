#!/usr/bin/env python3
"""Add verified Nikkei 225 option Put/Call turnover from JPX daily summary."""
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
    # Current official header: product type, product name, Japanese name,
    # underlying code, underlying name, volume, value, put volume, put value,
    # call volume, call value, date. Product code NK225E is the stable
    # identifier for Nikkei 225 Options in JPX's official user guide.
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
    raise ValueError('NK225E row not found in current trade summary')

def main():
    d=json.loads(OUT.read_text(encoding='utf-8')); prev=d.get('options') or {}
    base={'sourceName':'JPX 日経225オプション / 当日取引総括','sourceUrl':u.URLS['futures'],'comment':'Put/CallはJPXの日経225オプション（NK225E）の当日出来高比。IVとは別指標として扱います。'}
    # Preserve verified/calculated SQ information from the base updater.
    out={**prev,**base}
    try:
        url=latest_summary_url()
        if not url: raise ValueError('trade_summary_per_underlying.csv not found')
        x=parse_summary(url); out.update(x); out['summarySourceFileUrl']=url; out['status']='verified'; out['fetchedAt']=u.now()
        # IV is intentionally independent. Do not mark it as verified because
        # Put/Call was verified.
        if u.n(out.get('iv')) is None:
            out['ivStatus']='unavailable'; out['ivReason']='IVはJPX理論価格ファイルの専用パーサー実装まで取得不能'
        out.pop('error',None)
    except Exception as exc:
        out['status']='calculated' if out.get('nextSqDate') else 'unavailable'; out['error']=f'Put/Call取得失敗: {type(exc).__name__}: {exc}'; out['fetchedAt']=u.now()
    d['options']=out
    assess=u.assessment(d.get('futures') or {},d.get('arbitrage') or {},d.get('options') or {},d.get('foreignInvestors') or {})
    ratio=u.n(out.get('putCallRatio'))
    if ratio is not None:
        assess['options']='Put優勢・ヘッジ警戒' if ratio>=1.2 else 'Call優勢' if ratio<=0.8 else '中立'
        assess['reason']=f"短期先物={assess.get('shortTerm')}、裁定={assess.get('arbitrage')}、オプション={assess.get('options')}（出来高P/C={ratio:.2f}）、海外投資家={assess.get('foreign')}。各データの鮮度を分離して判定。"
    d['assessment']=assess
    keys=('spot','futures','sessions','arbitrage','options','participantFlow','foreignInvestors','participantOpenInterest','shortSelling','margin')
    statuses={k:(d.get(k) or {}).get('status','unavailable') for k in keys}
    d['sourceStatus']=f"{sum(v in {'verified','calculated'} for v in statuses.values())}/10主要セクション稼働（各内部指標の欠損は個別表示）"
    d.setdefault('diagnostics',{})['statuses']=statuses; d['diagnostics']['optionParser']='JPX trade_summary_per_underlying.csv NK225E Put/Call volume'; d['generatedAt']=u.now()
    OUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(d['options'],ensure_ascii=False))
if __name__=='__main__': main()
