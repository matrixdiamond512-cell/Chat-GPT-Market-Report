(()=>{'use strict';
const A=v=>Array.isArray(v)?v:(v==null?[]:[v]);
const E=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const T=v=>typeof v==='string'?v:(v?.text||v?.summary||v?.title||v?.name||'');
const short=(v,n=150)=>{const s=T(v).replace(/\s+/g,' ').trim();return s.length>n?s.slice(0,n-1)+'…':s};
const dir=v=>/上昇|強気|買い/.test(v||'')?'up':/下落|弱気|売り/.test(v||'')?'down':'neutral';
let report=null,busy=false;
const keys={
 '日経225先物':['日経225先物','日経先物','日経平均'],
 'USD/JPY':['USD/JPY','ドル円','164円','163円'],
 'EUR/USD':['EUR/USD','ユーロドル'],
 '金':['金','ゴールド'],
 '原油':['WTI','原油'],
 'BTCUSD':['BTCUSD','BTC','ビットコイン']
};
function marketFor(name){return A(report?.markets).find(m=>(m.name||'')===name||keys[name]?.some(k=>(m.name||'').includes(k)))}
function sentences(v){return A(v).flatMap(x=>T(x).split(/(?<=[。！？])/)).map(x=>x.trim()).filter(Boolean)}
function specific(name,...sources){const kk=keys[name]||[name];return sentences(sources).find(s=>kk.some(k=>s.includes(k)))||''}
function materialPrice(name,m){const mat=T(m?.material),p=T(m?.price);if(mat&&keys[name]?.some(k=>mat.includes(k)))return mat;const looksPrice=p&&p.length<80&&(/\d/.test(p));return looksPrice?p:(mat||'取得不能')}
function fallbackBuy(name,m){const own=A(m?.buyReasons).map(T).filter(Boolean);if(own.length)return own;const x=specific(name,m?.mainScenario,m?.positioning,report?.mainScenario,report?.positioning,report?.crossAssetFlow);return x?[x]:['明確な買い材料はレポートに記載なし']}
function fallbackSell(name,m){const own=A(m?.sellReasons).map(T).filter(Boolean);if(own.length)return own;const x=specific(name,m?.risk,m?.alternativeScenario,m?.breakCondition,report?.alternativeScenario,report?.riskManagement,report?.breakConditions);return x?[x]:['明確な売り材料はレポートに記載なし']}
function setList(box,items){if(!box)return;box.innerHTML=`<b>${box.classList.contains('buy')?'買い材料':'売り材料'}</b><ul>${items.slice(0,2).map(x=>`<li>${E(short(x,110))}</li>`).join('')}</ul>`}
function enrichCards(){document.querySelectorAll('.market-card').forEach(card=>{const name=card.querySelector('.market-head h3')?.textContent?.trim();if(!name)return;const m=marketFor(name);if(!m)return;const price=card.querySelector('.market-price');if(price)price.textContent=materialPrice(name,m);setList(card.querySelector('.reason-box.buy'),fallbackBuy(name,m));setList(card.querySelector('.reason-box.sell'),fallbackSell(name,m));const meta=card.querySelectorAll('.market-meta>div span');const shortOut=m.shortOutlook||specific(name,m.positioning,m.mainScenario,report.mainScenario,report.positioning)||m.material||'記載なし';const medium=m.mediumOutlook||specific(name,m.alternativeScenario,report.alternativeScenario)||'中期見通しはレポートに記載なし';const event=m.keyEvent||specific(name,report.events)||A(report.events).slice(0,2).map(T).join(' / ')||'記載なし';if(meta[0])meta[0].textContent=short(shortOut,190);if(meta[1])meta[1].textContent=short(medium,190);if(meta[2])meta[2].textContent=short(event,150);card.dataset.enriched='1'})}
function score(){return A(report?.markets).reduce((n,m)=>n+(dir(m.direction)==='up'?1:dir(m.direction)==='down'?-1:0),0)}
function sticky(){if(document.querySelector('.sticky-causal-bar'))return;const s=score(),cls=s>1?'up':s<-1?'down':'neutral',decision=cls==='up'?'買い優勢':cls==='down'?'売り優勢':'中立';const theme=short(report.theme,72),rates=short(report.leadingMarket||'金利・為替の連動を確認',72),flow=short(A(report.crossAssetFlow)[0]||'資金フローを確認',72),pos=short(A(report.positioning)[0]||'需給・ポジションを確認',72);document.querySelector('.tabs')?.insertAdjacentHTML('afterend',`<section class="sticky-causal-bar"><button class="sticky-causal-toggle" aria-label="因果関係バーを開閉">⌄</button><div class="sticky-causal-step theme"><small>市場テーマ</small><b>${E(theme)}</b><span>今日の主材料</span></div><div class="sticky-causal-step rates"><small>金利・為替</small><b>${E(rates)}</b><span>伝播経路</span></div><div class="sticky-causal-step flow"><small>資金フロー</small><b>${E(flow)}</b><span>流出元・流入先</span></div><div class="sticky-causal-step position"><small>需給</small><b>${E(pos)}</b><span>ポジションの偏り</span></div><div class="sticky-causal-step decision ${cls}"><small>売買判断</small><b>${decision}</b><span>${s>0?'+':''}${s} / 6</span></div></section>`);document.querySelector('.sticky-causal-toggle')?.addEventListener('click',()=>document.querySelector('.sticky-causal-bar')?.classList.toggle('open'))}
async function load(){try{const q=await fetch(`reports.json?v6=${Date.now()}`,{cache:'no-store'});const j=await q.json();report=(Array.isArray(j)?j:A(j.reports)).sort((a,b)=>new Date(`${b.date}T${b.time}:00+09:00`)-new Date(`${a.date}T${a.time}:00+09:00`))[0];run()}catch(e){console.error('v6 content',e)}}
function run(){if(!report||busy)return;busy=true;requestAnimationFrame(()=>{sticky();enrichCards();busy=false})}
new MutationObserver(run).observe(document.documentElement,{childList:true,subtree:true});window.addEventListener('DOMContentLoaded',load);setInterval(load,300000);
})();
