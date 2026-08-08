(function(){
'use strict';
const root=document.querySelector('[data-nikkei-dashboard]');
if(!root)return;
const DATA_URL='data/nikkei225-supply-demand.json';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
const num=v=>{if(v===null||v===undefined||v==='')return null;const x=Number(String(v).replace(/,/g,''));return Number.isFinite(x)?x:null};
const fmt=(v,d=0)=>num(v)===null?'取得待ち':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=0,suffix='')=>num(v)===null?'—':`${Number(v)>0?'+':''}${fmt(v,d)}${suffix}`;
const date=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得待ち';
function findCard(){
  return [...root.querySelectorAll('.nikkei-grid > .nikkei-card')].find(card=>{
    const t=card.querySelector('.nikkei-section-title');
    return t&&/^7\.\s*海外投資家/.test((t.textContent||'').trim());
  })||null;
}
function tone(cash,fut){
  if(cash>0&&fut>0)return{key:'buy',label:'現物・先物とも買い',read:'買い方向が揃い、中期需給は比較的強い。'};
  if(cash<0&&fut<0)return{key:'sell',label:'現物・先物とも売り',read:'売り方向が揃い、中期需給は弱い。'};
  if(cash<0&&fut>0)return{key:'mixed',label:'現物売り・先物買い',read:'方向不一致。ヘッジ・裁定・短期ポジションを含む綱引き。'};
  if(cash>0&&fut<0)return{key:'mixed',label:'現物買い・先物売り',read:'方向不一致。現物買いに対する先物ヘッジの可能性も確認。'};
  return{key:'neutral',label:'方向混在',read:'一方向に揃っていないため、次週のフロー継続性を確認。'};
}
function source(url,name,asof){
  if(!url)return'';
  return `<div class="nikkei-source">出典：<a href="${esc(url)}" target="_blank" rel="noopener">${esc(name)}</a>${asof?` / 基準日 ${esc(date(asof))}`:''}</div>`;
}
function niceMax(values){
  const m=Math.max(1000,...values.map(x=>Math.abs(x||0)));
  const p=Math.pow(10,Math.floor(Math.log10(m)));
  const n=m/p;
  const step=n<=2?2:n<=5?5:10;
  return step*p;
}
function priceBounds(values){
  const v=values.filter(x=>num(x)!==null).map(Number);
  if(!v.length)return null;
  let lo=Math.min(...v),hi=Math.max(...v);
  if(lo===hi){lo-=500;hi+=500;}
  const pad=Math.max(300,(hi-lo)*.12);
  lo=Math.floor((lo-pad)/500)*500;
  hi=Math.ceil((hi+pad)/500)*500;
  return{lo,hi};
}
function svg(series){
  const W=1120,H=360,L=72,R=74,T=28,B=56;
  const plotW=W-L-R,plotH=H-T-B;
  const vals=series.flatMap(x=>[num(x.cashNet)||0,num(x.nikkeiFuturesNet)||0]);
  const ymax=niceMax(vals),ymin=-ymax;
  const y=v=>T+(ymax-v)/(ymax-ymin)*plotH;
  const zero=y(0);
  const group=plotW/series.length,bar=Math.min(22,group*.24);
  const prices=series.map(x=>num(x.nikkeiFuturesPrice));
  const pb=priceBounds(prices);
  const py=pb?(v=>T+(pb.hi-v)/(pb.hi-pb.lo)*plotH):null;
  const grid=[];
  for(let i=0;i<=4;i++){
    const val=ymax-i*(2*ymax/4);
    const yy=y(val);
    grid.push(`<line class="nikkei-foreign-gridline" x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}"/><text class="nikkei-foreign-ylabel" x="${L-10}" y="${yy+3}" text-anchor="end">${esc(fmt(val,0))}</text>`);
  }
  if(pb){
    for(let i=0;i<=4;i++){
      const val=pb.hi-i*((pb.hi-pb.lo)/4),yy=py(val);
      grid.push(`<text class="nikkei-foreign-ylabel-right" x="${W-R+9}" y="${yy+3}" text-anchor="start">${esc(fmt(val,0))}</text>`);
    }
  }
  const nowX=L+(series.length-1)*group;
  const parts=[`<svg class="nikkei-foreign-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="海外投資家の現物株・日経225先物ネットフローと日経225先物価格の12週推移">`,`<rect class="nikkei-foreign-now" x="${nowX}" y="${T}" width="${group}" height="${plotH}" rx="5"/>`,...grid,`<line class="nikkei-foreign-zero" x1="${L}" y1="${zero}" x2="${W-R}" y2="${zero}"/>`];
  series.forEach((s,i)=>{
    const cx=L+i*group+group/2;
    const cash=num(s.cashNet),fut=num(s.nikkeiFuturesNet);
    const draw=(v,x,klass)=>{
      if(v===null)return;
      const yy=y(v),h=Math.abs(zero-yy),top=Math.min(zero,yy);
      parts.push(`<rect class="${klass}" x="${x-bar/2}" y="${top}" width="${bar}" height="${Math.max(1,h)}" rx="2"/>`);
    };
    draw(cash,cx-bar*.65,'nikkei-foreign-bar-cash');
    draw(fut,cx+bar*.65,'nikkei-foreign-bar-fut');
    const label=i===series.length-1?'今週':`${series.length-1-i}週前`;
    parts.push(`<text class="nikkei-foreign-xlabel ${i===series.length-1?'current':''}" x="${cx}" y="${H-28}" text-anchor="middle">${esc(label)}</text>`);
  });
  if(pb&&py){
    const points=series.map((s,i)=>{const p=num(s.nikkeiFuturesPrice);if(p===null)return null;const cx=L+i*group+group/2;return`${cx},${py(p)}`}).filter(Boolean);
    if(points.length>=2){
      parts.push(`<polyline class="nikkei-foreign-price-line" points="${points.join(' ')}"/>`);
      series.forEach((s,i)=>{const p=num(s.nikkeiFuturesPrice);if(p===null)return;const cx=L+i*group+group/2,cy=py(p);parts.push(`<circle class="nikkei-foreign-price-point" cx="${cx}" cy="${cy}" r="3.2"/>`);});
    }
  }
  parts.push(`<text class="nikkei-foreign-ylabel" x="${L}" y="15">差引（億円）</text>`);
  if(pb)parts.push(`<text class="nikkei-foreign-ylabel-right nikkei-foreign-axis-title-right" x="${W-R+4}" y="15">先物価格（円）</text>`);
  parts.push(`</svg>`);
  return parts.join('');
}
function apply(d){
  const f=d.foreignInvestors||{};
  const card=findCard();if(!card)return false;
  const series=Array.isArray(f.series)?f.series.filter(x=>num(x.cashNet)!==null&&num(x.nikkeiFuturesNet)!==null).slice(-12):[];
  const title=card.querySelector('.nikkei-section-title');if(title)title.textContent='7. 海外投資家の週次需給推移';
  card.classList.remove('nikkei-span-6');card.classList.add('nikkei-span-12','nikkei-foreign-card');
  const body=card.querySelector('.nikkei-section-body');if(!body)return false;
  const cash=num(f.cashNet),fut=num(f.nikkeiFuturesNet),t=tone(cash,fut);
  const weeks=series.length;
  const latest=series[series.length-1]||{},prev=series[series.length-2]||{};
  const latestPrice=num(latest.nikkeiFuturesPrice),prevPrice=num(prev.nikkeiFuturesPrice);
  const priceChange=latestPrice!==null&&prevPrice!==null?latestPrice-prevPrice:null;
  const insights=[];
  if(cash<0&&fut>0)insights.push('現物株は売り越し、日経225先物は買い越し。');
  else if(cash>0&&fut<0)insights.push('現物株は買い越し、日経225先物は売り越し。');
  else if(cash>0&&fut>0)insights.push('現物株・日経225先物とも買い越しで方向が一致。');
  else if(cash<0&&fut<0)insights.push('現物株・日経225先物とも売り越しで方向が一致。');
  else insights.push('現物株と先物の方向は明確に揃っていません。');
  if(fut!==null&&priceChange!==null){
    if(fut>0&&priceChange>0)insights.push(`先物買い越しと価格上昇（前週比 ${signed(priceChange,0,'円')}）が整合。`);
    else if(fut<0&&priceChange<0)insights.push(`先物売り越しと価格下落（前週比 ${signed(priceChange,0,'円')}）が整合。`);
    else if(fut>0&&priceChange<0)insights.push(`先物は買い越しでも価格は下落（前週比 ${signed(priceChange,0,'円')}）。買いを吸収する他主体の売り圧力も確認。`);
    else if(fut<0&&priceChange>0)insights.push(`先物は売り越しでも価格は上昇（前週比 ${signed(priceChange,0,'円')}）。他主体の買い・買い戻しの強さも確認。`);
  }else insights.push('先物フローと価格の整合性は、同一基準日の価格取得後に判定。');
  insights.push('ヘッジ・裁定・短期ポジションを含む可能性があるため、先物建玉や裁定残と併読。');
  body.innerHTML=`
    <div class="nikkei-foreign-headline">
      <div class="nikkei-foreign-metric"><div class="nikkei-foreign-metric-label">現物株</div><div class="nikkei-foreign-metric-value ${cash<0?'sell':cash>0?'buy':'neutral'}">${signed(cash,0,'億円')}</div><div class="nikkei-foreign-metric-note">海外投資家売買（現物・東証プライム）</div></div>
      <div class="nikkei-foreign-metric"><div class="nikkei-foreign-metric-label">日経225先物</div><div class="nikkei-foreign-metric-value ${fut<0?'sell':fut>0?'buy':'neutral'}">${signed(fut,0,'億円')}</div><div class="nikkei-foreign-metric-note">海外投資家売買（金額ベース）</div></div>
      <div class="nikkei-foreign-metric"><div class="nikkei-foreign-metric-label">判定</div><div class="nikkei-foreign-metric-value ${t.key}">${esc(t.label)}</div><div class="nikkei-foreign-metric-note">現物と先物を同一週で比較</div></div>
      <div class="nikkei-foreign-metric"><div class="nikkei-foreign-metric-label">読み方</div><div class="nikkei-foreign-metric-value neutral">${esc(t.read)}</div><div class="nikkei-foreign-metric-note">単独で売買主体を断定せず、他の需給指標と併読</div></div>
    </div>
    ${weeks===12?`<div class="nikkei-foreign-chart-panel"><div class="nikkei-foreign-chart-title-row"><div><div class="nikkei-foreign-chart-title">週次ネットフロー＋日経225先物価格（過去12週間）</div><div class="nikkei-foreign-chart-sub">同一基準日の現物・先物フローと、取引所発表の先物清算値（帳入値）を比較</div></div><div class="nikkei-foreign-chart-meta"><div class="nikkei-foreign-latest-price">先物 ${latestPrice===null?'取得待ち':`${fmt(latestPrice,0)}円`}</div><div class="nikkei-foreign-freshness">基準日 ${esc(date(f.asOfDate))} / ${esc(f.historyStatus||'verified')}</div></div></div><div class="nikkei-foreign-chart-scroll">${svg(series)}</div><div class="nikkei-foreign-legend"><span><i class="cash"></i>現物株ネットフロー</span><span><i class="futures"></i>日経225先物ネットフロー</span><span><i class="price"></i>日経225先物価格（右軸）</span></div><div class="nikkei-foreign-tooltip-note">※ 価格は同一基準日の清算値（帳入値）。合計フローは表示しません。現物と先物にはヘッジ関係が含まれるためです。</div></div>`:`<div class="nikkei-foreign-empty">12週の同一期間データが揃っていません。欠損週は推測で補いません。</div>`}
    <div class="nikkei-foreign-insight"><h3>このグラフから読むこと</h3><ul>${insights.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>
    <div class="nikkei-foreign-source-row">${source(f.cashSourceFileUrl,'JPX 東証プライム投資部門別売買状況',f.asOfDate)}${source(f.derivativesSourceFileUrl,'JPX 日経225先物 投資部門別取引状況',f.asOfDate)}${source(f.futuresPriceSourceUrl,'株探 日経225先物時系列（清算値）',f.asOfDate)}</div>`;
  return true;
}
fetch(DATA_URL,{cache:'no-store'}).then(r=>r.ok?r.json():Promise.reject(new Error('data load failed'))).then(d=>{let n=0;const t=setInterval(()=>{if(apply(d)||++n>80)clearInterval(t)},100);apply(d)}).catch(()=>{});
})();
