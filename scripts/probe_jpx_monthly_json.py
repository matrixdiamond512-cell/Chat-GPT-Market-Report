#!/usr/bin/env python3
import json,requests
from pathlib import Path
BASE='https://www.jpx.co.jp'
URL=BASE+'/automation/markets/statistics-derivatives/monthly-statistics/json/monthly_statistics_report2026.json'
HIST=BASE+'/automation/markets/statistics-derivatives/monthly-statistics/json/historical_records_2026.json'
OUT=Path(__file__).resolve().parents[1]/'data/debug-jpx-monthly-json.json'
h={'User-Agent':'Mozilla/5.0 market-report-maintenance/1.0'}
def fetch(u):
 r=requests.get(u,headers=h,timeout=30); r.raise_for_status(); return r.json()
def main():
 out={}
 for k,u in [('monthly',URL),('historical',HIST)]:
  try: out[k]=fetch(u)
  except Exception as e: out[k]={'error':repr(e),'url':u}
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:type(v).__name__ for k,v in out.items()},ensure_ascii=False))
if __name__=='__main__':main()
