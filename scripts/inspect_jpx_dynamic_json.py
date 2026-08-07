#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
import update_nikkei225_supply_demand as u
OUT=ROOT/'data/jpx-dynamic-json-inspection.json'
urls={
 'participantMonthlyList':'https://www.jpx.co.jp/automation/markets/derivatives/participant-volume/json/participant-volume_monthlylist.json',
 'participantCurrent':'https://www.jpx.co.jp/automation/markets/derivatives/participant-volume/json/participant_volume_202608.json',
 'openInterestYearList':'https://www.jpx.co.jp/automation/markets/derivatives/open-interest/json/open_interest_yearlist.json',
 'openInterestCurrent':'https://www.jpx.co.jp/automation/markets/derivatives/open-interest/json/open_interest_2026.json',
}
out={'generatedAt':u.now(),'results':{}}
for k,url in urls.items():
    try:
        r=u.get(url)
        text=r.text
        try:data=r.json()
        except Exception:data=None
        out['results'][k]={'url':url,'statusCode':r.status_code,'contentType':r.headers.get('content-type'),'json':data,'textHead':text[:5000]}
    except Exception as exc:
        out['results'][k]={'url':url,'error':f'{type(exc).__name__}: {exc}'}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(OUT)
