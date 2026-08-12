(()=>{
'use strict';
const root=document.querySelector('[data-usdjpy-positioning]');
if(!root)return;
const target=document.getElementById('usdjpy-positioning-content');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=v=>{if(v===null||v===undefined||v==='')return null;const x=Number(v);return Number.isFinite(x)?x:null};
const fmt=(v,d=0)=>n(v)===null?'—':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=0,suffix='')=>n(v)===null?'—':`${Number(v)>0?'+':''}${Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d})}${suffix}`;
const date=v=>v?String(v).slice(0,10).replaceAll('-','/'):'—';
const isoDate=v=>v?String(v).slice(0,10):'';
let sourceData=null;
let fullSeries=[];
let activeWeeks=52;
let apiStatus='loading';
let priceApiStatus='loading';

function injectStyles(){
  if(document.getElementById('usdjpy-cftc-range-style'))return;
  const s=document.createElement('style');
  s.id='usdjpy-cftc-range-style';
  s.textContent=`
  .usd-position-head-tools{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}
  .usd-position-range{display:inline-flex;padding:2px;border:1px solid #b9cbe2;border-radius:999px;background:#fff;box-shadow:0 1px 3px rgba(18,59,120,.08)}
  .usd-position-range button{appearance:none;border:0;background:transparent;color:#36577f;font:800 11px/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;padding:4px 10px;border-radius:999px;cursor:pointer}
  .usd-position-range button.is-active{background:#123b78;color:#fff}
  .usd-position-range button:focus-visible{outline:2px solid #72a6e6;outline-offset:1px}
  .usd-position-api-note{margin:8px 0 0;font-size:9.5px;color:#74849a;line-height:1.45}
  @media(max-width:760px){.usd-position-section-head{flex-wrap:wrap}.usd-position-head-tools{width:100%;justify-content:space-between}.usd-position-range button{padding:4px 9px}}
  `;
  document.head.appendChild(s);
}

function setupRangeControls(){
  const head=root.querySelector('.usd-position-section-head');
  const badge=document.getElementById('usdjpy-positioning-frequency');
  if(!head||!badge||head.querySelector('.usd-position-range'))return;
  const tools=document.createElement('div');
  tools.className='usd-position-head-tools';
  const range=document.createElement('div');
  range.className='usd-position-range';
  range.setAttribute('role','group');
  range.setAttribute('aria-label','CFTC表示期間');
  range.innerHTML='<button type="button" data-weeks="26">26週</button><button type="button" data-weeks="52" class="is-active">52週</button>';
  badge.replaceWith(tools);
  tools.append(range,badge);
  range.addEventListener('click',e=>{
    const btn=e.target.closest('button[data-weeks]');
    if(!btn)return;
    activeWeeks=Number(btn.dataset.weeks)||52;
    range.querySelectorAll('button').forEach(b=>b.classList.toggle('is-active',b===btn));
    renderCurrentRange();
  });
}

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
function labelSeries(series){
  const last=series.length-1;
  return series.map((d,i)=>({...d,label:i===last?'今週':`${last-i}週前`}));
}
function priceOnOrBefore(history,target){
  let best=null;
  for(const row of history||[]){
    if(row.date<=target)best=row.price;
    else break;
  }
  return best;
}
async function fetchUsdJpyDailyHistory(){
  const endpoint='https://query1.finance.yahoo.com/v8/finance/chart/USDJPY%3DX';
  const params=new URLSearchParams({range:'2y',interval:'1d',events:'history',includeAdjustedClose:'true'});
  const r=await fetch(`${endpoint}?${params.toString()}`,{cache:'no-store'});
  if(!r.ok)throw new Error(`Yahoo USDJPY ${r.status}`);
  const data=await r.json();
  const result=((data?.chart?.result)||[null])[0]||{};
  const timestamps=result.timestamp||[];
  const closes=((((result.indicators||{}).quote)||[{}])[0].close)||[];
  const out=[];
  timestamps.forEach((ts,i)=>{
    const close=n(closes[i]);
    if(close===null)return;
    out.push({date:new Date(Number(ts)*1000).toISOString().slice(0,10),price:close});
  });
  out.sort((a,b)=>a.date.localeCompare(b.date));
  if(out.length<200)throw new Error('Yahoo USDJPY history too short');
  return out;
}
function svgChart(series,priceAvailable,weeks){
  if(!Array.isArray(series)||series.length<2)return`<div class="usd-position-empty">${weeks}週推移を描画できるだけの検証済みデータがありません。</div>`;
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
  const barW=Math.max(5,Math.min(26,pw/series.length*.58));
  let out=`<svg class="usd-position-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="CFTC円先物投機筋${weeks}週ポジション推移">`;
  out+=`<text x="${L}" y="17" class="axis-title">枚数（枚）</text>`;
  if(showPrice)out+=`<text x="${W-R}" y="17" text-anchor="end" class="axis-title">USD/JPY（右軸）</text>`;
  for(let i=0;i<=5;i++){const v=min+(max-min)*i/5;const yy=yScale(v,min,max,T,ph);out+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" class="grid-line"/><text x="${L-12}" y="${yy+4}" text-anchor="end" class="axis-label">${esc(Math.round(v).toLocaleString('ja-JP'))}</text>`;}
  if(showPrice){for(let i=0;i<=2;i++){const v=pmin+(pmax-pmin)*i/2;const yy=T+ph-i*ph/2;out+=`<text x="${W-R+10}" y="${yy+4}" class="axis-label">${esc(Number(v).toFixed(1))}</text>`;}}
  const zero=yScale(0,min,max,T,ph);out+=`<line x1="${L}" x2="${W-R}" y1="${zero}" y2="${zero}" class="zero-line"/>`;
  series.forEach((d,i)=>{const xx=x(i),lv=n(d.long),sv=n(d.short);if(lv!==null){const yy=yScale(lv,min,max,T,ph);out+=`<rect x="${xx-barW/2}" y="${yy}" width="${barW}" height="${Math.max(0,zero-yy)}" rx="2" class="bar-long"/>`;}if(sv!==null){const yy=yScale(-sv,min,max,T,ph);out+=`<rect x="${xx-barW/2}" y="${zero}" width="${barW}" height="${Math.max(0,yy-zero)}" rx="2" class="bar-short"/>`;}});
  const netPts=series.map((d,i)=>n(d.net)===null?null:`${x(i)},${yScale(n(d.net),min,max,T,ph)}`).filter(Boolean);
  if(netPts.length>=2){out+=`<polyline points="${netPts.join(' ')}" class="line-net"/>`;series.forEach((d,i)=>{const v=n(d.net);if(v!==null)out+=`<circle cx="${x(i)}" cy="${yScale(v,min,max,T,ph)}" r="${series.length>30?2.2:3}" class="dot-net"/>`;});}
  if(showPrice){
    const chunks=[];let chunk=[];
    series.forEach((d,i)=>{const v=n(d.price);if(v===null){if(chunk.length)chunks.push(chunk);chunk=[];}else chunk.push(`${x(i)},${yScale(v,pmin,pmax,T,ph)}`);});if(chunk.length)chunks.push(chunk);
    chunks.filter(c=>c.length>=2).forEach(c=>{out+=`<polyline points="${c.join(' ')}" class="line-price"/>`;});
    series.forEach((d,i)=>{const v=n(d.price);if(v!==null)out+=`<circle cx="${x(i)}" cy="${yScale(v,pmin,pmax,T,ph)}" r="${series.length>30?2:2.5}" class="dot-price"/>`;});
  }
  const anchors=weeks===52?[0,13,26,39,series.length-1]:[0,5,10,15,20,series.length-1];
  [...new Set(anchors.map(i=>Math.min(Math.max(i,0),series.length-1)))].forEach(i=>{const d=series[i];out+=`<text x="${x(i)}" y="${H-26}" text-anchor="middle" class="axis-label">${esc(d.label||date(d.date))}</text>`;});
  out+='</svg>';return out;
}

async function fetchOfficialCftc52(localSeries,priceHistory){
  const endpoint='https://publicreporting.cftc.gov/resource/6dca-aqww.json';
  const params=new URLSearchParams({
    '$select':'report_date_as_yyyy_mm_dd,noncomm_positions_long_all,noncomm_positions_short_all',
    '$where':"cftc_contract_market_code='097741'",
    '$order':'report_date_as_yyyy_mm_dd DESC',
    '$limit':'52'
  });
  const r=await fetch(`${endpoint}?${params.toString()}`,{cache:'no-store'});
  if(!r.ok)throw new Error(`CFTC API ${r.status}`);
  const rows=await r.json();
  if(!Array.isArray(rows)||rows.length<26)throw new Error('CFTC API series too short');
  const priceMap=new Map((localSeries||[]).map(d=>[isoDate(d.date),n(d.price)]));
  const statusMap=new Map((localSeries||[]).map(d=>[isoDate(d.date),d.status]));
  const s=rows.map(row=>{
    const dt=isoDate(row.report_date_as_yyyy_mm_dd);
    const l=n(row.noncomm_positions_long_all),sh=n(row.noncomm_positions_short_all);
    const localPrice=priceMap.get(dt);
    const historyPrice=priceOnOrBefore(priceHistory,dt);
    return{date:dt,long:l,short:sh,net:l!==null&&sh!==null?l-sh:null,price:localPrice??historyPrice??null,status:statusMap.get(dt)||'official-api'};
  }).sort((a,b)=>a.date.localeCompare(b.date));
  return labelSeries(s.slice(-52));
}

function renderCurrentRange(){
  if(!sourceData)return;
  const c=sourceData?.cftc||{};
  const requested=activeWeeks;
  const series=labelSeries(fullSeries.slice(-requested));
  const latest=series.at(-1)||c;const prev=series.length>1?series.at(-2):null;
  const net=n(latest.net??c.net),long=n(latest.long??c.long),short=n(latest.short??c.short);
  const netChg=prev&&net!==null&&n(prev.net)!==null?net-n(prev.net):n(c.netChange);
  const longChg=prev&&long!==null&&n(prev.long)!==null?long-n(prev.long):n(c.longChange);
  const shortChg=prev&&short!==null&&n(prev.short)!==null?short-n(prev.short):n(c.shortChange);
  const netChangePct=n(c.netChangePct)!==null&&isoDate(c.asOf)===isoDate(latest.date)?n(c.netChangePct):(prev&&n(prev.net)!==null&&n(prev.net)!==0?Math.abs(netChg/n(prev.net)*100):null);
  const judge=judgement({net,netChange:netChg});const sub=judgementSub(judge);
  const verified=series.filter(d=>n(d.long)!==null&&n(d.short)!==null).length;
  const missing=Math.max(0,requested-verified);
  const badge=document.getElementById('usdjpy-positioning-frequency');
  if(badge)badge.textContent=`週次・${requested}週 / ${verified}点表示`;
  if(series.length<2){target.innerHTML=`<div class="usd-position-empty"><b>CFTC投機筋ポジション：取得待ち</b><br>${esc(c.error||`${requested}週の検証済み系列を準備しています。`)}</div>`;return;}
  const pricePoints=series.filter(d=>n(d.price)!==null).length;
  const priceAvailable=pricePoints>=2;
  const intro=priceAvailable?'Long・Short・Netの変化と取得済みUSD/JPY価格を重ね、投機筋の円買い／円売りの偏りと価格反応の整合性を確認します。':'Long・Short・Netの変化から、投機筋の円買い／円売りの偏りと巻き戻しの強さを確認します。';
  const apiText=apiStatus==='ok'?(priceApiStatus==='ok'?'CFTC公式52週＋USD/JPY日次履歴を取得':'CFTC公式Public Reporting APIから52週を取得'):'ローカル検証済み系列を表示（公式API取得失敗時のフォールバック）';
  const priceSourceName=priceApiStatus==='ok'?'Yahoo!ファイナンス USD/JPY時系列':(c.priceSourceName||'USD/JPY履歴価格');
  const priceSourceUrl=priceApiStatus==='ok'?'https://finance.yahoo.co.jp/quote/USDJPY=X/history':(c.priceSourceUrl||'https://finance.yahoo.co.jp/quote/USDJPY=X/history');
  target.innerHTML=`
    <div class="usd-position-intro">CFTCの <b>Japanese Yen / Non-Commercial</b> を直近${requested}週レンジで追跡します。${intro}</div>
    <div class="usd-position-stats">
      <div class="usd-position-stat net"><span>Net</span><b>${signed(net,0,'枚')}</b><small>${net!==null&&net<0?'円売り越し':net!==null&&net>0?'円買い越し':'中立'} ｜ 前週比 ${signed(netChg,0,'枚')}</small></div>
      <div class="usd-position-stat"><span>前週比</span><b class="${netChg!==null&&netChg>0?'usd-pos-positive':netChg!==null&&netChg<0?'usd-pos-negative':''}">${signed(netChg,0,'枚')}</b><small>${netChangePct!==null?signed(netChangePct,1,'%'):'Net変化'}</small></div>
      <div class="usd-position-stat long"><span>Long</span><b>${fmt(long)}枚</b><small>前週比 ${signed(longChg,0,'枚')}</small></div>
      <div class="usd-position-stat short"><span>Short</span><b>${fmt(short)}枚</b><small>前週比 ${signed(shortChg,0,'枚')}</small></div>
      <div class="usd-position-stat judge"><span>判定</span><b>${esc(judge)}</b><small>${esc(sub)}</small></div>
    </div>
    <div class="usd-position-reading"><b>読み方</b><span>円先物Netがプラス＝円買い越しでUSD/JPYの下押し要因、マイナス＝円売り越しでUSD/JPYの上押し要因。単独ではなく、日米金利差・出来高・オーダーと合わせて判断します。</span></div>
    <div class="usd-position-chart-shell"><div class="usd-position-chart-scroll">${svgChart(series,priceAvailable,requested)}</div><div class="usd-position-legend"><span><i class="lg-box long"></i>Long（円買い）</span><span><i class="lg-box short"></i>Short（円売り）</span><span><i class="lg-line net"></i>Net（円買い越し／売り越し）</span>${priceAvailable?'<span><i class="lg-line price"></i>USD/JPY（右軸）</span>':''}</div></div>
    ${missing?`<div class="usd-position-note">${requested}週レンジのうち${missing}週は現在欠損です。欠損値を0として扱わず空欄にします。</div>`:''}
    ${priceAvailable&&pricePoints<series.length?`<div class="usd-position-note">CFTCポジションは${verified}週分を表示しています。USD/JPY価格線は履歴価格を確認済みの${pricePoints}週分だけ重ね、未取得期間を推測で補完しません。</div>`:''}
    <div class="usd-position-note">${esc(c.comment||`${judge}。ポジションの方向とUSD/JPYの値動きが一致しているかを確認し、急激な巻き戻しが起きていないかを監視します。`)}</div>
    <div class="usd-position-api-note">${esc(apiText)}。表示期間は右上の「26週 / 52週」で切り替えできます。初期表示は52週です。</div>
    <div class="usd-position-source">出典：<a href="https://publicreporting.cftc.gov/Commitments-of-Traders/Legacy-Futures-Only/6dca-aqww" target="_blank" rel="noopener">CFTC Legacy - Futures Only / Public Reporting</a> ｜ 基準日 ${esc(date(latest.date||c.asOf))}${priceAvailable?`<br>価格線：<a href="${esc(priceSourceUrl)}" target="_blank" rel="noopener">${esc(priceSourceName)}</a>`:''}</div>`;
}

async function init(){
  injectStyles();setupRangeControls();
  try{
    const r=await fetch(`data/usdjpy-supply-demand.json?v=${Date.now()}`,{cache:'no-store'});
    if(!r.ok)throw new Error('JSON load failed');
    sourceData=await r.json();
    const local=Array.isArray(sourceData?.cftc?.series)?sourceData.cftc.series:[];
    fullSeries=labelSeries(local);
    renderCurrentRange();
    let priceHistory=[];
    try{
      priceHistory=await fetchUsdJpyDailyHistory();
      priceApiStatus='ok';
    }catch(e){
      priceApiStatus='fallback';
      console.warn('[USDJPY CFTC] Yahoo 52-week price history fallback:',e);
    }
    try{
      fullSeries=await fetchOfficialCftc52(local,priceHistory);
      apiStatus='ok';
    }catch(e){
      apiStatus='fallback';
      console.warn('[USDJPY CFTC] official 52-week API fallback:',e);
    }
    renderCurrentRange();
  }catch(e){
    target.innerHTML=`<div class="usd-position-empty">CFTCデータを読み込めませんでした。${esc(e.message||e)}</div>`;
  }
}
init();
})();
