#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fallback Nikkei 225 option updater using a public JPX-derived daily table.

Primary data source remains JPX.  This fallback is used only when the JPX Daily
Report PDF/ZIP parser cannot complete, so the dashboard does not silently lose
strike OI.  The fallback page states that its option table is built from JPX's
daily published nearest three expiries and provides day-over-day OI changes.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT_PATH=ROOT/'data'/'nikkei225-options-latest.json'
URL='https://matsutoushi.github.io/nk225-option-site/'
OFFICIAL='https://www.jpx.co.jp/markets/statistics-derivatives/daily/index.html'
JST=timezone(timedelta(hours=9))
UA='Mozilla/5.0 (compatible; MarketReportBot/1.0)'


def num(text, dash_zero=False):
    s=str(text or '').strip().replace(',','').replace('−','-')
    if s in {'','-','—','－'}: return 0 if dash_zero else None
    m=re.search(r'[+-]?\d+(?:\.\d+)?',s)
    return float(m.group()) if m else (0 if dash_zero else None)


def intnum(text,dash_zero=False):
    v=num(text,dash_zero=dash_zero)
    return int(v) if v is not None else None


def find_option_tables(soup):
    head=None
    for h in soup.find_all(['h2','h3']):
        if 'オプション建玉一覧' in h.get_text(' ',strip=True):
            head=h; break
    if not head: raise RuntimeError('option OI heading not found')
    tables=head.find_all_next('table',limit=2)
    if len(tables)<2: raise RuntimeError('option OI/change tables not found')
    return tables[0],tables[1]


def table_rows(table):
    return [[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'])] for tr in table.find_all('tr')]


def main():
    r=requests.get(URL,headers={'User-Agent':UA},timeout=40)
    r.raise_for_status()
    soup=BeautifulSoup(r.text,'html.parser')
    page_text=soup.get_text(' ',strip=True)

    dm=re.search(r'データ基準日\s*[:：]\s*(\d{4}-\d{2}-\d{2})',page_text)
    if not dm: raise RuntimeError('data date not found')
    asof=date.fromisoformat(dm.group(1))

    oi_table,ch_table=find_option_tables(soup)
    oi=[]
    for cells in table_rows(oi_table):
        if len(cells)<7 or not re.fullmatch(r'\d{2,3},\d{3}|\d{4,6}',cells[0].replace(' ','')):
            continue
        strike=intnum(cells[0]); call=intnum(cells[1],dash_zero=True); put=intnum(cells[4],dash_zero=True)
        if strike is None: continue
        oi.append({'strike':strike,'callOi':call or 0,'putOi':put or 0})
    if not oi: raise RuntimeError('no strike OI rows parsed')

    changes=[]
    for cells in table_rows(ch_table):
        if len(cells)<6: continue
        c=intnum(cells[0]); p=intnum(cells[3])
        # Header rows have no signed/number values.
        if c is None and p is None: continue
        changes.append({'callOiChange':c,'putOiChange':p})

    for i,row in enumerate(oi):
        if i<len(changes): row.update(changes[i])
        else: row.update({'callOiChange':None,'putOiChange':None})

    call_oi=sum(int(x.get('callOi') or 0) for x in oi)
    put_oi=sum(int(x.get('putOi') or 0) for x in oi)

    ratio_m=re.search(r'Put/Call\s*レシオは\s*([\d.]+).*?前営業日\s*([\d.]+)',page_text)
    published=float(ratio_m.group(1)) if ratio_m else None
    published_prev=float(ratio_m.group(2)) if ratio_m else None
    pm=re.search(r'プット出来高\s*([\d,]+)\s*枚',page_text)
    cm=re.search(r'コール出来高\s*([\d,]+)\s*枚',page_text)
    put_vol=int(pm.group(1).replace(',','')) if pm else None
    call_vol=int(cm.group(1).replace(',','')) if cm else None
    band_m=re.search(r'建玉が厚いのはコール\s*([\d,]+)円・プット\s*([\d,]+)円',page_text)
    upper=int(band_m.group(1).replace(',','')) if band_m else None
    lower=int(band_m.group(2).replace(',','')) if band_m else None
    sq_m=re.search(r'次回SQ\s*(\d{1,2})/(\d{1,2}).*?あと\s*(\d+)日',page_text)
    sq=None; days=None
    if sq_m:
        month,day,days=int(sq_m.group(1)),int(sq_m.group(2)),int(sq_m.group(3))
        year=asof.year + (1 if month<asof.month else 0)
        sq=date(year,month,day)

    overlay={
        'schemaVersion':'1.0.0',
        'sourceStatus':'verified-fallback',
        'sourceName':'JPX公表データ集計（公開サイト経由）',
        'sourceUrl':URL,
        'officialSourceUrl':OFFICIAL,
        'asOfDate':asof.isoformat(),
        'fetchedAt':datetime.now(JST).isoformat(timespec='seconds'),
        'optionContractMonth':asof.strftime('%Y%m'),
        'strikeOiCoverage':f'{asof.month}月限・前営業日終値の上下3,000円範囲',
        'strikeOpenInterest':oi,
        'putCallRatio':(put_oi/call_oi if call_oi else None),
        'putCallDefinition':'表示範囲の建玉残高ベース（Put OI / Call OI）',
        'putVolume':put_vol,'callVolume':call_vol,
        'publishedPutCallVolumeRatio':published,
        'publishedPutCallVolumeRatioPrevious':published_prev,
        'publishedPutCallDefinition':'出来高ベース（Put出来高 / Call出来高）',
        'upperCallConcentrationStrike':upper,
        'lowerPutConcentrationStrike':lower,
        'nextSqDate':sq.isoformat() if sq else None,
        'businessDaysToSq':days,
        'comment':'JPX公表データを基礎にした公開集計をフォールバック利用。権利行使価格別建玉・前日比・出来高PCRを取得し、方向予想ではなくヘッジ圧力が変わりやすい価格帯の確認に使用する。'
    }
    OUT_PATH.write_text(json.dumps(overlay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('[options-fallback] updated',OUT_PATH,'rows=',len(oi),'asof=',asof)

if __name__=='__main__':main()
