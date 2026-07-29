(()=>{'use strict';
const A=v=>Array.isArray(v)?v:(v==null?[]:[v]);
const E=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
let report=null,scheduled=false;
async function load(){try{const res=await fetch(`reports.json?labels=${Date.now()}`,{cache:'no-store'});if(!res.ok)return;const j=await res.json();const list=Array.isArray(j)?j:A(j.reports);report=list.sort((a,b)=>new Date(`${b.date}T${b.time}:00+09:00`)-new Date(`${a.date}T${a.time}:00+09:00`))[0]||null;apply()}catch(e){console.error('summary labels',e)}}
function hit(name){return A(report?.markets).find(x=>(x.name||'').includes(name))}
function apply(){if(!report)return;const cards=[...document.querySelectorAll('#s1 .summary-card')];if(cards.length<5)return;const rate=A(report.rates).find(x=>(x.name||'').includes('米10年'));
const defs=[
 {title:'日経225先物',sub:'大阪取引所・株式',icon:'日経',m:hit('日経225先物')},
 {title:'USD/JPY',sub:'ドル円・為替',icon:'¥$',m:hit('USD/JPY')},
 {title:'米10年債利回り',sub:'米国債・金利',icon:'10Y',rate},
 {title:'WTI原油',sub:'原油・商品',icon:'WTI',m:hit('原油')},
 {title:'BTCUSD',sub:'ビットコイン',icon:'₿',m:hit('BTCUSD')}
];
cards.forEach((card,i)=>{const d=defs[i];if(!d)return;const h=card.querySelector('h3'),strong=card.querySelector('strong'),small=card.querySelector('small'),icon=card.querySelector('.summary-icon');if(icon)icon.textContent=d.icon;if(h)h.innerHTML=`<span class="summary-instrument">${E(d.title)}</span><span class="summary-category">${E(d.sub)}</span>`;if(d.m){if(strong)strong.textContent=d.m.direction||'中立';if(small)small.innerHTML=`<b>${E(d.m.price||'—')}</b><span>${E(d.m.shortOutlook||d.m.material||'')}</span>`}else if(d.rate){if(strong)strong.textContent='金利水準';if(small)small.innerHTML=`<b>${E(d.rate.value??'—')}%</b><span>水準と変化方向を確認</span>`}}
)}
const observer=new MutationObserver(()=>{if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;apply()})});observer.observe(document.documentElement,{childList:true,subtree:true});window.addEventListener('DOMContentLoaded',load);setInterval(load,300000);
})();
