#!/usr/bin/env python3
"""Enrich Nikkei 225 supply-demand data with an independently verified spot close.

Primary practical source: Yahoo Finance chart JSON (^N225).  The value is only
used for basis calculations when its Tokyo calendar date matches the futures
as-of date. Existing verified data are preserved on fetch failure.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import update_nikkei225_supply_demand as u

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/nikkei225-supply-demand.json'
YAHOO='https://query1.finance.yahoo.com/v8/finance/chart/%5EN225?range=10d&interval=1d&includePrePost=false&events=div%2Csplits'
JST=timezone(timedelta(hours=9))


def fetch_spot():
    j=u.get(YAHOO).json()
    r=j['chart']['result'][0]
    ts=r.get('timestamp') or []
    q=(r.get('indicators') or {}).get('quote',[{}])[0]
    closes=q.get('close') or []
    rows=[]
    for t,c in zip(ts,closes):
        v=u.n(c)
        if v is None:
            continue
        d=datetime.fromtimestamp(int(t),tz=timezone.utc).astimezone(JST).date().isoformat()
        rows.append((d,v))
    if not rows:
        raise ValueError('Yahoo ^N225 daily close not found')
    d,v=rows[-1]
    return d,v


def main():
    d=json.loads(OUT.read_text(encoding='utf-8'))
    prev=d.get('spot') or {}
    base={
        'sourceName':'Yahoo Finance Nikkei 225 (^N225)',
        'sourceUrl':'https://finance.yahoo.com/quote/%5EN225/',
        'comment':'日経225現物の独立取得値。先物との単純ベーシスは基準日一致時のみ計算。'
    }
    try:
        asof,value=fetch_spot()
        d['spot']={**base,'value':value,'asOfDate':asof,'status':'verified','fetchedAt':u.now()}
    except Exception as exc:
        d['spot']=u.stale(prev,base,f'日経225現物取得失敗: {type(exc).__name__}: {exc}')
    d.setdefault('diagnostics',{})['spotParser']='Yahoo Finance chart JSON ^N225 daily close; basis requires same as-of date as OSE futures'
    d['generatedAt']=u.now()
    OUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(d['spot'],ensure_ascii=False))

if __name__=='__main__':
    main()
