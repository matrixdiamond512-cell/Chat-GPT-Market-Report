(()=>{
'use strict';
const originalFetch=window.fetch.bind(window);
const nativeDateNow=Date.now.bind(Date);
const INDEX_URL='data/usdjpy-supply-demand-archive/index.json';
const ARCHIVE_BASE='data/usdjpy-supply-demand-archive/';
const RAW_BASE='https://raw.githubusercontent.com/matrixdiamond512-cell/Chat-GPT-Market-Report';
const params=new URLSearchParams(location.search);
const requestedDate=params.get('date');
let historyNow=requestedDate?Date.parse(`${requestedDate}T23:59:59+09:00`):null;
let indexCache=null;
let entryPromise=null;
let bundlePromise=null;

const localMap=new Map([
  ['/data/market/latest.json','market'],
  ['/data/rates-bonds.json','rates'],
  ['/data/usdjpy-volume.json','volume'],
  ['/data/events.json','events'],
  ['/data/usdjpy-supply-demand.json','config']
]);
const sourcePaths={
  market:'data/market/latest.json',
  rates:'data/rates-bonds.json',
  volume:'data/usdjpy-volume.json',
  events:'data/events.json',
  config:'data/usdjpy-supply-demand.json'
};

if(requestedDate&&Number.isFinite(historyNow))Date.now=()=>historyNow;

async function jsonFetch(url){
  const r=await originalFetch(`${url}${url.includes('?')?'&':'?'}v=${nativeDateNow()}`,{cache:'no-store'});
  if(!r.ok)throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}
async function rawJson(commit,path){
  const url=`${RAW_BASE}/${encodeURIComponent(commit)}/${path}`;
  const r=await originalFetch(`${url}?v=${nativeDateNow()}`,{cache:'no-store'});
  if(!r.ok)throw new Error(`${path}@${commit}: HTTP ${r.status}`);
  return r.json();
}
async function commitBundle(commit){
  const entries=await Promise.all(Object.entries(sourcePaths).map(async([key,path])=>[key,await rawJson(commit,path)]));
  return Object.fromEntries(entries);
}
async function liveBundle(){
  const entries=await Promise.all(Object.entries(sourcePaths).map(async([key,path])=>[key,await jsonFetch(path)]));
  return Object.fromEntries(entries);
}
function reports(index){return Array.isArray(index?.reports)?index.reports.slice().sort((a,b)=>String(a.date).localeCompare(String(b.date))):[]}
function resolveEntry(index,date){
  const rows=reports(index);if(!rows.length)return null;
  if(!date)return rows.at(-1);
  const exact=rows.find(r=>r.date===date);if(exact)return exact;
  let prior=null;for(const row of rows){if(row.date<=date)prior=row;else break;}return prior||rows[0];
}
async function getIndex(){if(indexCache)return indexCache;indexCache=await jsonFetch(INDEX_URL);return indexCache}
async function getEntry(){
  if(entryPromise)return entryPromise;
  entryPromise=getIndex().then(index=>{
    const entry=resolveEntry(index,requestedDate);
    if(entry&&requestedDate){const t=Date.parse(`${entry.date}T23:59:59+09:00`);if(Number.isFinite(t))historyNow=t;}
    return entry;
  });
  return entryPromise;
}
async function getBundle(){
  if(bundlePromise)return bundlePromise;
  bundlePromise=(async()=>{
    const entry=await getEntry();
    if(!entry)throw new Error('保存済みUSD/JPY需給分析がありません');
    if(entry.live)return liveBundle();
    if(entry.file){
      try{return await jsonFetch(`${ARCHIVE_BASE}${entry.file}`)}catch(err){if(!entry.commit)throw err;}
    }
    if(entry.commit)return commitBundle(entry.commit);
    throw new Error('履歴データの保存先がありません');
  })();
  return bundlePromise;
}
function urlOf(input){try{return new URL(input instanceof Request?input.url:String(input),location.href)}catch{return null}}
function archivedKey(pathname){for(const [suffix,key] of localMap){if(pathname.endsWith(suffix))return key}return null}

if(requestedDate){
  window.__USDJPY_HISTORY_MODE__=true;
  window.fetch=async function(input,init){
    const u=urlOf(input);
    const key=archivedKey(u?.pathname||'');
    if(key){
      const bundle=await getBundle();
      const value=bundle?.[key];
      if(value===undefined)return new Response(JSON.stringify({}),{status:200,headers:{'Content-Type':'application/json'}});
      return new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
    }
    if(u&&(
      (u.hostname==='publicreporting.cftc.gov'&&u.pathname.includes('/resource/6dca-aqww.json'))||
      (u.hostname==='query1.finance.yahoo.com'&&u.pathname.includes('/v8/finance/chart/USDJPY'))
    )){
      return Promise.reject(new Error('過去表示では保存済みCFTC・USD/JPY履歴を使用します'));
    }
    return originalFetch(input,init);
  };
}

function fmt(v){return v?String(v).slice(0,10).replaceAll('-','/'):'取得不能'}
function navigate(date,latest){
  const u=new URL(location.href);
  if(latest)u.searchParams.delete('date');else u.searchParams.set('date',date);
  location.href=u.toString();
}
async function setupCalendar(){
  const shell=document.querySelector('[data-usdjpy-history]');
  const input=document.getElementById('usdHistoryDate');
  const prev=document.getElementById('usdHistoryPrev');
  const next=document.getElementById('usdHistoryNext');
  const status=document.getElementById('usdHistoryStatus');
  if(!shell||!input||!prev||!next||!status)return;
  try{
    const index=await getIndex();
    const rows=reports(index);
    if(!rows.length)throw new Error('保存済みレポートがありません');
    const latest=rows.at(-1);
    const current=requestedDate?resolveEntry(index,requestedDate):latest;
    if(!current)throw new Error('表示できるレポートがありません');
    const idx=rows.findIndex(r=>r.date===current.date);
    input.min=rows[0].date;input.max=latest.date;input.value=current.date;
    prev.disabled=idx<=0;next.disabled=idx<0||idx>=rows.length-1;
    const live=!requestedDate;
    status.textContent=`${live?'最新表示':'過去表示'}｜米国市場データ ${fmt(current.usDataDate)}｜東京市場データ ${fmt(current.tokyoDataDate)}｜CFTC ${fmt(current.cftcDate)}`;
    status.classList.toggle('is-history',!live);
    if(requestedDate&&requestedDate!==current.date){
      const u=new URL(location.href);u.searchParams.set('date',current.date);history.replaceState({},'',u.toString());
    }
    prev.addEventListener('click',()=>{if(idx>0)navigate(rows[idx-1].date,false)});
    next.addEventListener('click',()=>{if(idx<rows.length-1){const target=rows[idx+1];navigate(target.date,idx+1===rows.length-1)}});
    input.addEventListener('change',()=>{
      const target=resolveEntry(index,input.value);if(!target)return;
      navigate(target.date,target.date===latest.date);
    });
  }catch(err){
    prev.disabled=true;next.disabled=true;input.disabled=true;
    status.textContent=`履歴一覧を読み込めませんでした。最新データを表示します。理由：${err?.message||err}`;
    status.classList.add('is-error');
  }finally{shell.setAttribute('aria-busy','false')}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setupCalendar);else setupCalendar();
})();
