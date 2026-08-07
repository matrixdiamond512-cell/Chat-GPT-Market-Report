#!/usr/bin/env python3
"""Parse JPX weekly foreign-investor cash and Nikkei 225 futures flows."""
from __future__ import annotations
import csv,io,json,re
from datetime import date,datetime
from pathlib import Path
from typing import Any
import update_nikkei225_supply_demand as u
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/nikkei225-supply-demand.json'

def cash_pdf(url:str)->dict[str,Any]|None:
    _,text=u.doc(url)
    hm=re.search(r'(20\d{2})年\d{1,2}月第\d+週.*?\(\s*\d{1,2}/\d{1,2}\s*[-〜～]\s*(\d{1,2})/(\d{1,2})\s*\)',text,re.S)
    if not hm:return None
    y,mo,dy=int(hm.group(1)),int(hm.group(2)),int(hm.group(3))
    # Get current-period sales/purchases; optional balance fields can sit after
    # either row depending on the sign, so calculate net directly.
    sm=re.search(r'海外投資家\s+売り\s+Sales\s+([\d,]+)\s+[\d.]+(?:\s+[▲+-]?\s*[\d,]+)?\s+([\d,]+)\s+[\d.]+',text)
    pm=re.search(r'Foreigners\s+買い\s+Purchases\s+([\d,]+)\s+[\d.]+(?:\s+[▲+-]?\s*[\d,]+)?\s+([\d,]+)\s+[\d.]+',text)
    if not sm or not pm:return None
    current_sales=float(sm.group(2).replace(',','')); current_purchases=float(pm.group(2).replace(',',''))
    # PDF unit is thousand yen; 100,000 thousand yen = 1 oku yen.
    return {'cashNet':(current_purchases-current_sales)/100_000,'asOfDate':date(y,mo,dy).isoformat(),'cashSourceFileUrl':url}

def derivative_csv(url:str)->dict[str,Any]|None:
    text=u.decode(u.get(url).content); rows=list(csv.reader(io.StringIO(text)))
    if not rows:return None
    best=None
    for r in rows[1:]:
        if len(r)<12:continue
        # Product type 301 = Nikkei 225 Futures in the current JPX weekly file.
        # Investor type 60 = Foreigners; Volume/Value 2 = monetary value.
        if r[0].strip()=='301' and r[5].strip()=='60' and r[6].strip()=='2':
            sell=u.n(r[7]); buy=u.n(r[9])
            if sell is None or buy is None:continue
            try:asof=datetime.strptime(r[4].strip(),'%Y%m%d').date().isoformat()
            except:asof=None
            best={'nikkeiFuturesNet':(buy-sell)/100_000_000,'asOfDate':asof,'derivativesSourceFileUrl':url}
            break
    return best

def main():
    d=json.loads(OUT.read_text(encoding='utf-8')); prev=d.get('foreignInvestors') or {}; base={'sourceName':'JPX 投資部門別売買状況','sourceUrl':u.URLS['sector'],'cashNote':'東証プライム現物の海外投資家売買（金額ベース）','nikkeiNote':'日経225先物の海外投資家売買（金額ベース）','topixNote':'TOPIX先物は商品コード検証後に追加','comment':'週次の現物と日経225先物を同一期間で比較。日次の売買主体とは断定しません。'}
    try:
        cashlinks=[url for url,_ in u.links(u.URLS['cash']) if re.search(r'stock_val_1_\d+\.pdf(?:\?|$)',url,re.I)]
        cr=[]
        for url in cashlinks[:12]:
            try:
                x=cash_pdf(url)
                if x:cr.append(x)
            except Exception:pass
        cr.sort(key=lambda x:x['asOfDate'],reverse=True)
        sectorlinks=[url for url,_ in u.links(u.URLS['sector']) if re.search(r'Tousi_DV_W_20\d{6}_20\d{6}\.csv(?:\?|$)',url,re.I)]
        dr=[]
        for url in sectorlinks[:8]:
            try:
                x=derivative_csv(url)
                if x:dr.append(x)
            except Exception:pass
        dr.sort(key=lambda x:x.get('asOfDate') or '',reverse=True)
        if not cr or not dr:raise ValueError(f'cash={len(cr)} derivative={len(dr)}')
        # Use only matching period ends. If latest files are temporarily out of
        # sync, do not combine different weeks.
        pair=None
        bydate={x['asOfDate']:x for x in dr if x.get('asOfDate')}
        for x in cr:
            if x['asOfDate'] in bydate:pair=(x,bydate[x['asOfDate']]);break
        if not pair:raise ValueError('cash and derivative weekly period ends do not match')
        c,f=pair
        d['foreignInvestors']={**base,'cashNet':c['cashNet'],'nikkeiFuturesNet':f['nikkeiFuturesNet'],'topixFuturesNet':None,'asOfDate':c['asOfDate'],'cashSourceFileUrl':c['cashSourceFileUrl'],'derivativesSourceFileUrl':f['derivativesSourceFileUrl'],'status':'verified','fetchedAt':u.now()}
    except Exception as exc:
        d['foreignInvestors']=u.stale(prev,base,f'JPX海外投資家取得失敗: {type(exc).__name__}: {exc}')
    d['assessment']=u.assessment(d.get('futures') or {},d.get('arbitrage') or {},d.get('options') or {},d.get('foreignInvestors') or {})
    keys=('spot','futures','sessions','arbitrage','options','participantFlow','foreignInvestors','participantOpenInterest','shortSelling','margin'); statuses={k:(d.get(k) or {}).get('status','unavailable') for k in keys}; d['sourceStatus']=f"{sum(v in {'verified','calculated'} for v in statuses.values())}/10項目連携（基準日を個別表示）"; d.setdefault('diagnostics',{})['statuses']=statuses; d['diagnostics']['foreignParser']='JPX Prime cash value + product 301/investor 60 derivative value'; d['generatedAt']=u.now(); OUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(d['foreignInvestors'],ensure_ascii=False))
if __name__=='__main__':main()
