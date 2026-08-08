#!/usr/bin/env python3
"""Parse JPX weekly foreign-investor cash and Nikkei 225 futures flows.

The dashboard needs both the latest matching week and a matched history. Cash and
Nikkei 225 futures are never combined across different weekly period ends. No
missing week is fabricated.
"""
from __future__ import annotations
import csv,io,json,re
from datetime import date,datetime
from pathlib import Path
from typing import Any
import update_nikkei225_supply_demand as u
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/nikkei225-supply-demand.json'
HISTORY_WEEKS=12

def cash_pdf(url:str)->dict[str,Any]|None:
    _,text=u.doc(url)
    hm=re.search(r'(20\d{2})年\d{1,2}月第\d+週.*?\(\s*\d{1,2}/\d{1,2}\s*[-〜～]\s*(\d{1,2})/(\d{1,2})\s*\)',text,re.S)
    if not hm:return None
    y,mo,dy=int(hm.group(1)),int(hm.group(2)),int(hm.group(3))
    sm=re.search(r'海外投資家\s+売り\s+Sales\s+([\d,]+)\s+[\d.]+(?:\s+[▲+-]?\s*[\d,]+)?\s+([\d,]+)\s+[\d.]+',text)
    pm=re.search(r'Foreigners\s+買い\s+Purchases\s+([\d,]+)\s+[\d.]+(?:\s+[▲+-]?\s*[\d,]+)?\s+([\d,]+)\s+[\d.]+',text)
    if not sm or not pm:return None
    current_sales=float(sm.group(2).replace(',','')); current_purchases=float(pm.group(2).replace(',',''))
    return {'cashNet':(current_purchases-current_sales)/100_000,'asOfDate':date(y,mo,dy).isoformat(),'cashSourceFileUrl':url}

def derivative_csv(url:str)->dict[str,Any]|None:
    text=u.decode(u.get(url).content); rows=list(csv.reader(io.StringIO(text)))
    if not rows:return None
    best=None
    for r in rows[1:]:
        if len(r)<12:continue
        if r[0].strip()=='301' and r[5].strip()=='60' and r[6].strip()=='2':
            sell=u.n(r[7]); buy=u.n(r[9])
            if sell is None or buy is None:continue
            try:asof=datetime.strptime(r[4].strip(),'%Y%m%d').date().isoformat()
            except:asof=None
            best={'nikkeiFuturesNet':(buy-sell)/100_000_000,'asOfDate':asof,'derivativesSourceFileUrl':url}
            break
    return best

def direction(cash:float|None,fut:float|None)->str:
    if cash is None or fut is None:return '判定待ち'
    if cash>0 and fut>0:return '現物・先物とも買い'
    if cash<0 and fut<0:return '現物・先物とも売り'
    if cash<0 and fut>0:return '現物売り・先物買い'
    if cash>0 and fut<0:return '現物買い・先物売り'
    return '方向混在'

def main():
    d=json.loads(OUT.read_text(encoding='utf-8')); prev=d.get('foreignInvestors') or {}; base={'sourceName':'JPX 投資部門別売買状況','sourceUrl':u.URLS['sector'],'cashNote':'東証プライム現物の海外投資家売買（金額ベース）','nikkeiNote':'日経225先物の海外投資家売買（金額ベース）','topixNote':'TOPIX先物は商品コード検証後に追加','comment':'週次の現物と日経225先物を同一期間で比較。日次の売買主体とは断定しません。'}
    try:
        cashlinks=[url for url,_ in u.links(u.URLS['cash']) if re.search(r'stock_val_1_\d+\.pdf(?:\?|$)',url,re.I)]
        cr=[]
        for url in cashlinks[:32]:
            try:
                x=cash_pdf(url)
                if x:cr.append(x)
            except Exception:pass
        cr.sort(key=lambda x:x['asOfDate'],reverse=True)

        sectorlinks=[url for url,_ in u.links(u.URLS['sector']) if re.search(r'Tousi_DV_W_20\d{6}_20\d{6}\.csv(?:\?|$)',url,re.I)]
        dr=[]
        for url in sectorlinks[:32]:
            try:
                x=derivative_csv(url)
                if x:dr.append(x)
            except Exception:pass
        dr.sort(key=lambda x:x.get('asOfDate') or '',reverse=True)
        if not cr or not dr:raise ValueError(f'cash={len(cr)} derivative={len(dr)}')

        by_cash={x['asOfDate']:x for x in cr if x.get('asOfDate')}
        by_deriv={x['asOfDate']:x for x in dr if x.get('asOfDate')}
        matched=sorted(set(by_cash)&set(by_deriv))
        if not matched:raise ValueError('cash and derivative weekly period ends do not match')
        matched=matched[-HISTORY_WEEKS:]
        series=[]
        for dt in matched:
            c,f=by_cash[dt],by_deriv[dt]
            series.append({
                'asOfDate':dt,
                'cashNet':c['cashNet'],
                'nikkeiFuturesNet':f['nikkeiFuturesNet'],
                'direction':direction(c['cashNet'],f['nikkeiFuturesNet']),
                'cashSourceFileUrl':c['cashSourceFileUrl'],
                'derivativesSourceFileUrl':f['derivativesSourceFileUrl'],
            })
        latest=series[-1]
        d['foreignInvestors']={
            **base,
            'cashNet':latest['cashNet'],
            'nikkeiFuturesNet':latest['nikkeiFuturesNet'],
            'topixFuturesNet':None,
            'asOfDate':latest['asOfDate'],
            'cashSourceFileUrl':latest['cashSourceFileUrl'],
            'derivativesSourceFileUrl':latest['derivativesSourceFileUrl'],
            'direction':latest['direction'],
            'series':series,
            'historyWeeks':len(series),
            'historyTargetWeeks':HISTORY_WEEKS,
            'historyStatus':'verified' if len(series)>=HISTORY_WEEKS else 'partial',
            'status':'verified',
            'fetchedAt':u.now(),
        }
    except Exception as exc:
        d['foreignInvestors']=u.stale(prev,base,f'JPX海外投資家取得失敗: {type(exc).__name__}: {exc}')
    d['assessment']=u.assessment(d.get('futures') or {},d.get('arbitrage') or {},d.get('options') or {},d.get('foreignInvestors') or {})
    keys=('spot','futures','sessions','arbitrage','options','participantFlow','foreignInvestors','participantOpenInterest','shortSelling','margin'); statuses={k:(d.get(k) or {}).get('status','unavailable') for k in keys}; d['sourceStatus']=f"{sum(v in {'verified','calculated'} for v in statuses.values())}/10項目連携（基準日を個別表示）"; d.setdefault('diagnostics',{})['statuses']=statuses; d['diagnostics']['foreignParser']='JPX Prime cash + Nikkei 225 futures monetary value; matched weekly dates; up to 12-week history'; d['generatedAt']=u.now(); OUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(d['foreignInvestors'],ensure_ascii=False))
if __name__=='__main__':main()
