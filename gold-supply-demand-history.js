(()=>{
'use strict';

const originalFetch=window.fetch.bind(window);
const INDEX_URL='data/gold-supply-demand-archive/index.json';
const ARCHIVE_BASE='data/gold-supply-demand-archive/';
const params=new URLSearchParams(location.search);
const requestedDate=params.get('date');
let indexCache=null;
let entryPromise=null;
let bundlePromise=null;

const localMap=new Map([
  ['/data/gold-supply-demand.json','gold'],
  ['/data/market/latest.json','market'],
  ['/data/gold-etf-flow-history.json','etfHistory']
]);

async function jsonFetch(url){
  const r=await originalFetch(`${url}${url.includes('?')?'&':'?'}v=${Date.now()}`,{cache:'no-store'});
  if(!r.ok)throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

function reports(index){
  return Array.isArray(index?.reports)
    ? index.reports.slice().sort((a,b)=>String(a.date).localeCompare(String(b.date)))
    : [];
}

function resolveEntry(index,date){
  const rows=reports(index);
  if(!rows.length)return null;
  if(!date)return rows.at(-1);
  const exact=rows.find(r=>r.date===date);
  if(exact)return exact;
  let prior=null;
  for(const row of rows){
    if(row.date<=date)prior=row;
    else break;
  }
  return prior||rows[0];
}

async function getIndex(){
  if(indexCache)return indexCache;
  indexCache=await jsonFetch(INDEX_URL);
  return indexCache;
}

async function getEntry(){
  if(entryPromise)return entryPromise;
  entryPromise=getIndex().then(index=>resolveEntry(index,requestedDate));
  return entryPromise;
}

async function getBundle(){
  if(bundlePromise)return bundlePromise;
  bundlePromise=(async()=>{
    const entry=await getEntry();
    if(!entry)throw new Error('保存済みゴールド需給分析がありません');
    return jsonFetch(`${ARCHIVE_BASE}${entry.file}`);
  })();
  return bundlePromise;
}

function urlOf(input){
  try{return new URL(input instanceof Request?input.url:String(input),location.href)}catch{return null}
}

function archivedKey(pathname){
  for(const [suffix,key] of localMap){
    if(pathname.endsWith(suffix))return key;
  }
  return null;
}

if(requestedDate){
  window.__GOLD_HISTORY_MODE__=true;
  window.fetch=async function(input,init){
    const u=urlOf(input);
    const key=archivedKey(u?.pathname||'');
    if(key){
      const bundle=await getBundle();
      const value=bundle?.[key];
      if(value===undefined){
        return new Response(JSON.stringify({}),{
          status:200,
          headers:{'Content-Type':'application/json','Cache-Control':'no-store'}
        });
      }
      return new Response(JSON.stringify(value),{
        status:200,
        headers:{'Content-Type':'application/json','Cache-Control':'no-store'}
      });
    }
    return originalFetch(input,init);
  };
}

function fmt(v){return v?String(v).slice(0,10).replaceAll('-','/'):'取得不能'}

function navigate(date,latest){
  const u=new URL(location.href);
  if(latest)u.searchParams.delete('date');
  else u.searchParams.set('date',date);
  location.href=u.toString();
}

async function setupCalendar(){
  const shell=document.querySelector('[data-gold-history]');
  const input=document.getElementById('goldHistoryDate');
  const prev=document.getElementById('goldHistoryPrev');
  const next=document.getElementById('goldHistoryNext');
  const status=document.getElementById('goldHistoryStatus');
  if(!shell||!input||!prev||!next||!status)return;

  try{
    const index=await getIndex();
    const rows=reports(index);
    if(!rows.length)throw new Error('保存済みレポートがありません');

    const latest=rows.at(-1);
    const current=requestedDate?resolveEntry(index,requestedDate):latest;
    if(!current)throw new Error('表示できるレポートがありません');
    const idx=rows.findIndex(r=>r.date===current.date);

    input.min=rows[0].date;
    input.max=latest.date;
    input.value=current.date;
    prev.disabled=idx<=0;
    next.disabled=idx<0||idx>=rows.length-1;

    const live=!requestedDate;
    status.textContent=`${live?'最新表示':'過去表示'}｜市場データ ${fmt(current.marketDataDate)}｜COMEX ${fmt(current.comexDate)}｜CFTC ${fmt(current.cftcDate)}｜ETF ${fmt(current.etfDate)}`;
    status.dataset.mode=live?'latest':'historical';

    if(requestedDate&&requestedDate!==current.date){
      const u=new URL(location.href);
      u.searchParams.set('date',current.date);
      history.replaceState({},'',u.toString());
    }

    prev.addEventListener('click',()=>{
      if(idx>0)navigate(rows[idx-1].date,false);
    });

    next.addEventListener('click',()=>{
      if(idx<rows.length-1){
        const target=rows[idx+1];
        navigate(target.date,idx+1===rows.length-1);
      }
    });

    input.addEventListener('change',()=>{
      const target=resolveEntry(index,input.value);
      if(!target)return;
      navigate(target.date,target.date===latest.date);
    });
  }catch(err){
    prev.disabled=true;
    next.disabled=true;
    input.disabled=true;
    status.textContent=`履歴一覧を読み込めませんでした。最新データを表示します。理由：${err?.message||err}`;
    status.dataset.mode='error';
  }finally{
    shell.setAttribute('aria-busy','false');
  }
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setupCalendar);
else setupCalendar();
})();
