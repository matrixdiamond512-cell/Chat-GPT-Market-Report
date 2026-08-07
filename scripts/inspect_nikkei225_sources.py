#!/usr/bin/env python3
"""Inspect public JPX source files used by the Nikkei 225 supply-demand updater.

This writes only link metadata and small row samples so parsers can be maintained
without guessing column positions. It is diagnostic data, not a market-data source.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import update_nikkei225_supply_demand as u
OUT=ROOT/'data/nikkei225-source-inspection.json'

def clean(v):
    s=u.txt(v)
    return s[:180] if s else ''

def inspect_page(key: str, max_docs: int=5):
    page=u.URLS[key]
    result={'page':page,'links':[],'documents':[]}
    try:
        ll=u.links(page)
        result['links']=[{'url':url,'label':label[:240]} for url,label in ll[:25]]
        for url,label in ll[:max_docs]:
            try:
                rows,text=u.doc(url)
                sample=[]
                for row in rows:
                    vals=[clean(x) for x in row if clean(x)]
                    if vals:
                        sample.append(vals[:14])
                    if len(sample)>=35:
                        break
                result['documents'].append({'url':url,'label':label[:240],'sampleRows':sample,'textHead':text[:1800]})
            except Exception as exc:
                result['documents'].append({'url':url,'label':label[:240],'error':f'{type(exc).__name__}: {exc}'})
    except Exception as exc:
        result['error']=f'{type(exc).__name__}: {exc}'
    return result

def main():
    payload={'generatedAt':u.now(),'note':'parser-maintenance diagnostic; sampled public JPX files only','sources':{}}
    for key in ('futures','arbitrage','options','flow','cash','sector','oi','short','margin'):
        payload['sources'][key]=inspect_page(key)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(OUT)

if __name__=='__main__': main()
