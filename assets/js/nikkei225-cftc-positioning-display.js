(function(){
'use strict';
const root=document.querySelector('[data-nikkei-dashboard]');
if(!root)return;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const fmt=(v,d=0)=>num(v)===null?'取得待ち':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=0,suffix='')=>num(v)===null?'—':`${Number(v)>0?'+':''}${Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d})}${suffix}`;
const date=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得待ち';
function statusClass(text){if(/買い越し拡大/.test(text||''))return'nikkei-status-good';if(/売り越し拡大/.test(text||''))return'nikkei-status-bad';if(/縮小/.test(text||''))return'nikkei-status-warn';return'nikkei-status-purple';}
function yScale(v,min,max,top,h){if(max===min)return top+h/2;return top+(max-v)/(max-min)*h;}
function niceStep(span,target){if(!Number.isFinite(span)||span<=0)return 1;const raw=span/target;const power=Math.pow(10,Math.floor(Math.log10(raw)));const n=raw/power;const step=n<=1?1:n<=2?2:n<=5?5:10;return step*power;}
function svgChart(sp){
 const series=Array.isArray(sp.series)?sp.series:[];if(series.length<2)return'<div class="nikkei-position-empty">26週推移を描画できるだけのデータがありません。</div>';
 const W=1000,H=390,L=70,R=78,T=30,B=52,pw=W-L-R,ph=H-T-B;
 const posVals=[];series.forEach(x=>{const l=num(x.long),s=num(x.short),net=num(x.net);if(l!==null)posVals.push(l);if(s!==null)posVals.push(-s);if(net!==null)posVals.push(net)});
 let min=Math.min(0,...posVals),max=Math.max(0,...posVals);let span=max-min;if(!Number.isFinite(span)||span===0){min=-1;max=1;span=2}
 const pad=span*.08;min-=pad;max+=pad;const pstep=niceStep(max-min,5);min=Math.floor(min/pstep)*pstep;max=Math.ceil(max/pstep)*pstep;
 const prices=series.map(x=>num(x.price)).filter(v=>v!==null);let pmin=null,pmax=null,pprice=false;if(prices.length>=2){pmin=Math.min(...prices);pmax=Math.max(...prices);const pspan=pmax-pmin||1;pmin-=pspan*.08;pmax+=pspan*.08;pprice=true}
 const x=i=>L+(series.length===1?pw/2:i*pw/(series.length-1));const barW=Math.max(7,Math.min(22,pw/series.length*.55));
 let out=`<svg class="nikkei-position-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="CFTC Leveraged Funds 26週ポジション推移">`;
 out+=`<text x="${L}" y="15" class="axis-title">枚数（枚）</text>`;if(pprice)out+=`<text x="${W-R}" y="15" text-anchor="end" class="axis-title">日経225（右軸）</text>`;
 for(let i=0;i<=5;i++){const v=min+(max-min)*i/5;const yy=yScale(v,min,max,T,ph);out+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" class="grid-line"/><text x="${L-10}" y="${yy+4}" text-anchor="end" class="axis-label">${esc(Math.round(v).toLocaleString('ja-JP'))}</text>`}
 if(pprice){for(let i=0;i<=2;i++){const v=pmin+(pmax-pmin)*i/2;const yy=T+ph-i*ph/2;out+=`<text x="${W-R+10}" y="${yy+4}" class="axis-label">${esc(Math.round(v).toLocaleString('ja-JP'))}</text>`}}
 const zero=yScale(0,min,max,T,ph);out+=`<line x1="${L}" x2="${W-R}" y1="${zero}" y2="${zero}" class="zero-line"/>`;
 series.forEach((d,i)=>{const xx=x(i),lv=num(d.long),sv=num(d.short);if(lv!==null){const yy=yScale(lv,min,max,T,ph);out+=`<rect x="${xx-barW/2}" y="${yy}" width="${barW}" height="${Math.max(0,zero-yy)}" rx="2" class="bar-long"/>`}if(sv!==null){const yy=yScale(-sv,min,max,T,ph);out+=`<rect x="${xx-barW/2}" y="${zero}" width="${barW}" height="${Math.max(0,yy-zero)}" rx="2" class="bar-short"/>`}});
 const netPts=series.map((d,i)=>{const v=num(d.net);return v===null?null:`${x(i)},${yScale(v,min,max,T,ph)}`}).filter(Boolean);if(netPts.length>=2){out+=`<polyline points="${netPts.join(' ')}" class="line-net"/>`;series.forEach((d,i)=>{const v=num(d.net);if(v!==null)out+=`<circle cx="${x(i)}" cy="${yScale(v,min,max,T,ph)}" r="2.6" class="dot-net"/>`})}
 if(pprice){const pp=series.map((d,i)=>{const v=num(d.price);return v===null?null:`${x(i)},${yScale(v,pmin,pmax,T,ph)}`}).filter(Boolean);if(pp.length>=2){out+=`<polyline points="${pp.join(' ')}" class="line-price"/>`;series.forEach((d,i)=>{const v=num(d.price);if(v!==null)out+=`<circle cx="${x(i)}" cy="${yScale(v,pmin,pmax,T,ph)}" r="2.2" class="dot-price"/>`})}}
 series.forEach((d,i)=>{if(i===0||i===series.length-1||i%5===0){out+=`<text x="${x(i)}" y="${H-24}" text-anchor="middle" class="axis-label x-label">${esc(d.label||'')}</text>`}});
 out+='</svg>';return out;
}
function findGrid(){return root.querySelector('.nikkei-grid');}
function findAi(){return root.querySelector('.nikkei-ai');}
function render(d){
 if(root.querySelector('[data-cftc-positioning]'))return true;
 const grid=findGrid();if(!grid)return false;
 const sp=d&&d.speculativePositioning||{};const latest=sp.latest||{};
 const card=document.createElement('article');card.className='nikkei-card nikkei-span-12 nikkei-positioning-card';card.setAttribute('data-cftc-positioning','');
 const state=sp.status||'unavailable';const usable=(state==='verified'||state==='stale')&&Array.isArray(sp.series)&&sp.series.length>=2;
 let body='';
 if(usable){
  body=`<div class="nikkei-position-intro">CFTCの金融先物用TFFから、CME円建て日経225先物の <b>Leveraged Funds</b> を26週で追跡します。ゴールドのManaged Moneyとは分類体系が異なり、OSE先物やJPX投資部門別とは別の中期補助指標です。</div>
  <div class="nikkei-position-stats">
   <div class="nikkei-position-stat"><span>Net</span><b class="${num(latest.net)>=0?'nikkei-up':'nikkei-down'}">${signed(latest.net,0,'枚')}</b><small>前週比 ${signed(latest.netChange,0,'枚')}</small></div>
   <div class="nikkei-position-stat"><span>前週比</span><b class="${num(latest.netChange)>=0?'nikkei-up':'nikkei-down'}">${signed(latest.netChange,0,'枚')}</b><small>Net変化</small></div>
   <div class="nikkei-position-stat long"><span>Long</span><b>${fmt(latest.long)}枚</b><small>前週比 ${signed(latest.longChange,0,'枚')}</small></div>
   <div class="nikkei-position-stat short"><span>Short</span><b>${fmt(latest.short)}枚</b><small>前週比 ${signed(latest.shortChange,0,'枚')}</small></div>
   <div class="nikkei-position-stat judge"><span>判定</span><b class="${statusClass(latest.judgement)}">${esc(latest.judgement||'判定待ち')}</b><small>${esc(latest.judgementSub||'')}</small></div>
  </div>
  <div class="nikkei-position-chart-scroll">${svgChart(sp)}</div>
  <div class="nikkei-position-legend"><span><i class="lg-box long"></i>Long（買い）</span><span><i class="lg-box short"></i>Short（売り）</span><span><i class="lg-line net"></i>Net（買い越し）</span>${sp.priceStatus==='available'?'<span><i class="lg-line price"></i>日経225現物（右軸）</span>':''}</div>
  <div class="nikkei-callout">${esc(sp.comment||'')}</div>
  ${state==='stale'?`<div class="nikkei-callout nikkei-position-warning">最新取得に失敗したため前回の検証済みデータを表示しています。${esc(sp.error||'')}</div>`:''}
  ${sp.priceStatus!=='available'?`<div class="nikkei-note">価格線：取得不能${sp.priceReason?`（${esc(sp.priceReason)}）`:''}。CFTCポジション自体の表示は継続します。</div>`:''}
  <div class="nikkei-source">出典：<a href="${esc(sp.sourceUrl||'#')}" target="_blank" rel="noopener">${esc(sp.sourceName||'CFTC TFF')}</a> / CFTCコード ${esc(sp.cftcContractMarketCode||'240743')} / 基準日 ${esc(date(sp.asOfDate))}${sp.priceStatus==='available'?`<br>価格線：<a href="${esc(sp.priceSourceUrl||'#')}" target="_blank" rel="noopener">${esc(sp.priceSourceName||'日経225価格')}</a>`:''}</div>`;
 }else{
  body=`<div class="nikkei-error"><b>CFTC投機筋ポジション：取得不能</b><br>${esc(sp.error||'CFTC TFFの検証済みデータがまだありません。')}</div><div class="nikkei-note">数値は推測・代用しません。次回データ更新時にCFTC公式TFFを再取得します。</div>`;
 }
 card.innerHTML=`<div class="nikkei-section-head"><h2 class="nikkei-section-title">10. 海外投機筋ポジション推移（CFTC・週次）</h2><span class="nikkei-freq weekly">週次・${esc(sp.lookbackWeeks||0)}週取得</span></div><div class="nikkei-section-body">${body}</div>`;
 const ai=findAi();if(ai&&ai.parentElement===grid)grid.insertBefore(card,ai);else grid.appendChild(card);
 if(ai){const t=ai.querySelector('.nikkei-section-title');if(t&&/AI/.test(t.textContent||''))t.textContent=(t.textContent||'AI需給コメント').replace(/^\d+\./,'11.');}
 return true;
}
fetch('data/nikkei225-supply-demand.json',{cache:'no-store'})
 .then(r=>r.ok?r.json():Promise.reject(new Error('JSON load failed')))
 .then(d=>{let n=0;const t=setInterval(()=>{if(render(d)||++n>60)clearInterval(t)},100);render(d)})
 .catch(()=>{});
})();
