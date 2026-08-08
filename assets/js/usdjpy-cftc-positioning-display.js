(()=>{
'use strict';
const root=document.querySelector('[data-usdjpy-positioning]');
if(!root)return;
const target=document.getElementById('usdjpy-positioning-content');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const fmt=(v,d=0)=>n(v)===null?'—':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=0,suffix='')=>n(v)===null?'—':`${Number(v)>0?'+':''}${Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d})}${suffix}`;
const date=v=>v?String(v).slice(0,10).replaceAll('-','/'):'—';
function yScale(v,min,max,top,h){if(max===min)return top+h/2;return top+(max-v)/(max-min)*h;}
function niceStep(span,targetCount){if(!Number.isFinite(span)||span<=0)return 1;const raw=span/targetCount;const pow=Math.pow(10,Math.floor(Math.log10(raw)));const z=raw/pow;return(z<=1?1:z<=2?2:z<=5?5:10)*pow;}
function judgement(c){
  if(c?.judgement)return c.judgement;
  const net=n(c?.net),chg=n(c?.netChange??(n(c?.previousNet)!==null&&net!==null?net-n(c.previousNet):null));
  if(net===null)return'判定待ち';
  if(net<0)return chg!==null&&chg<0?'円売り越し拡大':'円売り越し縮小';
  if(net>0)return chg!==null&&chg>0?'円買い越し拡大':'円買い越し縮小';
  return'中立';
}
function judgementSub(text){
  if(/円売り越し拡大/.test(text))return'USD/JPYの上昇圧力';
  if(/円売り越し縮小/.test(text))return'ドル買い圧力が弱まる方向';
  if(/円買い越し拡大/.test(text))return'USD/JPYの下押し圧力';
  if(/円買い越し縮小/.test(text))return'円買い圧力が弱まる方向';
  return'方向感を確認';
}
function svgChart(series,priceAvailable){
  if(!Array.isArray(series)||series.length<2)return'<div class="usd-position-empty">26週推移を描画できるだけの検証済みデータがありません。</div>';
  const W=1120,H=420,L=82,R=88,T=32,B=58,pw=W-L-R,ph=H-T-B;
  const vals=[];
  series.forEach(d=>{const l=n(d.long),s=n(d.short),net=n(d.net);if(l!==null)vals.push(l);if(s!==null)vals.push(-s);if(net!==null)vals.push(net)});
  let min=Math.min(0,...vals),max=Math.max(0,...vals);let span=max-min;
  if(!Number.isFinite(span)||span===0){min=-1;max=1;span=2;}
  const pad=span*.07;min-=pad;max+=pad;const step=niceStep(max-min,5);min=Math.floor(min/step)*step;max=Math.ceil(max/step)*step;
  const prices=series.map(d=>n(d.price)).filter(v=>v!==null);
  let pmin=null,pmax=null,showPrice=priceAvailable&&prices.length>=2;
  if(showPrice){pmin=Math.min(...prices);pmax=Math.max(...prices);const ps=pmax-pmin||1;pmin-=ps*.08;pmax+=ps*.08;}
  const x=i=>L+(series.length===1?pw/2:i*pw/(series.length-1));
  const barW=Math.max(9,Math.min(26,pw/series.length*.58));
  let out=`<svg class="usd-position-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="CFTC円先物投機筋26週ポジション推移">`;
  out+=`<text x="${L}" y="17" class="axis-title">枚数（枚）</text>`;
  if(showPrice)out+=`<text x="${W-R}" y="17" text-anchor="end" class="axis-title">USD/JPY（右軸）</text>`;
  for(let i=0;i<=5;i++){const v=min+(max-min)*i/5;const yy=yScale(v,min,max,T,ph);out+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" class="grid-line"/><text x="${L-12}" y="${yy+4}" text-anchor="end" class="axis-label">${esc(Math.round(v).toLocaleString('ja-JP'))}</text>`;}
  if(showPrice){for(let i=0;i<=2;i++){const v=pmin+(pmax-pmin)*i/2;const yy=T+ph-i*ph/2;out+=`<text x="${W-R+10}" y="${yy+4}" class="axis-label">${esc(Number(v).toFixed(1))}</text>`;}}
  const zero=yScale(0,min,max,T,ph);out+=`<line x1="${L}" x2="${W-R}" y1="${zero}" y2="${zero}" class="zero-line"/>`;
  series.forEach((d,i)=>{const xx=x(i),lv=n(d.long),sv=n(d.short);if(lv!==null){const yy=yScale(lv,min,max,T,ph);out+=`<rect x="${xx-barW/2}" y="${yy}" width="${barW}" height="${Math.max(0,zero-yy)}" rx="2" class="bar-long"/>`;}if(sv!==null){const yy=yScale(-sv,min,max,T,ph);out+=`<rect x="${xx-barW/2}" y="${zero}" width="${barW}" height="${Math.max(0,yy-zero)}" rx="2" class="bar-short"/>`;}});
  const netPts=series.map((d,i)=>n(d.net)===null?null:`${x(i)},${yScale(n(d.net),min,max,T,ph)}`).filter(Boolean);
  if(netPts.length>=2){out+=`<polyline points="${netPts.join(' ')}" class="line-net"/>`;series.forEach((d,i)=>{const v=n(d.net);if(v!==null)out+=`<circle cx="${x(i)}" cy="${yScale(v,min,max,T,ph)}" r="3" class="dot-net"/>`;});}
  if(showPrice){const pts=series.map((d,i)=>n(d.price)===null?null:`${x(i)},${yScale(n(d.price),pmin,pmax,T,ph)}`).filter(Boolean);if(pts.length>=2){out+=`<polyline points="${pts.join(' ')}" class="line-price"/>`;series.forEach((d,i)=>{const v=n(d.price);if(v!==null)out+=`<circle cx="${x(i)}" cy="${yScale(v,pmin,pmax,T,ph)}" r="2.5" class="dot-price"/>`;});}}
  series.forEach((d,i)=>{if(i===0||i===series.length-1||i%5===0){out+=`<text x="${x(i)}" y="${H-26}" text-anchor="middle" class="axis-label">${esc(d.label||date(d.date))}</text>`;}});
  out+='</svg>';return out;
}
function render(data){
  const c=data?.cftc||{};const series=Array.isArray(c.series)?c.series:[];const latest=series.at(-1)||c;const prev=series.length>1?series.at(-2):null;
  const net=n(latest.net??c.net),long=n(latest.long??c.long),short=n(latest.short??c.short);
  const netChg=n(c.netChange)!==null?n(c.netChange):(prev&&net!==null&&n(prev.net)!==null?net-n(prev.net):n(c.previousNet)!==null&&net!==null?net-n(c.previousNet):null);
  const longChg=n(c.longChange)!==null?n(c.longChange):(prev&&long!==null&&n(prev.long)!==null?long-n(prev.long):null);
  const shortChg=n(c.shortChange)!==null?n(c.shortChange):(prev&&short!==null&&n(prev.short)!==null?short-n(prev.short):null);
  const judge=judgement({...c,net,netChange:netChg});const sub=c.judgementSub||judgementSub(judge);
  const state=c.status||'unavailable';const usable=(state==='confirmed'||state==='stale')&&series.length>=2;
  const badge=document.getElementById('usdjpy-positioning-frequency');if(badge)badge.textContent=`週次・${series.length||0}週取得`;
  if(!usable){target.innerHTML=`<div class="usd-position-empty"><b>CFTC投機筋ポジション：取得待ち</b><br>${esc(c.error||'26週の検証済み系列を準備しています。')}</div>`;return;}
  const priceAvailable=c.priceStatus==='available'||series.filter(d=>n(d.price)!==null).length>=2;
  target.innerHTML=`
    <div class="usd-position-intro">CFTCの <b>Japanese Yen / Non-Commercial</b> を26週で追跡します。Long・Short・Netの変化とUSD/JPY価格を重ね、投機筋の円買い／円売りの偏りと価格反応の整合性を確認します。</div>
    <div class="usd-position-stats">
      <div class="usd-position-stat net"><span>Net</span><b>${signed(net,0,'枚')}</b><small>${net!==null&&net<0?'円売り越し':net!==null&&net>0?'円買い越し':'中立'} ｜ 前週比 ${signed(netChg,0,'枚')}</small></div>
      <div class="usd-position-stat"><span>前週比</span><b class="${netChg!==null&&netChg>0?'usd-pos-positive':netChg!==null&&netChg<0?'usd-pos-negative':''}">${signed(netChg,0,'枚')}</b><small>${n(c.netChangePct)!==null?signed(c.netChangePct,1,'%'):'Net変化'}</small></div>
      <div class="usd-position-stat long"><span>Long</span><b>${fmt(long)}枚</b><small>前週比 ${signed(longChg,0,'枚')}</small></div>
      <div class="usd-position-stat short"><span>Short</span><b>${fmt(short)}枚</b><small>前週比 ${signed(shortChg,0,'枚')}</small></div>
      <div class="usd-position-stat judge"><span>判定</span><b>${esc(judge)}</b><small>${esc(sub)}</small></div>
    </div>
    <div class="usd-position-reading"><b>読み方</b><span>円先物Netがプラス＝円買い越しでUSD/JPYの下押し要因、マイナス＝円売り越しでUSD/JPYの上押し要因。単独ではなく、日米金利差・出来高・オーダーと合わせて判断します。</span></div>
    <div class="usd-position-chart-shell"><div class="usd-position-chart-scroll">${svgChart(series,priceAvailable)}</div><div class="usd-position-legend"><span><i class="lg-box long"></i>Long（円買い）</span><span><i class="lg-box short"></i>Short（円売り）</span><span><i class="lg-line net"></i>Net（円買い越し／売り越し）</span>${priceAvailable?'<span><i class="lg-line price"></i>USD/JPY（右軸）</span>':''}</div></div>
    <div class="usd-position-note">${esc(c.comment||`${judge}。ポジションの方向とUSD/JPYの値動きが一致しているかを確認し、急激な巻き戻しが起きていないかを監視します。`)}</div>
    <div class="usd-position-source">出典：<a href="${esc(c.url||'https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm')}" target="_blank" rel="noopener">CFTC Commitments of Traders</a> ｜ 基準日 ${esc(date(c.asOf||latest.date))}${priceAvailable?`<br>価格線：<a href="${esc(c.priceSourceUrl||'https://finance.yahoo.co.jp/quote/USDJPY=X/history')}" target="_blank" rel="noopener">${esc(c.priceSourceName||'Yahoo!ファイナンス USD/JPY時系列')}</a>`:''}</div>`;
}
fetch(`data/usdjpy-supply-demand.json?v=${Date.now()}`,{cache:'no-store'}).then(r=>r.ok?r.json():Promise.reject(new Error('JSON load failed'))).then(render).catch(e=>{target.innerHTML=`<div class="usd-position-empty">CFTC 26週データを読み込めませんでした。${esc(e.message||e)}</div>`;});
})();
