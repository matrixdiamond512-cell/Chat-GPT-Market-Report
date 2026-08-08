#!/usr/bin/env python3
"""Parse JPX weekly foreign-investor cash and Nikkei 225 futures flows.

The dashboard always targets the latest 12 verified matching weeks. Current and
JPX official archive pages are scanned together. Cash and Nikkei 225 futures are
never combined across different weekly period ends, and missing weeks are never
fabricated. The same weekly dates are enriched with Nikkei 225 futures settlement
prices from Kabutan's historical table (exchange-published settlement values).
"""
from __future__ import annotations
import csv,io,json,re
from datetime import date,datetime
from pathlib import Path
from typing import Any
from bs4 import BeautifulSoup
import update_nikkei225_supply_demand as u
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/nikkei225-supply-demand.json'
HISTORY_WEEKS=12
CASH_ARCHIVE='https://www.jpx.co.jp/markets/statistics-equities/investor-type/00-00-archives-00.html'
SECTOR_ARCHIVE='https://www.jpx.co.jp/markets/statistics-derivatives/sector/00-archives-00.html'
KABUTAN_FUTURES_HISTORY='https://s.kabutan.jp/futures/%E6%97%A5%E7%B5%8C225%E5%85%88%E7%89%A9/historical_prices/daily/'

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
    for r in rows[1:]:
        if len(r)<12:continue
        # Current JPX format: product type 301 = Nikkei 225 Futures,
        # investor type 60 = Foreigners, Volume/Value 2 = monetary value.
        if r[0].strip()=='301' and r[5].strip()=='60' and r[6].strip()=='2':
            sell=u.n(r[7]); buy=u.n(r[9])
            if sell is None or buy is None:continue
            try:asof=datetime.strptime(r[4].strip(),'%Y%m%d').date().isoformat()
            except:asof=None
            return {'nikkeiFuturesNet':(buy-sell)/100_000_000,'asOfDate':asof,'derivativesSourceFileUrl':url}
    return None

def direction(cash:float|None,fut:float|None)->str:
    if cash is None or fut is None:return '判定待ち'
    if cash>0 and fut>0:return '現物・先物とも買い'
    if cash<0 and fut<0:return '現物・先物とも売り'
    if cash<0 and fut>0:return '現物売り・先物買い'
    if cash>0 and fut<0:return '現物買い・先物売り'
    return '方向混在'

def valid_old_series(prev:dict[str,Any])->dict[str,dict[str,Any]]:
    out={}
    for row in prev.get('series') or []:
        if not isinstance(row,dict):continue
        dt=row.get('asOfDate'); cash=row.get('cashNet'); fut=row.get('nikkeiFuturesNet')
        if not dt or cash is None or fut is None:continue
        out[str(dt)[:10]]={
            'asOfDate':str(dt)[:10],
            'cashNet':cash,
            'nikkeiFuturesNet':fut,
            'nikkeiFuturesPrice':row.get('nikkeiFuturesPrice'),
            'direction':row.get('direction') or direction(cash,fut),
            'cashSourceFileUrl':row.get('cashSourceFileUrl'),
            'derivativesSourceFileUrl':row.get('derivativesSourceFileUrl'),
            'futuresPriceSourceUrl':row.get('futuresPriceSourceUrl'),
        }
    return out

def all_links(pages:list[str],pattern:str)->list[str]:
    seen=set(); out=[]
    for page in pages:
        try:
            for url,_ in u.links(page):
                if re.search(pattern,url,re.I) and url not in seen:
                    seen.add(url); out.append(url)
        except Exception:
            pass
    return out

def kabutan_futures_prices(target_dates:list[str])->dict[str,float]:
    """Return settlement prices for exact target dates from Kabutan daily history.

    Kabutan labels the displayed close as the exchange-published settlement/book
    value. The visible table omits the year, so rows are matched only against the
    month/day pairs of the requested 12-week dates; those pairs are unique inside
    this short window.
    """
    wanted={str(x)[:10] for x in target_dates}
    by_md={(int(x[5:7]),int(x[8:10])):x for x in wanted}
    found:dict[str,float]={}
    for page in range(1,7):
        url=KABUTAN_FUTURES_HISTORY if page==1 else f'{KABUTAN_FUTURES_HISTORY}?page={page}'
        html=u.get(url).text
        soup=BeautifulSoup(html,'html.parser')
        for tr in soup.find_all('tr'):
            cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'])]
            if len(cells)<5:continue
            m=re.search(r'(\d{1,2})月\s*(\d{1,2})日',cells[0])
            if not m:continue
            md=(int(m.group(1)),int(m.group(2)))
            target=by_md.get(md)
            if not target:continue
            close=u.n(cells[4])
            if close is not None:
                found[target]=float(close)
        if len(found)>=len(wanted):break
    return found

def main():
    d=json.loads(OUT.read_text(encoding='utf-8')); prev=d.get('foreignInvestors') or {}
    base={
        'sourceName':'JPX 投資部門別売買状況',
        'sourceUrl':u.URLS['sector'],
        'cashNote':'東証プライム現物の海外投資家売買（金額ベース）',
        'nikkeiNote':'日経225先物の海外投資家売買（金額ベース）',
        'topixNote':'TOPIX先物は商品コード検証後に追加',
        'comment':'週次の現物と日経225先物を同一期間で比較。日次の売買主体とは断定しません。',
        'futuresPriceSourceName':'株探 日経225先物時系列（取引所発表の清算値・帳入値）',
        'futuresPriceSourceUrl':KABUTAN_FUTURES_HISTORY,
        'futuresPriceDefinition':'各週の基準日と同日の取引所発表清算値（帳入値）。実際の最終約定価格とは異なる場合があります。'
    }
    try:
        cashlinks=all_links([u.URLS['cash'],CASH_ARCHIVE],r'stock_val_1_\d+\.pdf(?:\?|$)')
        cr=[]
        for url in cashlinks:
            try:
                x=cash_pdf(url)
                if x:cr.append(x)
            except Exception:pass
        cr.sort(key=lambda x:x['asOfDate'],reverse=True)

        sectorlinks=all_links([u.URLS['sector'],SECTOR_ARCHIVE],r'Tousi_DV_W_20\d{6}_20\d{6}\.csv(?:\?|$)')
        dr=[]
        for url in sectorlinks:
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

        merged=valid_old_series(prev)
        for dt in matched:
            c,f=by_cash[dt],by_deriv[dt]
            old=merged.get(dt) or {}
            merged[dt]={
                'asOfDate':dt,
                'cashNet':c['cashNet'],
                'nikkeiFuturesNet':f['nikkeiFuturesNet'],
                'nikkeiFuturesPrice':old.get('nikkeiFuturesPrice'),
                'direction':direction(c['cashNet'],f['nikkeiFuturesNet']),
                'cashSourceFileUrl':c['cashSourceFileUrl'],
                'derivativesSourceFileUrl':f['derivativesSourceFileUrl'],
                'futuresPriceSourceUrl':old.get('futuresPriceSourceUrl'),
            }
        series=[merged[k] for k in sorted(merged)][-HISTORY_WEEKS:]
        if len(series)<HISTORY_WEEKS:
            raise ValueError(f'12-week history incomplete: {len(series)}/{HISTORY_WEEKS}')

        prices=kabutan_futures_prices([x['asOfDate'] for x in series])
        for row in series:
            px=prices.get(row['asOfDate'])
            if px is not None:
                row['nikkeiFuturesPrice']=px
                row['futuresPriceSourceUrl']=KABUTAN_FUTURES_HISTORY
        missing=[x['asOfDate'] for x in series if x.get('nikkeiFuturesPrice') is None]
        if missing:
            raise ValueError('12-week futures price history incomplete: '+','.join(missing))

        latest=series[-1]
        d['foreignInvestors']={
            **base,
            'cashNet':latest['cashNet'],
            'nikkeiFuturesNet':latest['nikkeiFuturesNet'],
            'nikkeiFuturesPrice':latest['nikkeiFuturesPrice'],
            'topixFuturesNet':None,
            'asOfDate':latest['asOfDate'],
            'cashSourceFileUrl':latest['cashSourceFileUrl'],
            'derivativesSourceFileUrl':latest['derivativesSourceFileUrl'],
            'direction':latest['direction'],
            'series':series,
            'historyWeeks':len(series),
            'historyTargetWeeks':HISTORY_WEEKS,
            'historyStatus':'verified',
            'priceHistoryWeeks':sum(x.get('nikkeiFuturesPrice') is not None for x in series),
            'priceHistoryStatus':'verified',
            'historyPolicy':'current-plus-official-archive-same-week-only-no-fabrication',
            'archiveSources':{'cash':CASH_ARCHIVE,'derivatives':SECTOR_ARCHIVE},
            'status':'verified',
            'fetchedAt':u.now(),
        }
    except Exception as exc:
        d['foreignInvestors']=u.stale(prev,base,f'JPX海外投資家取得失敗: {type(exc).__name__}: {exc}')
    d['assessment']=u.assessment(d.get('futures') or {},d.get('arbitrage') or {},d.get('options') or {},d.get('foreignInvestors') or {})
    keys=('spot','futures','sessions','arbitrage','options','participantFlow','foreignInvestors','participantOpenInterest','shortSelling','margin')
    statuses={k:(d.get(k) or {}).get('status','unavailable') for k in keys}
    d['sourceStatus']=f"{sum(v in {'verified','calculated'} for v in statuses.values())}/10項目連携（基準日を個別表示）"
    d.setdefault('diagnostics',{})['statuses']=statuses
    d['diagnostics']['foreignParser']='JPX Prime cash + Nikkei 225 futures flows, exact 12 matched weeks; Kabutan exchange settlement price on the same dates'
    d['generatedAt']=u.now()
    OUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(d['foreignInvestors'],ensure_ascii=False))
if __name__=='__main__':main()
