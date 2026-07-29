(()=>{'use strict';
const A=v=>Array.isArray(v)?v:(v==null?[]:[v]);
const E=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const T=v=>typeof v==='string'?v:(v?.text||v?.summary||v?.title||v?.name||'');
const firstArray=(r,keys)=>{for(const k of keys){const v=k.split('.').reduce((o,p)=>o?.[p],r);if(Array.isArray(v)&&v.length)return v}return[]};
const value=x=>x?.contribution??x?.change??x?.changePct??x?.rate??x?.percent??x?.performance??'';
const reason=x=>x?.reason??x?.driver??x?.catalyst??x?.riseReason??x?.fallReason??x?.boughtReason??x?.soldReason??'';
const num=v=>{const m=String(v??'').replace(/,/g,'').match(/-?\d+(?:\.\d+)?/);return m?Number(m[0]):0};
const normalize=(arr,mode)=>A(arr).map(x=>typeof x==='string'?{name:x}:{...x,name:x.name||x.title||x.symbol||x.ticker||T(x)}).filter(x=>x.name).sort((a,b)=>mode==='asc'?num(value(a))-num(value(b)):num(value(b))-num(value(a))).slice(0,5);
const empty=label=>`<p class="muted data-missing">取得不能（${E(label)}のTop5データがレポート本文・構造化データに未収録）</p>`;
function bars(arr,kind,label){const data=normalize(arr,kind==='negative'||kind==='loser'?'asc':'desc');if(!data.length)return empty(label);const max=Math.max(...data.map(x=>Math.abs(num(value(x)))),1);return `<div class="equity-bars">${data.map((x,i)=>{const v=value(x),w=Math.max(8,Math.min(100,Math.abs(num(v))/max*100)),r=reason(x);return `<div class="equity-item ${kind}"><div class="equity-line"><span class="rank">${i+1}</span><span class="equity-name">${E(x.name)}</span><b>${E(v||'取得不能')}</b></div><div class="equity-track"><i style="width:${w}%"></i></div>${r?`<small>${E(r)}</small>`:''}</div>`}).join('')}</div>`}
function reportArrays(r){return{
 usSectors:firstArray(r,['usSectors','usSectorPerformance','usMarketSectors','equities.usSectors','stockMarket.usSectors']),
 jpSectors:firstArray(r,['japanSectors','tokyoSectors','japanSectorPerformance','equities.japanSectors','stockMarket.japanSectors']),
 nkPos:firstArray(r,['nikkeiPositiveContributors','nikkei225PositiveContributors','nikkeiContributors.positive','equities.nikkeiPositive']),
 nkNeg:firstArray(r,['nikkeiNegativeContributors','nikkei225NegativeContributors','nikkeiContributors.negative','equities.nikkeiNegative']),
 gainers:firstArray(r,['usTopGainers','usGainers','usMarketGainers','equities.usTopGainers','stockMarket.usTopGainers']),
 losers:firstArray(r,['usTopLosers','usLosers','usMarketLosers','equities.usTopLosers','stockMarket.usTopLosers'])
}}
function replaceCard(card,title,html){if(!card)return;const h=card.querySelector('h2');if(h)h.textContent=title;[...card.children].filter(x=>x!==h).forEach(x=>x.remove());card.insertAdjacentHTML('beforeend',html)}
function apply(r){const grid=document.querySelector('#s7.depth-grid');if(!grid)return;const cards=[...grid.querySelectorAll(':scope > .card')];if(cards.length<4)return;const d=reportArrays(r);
 replaceCard(cards[0],'米国市場のセクター・業種 Top5',bars(d.usSectors,'positive','米国市場セクター・業種'));
 replaceCard(cards[1],'東京市場のセクター・業種 Top5',bars(d.jpSectors,'positive','東京市場セクター・業種'));
 replaceCard(cards[2],'日経225 寄与度 Top5',`<div class="dual equity-dual"><div><div class="subhead positive">プラス寄与 Top5</div>${bars(d.nkPos,'positive','日経225プラス寄与度')}</div><div><div class="subhead negative">マイナス寄与 Top5</div>${bars(d.nkNeg,'negative','日経225マイナス寄与度')}</div></div>`);
 replaceCard(cards[3],'米国市場の大幅上昇・下落 Top5',`<div class="dual equity-dual"><div><div class="subhead positive">大幅上昇 Top5</div>${bars(d.gainers,'gainer','米国市場大幅上昇銘柄')}</div><div><div class="subhead negative">大幅下落 Top5</div>${bars(d.losers,'loser','米国市場大幅下落銘柄')}</div></div>`);
 grid.dataset.equityV7='1'}
let report=null,busy=false;
async function load(){try{const q=await fetch(`reports.json?equity=${Date.now()}`,{cache:'no-store'});if(!q.ok)return;const j=await q.json(),list=Array.isArray(j)?j:A(j.reports);report=list.sort((a,b)=>new Date(`${b.date}T${b.time}:00+09:00`)-new Date(`${a.date}T${a.time}:00+09:00`))[0]||null;run()}catch(e){console.error('equity v7',e)}}
function run(){if(!report||busy)return;busy=true;requestAnimationFrame(()=>{apply(report);busy=false})}
new MutationObserver(run).observe(document.documentElement,{childList:true,subtree:true});window.addEventListener('DOMContentLoaded',load);setInterval(load,300000);
})();