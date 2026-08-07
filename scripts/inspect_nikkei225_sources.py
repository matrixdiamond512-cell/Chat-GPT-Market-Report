#!/usr/bin/env python3
"""Quickly inspect public JPX file links used by the Nikkei 225 updater."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import update_nikkei225_supply_demand as u
OUT=ROOT/'data/nikkei225-source-inspection.json'

def inspect_page(key: str):
    page=u.URLS[key]
    try:
        ll=u.links(page)
        return {'page':page,'links':[{'url':url,'label':label[:300]} for url,label in ll[:40]]}
    except Exception as exc:
        return {'page':page,'links':[],'error':f'{type(exc).__name__}: {exc}'}

def main():
    payload={'generatedAt':u.now(),'note':'parser-maintenance diagnostic; public JPX link metadata only','sources':{}}
    for key in ('futures','arbitrage','options','flow','cash','sector','oi','short','margin'):
        payload['sources'][key]=inspect_page(key)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(OUT)

if __name__=='__main__': main()
