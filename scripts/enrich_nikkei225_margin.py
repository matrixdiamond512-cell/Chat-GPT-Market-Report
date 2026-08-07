#!/usr/bin/env python3
"""Parse JPX weekly margin balances for the Nikkei 225 supply-demand page."""
from __future__ import annotations
import json,re
from datetime import date
from pathlib import Path
from typing import Any
import update_nikkei225_supply_demand as u
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/nikkei225-supply-demand.json'

def signed(sign:str|None,v:str)->float:
    x=float(v.replace(',','')); return -x if sign else x

def parse_pdf(url:str)->dict[str,Any]|None:
    _,text=u.doc(url)
    dm=re.search(r'（(20\d{2})/(\d{1,2})/(\d{1,2})申込み現在）',text)
    if not dm:return None
    # Total monetary balances, unit JPY million:
    # sell balance, sell weekly change, buy balance, buy weekly change.
    m=re.search(r'Total\s+金額\s+Val\.\s+([\d,]+)\s+(▲\s*)?([\d,]+)\s+([\d,]+)\s+(▲\s*)?([\d,]+)',text,re.I)
    if not m:return None
    asof=date(int(dm.group(1)),int(dm.group(2)),int(dm.group(3))).isoformat()
    sell=float(m.group(1).replace(',','')); sellchg=signed(m.group(2),m.group(3)); buy=float(m.group(4).replace(',','')); buychg=signed(m.group(5),m.group(6))
    # Page schema stores balances in trillion yen.
    return {'asOfDate':asof,'sellBalance':sell/1_000_000,'sellChange':sellchg/1_000_000,'buyBalance':buy/1_000_000,'buyChange':buychg/1_000_000,'ratio':buy/sell if sell else None,'sourceFileUrl':url}

def main():
    d=json.loads(OUT.read_text(encoding='utf-8')); prev=d.get('margin') or {}; base={'sourceName':'JPX 信用取引現在高','sourceUrl':u.URLS['margin'],'comment':'信用需給は日本株個人投資家の補助指標。買い残・売り残は金額ベース（兆円）で表示。'}
    try:
        pdfs=[url for url,_ in u.links(u.URLS['margin']) if re.search(r'mtgaisan\d+\.pdf(?:\?|$)',url,re.I)]
        rows=[]
        for url in pdfs[:12]:
            try:
                x=parse_pdf(url)
                if x:rows.append(x)
            except Exception:pass
        rows.sort(key=lambda x:x['asOfDate'],reverse=True)
        if not rows:raise ValueError('weekly margin total monetary row not found')
        d['margin']={**base,**rows[0],'status':'verified','fetchedAt':u.now()}
    except Exception as exc:
        d['margin']=u.stale(prev,base,f'JPX信用需給取得失敗: {type(exc).__name__}: {exc}')
    keys=('spot','futures','sessions','arbitrage','options','participantFlow','foreignInvestors','participantOpenInterest','shortSelling','margin'); statuses={k:(d.get(k) or {}).get('status','unavailable') for k in keys}; d['sourceStatus']=f"{sum(v in {'verified','calculated'} for v in statuses.values())}/10項目連携（基準日を個別表示）"; d.setdefault('diagnostics',{})['statuses']=statuses; d['generatedAt']=u.now(); OUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(d['margin'],ensure_ascii=False))
if __name__=='__main__':main()
