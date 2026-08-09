(function(){
'use strict';

const DATA_URL='data/gold-supply-demand.json';
let installPromise=null;
let fullHistory=[];
let activeWeeks=52;
let currentCot=null;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const fmt=(v,d=0)=>n(v)===null?'取得待ち':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=0,suffix='')=>n(v)===null?'—':`${Number(v)>0?'+':''}${fmt(v,d)}${suffix}`;
const cls=v=>n(v)>0?'up':n(v)<0?'down':'';

function injectRangeStyles(){
  if(document.getElementById('gold-cftc-range-style'))return;
  const style=document.createElement('style');
  style.id='gold-cftc-range-style';
  style.textContent=`
    .gold-cftc-head-tools{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}
    .gold-cftc-range{display:inline-flex;padding:2px;border:1px solid #b9cbe2;border-radius:999px;background:#fff;box-shadow:0 1px 3px rgba(18,59,120,.08)}
    .gold-cftc-range button{appearance:none;border:0;background:transparent;color:#36577f;font:800 11px/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;padding:4px 10px;border-radius:999px;cursor:pointer}
    .gold-cftc-range button.is-active{background:#123b78;color:#fff}
    .gold-cftc-range button:focus-visible{outline:2px solid #72a6e6;outline-offset:1px}
    @media(max-width:760px){.gold-cftc-head-tools{width:100%;justify-content:space-between}.gold-cftc-range button{padding:4px 9px}}
  `;
  document.head.appendChild(style);
}

function judgement(change){
  if(n(change)===null)return'判定待ち';
  if(Number(change)>0)return'買い越し拡大';
  if(Number(change)<0)return'買い越し縮小';
  return'横ばい';
}

function pctChange(change,previousNet){
  if(n(change)===null||n(previousNet)===null||Number(previousNet)===0)return null;
  return Number(change)/Math.abs(Number(previousNet))*100;
}

function findCftcCard(){
  const titles=[...document.querySelectorAll('.gold-section-title')];
  const title=titles.find(el=>el.textContent.trim()==='CFTC投機筋ポジション');
  return title?title.closest('.gold-card'):null;
}

function rangeHistory(){
  const requested=activeWeeks;
  return fullHistory.slice(-requested);
}

function buildSvg(history,weeks){
  const W=1020,H=430,m={t:28,r:82,b:46,l:82};
  const pw=W-m.l-m.r,ph=H-m.t-m.b;
  const nets=history.map(d=>n(d.net)).filter(v=>v!==null);
  const longs=history.map(d=>n(d.long)).filter(v=>v!==null);
  const shorts=history.map(d=>n(d.short)).filter(v=>v!==null);
  const prices=history.map(d=>n(d.goldPrice)).filter(v=>v!==null);
  const magnitude=Math.max(100000,...nets.map(Math.abs),...longs.map(Math.abs),...shorts.map(Math.abs));
  const yMax=Math.ceil(magnitude/50000)*50000;
  const yMin=-yMax;
  const priceMin=prices.length?Math.floor(Math.min(...prices)/100)*100:0;
  const priceMax=prices.length?Math.ceil(Math.max(...prices)/100)*100:1;
  const px=i=>m.l+(pw*i/Math.max(1,history.length-1));
  const py=v=>m.t+((yMax-v)/(yMax-yMin))*ph;
  const pyp=v=>m.t+((priceMax-v)/Math.max(1,priceMax-priceMin))*ph;
  const zero=py(0);
  const barW=Math.max(5,Math.min(24,pw/history.length*.58));

  const gridVals=[-yMax,-yMax/2,0,yMax/2,yMax];
  const grid=gridVals.map(v=>`<g><line x1="${m.l}" y1="${py(v)}" x2="${m.l+pw}" y2="${py(v)}" class="gold-cftc-grid"/><text x="${m.l-10}" y="${py(v)+4}" text-anchor="end" class="gold-cftc-axis-text">${fmt(v,0)}</text></g>`).join('');

  const bars=history.map((d,i)=>{
    const x=px(i),long=n(d.long)||0,short=n(d.short)||0;
    const longY=py(long),shortY=py(-short);
    return `<rect x="${x-barW/2}" y="${longY}" width="${barW}" height="${Math.max(0,zero-longY)}" class="gold-cftc-bar-long"/><rect x="${x-barW/2}" y="${zero}" width="${barW}" height="${Math.max(0,shortY-zero)}" class="gold-cftc-bar-short"/>`;
  }).join('');

  const netPts=history.map((d,i)=>n(d.net)===null?null:[px(i),py(Number(d.net))]).filter(Boolean);
  const netPath=netPts.map((p,i)=>`${i?'L':'M'}${p[0]},${p[1]}`).join(' ');
  const pricePts=history.map((d,i)=>n(d.goldPrice)===null?null:[px(i),pyp(Number(d.goldPrice))]).filter(Boolean);
  const pricePath=pricePts.map((p,i)=>`${i?'L':'M'}${p[0]},${p[1]}`).join(' ');

  const rawTicks=weeks===52?[0,13,26,39,history.length-1]:[0,5,10,15,20,history.length-1];
  const tickCandidates=[...new Set(rawTicks.map(v=>Math.max(0,Math.min(history.length-1,v))))];
  const xTicks=tickCandidates.map(idx=>{
    const weeksAgo=history.length-1-idx;
    const label=idx===history.length-1?'今週':`${weeksAgo}週前`;
    return `<g><line x1="${px(idx)}" y1="${m.t+ph}" x2="${px(idx)}" y2="${m.t+ph+6}" class="gold-cftc-axis"/><text x="${px(idx)}" y="${m.t+ph+23}" text-anchor="middle" class="gold-cftc-axis-text">${label}</text></g>`;
  }).join('');

  const priceTicks=[priceMin,(priceMin+priceMax)/2,priceMax].map(v=>`<text x="${m.l+pw+10}" y="${pyp(v)+4}" class="gold-cftc-axis-text">${fmt(v,0)}</text>`).join('');
  const netDots=netPts.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="${history.length>30?2:2.4}" class="gold-cftc-point-net"/>`).join('');
  const priceDots=pricePts.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="${history.length>30?1.8:2.2}" class="gold-cftc-point-price"/>`).join('');

  return `<svg viewBox="0 0 ${W} ${H}" class="gold-cftc-svg" role="img" aria-label="CFTC Managed Money ${weeks}週推移。Long、Short、Netと金価格を表示。"><text x="${m.l}" y="16" class="gold-cftc-axis-title">枚数（枚）</text><text x="${m.l+pw+10}" y="16" class="gold-cftc-axis-title">金価格（USD/oz）</text>${grid}<line x1="${m.l}" y1="${zero}" x2="${m.l+pw}" y2="${zero}" class="gold-cftc-zero"/>${bars}${netPath?`<path d="${netPath}" class="gold-cftc-net-line"/>${netDots}`:''}${pricePath?`<path d="${pricePath}" class="gold-cftc-price-line"/>${priceDots}`:''}${xTicks}${priceTicks}</svg>`;
}

function statusLabel(cot,history){
  const count=history.length;
  if(cot.historyStatus==='verified')return`${count}週取得済み`;
  if(cot.historyStatus==='stale')return`前回${count}週履歴`;
  return'履歴取得待ち';
}

function renderInner(cot){
  const history=rangeHistory();
  const latest=history.length?history[history.length-1]:{};
  const previous=history.length>1?history[history.length-2]:{};
  const net=n(cot.managedMoneyNet)!==null?cot.managedMoneyNet:latest.net;
  const netChange=n(cot.managedMoneyNetChange)!==null?cot.managedMoneyNetChange:latest.netChange;
  const long_=n(cot.managedMoneyLong)!==null?cot.managedMoneyLong:latest.long;
  const short=n(cot.managedMoneyShort)!==null?cot.managedMoneyShort:latest.short;
  const longChange=n(cot.managedMoneyLongChange)!==null?cot.managedMoneyLongChange:latest.longChange;
  const shortChange=n(cot.managedMoneyShortChange)!==null?cot.managedMoneyShortChange:latest.shortChange;
  const netPct=pctChange(netChange,previous.net);
  const requested=activeWeeks;

  return `<div class="gold-section-body"><p class="gold-cftc-history-intro">CFTC Managed Money の${requested}週推移から、投機筋の買い越し・売り越しの変化と金価格との整合性を確認します。</p><div class="gold-cftc-kpis"><div class="gold-cftc-kpi"><div class="label">Net</div><div class="value ${cls(net)}">${signed(net,0,'枚')}</div><div class="sub">前週比 <span class="${cls(netChange)}">${signed(netChange,0,'枚')}</span></div></div><div class="gold-cftc-kpi"><div class="label">前週比</div><div class="value ${cls(netChange)}">${signed(netChange,0,'枚')}</div><div class="sub">${netPct===null?'—':signed(netPct,1,'%')}</div></div><div class="gold-cftc-kpi long"><div class="label">Long</div><div class="value">${fmt(long_,0)}枚</div><div class="sub">前週比 <span class="${cls(longChange)}">${signed(longChange,0,'枚')}</span></div></div><div class="gold-cftc-kpi short"><div class="label">Short</div><div class="value">${fmt(short,0)}枚</div><div class="sub">前週比 <span class="${cls(shortChange)}">${signed(shortChange,0,'枚')}</span></div></div><div class="gold-cftc-kpi judge"><div class="label">判定</div><div class="value">${esc(judgement(netChange))}</div><div class="sub">${esc(cot.judgement||'週次ポジションから判定')}</div></div></div>${history.length>=2?`<div class="gold-cftc-chart-shell">${buildSvg(history,requested)}<div class="gold-cftc-legend"><span><i class="long"></i>Long（買い）</span><span><i class="short"></i>Short（売り）</span><span><i class="net"></i>Net（買い越し）</span><span><i class="price"></i>金価格（右軸）</span></div></div>`:`<div class="gold-cftc-empty">CFTC ${requested}週時系列を取得中です。次回のゴールド需給更新後にグラフを表示します。</div>`}<div class="gold-cftc-read"><b>読み方</b><ul><li>Net上昇＝投機筋の買い越し拡大</li><li>Net下降＝買い越し縮小、または売り圧力の増加</li><li>金価格とNetが逆行する場合は、値動きとポジションの乖離に注意</li><li>CFTCは週次公表のため、日次データより遅行します</li></ul></div><div class="gold-cftc-foot"><span>出典：<a href="${esc(cot.sourceUrl||'https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm')}" target="_blank" rel="noopener">${esc(cot.sourceName||'CFTC Commitments of Traders')}</a></span><span>単位：枚（COMEX Gold futures 1枚＝100トロイオンス）</span></div></div>`;
}

function renderCard(cot){
  currentCot=cot;
  fullHistory=Array.isArray(cot.historyWeeks)?cot.historyWeeks:[];
  const initialHistory=rangeHistory();
  return `<article class="gold-card gold-cftc-history-card" data-cftc-history-card><div class="gold-section-head"><h2 class="gold-section-title">投機筋ポジション推移</h2><div class="gold-cftc-head-tools"><div class="gold-cftc-range" role="group" aria-label="CFTC表示期間"><button type="button" data-weeks="26">26週</button><button type="button" data-weeks="52" class="is-active">52週</button></div><span class="gold-frequency" data-gold-cftc-frequency>週次・${esc(statusLabel(cot,initialHistory))}</span></div></div><div data-gold-cftc-body>${renderInner(cot)}</div></article>`;
}

function rerenderRange(card){
  if(!card||!currentCot)return;
  const body=card.querySelector('[data-gold-cftc-body]');
  const badge=card.querySelector('[data-gold-cftc-frequency]');
  const history=rangeHistory();
  if(body)body.innerHTML=renderInner(currentCot);
  if(badge)badge.textContent=`週次・${statusLabel(currentCot,history)}`;
}

function installRangeEvents(card){
  if(!card||card.dataset.rangeReady==='1')return;
  card.dataset.rangeReady='1';
  card.addEventListener('click',e=>{
    const btn=e.target.closest('button[data-weeks]');
    if(!btn)return;
    activeWeeks=Number(btn.dataset.weeks)||52;
    card.querySelectorAll('.gold-cftc-range button').forEach(b=>b.classList.toggle('is-active',b===btn));
    rerenderRange(card);
  });
}

async function install(){
  const existing=document.querySelector('[data-cftc-history-card]');
  if(existing){installRangeEvents(existing);return true;}
  if(installPromise)return installPromise;
  const anchor=findCftcCard();
  if(!anchor)return false;

  installPromise=(async()=>{
    try{
      const r=await fetch(`${DATA_URL}?ts=${Date.now()}`,{cache:'no-store'});
      if(!r.ok)throw new Error(`HTTP ${r.status}`);
      const data=await r.json();
      if(!document.querySelector('[data-cftc-history-card]')){
        anchor.insertAdjacentHTML('afterend',renderCard(data.cftc||{}));
      }
      installRangeEvents(document.querySelector('[data-cftc-history-card]'));
    }catch(err){
      if(!document.querySelector('[data-cftc-history-card]')){
        anchor.insertAdjacentHTML('afterend',`<article class="gold-card gold-cftc-history-card" data-cftc-history-card><div class="gold-section-head"><h2 class="gold-section-title">投機筋ポジション推移</h2><span class="gold-frequency">週次</span></div><div class="gold-section-body"><div class="gold-cftc-empty">CFTC時系列データの読み込みに失敗しました。再読込してください。</div></div></article>`);
      }
    }
    return true;
  })().finally(()=>{installPromise=null;});

  return installPromise;
}

async function waitForBaseRender(){
  injectRangeStyles();
  if(await install())return;
  const root=document.querySelector('[data-gold-dashboard]')||document.body;
  const observer=new MutationObserver(async()=>{if(await install())observer.disconnect();});
  observer.observe(root,{childList:true,subtree:true});
  setTimeout(()=>observer.disconnect(),15000);
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{void waitForBaseRender();},{once:true});else void waitForBaseRender();
})();
