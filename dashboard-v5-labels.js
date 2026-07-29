(()=>{'use strict';
const A=v=>Array.isArray(v)?v:(v==null?[]:[v]);
const E=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const T=v=>typeof v==='string'?v:(v?.text||v?.summary||v?.title||v?.name||'');
const D=v=>/上昇|強気|買い/.test(v||'')?'up':/下落|弱気|売り/.test(v||'')?'down':'neutral';
let report=null,scheduled=false;
async function load(){try{const res=await fetch(`reports.json?labels=${Date.now()}`,{cache:'no-store'});if(!res.ok)return;const j=await res.json();const list=Array.isArray(j)?j:A(j.reports);report=list.sort((a,b)=>new Date(`${b.date}T${b.time}:00+09:00`)-new Date(`${a.date}T${a.time}:00+09:00`))[0]||null;apply()}catch(e){console.error('summary labels',e)}}
function hit(name){return A(report?.markets).find(x=>(x.name||'').includes(name))}
function first(v,fallback='—'){return T(A(v).find(x=>T(x)))||fallback}
function card(d){const m=d.m||{},direction=m.direction||'中立',cls=D(direction),buy=first(m.buyReasons,'買い材料なし'),sell=first(m.sellReasons,'売り材料なし'),watch=m.watchPoint||m.keyLevel||m.breakCondition||m.keyEvent||'監視水準なし',change=m.change||m.dailyChange||'';return `<article class="card summary-card decision-card ${cls}" data-summary-symbol="${E(d.title)}"><span class="summary-icon">${E(d.icon)}</span><div class="summary-main"><h3><span class="summary-instrument">${E(d.title)}</span><span class="summary-category">${E(d.sub)}</span></h3><div class="summary-quote"><b>${E(m.price||'—')}</b>${change?`<span class="summary-change">${E(change)}</span>`:''}</div><span class="summary-direction ${cls}">${E(direction)}</span></div><div class="summary-decision"><div class="decision-row buy"><b>買い材料</b><span>${E(buy)}</span></div><div class="decision-row sell"><b>売り材料</b><span>${E(sell)}</span></div><div class="decision-row watch"><b>監視</b><span>${E(watch)}</span></div></div></article>`}
function apply(){if(!report)return;const grid=document.querySelector('#s1.summary-grid');if(!grid)return;const defs=[
 {title:'日経225先物',sub:'大阪取引所・株式',icon:'日経',m:hit('日経225先物')},
 {title:'USD/JPY',sub:'ドル円・為替',icon:'¥$',m:hit('USD/JPY')},
 {title:'EUR/USD',sub:'ユーロドル・為替',icon:'€$',m:hit('EUR/USD')},
 {title:'金',sub:'ゴールド・商品',icon:'Au',m:hit('金')},
 {title:'WTI原油',sub:'原油・商品',icon:'WTI',m:hit('原油')},
 {title:'BTCUSD',sub:'ビットコイン',icon:'₿',m:hit('BTCUSD')}
];
const key=defs.map(d=>`${d.title}:${d.m?.price||''}:${d.m?.direction||''}:${first(d.m?.buyReasons,'')}:${first(d.m?.sellReasons,'')}:${d.m?.breakCondition||''}`).join('|');if(grid.dataset.summaryKey===key&&grid.children.length===6)return;grid.dataset.summaryKey=key;grid.innerHTML=defs.map(card).join('')}
const observer=new MutationObserver(()=>{if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;apply()})});observer.observe(document.documentElement,{childList:true,subtree:true});window.addEventListener('DOMContentLoaded',load);setInterval(load,300000);
})();
