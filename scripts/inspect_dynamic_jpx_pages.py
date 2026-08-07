#!/usr/bin/env python3
from __future__ import annotations
import json,re,sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
import update_nikkei225_supply_demand as u
OUT=ROOT/'data/jpx-dynamic-page-inspection.json'
pages={
 'participantVolume':'https://www.jpx.co.jp/markets/derivatives/participant-volume/',
 'participantOpenInterest':'https://www.jpx.co.jp/markets/derivatives/open-interest/',
}
def inspect(name,url):
 r=u.get(url); html=r.text; soup=BeautifulSoup(html,'html.parser')
 scripts=[]
 for s in soup.find_all('script'):
  if s.get('src'): scripts.append(urljoin(url,s['src']))
 inline='\n'.join(s.get_text('\n') for s in soup.find_all('script') if not s.get('src'))
 hrefs=[urljoin(url,a['href']) for a in soup.find_all('a',href=True)]
 needles=[]
 for blob in (html,inline):
  for m in re.finditer(r'https?://[^\"\'<>\s]+|/automation/[^\"\'<>\s]+|[A-Za-z0-9_./-]+\.(?:csv|xlsx|pdf)',blob,re.I):
   v=m.group(0).replace('&amp;','&')
   if any(k in v.lower() for k in ('participant','open-interest','volume','tategyoku','automation')): needles.append(v[:500])
 return {'url':url,'scriptSrc':scripts,'fileHrefs':[x for x in hrefs if re.search(r'\.(csv|xlsx|pdf)(?:\?|$)',x,re.I)],'matches':list(dict.fromkeys(needles))[:300],'htmlHead':html[:1200]}
out={'generatedAt':u.now(),'pages':{k:inspect(k,v) for k,v in pages.items()}}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(OUT)
