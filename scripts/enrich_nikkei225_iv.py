#!/usr/bin/env python3
"""Add JPX Nikkei 225 option base volatility from theoretical-price data.

Current JPX format (Apr. 13 2026 onward) is a 17-column record beginning with
Product Code.  Nikkei 225 Options use NK225E.  The single dashboard IV is the
JPX Base Volatility field, explicitly labelled as such; issue-level put/call
settlement volatilities are kept separate and are not averaged into a made-up
market IV.
"""
from __future__ import annotations
import csv,json,re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import update_nikkei225_supply_demand as u

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/nikkei225-supply-demand.json'
PAGE='https://www.jpx.co.jp/markets/derivatives/option-price/'
BASE='https://www.jpx.co.jp'


def walk_strings(x):
    if isinstance(x,dict):
        for v in x.values(): yield from walk_strings(v)
    elif isinstance(x,list):
        for v in x: yield from walk_strings(v)
    elif isinstance(x,str):
        yield x


def discover_csvs():
    html=u.get(PAGE).text
    soup=BeautifulSoup(html,'html.parser')
    found=[]
    for a in soup.find_all('a',href=True):
        z=urljoin(PAGE,a['href'])
        if re.search(r'\.csv(?:\?|$)',z,re.I): found.append(z)
    json_urls=[]
    for m in re.finditer(r'(?P<p>/automation/[^"\'<>\s]+\.json)',html,re.I):
        json_urls.append(urljoin(BASE,m.group('p')))
    seen=set(); queue=list(dict.fromkeys(json_urls)); depth=0
    while queue and depth<4:
        nextq=[]
        for ju in queue:
            if ju in seen: continue
            seen.add(ju)
            try: obj=u.get(ju).json()
            except Exception: continue
            for s in walk_strings(obj):
                if re.search(r'\.csv(?:\?|$)',s,re.I): found.append(urljoin(BASE,s))
                elif re.search(r'\.json(?:\?|$)',s,re.I): nextq.append(urljoin(BASE,s))
        queue=nextq; depth+=1
    return [z for z in dict.fromkeys(found) if not z.lower().endswith('/head.csv')]


def date_score(url):
    ms=re.findall(r'(20\d{6})',url)
    return max(ms) if ms else ''


def to_pct(v):
    x=u.n(v)
    if x is None: return None
    return x*100.0 if 0 < abs(x) < 2 else x


def parse_file(url):
    text=u.decode(u.get(url).content)
    rows=list(csv.reader(text.splitlines()))
    candidates=[]
    for r in rows:
        # JPX current record:
        # 0 Product Code, 1 Product Type, 2 Contract Month, 3 Strike Price,
        # 4 Reserve, 5 Put Issue Code, 6 Put Close, 7 Reserve,
        # 8 Put Theo, 9 Put Vol, 10 Call Issue Code, 11 Call Close,
        # 12 Reserve, 13 Call Theo, 14 Call Vol,
        # 15 Underlying Close, 16 Base Volatility.
        if len(r)<17 or u.txt(r[0]).upper()!='NK225E':
            continue
        month=u.txt(r[2]); strike=u.n(r[3]); putv=to_pct(r[9]); callv=to_pct(r[14])
        underlying=u.n(r[15]); basev=to_pct(r[16])
        if basev is None:
            continue
        key=re.sub(r'\D','',month)
        candidates.append((key,{
            'productCode':'NK225E','contractMonth':month,'strikePrice':strike,
            'putSettlementVolatility':putv,'callSettlementVolatility':callv,
            'underlyingClose':underlying,'baseVolatility':basev
        }))
    if not candidates:
        raise ValueError('NK225E 17-column base-volatility row not found')
    # nearest listed contract first; base volatility is a product-level reference
    # repeated across strikes, so one row is sufficient once contract is fixed.
    candidates.sort(key=lambda x:x[0] or '99999999')
    return candidates[0][1]


def main():
    d=json.loads(OUT.read_text(encoding='utf-8')); prev=d.get('options') or {}
    out=dict(prev)
    out.update({'sourceName':'JPX 日経225オプション / オプション理論価格等情報','sourceUrl':PAGE})
    files=[]
    try:
        files=sorted(discover_csvs(),key=date_score,reverse=True)
        if not files: raise ValueError('JPX option-price data CSV was not discovered')
        last=None
        for url in files[:16]:
            try:
                x=parse_file(url); last=(url,x); break
            except Exception:
                continue
        if not last:
            raise ValueError('latest JPX theoretical-price CSVs had no NK225E current-format row')
        url,x=last
        out['iv']=x['baseVolatility']
        out['ivDefinition']='JPX基準ボラティリティ（NK225E・期近限月）'
        out['baseVolatility']=x['baseVolatility']
        out['referencePutSettlementVolatility']=x['putSettlementVolatility']
        out['referenceCallSettlementVolatility']=x['callSettlementVolatility']
        out['ivContractMonth']=x['contractMonth']
        out['ivUnderlyingClose']=x['underlyingClose']
        out['ivStatus']='verified'
        out['ivSourceFileUrl']=url
        ds=date_score(url)
        if ds:
            try: out['ivAsOfDate']=datetime.strptime(ds,'%Y%m%d').date().isoformat()
            except Exception: pass
        out['fetchedAt']=u.now(); out.pop('ivReason',None)
    except Exception as exc:
        out['ivStatus']='unavailable'
        out['ivReason']=f'JPX基準ボラティリティ取得失敗: {type(exc).__name__}: {exc}'
        out['ivCandidateFiles']=files[:8]
        out['fetchedAt']=u.now()
    d['options']=out
    d.setdefault('diagnostics',{})['ivParser']='JPX current 17-column theoretical-price CSV; NK225E; dashboard IV = Base Volatility'
    d['generatedAt']=u.now()
    OUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'iv':out.get('iv'),'ivStatus':out.get('ivStatus'),'ivDefinition':out.get('ivDefinition'),'ivReason':out.get('ivReason'),'ivSourceFileUrl':out.get('ivSourceFileUrl')},ensure_ascii=False))

if __name__=='__main__': main()
