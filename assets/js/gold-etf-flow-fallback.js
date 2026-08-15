(function(){
'use strict';

const DATA_URL='data/gold-supply-demand.json';
const MIN_ALIGNED_HISTORY_DAYS=20;
const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function normalize(rows){
  return (Array.isArray(rows)?rows:[]).map(row=>({
    date:String(row&&row.asOfDate||'').slice(0,10),
    value:n(row&&row.changeTonnes),
    tonnes:n(row&&row.tonnes)
  })).filter(x=>x.date&&x.value!==null).sort((a,b)=>a.date.localeCompare(b.date));
}

function barSvg(rows){
  if(!rows.length)return '<div class="gold-etf-chart-empty">ETF履歴を蓄積中です。</div>';
  const W=1180,H=280,L=48,R=18,T=28,B=54,plotW=W-L-R,plotH=H-T-B;
  const maxAbs=Math.max(1,...rows.map(x=>Math.abs(x.value)))*1.15;
  const y=v=>T+(maxAbs-v)/(maxAbs*2)*plotH;
  const zero=y(0),step=plotW/rows.length,barW=Math.max(8,Math.min(34,step*.55));
  const labelEvery=Math.max(1,Math.ceil(rows.length/12));
  const ticks=[maxAbs,maxAbs/2,0,-maxAbs/2,-maxAbs];
  let svg=`<svg class="gold-etf-chart-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="GLD日次フロー棒グラフ">`;
  ticks.forEach(t=>{const yy=y(t);svg+=`<line class="${t===0?'zero':'grid'}" x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}"></line><text class="axis-text" x="${L-7}" y="${yy+3}" text-anchor="end">${Math.abs(t)<.005?'0':t.toFixed(1)}</text>`;});
  rows.forEach((row,i)=>{
    const cx=L+step*i+step/2,yy=y(row.value),top=Math.min(yy,zero),height=Math.max(2,Math.abs(zero-yy));
    const valueY=row.value>=0?top-6:top+height+13;
    const label=row.date.slice(5).replace('-','/');
    svg+=`<rect class="${row.value>=0?'bar-positive':'bar-negative'}" x="${cx-barW/2}" y="${top}" width="${barW}" height="${height}" rx="2"><title>${esc(row.date)} ${row.value>0?'+':''}${row.value.toFixed(2)}t</title></rect>`;
    if(rows.length<=35)svg+=`<text class="value-text" x="${cx}" y="${valueY}" text-anchor="middle">${row.value>0?'+':''}${row.value.toFixed(2)}</text>`;
    if(i%labelEvery===0||i===rows.length-1)svg+=`<text class="axis-text" x="${cx}" y="${H-20}" text-anchor="middle">${esc(label)}</text>`;
  });
  return svg+'</svg>';
}

function cumulativeSvg(rows){
  if(rows.length<2)return '<div class="gold-etf-chart-empty">GLD履歴を蓄積中です。</div>';
  let total=0;
  const startRow=rows[0],endRow=rows[rows.length-1];
  const startTonnes=n(startRow.tonnes),endTonnes=n(endRow.tonnes);
  const points=rows.map(x=>({date:x.date,value:(total+=x.value)}));
  const W=1180,H=280,L=48,R=18,T=28,B=54,plotW=W-L-R,plotH=H-T-B;
  const vals=points.map(x=>x.value).concat([0]);
  let min=Math.min(...vals),max=Math.max(...vals);if(min===max){min-=1;max+=1;}
  const pad=(max-min)*.15||1;min-=pad;max+=pad;
  const x=i=>L+i*plotW/(points.length-1),y=v=>T+(max-v)/(max-min)*plotH;
  let d='';points.forEach((p,i)=>{d+=`${i?'L':'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)} `;});
  const meaning=startTonnes!==null&&endTonnes!==null
    ?`意味：GLD金保有量の期間差　${endTonnes.toFixed(2)}t − ${startTonnes.toFixed(2)}t = ${total>0?'+':''}${total.toFixed(2)}t`
    :`意味：${startRow.date}〜${endRow.date}の日次GLD保有量変化の累計`;
  let svg=`<div class="gold-etf-cum-total ${total>0?'up':total<0?'down':''}">${total>0?'+':''}${total.toFixed(2)}t</div><div class="gold-etf-cum-explainer">${esc(meaning)}</div><svg class="gold-etf-chart-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="GLD累積フロー折れ線グラフ">`;
  [0,.25,.5,.75,1].forEach(fr=>{const yy=T+plotH*fr,val=max-(max-min)*fr;svg+=`<line class="grid" x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}"></line><text class="axis-text" x="${L-6}" y="${yy+3}" text-anchor="end">${val.toFixed(1)}</text>`;});
  svg+=`<path class="cum-line" d="${d.trim()}"></path>`;
  points.slice(1).forEach((p,i)=>{const prev=points[i],trend=p.value>=prev.value?'cum-positive':'cum-negative';svg+=`<line class="cum-segment ${trend}" x1="${x(i)}" y1="${y(prev.value)}" x2="${x(i+1)}" y2="${y(p.value)}"><title>${esc(p.date)} ${p.value>=prev.value?'増加':'減少'} ${p.value.toFixed(2)}t</title></line>`;});
  const labelEvery=Math.max(1,Math.ceil(points.length/12));
  points.forEach((p,i)=>{if(i%labelEvery===0||i===points.length-1){const label=p.date.slice(5).replace('-','/');svg+=`<text class="axis-text" x="${x(i)}" y="${H-18}" text-anchor="middle">${esc(label)}</text>`;}});
  svg+='</svg>';
  return svg;
}

async function install(){
  let data;
  try{const r=await fetch(`${DATA_URL}?ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)return;data=await r.json();}catch(_){return;}
  const etf=data.etf||{},aligned=Array.isArray(etf.historyDaily)?etf.historyDaily:[],gld=normalize(etf.gldHistory);
  if(aligned.length>=MIN_ALIGNED_HISTORY_DAYS||gld.length<2)return;

  const apply=(range=22)=>{
    const bar=document.querySelector('[data-etf-bar]');
    const cumulative=document.querySelector('[data-etf-cumulative]');
    if(!bar)return false;
    const slice=gld.slice(-range);
    bar.innerHTML=barSvg(slice);
    if(cumulative)cumulative.innerHTML=cumulativeSvg(slice);
    const cards=[...document.querySelectorAll('.gold-etf-chart-card')];
    if(cards[0]){const t=cards[0].querySelector('.gold-etf-chart-title');if(t)t.textContent='直近の日次ETFフロー（GLD・IAU履歴蓄積中）';}
    const cum=document.querySelector('.gold-etf-chart-card.cumulative .gold-etf-chart-title');if(cum)cum.textContent='GLD金保有量の累積増減（暫定）';
    let note=document.querySelector('[data-etf-fallback-note]');
    if(!note&&cards[0]){
      note=document.createElement('div');note.className='gold-etf-footnote';note.setAttribute('data-etf-fallback-note','');
      note.textContent='暫定表示：IAUの過去日次履歴を蓄積中のため、グラフはGLD単独の公式履歴を表示しています。同一基準日のGLD＋IAU履歴が十分に蓄積すると、自動的に合計フロー表示へ切り替わります。';
      cards[0].appendChild(note);
    }
    return true;
  };

  let tries=0;
  const timer=setInterval(()=>{tries+=1;if(apply(132)||tries>40)clearInterval(timer);},250);
  document.addEventListener('click',ev=>{
    const btn=ev.target.closest&&ev.target.closest('[data-etf-range]');
    if(!btn)return;
    const range=Number(btn.getAttribute('data-etf-range'))||22;
    setTimeout(()=>apply(range),0);
  },true);
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{void install();},{once:true});
else void install();
})();
