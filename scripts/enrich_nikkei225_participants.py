#!/usr/bin/env python3
"""Parse JPX participant turnover leaders and weekly net OI leaders for Nikkei 225 futures."""
from __future__ import annotations
import io,json,re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from openpyxl import load_workbook
import update_nikkei225_supply_demand as u

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/nikkei225-supply-demand.json'
BASE='https://www.jpx.co.jp'

def latest_participant_volume_file():
    ml=u.get(BASE+'/automation/markets/derivatives/participant-volume/json/participant-volume_monthlylist.json').json()
    month=ml['TableDatas'][0]['Month']
    cur=u.get(BASE+f'/automation/markets/derivatives/participant-volume/json/participant_volume_{month}.json').json()
    row=cur['TableDatas'][0]
    return row['TradeDate'],urljoin(BASE,row['WholeDay'])

def parse_turnover_leaders(url:str):
    wb=load_workbook(io.BytesIO(u.get(url).content),read_only=True,data_only=True)
    rows=[]
    for ws in wb.worksheets:
        for raw in ws.iter_rows(values_only=True):
            r=list(raw)
            if len(r)<8 or u.txt(r[0])!='NK225F': continue
            contract=u.txt(r[2]); rank=u.n(r[3]); name=u.txt(r[5]); vol=u.n(r[7])
            if not contract or rank is None or not name or vol is None: continue
            rows.append({'contract':contract,'rank':int(rank),'name':name,'volume':int(round(vol))})
    if not rows: raise ValueError('NK225F turnover rows not found')
    front=rows[0]['contract']
    leaders=[{'name':x['name'],'volume':x['volume'],'rank':x['rank']} for x in rows if x['contract']==front]
    leaders.sort(key=lambda x:x['rank'])
    return front,leaders[:10]

def latest_participant_oi_file():
    yl=u.get(BASE+'/automation/markets/derivatives/open-interest/json/open_interest_yearlist.json').json()
    year=yl['TableDatas'][0]
    cur=u.get(urljoin(BASE,year['Jsonfile'])).json()
    row=cur['TableDatas'][0]
    return row['TradeDate'],urljoin(BASE,row['IndexFutures'])

def parse_oi_leaders(url:str):
    wb=load_workbook(io.BytesIO(u.get(url).content),read_only=True,data_only=True)
    for ws in wb.worksheets:
        rows=list(ws.iter_rows(values_only=True)); start=None
        for i,raw in enumerate(rows):
            first=u.txt(raw[0]) if len(raw)>0 else ''
            if first=='＜日経225先物＞': start=i+1; break
        if start is None: continue
        first_contract=None; sellers=[]; buyers=[]
        for raw in rows[start:]:
            r=list(raw); first=u.txt(r[0]) if len(r)>0 else ''
            if first.startswith('＜') and first.endswith('＞'): break
            contract=u.txt(r[1]) if len(r)>1 else ''; rank=u.n(r[0]) if len(r)>0 else None
            if rank is None or not re.search(r'20\d{2}年\d{2}月限月',contract): continue
            if first_contract is None: first_contract=contract
            if contract!=first_contract: continue
            sell_name=u.txt(r[3]) if len(r)>3 else ''; sell_qty=u.n(r[4]) if len(r)>4 else None
            buy_name=u.txt(r[6]) if len(r)>6 else ''; buy_qty=u.n(r[7]) if len(r)>7 else None
            if sell_name and sell_qty is not None: sellers.append({'name':sell_name,'openInterest':int(round(sell_qty)),'rank':int(rank)})
            if buy_name and buy_qty is not None: buyers.append({'name':buy_name,'openInterest':int(round(buy_qty)),'rank':int(rank)})
        if first_contract and (sellers or buyers):
            sellers.sort(key=lambda x:x['rank']); buyers.sort(key=lambda x:x['rank'])
            return first_contract,sellers[:10],buyers[:10]
    raise ValueError('日経225先物の売超/買超参加者表を特定できません')

def iso_date(s:str): return datetime.strptime(s,'%Y%m%d').date().isoformat()

def main():
    d=json.loads(OUT.read_text(encoding='utf-8'))
    prev=d.get('participantFlow') or {}
    base={'sourceName':'JPX 取引参加者別取引高（手口上位一覧）','sourceUrl':'https://www.jpx.co.jp/markets/derivatives/participant-volume/','comment':'日次ファイルは売買方向別ではなく取引高上位です。取引高上位を売り・買いと読み替えません。'}
    try:
        td,url=latest_participant_volume_file(); contract,leaders=parse_turnover_leaders(url)
        d['participantFlow']={**base,'asOfDate':iso_date(td),'contract':contract,'leaders':leaders,'sourceFileUrl':url,'status':'verified','fetchedAt':u.now()}
    except Exception as exc:
        d['participantFlow']=u.stale(prev,base,f'JPX手口上位取得失敗: {type(exc).__name__}: {exc}')
    prev=d.get('participantOpenInterest') or {}
    base={'sourceName':'JPX 取引参加者別建玉残高','sourceUrl':'https://www.jpx.co.jp/markets/derivatives/open-interest/','comment':'週次の期近限月について、JPXが明示する売超参加者・買超参加者の上位を表示します。最終投資家を直接示すものではありません。'}
    try:
        td,url=latest_participant_oi_file(); contract,sellers,buyers=parse_oi_leaders(url)
        d['participantOpenInterest']={**base,'asOfDate':iso_date(td),'contract':contract,'sellers':sellers,'buyers':buyers,'sourceFileUrl':url,'status':'verified','fetchedAt':u.now()}
    except Exception as exc:
        d['participantOpenInterest']=u.stale(prev,base,f'JPX参加者別建玉取得失敗: {type(exc).__name__}: {exc}')
    keys=('spot','futures','sessions','arbitrage','options','participantFlow','foreignInvestors','participantOpenInterest','shortSelling','margin')
    statuses={k:(d.get(k) or {}).get('status','unavailable') for k in keys}
    connected=sum(v in {'verified','calculated'} for v in statuses.values())
    d['sourceStatus']=f'{connected}/10主要セクション稼働（各内部指標の欠損は個別表示）'
    d.setdefault('diagnostics',{})['statuses']=statuses
    d['diagnostics']['participantParser']='JPX dynamic JSON -> daily WholeDay turnover leaders + weekly IndexFutures sell/buy net OI'
    d['generatedAt']=u.now()
    OUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'participantFlow':d['participantFlow'],'participantOpenInterest':d['participantOpenInterest'],'sourceStatus':d['sourceStatus']},ensure_ascii=False))
if __name__=='__main__': main()
