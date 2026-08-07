#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
import update_nikkei225_supply_demand as u
OUT=ROOT/'data/nikkei225-options-file-inspection.json'
links=u.links(u.URLS['futures'])
files={}
for url,_ in links:
    if 'trade_summary_per_underlying.csv' in url: files['summary']=url
    if 'individual_options_quotes.csv' in url: files['quotes']=url
out={'generatedAt':u.now(),'files':{}}
for key,url in files.items():
    text=u.decode(u.get(url).content); rows=list(csv.reader(text.splitlines()))
    selected=[]
    for i,r in enumerate(rows):
        blob=' | '.join(u.txt(x) for x in r)
        keep=(key=='summary') or i<3 or re.search(r'NIKKEI 225|NK225|日経225|日経２２５',blob,re.I)
        if keep:
            selected.append({'row':i+1,'cells':[[j,u.txt(v)] for j,v in enumerate(r) if u.txt(v)]})
            if len(selected)>=500:break
    out['files'][key]={'url':url,'rowCount':len(rows),'rows':selected}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(OUT)
