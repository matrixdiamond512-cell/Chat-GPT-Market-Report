#!/usr/bin/env python3
"""Add JPX Nikkei 225 option base volatility and official underlying close.

Current JPX format (Apr. 13 2026 onward) is a 17-column record beginning with
Product Code. Nikkei 225 Options use NK225E. The dashboard IV is explicitly the
JPX Base Volatility. The same official file's Underlying Close is also used as
the preferred Nikkei 225 spot close, allowing a same-trade-date simple
cash/futures comparison without relying on a stale secondary spot source.
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
        # 0 Product Code, 1 Product Type, 2 Contract Month, 3 Strike Price,
        # 4 Reserve, 5 Put Issue Code, 6 Put Close, 7 Reserve,
        # 8 Put Theo, 9 Put Vol, 10 Call Issue Code, 11 Call Close,
        # 12 Reserve, 13 Call Theo, 14 Call Vol,
        # 15 Underlying Close, 16 Base Volatility.
        if len(r)<17 or u.txt(r[0]).upper()!='NK225E':
            continue
        month=u.txt(r[2]); strike=u.n(r[3]); putv=to_pct(r[9]); callv=to_pct(r[14])
        underlying=u.n(r[15]); basev=to_pct(r[16])
        if basev is None or underlying is None:
            continue
        key=re.sub(r'\D','',month)
        candidates.append((key,{
            'productCode':'NK225E','contractMonth':month,'strikePrice':strike,
            'putSettlementVolatility':putv,'callSettlementVolatility':callv,
            'underlyingClose':underlying,'baseVolatility':basev
        }))
    if not candidates:
        raise ValueError('NK225E 17-column base-volatility row not found')
    # First select the nearest listed contract, then pick the strike nearest the
    # underlying close. Base volatility is repeated, while this keeps the
    # optional reference strike volatilities economically meaningful.
    months=sorted({k for k,_ in candidates if k})
    nearest=months[0] if months else candidates[0][0]
    pool=[x for k,x in candidates if k==nearest] or [x for _,x in candidates]
    pool.sort(key=lambda x: abs(x['strikePrice']-x['underlyingClose']) if x['strikePrice'] is not None else 10**12)
    return pool[0]


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
        out['referenceStrikePrice']=x['strikePrice']
        out['referencePutSettlementVolatility']=x['putSettlementVolatility']
        out['referenceCallSettlementVolatility']=x['callSettlementVolatility']
        out['ivContractMonth']=x['contractMonth']
        out['ivUnderlyingClose']=x['underlyingClose']
        out['ivStatus']='verified'
        out['ivSourceFileUrl']=url
        ds=date_score(url)
        iv_date=None
        if ds:
            try: iv_date=datetime.strptime(ds,'%Y%m%d').date().isoformat(); out['ivAsOfDate']=iv_date
            except Exception: pass
        out['fetchedAt']=u.now(); out.pop('ivReason',None)
        # Prefer the official JPX underlying close over a secondary spot source.
        # This value is the Nikkei 225 underlying close embedded in the verified
        # NK225E theoretical-price record.
        if x['underlyingClose'] is not None and iv_date:
            d['spot']={
                'sourceName':'JPX 日経225オプション理論価格等情報・原資産終値',
                'sourceUrl':PAGE,
                'sourceFileUrl':url,
                'comment':'NK225E理論価格ファイルの原資産終値。先物とは同一取引日でも時刻が異なるため、表示差は理論ベーシスではなく単純な現物終値対比。',
                'value':x['underlyingClose'],
                'asOfDate':iv_date,
                'status':'verified',
                'fetchedAt':u.now()
            }
    except Exception as exc:
        out['ivStatus']='unavailable'
        out['ivReason']=f'JPX基準ボラティリティ取得失敗: {type(exc).__name__}: {exc}'
        out['ivCandidateFiles']=files[:8]
        out['fetchedAt']=u.now()
    d['options']=out
    d.setdefault('diagnostics',{})['ivParser']='JPX current 17-column theoretical-price CSV; NK225E; dashboard IV = Base Volatility; spot = Underlying Close'
    d['generatedAt']=u.now()
    OUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'iv':out.get('iv'),'ivStatus':out.get('ivStatus'),'ivDefinition':out.get('ivDefinition'),'ivSourceFileUrl':out.get('ivSourceFileUrl'),'spot':d.get('spot')},ensure_ascii=False))

if __name__=='__main__': main()
