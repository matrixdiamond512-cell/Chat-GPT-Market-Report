#!/usr/bin/env python3
from __future__ import annotations
import io,json,re
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from openpyxl import load_workbook
import update_nikkei225_supply_demand as u

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/nikkei225-supply-demand.json'
PAGES=[
 'https://www.jpx.co.jp/markets/statistics-derivatives/sector/',
 'https://www.jpx.co.jp/markets/statistics-derivatives/sector/00-archives-00.html',
 'https://www.jpx.co.jp/markets/statistics-derivatives/sector/00-archives-01.html',
]

def main():
 d=json.loads(OUT.read_text(encoding='utf-8'))
 target=str((d.get('participantOpenInterest') or {}).get('asOfDate') or '').replace('-','')[:8]
 links=[]
 for page in PAGES:
  try:
   soup=BeautifulSoup(u.get(page).text,'html.parser')
   for a in soup.find_all('a',href=True):
    href=urljoin(page,a['href'])
    if re.search(r'Tategyoku_W_.*\.xlsx(?:\?|$)',href,re.I): links.append(href)
  except Exception as exc:
   pass
 links=list(dict.fromkeys(links))
 chosen=next((x for x in links if target and target in x.rsplit('/',1)[-1]),None)
 probe={'target':target,'linkCount':len(links),'links':[x.rsplit('/',1)[-1] for x in links[:20]],'chosen':chosen}
 if chosen:
  try:
   wb=load_workbook(io.BytesIO(u.get(chosen).content),read_only=True,data_only=True)
   sheets=[]
   for ws in wb.worksheets:
    rows=[]
    for raw in ws.iter_rows(values_only=True):
     vals=[u.txt(x) if x is not None else '' for x in raw]
     if not any(vals): continue
     rows.append(vals[:18])
     if len(rows)>=60: break
    sheets.append({'title':ws.title,'rows':rows})
   probe['sheets']=sheets
  except Exception as exc:
   probe['error']=f'{type(exc).__name__}: {exc}'
 d.setdefault('diagnostics',{})['tategyokuProbe']=probe
 d['generatedAt']=u.now()
 OUT.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(probe,ensure_ascii=False))
if __name__=='__main__': main()
