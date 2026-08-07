#!/usr/bin/env python3
"""Add JPX Nikkei 225 option base volatility from theoretical-price data.

JPX's option theoretical-price files contain both issue-level settlement
volatility and a base volatility.  This script intentionally exposes the
base volatility as the single dashboard IV value and records the definition,
rather than silently choosing one strike's volatility.
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
GUIDE='https://www.jpx.co.jp/markets/derivatives/option-price/01.html'
BASE='https://www.jpx.co.jp'


def walk_strings(x):
    if isinstance(x,dict):
        for v in x.values():
            yield from walk_strings(v)
    elif isinstance(x,list):
        for v in x:
            yield from walk_strings(v)
    elif isinstance(x,str):
        yield x


def discover_csvs():
    html=u.get(PAGE).text
    soup=BeautifulSoup(html,'html.parser')
    found=[]
    for a in soup.find_all('a',href=True):
        z=urljoin(PAGE,a['href'])
        if re.search(r'\.csv(?:\?|$)',z,re.I):
            found.append(z)
    # JPX list pages often load current files from JSON endpoints embedded in HTML.
    json_urls=[]
    for m in re.finditer(r'(?P<p>/automation/[^"\'<>\s]+\.json)',html,re.I):
        json_urls.append(urljoin(BASE,m.group('p')))
    seen=set()
    queue=list(dict.fromkeys(json_urls))
    depth=0
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
    # Never use the header sample itself as market data.
    out=[]
    for z in dict.fromkeys(found):
        if z.lower().endswith('/head.csv'): continue
        out.append(z)
    return out


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
    if not rows: raise ValueError('empty theoretical-price csv')
    # JPX guide order from Apr. 13 2026:
    # underlying/index name, contract month, issue code, premium close,
    # theoretical price, settlement-calculation volatility, underlying close,
    # base volatility.
    best=None
    for r in rows:
        if len(r)<8: continue
        name=u.txt(r[0])
        if not re.search(r'(日経\s*225|NIKKEI\s*225|日経平均)',name,re.I): continue
        basev=to_pct(r[7]); issuev=to_pct(r[5]); underlying=u.n(r[6]); month=u.txt(r[1]); code=u.txt(r[2])
        if basev is None: continue
        key=re.sub(r'\D','',month)
        item={'underlyingName':name,'contractMonth':month,'issueCode':code,'baseVolatility':basev,'settlementVolatility':issuev,'underlyingClose':underlying}
        if best is None or (key and key < best[0]): best=(key,item)
    if not best: raise ValueError('Nikkei 225 base volatility row not found')
    return best[1]


def main():
    d=json.loads(OUT.read_text(encoding='utf-8')); prev=d.get('options') or {}
    out=dict(prev)
    out.update({'sourceName':'JPX 日経225オプション / オプション理論価格等情報','sourceUrl':PAGE})
    try:
        files=discover_csvs()
        if not files: raise ValueError('JPX option-price data CSV was not discovered')
        files=sorted(files,key=date_score,reverse=True)
        last=None
        for url in files[:12]:
            try:
                x=parse_file(url); last=(url,x); break
            except Exception:
                continue
        if not last: raise ValueError('latest JPX theoretical-price CSVs had no Nikkei 225 base-volatility row')
        url,x=last
        out['iv']=x['baseVolatility']
        out['ivDefinition']='JPX基準ボラティリティ（単一ダッシュボード値として採用）'
        out['baseVolatility']=x['baseVolatility']
        out['referenceSettlementVolatility']=x['settlementVolatility']
        out['ivContractMonth']=x['contractMonth']
        out['ivUnderlyingClose']=x['underlyingClose']
        out['ivStatus']='verified'
        out['ivSourceFileUrl']=url
        ds=date_score(url)
        if ds:
            try: out['ivAsOfDate']=datetime.strptime(ds,'%Y%m%d').date().isoformat()
            except Exception: pass
        out['fetchedAt']=u.now()
        # Keep Put/Call status independent; remove only the old IV-specific reason.
        if out.get('ivReason'): out.pop('ivReason',None)
    except Exception as exc:
        out['ivStatus']='unavailable'
        out['ivReason']=f'JPX基準ボラティリティ取得失敗: {type(exc).__name__}: {exc}'
        out['fetchedAt']=u.now()
    d['options']=out
    d.setdefault('diagnostics',{})['ivParser']='JPX option-price dynamic JSON/CSV discovery; single IV = JPX base volatility, not arbitrary strike IV'
    d['generatedAt']=u.now()
    OUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'iv':out.get('iv'),'ivStatus':out.get('ivStatus'),'ivDefinition':out.get('ivDefinition'),'ivReason':out.get('ivReason')},ensure_ascii=False))

if __name__=='__main__':
    main()
