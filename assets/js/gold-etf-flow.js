(function(){
'use strict';

const DATA_URL='data/gold-supply-demand.json';
const CARD_ATTR='data-gold-etf-enhanced';
let cachedData=null;
let loading=null;

const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
const fmt=(v,d=2)=>n(v)===null?'取得待ち':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=2,suffix='')=>n(v)===null?'取得待ち':`${Number(v)>0?'+':''}${fmt(v,d)}${suffix}`;
const cls=v=>n(v)>0?'up':n(v)<0?'down':'';
const dateText=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得待ち';
const dtText=v=>{if(!v)return'取得待ち';try{return new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(v)).replace(/\//g,'/')+' JST'}catch(_){return String(v)}};

function findCard(){
  const heads=[...document.querySelectorAll('.gold-section-title')];
  const head=heads.find(el=>String(el.textContent||'').trim()==='ETF資金フロー');
  return head?head.closest('.gold-card'):null;
}

function statusInfo(x){
  const s=String(x&&x.status||'unavailable');
  if(s==='verified')return {label:'更新済み',cls:'good'};
  if(s==='stale')return {label:'前回確認値',cls:'warn'};
  return {label:'取得待ち',cls:'muted'};
}

function sameDate(a,b){return Boolean(a&&b&&String(a).slice(0,10)===String(b).slice(0,10));}

function firstNumber(obj,keys){
  for(const key of keys){
    const value=n(obj&&obj[key]);
    if(value!==null)return value;
  }
  return null;
}

function firstText(obj,keys){
  for(const key of keys){
    const value=obj&&obj[key];
    if(value!==undefined&&value!==null&&String(value).trim())return String(value);
  }
  return '';
}

function normalizeHistory(etf){
  const raw=Array.isArray(etf.historyDaily)?etf.historyDaily:
    Array.isArray(etf.dailyHistory)?etf.dailyHistory:
    Array.isArray(etf.history)?etf.history:[];
  const rows=raw.map(row=>{
    const date=firstText(row,['asOfDate','date','day']);
    const gldChange=firstNumber(row,['gldChangeTonnes','gldChange','gldFlowTonnes']);
    const iauChange=firstNumber(row,['iauChangeTonnes','iauChange','iauFlowTonnes']);
    const explicit=firstNumber(row,['combinedChangeTonnes','combinedChange','totalChangeTonnes']);
    const aligned=row&&row.aligned===false?false:true;
    const combined=explicit!==null?explicit:(aligned&&gldChange!==null&&iauChange!==null?gldChange+iauChange:null);
    return {date,gldChange,iauChange,combined};
  }).filter(x=>x.date&&x.combined!==null);
  rows.sort((a,b)=>String(a.date).localeCompare(String(b.date)));

  const gld=etf.gld||{},iau=etf.iau||{};
  if(sameDate(gld.asOfDate,iau.asOfDate)&&n(gld.changeTonnes)!==null&&n(iau.changeTonnes)!==null){
    const date=String(gld.asOfDate).slice(0,10);
    if(!rows.some(x=>String(x.date).slice(0,10)===date)){
      rows.push({date,gldChange:Number(gld.changeTonnes),iauChange:Number(iau.changeTonnes),combined:Number(gld.changeTonnes)+Number(iau.changeTonnes)});
    }
  }
  rows.sort((a,b)=>String(a.date).localeCompare(String(b.date)));
  return rows;
}

function sourceLine(x){
  if(!x||!x.sourceUrl)return'';
  return `<div class="gold-etf-source-line">出典：<a href="${esc(x.sourceUrl)}" target="_blank" rel="noopener">${esc(x.sourceName||'情報源')}</a></div>`;
}

function summaryTile(index,label,value,valueClass,sub,meta,extraClass=''){
  return `<div class="gold-etf-summary-tile ${extraClass}">
    <div class="gold-etf-tile-head"><span class="gold-etf-index">${index}</span><span>${esc(label)}</span></div>
    <div class="gold-etf-tile-value ${valueClass||''}">${value}</div>
    ${sub?`<div class="gold-etf-tile-sub">${sub}</div>`:''}
    ${meta?`<div class="gold-etf-tile-meta">${meta}</div>`:''}
  </div>`;
}

function buildGlobalTile(global,index){
  const holdings=firstNumber(global,['tonnes','holdingsTonnes','totalTonnes','goldHoldingsTonnes']);
  const ytd=firstNumber(global,['ytdFlowTonnes','ytdChangeTonnes','yearToDateTonnes']);
  const monthly=firstNumber(global,['monthlyFlowTonnes','flowTonnes','changeTonnes']);
  const flow=ytd!==null?ytd:monthly;
  const flowLabel=ytd!==null?'年初来':monthly!==null?'最新フロー':'最新フロー';
  const st=statusInfo(global);
  return `<div class="gold-etf-summary-tile global">
    <div class="gold-etf-tile-head"><span class="gold-etf-index">${index}</span><span>世界金ETF 最新</span></div>
    <span class="gold-etf-frequency-pill">週次 / 月次</span>
    <div class="gold-etf-global-lines">
      <div class="gold-etf-global-line"><span>保有量</span><strong>${holdings===null?'取得待ち':fmt(holdings,1)+'t'}</strong></div>
      <div class="gold-etf-global-line"><span>${flowLabel}</span><strong class="${cls(flow)}">${flow===null?'取得待ち':signed(flow,1,'t')}</strong></div>
    </div>
    <div class="gold-etf-tile-meta">基準日 ${dateText(global.asOfDate||global.period)}<br><span class="gold-etf-status ${st.cls}">${st.label}</span></div>
  </div>`;
}

function buildDateTile(data,index,gld,iau,global){
  const dates=[gld.asOfDate,iau.asOfDate,global.asOfDate||global.period].filter(Boolean).map(v=>String(v).slice(0,10));
  const latest=dates.length?dates.sort().slice(-1)[0]:null;
  return `<div class="gold-etf-summary-tile date">
    <div class="gold-etf-tile-head"><span class="gold-etf-index">${index}</span><span>基準日 / 更新日</span></div>
    <div class="gold-etf-date-grid">
      <div class="gold-etf-date-row"><span>最新基準日</span><strong>${dateText(latest)}</strong></div>
      <div class="gold-etf-date-row"><span>ページ更新</span><strong>${dtText(data.generatedAt)}</strong></div>
    </div>
    <div class="gold-etf-tile-meta">各ETFの基準日は下表に個別表示</div>
  </div>`;
}

function buildBarSvg(rows){
  if(!rows.length)return '<div class="gold-etf-chart-empty">同一基準日のGLD・IAU履歴がまだありません。<br>基準日が揃ったデータから日次合計を描画します。</div>';
  const W=1180,H=280,L=48,R=18,T=28,B=54,plotW=W-L-R,plotH=H-T-B;
  const maxAbs=Math.max(1,...rows.map(x=>Math.abs(x.combined)))*1.15;
  const y=v=>T+(maxAbs-v)/(maxAbs*2)*plotH;
  const zero=y(0);
  const step=plotW/rows.length;
  const barW=Math.max(8,Math.min(34,step*.55));
  const labelEvery=Math.max(1,Math.ceil(rows.length/12));
  const ticks=[maxAbs,maxAbs/2,0,-maxAbs/2,-maxAbs];
  let svg=`<svg class="gold-etf-chart-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="GLDとIAUの日次合計フロー棒グラフ">`;
  ticks.forEach(t=>{const yy=y(t);svg+=`<line class="${t===0?'zero':'grid'}" x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}"></line><text class="axis-text" x="${L-7}" y="${yy+3}" text-anchor="end">${Math.abs(t)<.005?'0':t.toFixed(1)}</text>`;});
  rows.forEach((row,i)=>{
    const cx=L+step*i+step/2;
    const yy=y(row.combined),top=Math.min(yy,zero),height=Math.max(2,Math.abs(zero-yy));
    const barClass=row.combined>=0?'bar-positive':'bar-negative';
    const valueY=row.combined>=0?top-6:top+height+13;
    const label=String(row.date).slice(5).replace('-','/');
    svg+=`<rect class="${barClass}" x="${cx-barW/2}" y="${top}" width="${barW}" height="${height}" rx="2"><title>${esc(row.date)} ${row.combined>0?'+':''}${row.combined.toFixed(2)}t</title></rect>`;
    if(rows.length<=35)svg+=`<text class="value-text" x="${cx}" y="${valueY}" text-anchor="middle">${row.combined>0?'+':''}${row.combined.toFixed(2)}</text>`;
    if(i%labelEvery===0||i===rows.length-1)svg+=`<text class="axis-text" x="${cx}" y="${H-20}" text-anchor="middle">${esc(label)}</text>`;
  });
  svg+='</svg>';
  return svg;
}

function buildCumulativeSvg(rows){
  if(rows.length<2)return '<div class="gold-etf-chart-empty">累積フローは同一基準日の履歴が2営業日以上蓄積すると表示します。</div>';
  let total=0;
  const points=rows.map(x=>{total+=x.combined;return {date:x.date,value:total};});
  const W=1180,H=280,L=48,R=18,T=28,B=54,plotW=W-L-R,plotH=H-T-B;
  const vals=points.map(x=>x.value).concat([0]);
  let min=Math.min(...vals),max=Math.max(...vals);
  if(min===max){min-=1;max+=1;}
  const pad=(max-min)*.15||1;min-=pad;max+=pad;
  const x=i=>L+(points.length===1?plotW/2:i*plotW/(points.length-1));
  const y=v=>T+(max-v)/(max-min)*plotH;
  const zero=y(0);
  let d='';
  points.forEach((p,i)=>{d+=`${i?'L':'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)} `;});
  let svg=`<svg class="gold-etf-chart-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="GLDとIAUの累積フロー折れ線グラフ">`;
  [0,.25,.5,.75,1].forEach(fr=>{const yy=T+plotH*fr;const val=max-(max-min)*fr;svg+=`<line class="${Math.abs(val)<.02?'zero':'grid'}" x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}"></line><text class="axis-text" x="${L-6}" y="${yy+3}" text-anchor="end">${val.toFixed(1)}</text>`;});
  if(zero>=T&&zero<=T+plotH)svg+=`<line class="zero" x1="${L}" x2="${W-R}" y1="${zero}" y2="${zero}"></line>`;
  svg+=`<path class="cum-line" d="${d.trim()}"></path>`;
  points.slice(1).forEach((p,i)=>{
    const prev=points[i],trend=p.value>=prev.value?'cum-positive':'cum-negative';
    svg+=`<line class="cum-segment ${trend}" x1="${x(i)}" y1="${y(prev.value)}" x2="${x(i+1)}" y2="${y(p.value)}"><title>${esc(p.date)} ${p.value>=prev.value?'増加':'減少'} ${p.value.toFixed(2)}t</title></line>`;
  });
  points.forEach((p,i)=>{if(i===0||i===points.length-1)svg+=`<circle class="cum-dot" cx="${x(i)}" cy="${y(p.value)}" r="3.5"></circle>`;});
  const labelEvery=Math.max(1,Math.ceil(points.length/12));
  points.forEach((p,i)=>{if(i%labelEvery===0||i===points.length-1){const label=String(p.date).slice(5).replace('-','/');svg+=`<text class="axis-text" x="${x(i)}" y="${H-18}" text-anchor="middle">${esc(label)}</text>`;}});
  svg+='</svg>';
  return `<div class="gold-etf-cum-total">${total>0?'+':''}${total.toFixed(2)}t</div>${svg}`;
}

function rowHtml(name,fundClass,x,change,holdings,statusText,asOf,updated){
  const st=statusInfo(x);
  return `<tr>
    <td class="fund ${fundClass||''}">${esc(name)}</td>
    <td>${dateText(asOf)}</td>
    <td class="num">${holdings===null?'取得待ち':fmt(holdings,2)+' t'}</td>
    <td class="num ${cls(change)}">${change===null?'—':signed(change,2,' t')}</td>
    <td><span class="gold-etf-status ${st.cls}">${esc(statusText||st.label)}</span>${updated?`<div class="gold-etf-tile-meta">${esc(updated)}</div>`:''}</td>
  </tr>`;
}

function renderCard(card,data){
  if(card.hasAttribute(CARD_ATTR))return;
  const etf=data.etf||{},gld=etf.gld||{},iau=etf.iau||{},global=etf.global||{};
  const aligned=sameDate(gld.asOfDate,iau.asOfDate);
  const gldChange=n(gld.changeTonnes),iauChange=n(iau.changeTonnes);
  const combinedChange=aligned&&gldChange!==null&&iauChange!==null?gldChange+iauChange:null;
  const combinedHoldings=aligned&&n(gld.tonnes)!==null&&n(iau.tonnes)!==null?Number(gld.tonnes)+Number(iau.tonnes):null;
  const history=normalizeHistory(etf);
  const globalHoldings=firstNumber(global,['tonnes','holdingsTonnes','totalTonnes','goldHoldingsTonnes']);
  const globalFlow=firstNumber(global,['ytdFlowTonnes','ytdChangeTonnes','yearToDateTonnes','monthlyFlowTonnes','flowTonnes','changeTonnes']);
  const gldStatus=statusInfo(gld),iauStatus=statusInfo(iau),globalStatus=statusInfo(global);
  const combinedSub=aligned?'同一基準日のGLD＋IAU':'算出保留：GLDとIAUの基準日不一致';
  const combinedMeta=`GLD ${dateText(gld.asOfDate)} / IAU ${dateText(iau.asOfDate)}`;
  const body=card.querySelector('.gold-section-body');
  if(!body)return;
  card.classList.add('gold-etf-enhanced');
  card.setAttribute(CARD_ATTR,'');
  body.innerHTML=`
    <div class="gold-etf-summary-grid">
      ${summaryTile(1,'GLD 前日比',gldChange===null?'取得待ち':signed(gldChange,2,'t'),gldChange===null?'wait':cls(gldChange),`<span class="gold-etf-status ${gldStatus.cls}">${gldStatus.label}</span>`,`基準日 ${dateText(gld.asOfDate)}<br>更新 ${dtText(gld.fetchedAt)}`)}
      ${summaryTile(2,'IAU 前日比',iauChange===null?'取得待ち':signed(iauChange,2,'t'),iauChange===null?'wait':cls(iauChange),`<span class="gold-etf-status ${iauStatus.cls}">${iauStatus.label}</span>`,`基準日 ${dateText(iau.asOfDate)}<br>更新 ${dtText(iau.fetchedAt)}`)}
      ${summaryTile(3,'GLD＋IAU 日次合計',combinedChange===null?'算出保留':signed(combinedChange,2,'t'),combinedChange===null?'wait':cls(combinedChange),esc(combinedSub),esc(combinedMeta),'combined')}
      ${buildGlobalTile(global,4)}
      ${buildDateTile(data,5,gld,iau,global)}
    </div>
    <div class="gold-etf-charts">
      <div class="gold-etf-chart-card">
        <div class="gold-etf-chart-head"><div class="gold-etf-chart-title">直近の日次ETFフロー（GLD＋IAU・同一基準日のみ）</div><div class="gold-etf-range"><button type="button" data-etf-range="10">10日</button><button type="button" data-etf-range="22">1か月</button><button type="button" data-etf-range="66">3か月</button><button type="button" class="active" data-etf-range="132">6か月</button></div></div>
        <div class="gold-etf-chart-wrap" data-etf-bar>${buildBarSvg(history.slice(-132))}</div>
      </div>
      <div class="gold-etf-chart-card cumulative">
        <div class="gold-etf-chart-head"><div class="gold-etf-chart-title">累積フロー（GLD＋IAU）</div></div>
        <div class="gold-etf-chart-wrap" data-etf-cumulative>${buildCumulativeSvg(history.slice(-132))}</div>
      </div>
    </div>
    <div class="gold-etf-table-wrap"><table class="gold-etf-table"><thead><tr><th>ETF</th><th>基準日</th><th>保有量</th><th>前回比</th><th>状態 / 更新</th></tr></thead><tbody>
      ${rowHtml('GLD','gld',gld,gldChange,n(gld.tonnes),gldStatus.label,gld.asOfDate,dtText(gld.fetchedAt))}
      ${rowHtml('IAU','',iau,iauChange,n(iau.tonnes),iauStatus.label,iau.asOfDate,dtText(iau.fetchedAt))}
      ${rowHtml('GLD＋IAU 日次合計','',aligned?{status:'verified'}:{status:'unavailable'},combinedChange,combinedHoldings,aligned?'同一基準日':'基準日不一致',aligned?gld.asOfDate:null,aligned?dtText(data.generatedAt):'算出しません')}
      ${rowHtml('世界金ETF','',global,globalFlow,globalHoldings,globalStatus.label,global.asOfDate||global.period,global.fetchedAt?dtText(global.fetchedAt):'週次 / 月次')}
    </tbody></table></div>
    <div class="gold-etf-footnote">※ GLDとIAUは更新タイミングが異なる場合があります。日次合計とグラフは、両ETFの基準日が一致したデータだけを使用します。世界金ETFはWGC等の週次・月次データで、GLD・IAUの日次データとは更新頻度が異なるため、基準日と更新状況を個別表示します。</div>
    ${sourceLine(gld)}${sourceLine(iau)}${sourceLine(global)}
  `;
  card.querySelectorAll('[data-etf-range]').forEach(btn=>btn.addEventListener('click',()=>{
    card.querySelectorAll('[data-etf-range]').forEach(x=>x.classList.toggle('active',x===btn));
    const range=Number(btn.getAttribute('data-etf-range'))||22;
    const target=card.querySelector('[data-etf-bar]');
    if(target)target.innerHTML=buildBarSvg(history.slice(-range));
    const cumulative=card.querySelector('[data-etf-cumulative]');
    if(cumulative)cumulative.innerHTML=buildCumulativeSvg(history.slice(-range));
  }));
}

async function getData(){
  if(cachedData)return cachedData;
  if(loading)return loading;
  loading=fetch(`${DATA_URL}?ts=${Date.now()}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}).then(data=>(cachedData=data)).finally(()=>{loading=null;});
  return loading;
}

async function enhance(){
  const card=findCard();
  if(!card||card.hasAttribute(CARD_ATTR))return false;
  try{renderCard(card,await getData());return true;}catch(err){console.error('gold ETF flow enhancement failed',err);return false;}
}

function install(){
  void enhance();
  const root=document.querySelector('[data-gold-dashboard]')||document.body;
  const observer=new MutationObserver(()=>{void enhance();});
  observer.observe(root,{childList:true,subtree:true});
  setTimeout(()=>observer.disconnect(),20000);
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});
else install();
})();
