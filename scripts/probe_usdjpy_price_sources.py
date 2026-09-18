"""One-off troubleshooting helper for USDJPY chart price providers."""
from __future__ import annotations
import re
import urllib.request
from io import BytesIO
from pypdf import PdfReader

urls = {
  'YahooJP': 'https://finance.yahoo.co.jp/quote/USDJPY=X/history',
  'Stooq': 'https://stooq.com/q/d/l/?s=usdjpy&i=d&d1=20260901&d2=20260918',
  'BOJ': 'https://www.boj.or.jp/statistics/market/forex/fxdaily/fxlist/fx260917.pdf',
}
for name,url in urls.items():
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36','Accept-Language':'ja,en-US;q=0.9,en;q=0.8'})
        with urllib.request.urlopen(request,timeout=20) as response:
            raw=response.read()
            print(name,'HTTP',response.status,'bytes',len(raw),'contentType',response.headers.get('Content-Type'))
        if name=='BOJ':
            text='\n'.join(p.extract_text() or '' for p in PdfReader(BytesIO(raw)).pages)
            print('BOJ pdf extract sample:',repr(text[:2600]))
        elif name=='Stooq':
            print('Stooq sample:',repr(raw[:450]))
        else:
            text=raw.decode('utf-8','replace')
            for marker in ('2026/9/17','2026/9/16','<table','__NEXT_DATA__'):
                print('YahooJP marker',marker,'position:',text.find(marker))
            print('YahooJP sample:',repr(re.sub(r'(?s)<script.*?</script>','',text)[:400]))
    except Exception as exc:
        print(name,'FAILED:',type(exc).__name__,str(exc))
