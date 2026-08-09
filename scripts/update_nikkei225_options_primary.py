#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the small Nikkei 225 options data overlay directly from JPX Daily Report."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from update_nikkei225_options import (
    JPX_DAILY_JA,
    aggregate,
    choose_contract_month,
    discover_reports,
    parse_rows,
    report_pdf_bytes,
)

ROOT=Path(__file__).resolve().parents[1]
BASE_PATH=ROOT/'data'/'nikkei225-supply-demand.json'
OUT_PATH=ROOT/'data'/'nikkei225-options-latest.json'
JST=timezone(timedelta(hours=9))


def business_days_after(asof: date, sq: date) -> int:
    d=asof+timedelta(days=1); n=0
    while d<=sq:
        if d.weekday()<5:n+=1
        d+=timedelta(days=1)
    return n


def main():
    base=json.loads(BASE_PATH.read_text(encoding='utf-8'))
    opt=base.get('options') or {}
    sq=date.fromisoformat(opt.get('nextSqDate')) if opt.get('nextSqDate') else None
    preferred=sq.strftime('%Y%m') if sq else None
    current=opt.get('ivUnderlyingClose') or (base.get('futures') or {}).get('price')
    current=float(current) if current is not None else None

    session=requests.Session()
    reports=discover_reports(session)
    if not reports: raise RuntimeError('JPX Daily Report links not found')
    latest=reports[0]; previous=reports[1] if len(reports)>1 else None
    latest_pdf,latest_source=report_pdf_bytes(session,latest)
    latest_rows=parse_rows(latest_pdf)
    month=choose_contract_month(latest_rows,preferred,latest[0])
    latest_agg,put_vol,call_vol=aggregate(latest_rows,month)
    if not latest_agg: raise RuntimeError(f'No Nikkei 225 options OI for {month}')

    prev_agg={}; prev_source=None; prev_date=None
    if previous:
        try:
            prev_pdf,prev_source=report_pdf_bytes(session,previous)
            prev_rows=parse_rows(prev_pdf)
            prev_agg,_,_=aggregate(prev_rows,month)
            prev_date=previous[0]
        except Exception as exc:
            print('[options-primary] previous report unavailable:',exc)

    # Keep a useful near-market window; far OTM legacy positions should not dominate the dashboard.
    strikes=sorted(latest_agg)
    if current is not None:
        visible=[s for s in strikes if current-5000<=s<=current+5000]
        if visible:strikes=visible

    out_rows=[]
    for strike in strikes:
        cur=latest_agg[strike]; prv=prev_agg.get(strike,{})
        po=cur.get('putOi'); co=cur.get('callOi')
        pprev=prv.get('putOi'); cprev=prv.get('callOi')
        out_rows.append({
            'strike':strike,
            'putOi':po,'callOi':co,
            'putOiChange':(int(po or 0)-int(pprev or 0)) if po is not None and pprev is not None else None,
            'callOiChange':(int(co or 0)-int(cprev or 0)) if co is not None and cprev is not None else None,
            'putVolume':int(cur.get('putVolume') or 0),
            'callVolume':int(cur.get('callVolume') or 0),
        })

    put_oi=sum(int(r.get('putOi') or 0) for r in out_rows)
    call_oi=sum(int(r.get('callOi') or 0) for r in out_rows)
    upper=[r for r in out_rows if current is None or r['strike']>=current]
    lower=[r for r in out_rows if current is None or r['strike']<=current]
    upper_strike=max(upper,key=lambda r:int(r.get('callOi') or 0))['strike'] if upper else None
    lower_strike=max(lower,key=lambda r:int(r.get('putOi') or 0))['strike'] if lower else None
    asof=date(int(latest[0][:4]),int(latest[0][4:6]),int(latest[0][6:]))
    now=datetime.now(JST)

    overlay={
        'schemaVersion':'1.0.0',
        'sourceStatus':'verified-primary',
        'sourceName':'JPX 大阪取引所日報・指数オプション相場表',
        'sourceUrl':JPX_DAILY_JA,
        'officialSourceUrl':JPX_DAILY_JA,
        'optionDailyReportUrl':latest_source,
        'previousOptionDailyReportUrl':prev_source,
        'asOfDate':asof.isoformat(),
        'previousAsOfDate':(f'{prev_date[:4]}-{prev_date[4:6]}-{prev_date[6:]}' if prev_date else None),
        'fetchedAt':now.isoformat(timespec='seconds'),
        'optionContractMonth':month,
        'strikeOiCoverage':f'{month[4:6]}月限・原資産近辺±5,000円',
        'strikeOpenInterest':out_rows,
        'putCallRatio':(put_oi/call_oi if call_oi else None),
        'putCallDefinition':'表示範囲の建玉残高ベース（Put OI / Call OI）',
        'putVolume':put_vol,'callVolume':call_vol,
        'publishedPutCallVolumeRatio':(put_vol/call_vol if call_vol else None),
        'publishedPutCallDefinition':'当月限の出来高ベース（Put出来高 / Call出来高）',
        'upperCallConcentrationStrike':upper_strike,
        'lowerPutConcentrationStrike':lower_strike,
        'nextSqDate':sq.isoformat() if sq else opt.get('nextSqDate'),
        'businessDaysToSq':business_days_after(asof,sq) if sq else opt.get('businessDaysToSq'),
        'comment':'JPX大阪取引所日報から日経225オプション当月限の権利行使価格別建玉と前日比を取得。方向予想ではなく、価格帯・OI増減・IV・PCR・SQ接近によるヘッジ圧力分析に使用する。'
    }
    OUT_PATH.write_text(json.dumps(overlay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('[options-primary] updated',OUT_PATH,'rows=',len(out_rows),'asof=',asof)

if __name__=='__main__':main()
