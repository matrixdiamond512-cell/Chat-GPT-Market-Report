(function(){
'use strict';
const root=document.querySelector('[data-nikkei-dashboard]');
if(!root)return;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>{if(v===null||v===undefined||v==='')return null;const x=Number(v);return Number.isFinite(x)?x:null};
const fmt=(v,d=0)=>num(v)===null?'取得待ち':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=0,suffix='')=>num(v)===null?'—':`${Number(v)>0?'+':''}${Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d})}${suffix}`;
const date=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得待ち';
let activeWeeks=52;
function statusClass(text){if(/買い越し拡大/.test(text||''))return'nikkei-status-good';if(/売り越し拡大/.test(text||''))return'nikkei-status-bad';if(/縮小/.test(text||''))return'nikkei-status-warn';return'nikkei-status-purple';}
function yScale(v,min,max,top,h){if(max===min)return top+h/2;return top+(max-v)/(max-min)*h;}
function niceStep(span,target){if(!Number.isFinite(span)||span<=0)return 1;const raw=span/target;const power=Math.pow(10,Math.floor(Math.log10(raw)));const n=raw/power;const step=n<=1?1:n<=2?2:n<=5?5:10;return step*power;}
function injectStyles(){
 if(document.getElementById('nikkei-cftc-range-style'))return;
 const s=document.createElement('style');s.id='nikkei-cftc-range-style';s.textContent=`
 .nikkei-cftc-head-tools{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}
 .nikkei-cftc-range{display:inline-flex;padding:2px;border:1px solid #b9cbe2;border-radius:999px;background:#fff;box-shadow:0 1px 3px rgba(18,59,120,.08)}
 .nikkei-cftc-range button{appearance:none;border:0;background:transparent;color:#36577f;font:800 11px/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;padding:4px 10px;border-radius:999px;cursor:pointer}
 .nikkei-cftc-range button.is-active{background:#123b78;color:#fff}
 .nikkei-cftc-range button:focus-visible{outline:2px solid #72a6e6;outline-offset:1px}
 @media(max-width:760px){.nikkei-section-head{flex-wrap:wrap}.nikkei-cftc-head-tools{width:100%;justify-content:space-between}.nikkei-cftc-range button{padding:4px 9px}}
 `;document.head.appendChild(s);
}
function labelSeries(series){const last=series.length-1;return series.map((d,i)=>({...d,label:i===last?'今週':`${last-i}週前`}));}
function sliceSeries(sp,weeks){const all=Array.isArray(sp.series)?sp.series:[];return labelSeries(all.slice(-weeks));}
function svgChart(series,weeks){
 if(series.length<2)return`<div class="nikkei-position-empty">${weeks}週推移を描画できるだけのデータがありません。</div>`;
 const W=1000,H=390,L=70,R=78,T=30,B=52,pw=W-L-R,ph=H-T-B;
 const posVals=[];series.forEach(x=>{const l=num(x.long),s=num(x.short),net=num(x.net);if(l!==null)posVals.push(l);if(s!==null)posVals.push(-s);if(net!==null)posVals.push(net)});
 let min=Math.min(0,...posVals),max=Math.max(0,...posVals);let span=max-min;if(!Number.isFinite(span)||span===0){min=-1;max=1;span=2}
 const pad=span*.08;min-=pad;max+=pad;const pstep=niceStep(max-min,5);min=Math.floor(min/pstep)*pstep;max=Math.ceil(max/pstep)*pstep;
 const prices=series.map(x=>num(x.price)).filter(v=>v!==null);let pmin=null,pmax=null,pprice=false;if(prices.length>=2){pmin=Math.min(...prices);pmax=Math.max(...prices);const pspan=pmax-pmin||1;pmin-=pspan*.08;pmax+=pspan*.08;pprice=true}
 const x=i=>L+(series.length===1?pw/2:i*pw/(series.length-1));const barW=Math.max(5,Math.min(22,pw/series.length*.55));
 let out=`<svg class="nikkei-position-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="CFTC Leveraged Funds ${weeks}週ポジション推移">`;
 out+=`<text x="${L}" y="15" class="axis-title">枚数（枚）</text>`;if(pprice)out+=`<text x="${W-R}" y="15" text-anchor="end" class="axis-title">日経225（右軸）</text>`;
 for(let i=0;i<=5;i++){const v=min+(max-min)*i/5;const yy=yScale(v,min,max,T,ph);out+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" class="grid-line"/><text x="${L-10}" y="${yy+4}" text-anchor="end" class="axis-label">${esc(Math.round(v).toLocaleString('ja-JP'))}</text>`}
 if(pprice){for(let i=0;i<=2;i++){const v=pmin+(pmax-pmin)*i/2;const yy=T+ph-i*ph/2;out+=`<text x="${W-R+10}" y="${yy+4}" class="axis-label">${esc(Math.round(v).toLocaleString('ja-JP'))}</text>`}}
 const zero=yScale(0,min,max,T,ph);out+=`<line x1="${L}" x2="${W-R}" y1="${zero}" y2="${zero}" class="zero-line"/>`;
 series.forEach((d,i)=>{const xx=x(i),lv=num(d.long),sv=num(d.short);if(lv!==null){const yy=yScale(lv,min,max,T,ph);out+=`<rect x="${xx-barW/2}" y="${yy}" width="${barW}" height="${Math.max(0,zero-yy)}" rx="2" class="bar-long"/>`}if(sv!==null){const yy=yScale(-sv,min,max,T,ph);out+=`<rect x="${xx-barW/2}" y="${zero}" width="${barW}" height="${Math.max(0,yy-zero)}" rx="2" class="bar-short"/>`}});
 const netPts=series.map((d,i)=>{const v=num(d.net);return v===null?null:`${x(i)},${yScale(v,min,max,T,ph)}`}).filter(Boolean);if(netPts.length>=2){out+=`<polyline points="${netPts.join(' ')}" class="line-net"/>`;series.forEach((d,i)=>{const v=num(d.net);if(v!==null)out+=`<circle cx="${x(i)}" cy="${yScale(v,min,max,T,ph)}" r="${series.length>30?2.1:2.6}" class="dot-net"/>`})}
 if(pprice){const chunks=[];let chunk=[];series.forEach((d,i)=>{const v=num(d.price);if(v===null){if(chunk.length)chunks.push(chunk);chunk=[]}else chunk.push(`${x(i)},${yScale(v,pmin,pmax,T,ph)}`)});if(chunk.length)chunks.push(chunk);chunks.filter(c=>c.length>=2).forEach(c=>{out+=`<polyline points="${c.join(' ')}" class="line-price"/>`});series.forEach((d,i)=>{const v=num(d.price);if(v!==null)out+=`<circle cx="${x(i)}" cy="${yScale(v,pmin,pmax,T,ph)}" r="${series.length>30?1.9:2.2}" class="dot-price"/>`})}
 const anchors=weeks===52?[0,13,26,39,series.length-1]:[0,5,10,15,20,series.length-1];
 [...new Set(anchors.map(i=>Math.min(Math.max(i,0),series.length-1)))].forEach(i=>{out+=`<text x="${x(i)}" y="${H-24}" text-anchor="middle" class="axis-label x-label">${esc(series[i].label||'')}</text>`});
 out+='</svg>';return out;
}
function findGrid(){return root.querySelector('.nikkei-grid');}
function findAi(){return root.querySelector('.nikkei-ai');}
function paint(card,sp){
 const state=sp.status||'unavailable';const all=Array.isArray(sp.series)?sp.series:[];const series=sliceSeries(sp,activeWeeks);const usable=(state==='verified'||state==='stale')&&series.length>=2;
 const latest=series.at(-1)||sp.latest||{};const prev=series.length>1?series.at(-2):null;
 const latestNet=num(latest.net),latestLong=num(latest.long),latestShort=num(latest.short);
 const netChange=prev&&latestNet!==null&&num(prev.net)!==null?latestNet-num(prev.net):num((sp.latest||{}).netChange);
 const longChange=prev&&latestLong!==null&&num(prev.long)!==null?latestLong-num(prev.long):num((sp.latest||{}).longChange);
 const shortChange=prev&&latestShort!==null&&num(prev.short)!==null?latestShort-num(prev.short):num((sp.latest||{}).shortChange);
 const judge=(sp.latest||{}).judgement||'判定待ち';const judgeSub=(sp.latest||{}).judgementSub||'';
 const verified=series.filter(d=>num(d.long)!==null&&num(d.short)!==null).length;const pricePoints=series.filter(d=>num(d.price)!==null).length;
 const tools=`<div class="nikkei-cftc-head-tools"><div class="nikkei-cftc-range" role="group" aria-label="CFTC表示期間"><button type="button" data-weeks="26" class="${activeWeeks===26?'is-active':''}">26週</button><button type="button" data-weeks="52" class="${activeWeeks===52?'is-active':''}">52週</button></div><span class="nikkei-freq weekly">週次・${activeWeeks}週 / ${verified}点確認済み</span></div>`;
 let body='';
 if(usable){
  body=`<div class="nikkei-position-intro">CFTCの金融先物用TFFから、CME円建て日経225先物の <b>Leveraged Funds</b> を直近${activeWeeks}週で追跡します。ゴールドのManaged Moneyとは分類体系が異なり、OSE先物やJPX投資部門別とは別の中期補助指標です。</div>
  <div class="nikkei-position-stats">
   <div class="nikkei-position-stat"><span>Net</span><b class="${latestNet>=0?'nikkei-up':'nikkei-down'}">${signed(latestNet,0,'枚')}</b><small>前週比 ${signed(netChange,0,'枚')}</small></div>
   <div class="nikkei-position-stat"><span>前週比</span><b class="${netChange>=0?'nikkei-up':'nikkei-down'}">${signed(netChange,0,'枚')}</b><small>Net変化</small></div>
   <div class="nikkei-position-stat long"><span>Long</span><b>${fmt(latestLong)}枚</b><small>前週比 ${signed(longChange,0,'枚')}</small></div>
   <div class="nikkei-position-stat short"><span>Short</span><b>${fmt(latestShort)}枚</b><small>前週比 ${signed(shortChange,0,'枚')}</small></div>
   <div class="nikkei-position-stat judge"><span>判定</span><b class="${statusClass(judge)}">${esc(judge)}</b><small>${esc(judgeSub)}</small></div>
  </div>
  <div class="nikkei-position-chart-scroll">${svgChart(series,activeWeeks)}</div>
  <div class="nikkei-position-legend"><span><i class="lg-box long"></i>Long（買い）</span><span><i class="lg-box short"></i>Short（売り）</span><span><i class="lg-line net"></i>Net（買い越し）</span>${pricePoints>=2?'<span><i class="lg-line price"></i>日経225現物（右軸）</span>':''}</div>
  ${pricePoints<series.length?`<div class="nikkei-note">日経225価格線は確認済みの${pricePoints}週分を表示し、未取得期間は推測で補完しません。</div>`:''}
  <div class="nikkei-callout">${esc(sp.comment||'')}</div>
  ${state==='stale'?`<div class="nikkei-callout nikkei-position-warning">最新取得に失敗したため前回の検証済みデータを表示しています。${esc(sp.error||'')}</div>`:''}
  <div class="nikkei-source">出典：<a href="${esc(sp.sourceUrl||'#')}" target="_blank" rel="noopener">${esc(sp.sourceName||'CFTC TFF')}</a> / CFTCコード ${esc(sp.cftcContractMarketCode||'240743')} / 基準日 ${esc(date(sp.asOfDate))}${pricePoints>=2?`<br>価格線：<a href="${esc(sp.priceSourceUrl||'#')}" target="_blank" rel="noopener">${esc(sp.priceSourceName||'日経225価格')}</a>`:''}</div>`;
 }else{
  body=`<div class="nikkei-error"><b>CFTC投機筋ポジション：取得不能</b><br>${esc(sp.error||'CFTC TFFの検証済みデータがまだありません。')}</div><div class="nikkei-note">数値は推測・代用しません。次回データ更新時にCFTC公式TFFを再取得します。</div>`;
 }
 card.innerHTML=`<div class="nikkei-section-head"><h2 class="nikkei-section-title">10. 海外投機筋ポジション推移（CFTC・週次）</h2>${tools}</div><div class="nikkei-section-body">${body}</div>`;
 card.querySelectorAll('.nikkei-cftc-range button[data-weeks]').forEach(btn=>btn.addEventListener('click',()=>{activeWeeks=Number(btn.dataset.weeks)||52;paint(card,sp)}));
}
function render(d){
 let card=root.querySelector('[data-cftc-positioning]');
 if(card)return true;
 const grid=findGrid();if(!grid)return false;
 const sp=d&&d.speculativePositioning||{};
 card=document.createElement('article');card.className='nikkei-card nikkei-span-12 nikkei-positioning-card';card.setAttribute('data-cftc-positioning','');
 paint(card,sp);
 const ai=findAi();if(ai&&ai.parentElement===grid)grid.insertBefore(card,ai);else grid.appendChild(card);
 if(ai){const t=ai.querySelector('.nikkei-section-title');if(t&&/AI/.test(t.textContent||''))t.textContent=(t.textContent||'AI需給コメント').replace(/^\d+\./,'11.');}
 return true;
}
injectStyles();
fetch(`data/nikkei225-supply-demand.json?v=${Date.now()}`,{cache:'no-store'})
 .then(r=>r.ok?r.json():Promise.reject(new Error('JSON load failed')))
 .then(d=>{let n=0;const t=setInterval(()=>{if(render(d)||++n>60)clearInterval(t)},100);render(d)})
 .catch(()=>{});
})();
