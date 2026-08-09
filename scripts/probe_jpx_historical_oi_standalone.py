#!/usr/bin/env python3
from __future__ import annotations
import json,re,requests
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
OUT=Path(__file__).resolve().parents[1]/'data/debug-jpx-historical-oi.json'
UA={'User-Agent':'Mozilla/5.0 market-report-maintenance/1.0'}
PAGES=[
 'https://www.jpx.co.jp/markets/statistics-derivatives/monthly-statistics/',
 'https://www.jpx.co.jp/markets/statistics-derivatives/monthly-quotations/',
 'https://www.jpx.co.jp/markets/statistics-derivatives/daily/',
 'https://www.jpx.co.jp/markets/statistics-derivatives/sector/',
]

def get(url):
 r=requests.get(url,headers=UA,timeout=30); r.raise_for_status(); return r.text

def scan(url):
 h=get(url); s=BeautifulSoup(h,'html.parser'); items=[]
 for a in s.find_all('a',href=True):
  href=urljoin(url,a['href']); txt=' '.join(a.stripped_strings); par=' '.join(a.parent.stripped_strings) if a.parent else ''
  if re.search(r'(2026|202607|20260731|\.xlsx|\.xls|\.csv|\.zip|\.pdf|archive|バックナンバー|建玉)',txt+' '+par+' '+href,re.I):
   items.append({'text':txt[:180],'parent':par[:300],'href':href})
 scripts=[urljoin(url,x['src']) for x in s.find_all('script',src=True)]
 return {'url':url,'items':items,'scripts':scripts,'htmlHints':[x[:500] for x in re.findall(r'.{0,160}(?:202607|monthly|archive|json).{0,300}',h,re.I)[:80]]}

def main():
 out={'pages':[],'follow':[]}
 for p in PAGES:
  try: out['pages'].append(scan(p))
  except Exception as e: out['pages'].append({'url':p,'error':repr(e)})
 follow=[]
 for p in out['pages']:
  for x in p.get('items',[]):
   h=x['href']
   if h.startswith('https://www.jpx.co.jp/') and h.endswith('.html') and h not in PAGES and ('archive' in h or 'back' in h or 'statistics-derivatives' in h): follow.append(h)
 for h in list(dict.fromkeys(follow))[:40]:
  try: out['follow'].append(scan(h))
  except Exception as e: out['follow'].append({'url':h,'error':repr(e)})
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'pages':len(out['pages']),'follow':len(out['follow'])},ensure_ascii=False))
if __name__=='__main__': main()
