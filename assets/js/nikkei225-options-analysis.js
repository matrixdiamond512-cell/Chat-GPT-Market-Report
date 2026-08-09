(function(){
'use strict';

const ROOT='[data-nikkei-dashboard]';
const DATA_URL='data/nikkei225-supply-demand.json';
const MARKET_URL='data/market/latest.json';

const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>{if(v===null||v===undefined||v==='')return null;const n=Number(String(v).replace(/,/g,''));return Number.isFinite(n)?n:null};
const fmt=(v,d=0)=>num(v)===null?'取得待ち':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=0,suffix='')=>num(v)===null?'—':`${Number(v)>0?'+':''}${Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d})}${suffix}`;
const dateOnly=v=>{if(!v)return'取得待ち';const s=String(v).slice(0,10);return /^\d{4}-\d{2}-\d{2}$/.test(s)?s.replaceAll('-','/'):String(v)};

function pickArray(opt,names){
  for(const k of names){if(Array.isArray(opt?.[k])&&opt[k].length)return opt[k]}
  return [];
}

function normRows(opt){
  const rows=pickArray(opt,['strikeOpenInterest','strikeOI','openInterestByStrike','optionChain']);
  return rows.map(r=>({
    strike:num(r.strike??r.strikePrice??r.price),
    putOi:num(r.putOi??r.putOpenInterest??r.put_oi),
    callOi:num(r.callOi??r.callOpenInterest??r.call_oi),
    putChange:num(r.putOiChange??r.putChange??r.put_oi_change),
    callChange:num(r.callOiChange??r.callChange??r.call_oi_change)
  })).filter(r=>r.strike!==null).sort((a,b)=>a.strike-b.strike);
}

function ratio(a,b){return num(a)!==null&&num(b)!==null&&Number(b)!==0?Number(a)/Number(b):null}

function calcMetrics(rows,current,opt){
  const totalPut=rows.reduce((s,r)=>s+(r.putOi||0),0);
  const totalCall=rows.reduce((s,r)=>s+(r.callOi||0),0);
  const overallPcr=num(opt.putCallRatio)??(rows.length?ratio(totalPut,totalCall):null);
  let atmPcr=null;
  if(rows.length&&current!==null){
    const lo=current*0.98,hi=current*1.02;
    const atm=rows.filter(r=>r.strike>=lo&&r.strike<=hi);
    const p=atm.reduce((s,r)=>s+(r.putOi||0),0);
    const c=atm.reduce((s,r)=>s+(r.callOi||0),0);
    atmPcr=ratio(p,c);
  }
  const putVol=num(opt.putVolume),callVol=num(opt.callVolume);
  const totalVol=putVol!==null||callVol!==null?(putVol||0)+(callVol||0):null;
  const refPut=num(opt.referencePutSettlementVolatility),refCall=num(opt.referenceCallSettlementVolatility);
  let skew=opt.skewLabel||opt.skew||null;
  if(!skew&&refPut!==null&&refCall!==null){
    const d=refPut-refCall;
    skew=Math.abs(d)<0.3?'ほぼ中立':d>0?'Put優位':'Call優位';
  }
  return {overallPcr,atmPcr,totalVol,skew:skew||'取得待ち'};
}

function calcBands(rows,current){
  if(!rows.length)return{};
  const calls=[...rows].filter(r=>num(r.callOi)!==null).sort((a,b)=>(b.callOi||0)-(a.callOi||0));
  const puts=[...rows].filter(r=>num(r.putOi)!==null).sort((a,b)=>(b.putOi||0)-(a.putOi||0));
  const topCall=calls[0]?.strike??null;
  const topPut=puts[0]?.strike??null;
  const upper=current!==null?rows.filter(r=>r.strike>=current).sort((a,b)=>(b.callOi||0)-(a.callOi||0))[0]?.strike??null:null;
  const lower=current!==null?rows.filter(r=>r.strike<=current).sort((a,b)=>(b.putOi||0)-(a.putOi||0))[0]?.strike??null:null;
  return {topCall,topPut,upper,lower};
}

function rangeText(primary,secondary){
  if(primary===null&&secondary===null)return'取得待ち';
  if(primary!==null&&secondary!==null&&primary!==secondary){
    const a=Math.min(primary,secondary),b=Math.max(primary,secondary);
    return `${fmt(a)}〜${fmt(b)}円`;
  }
  return `${fmt(primary??secondary)}円`;
}

function metric(label,value,sub=''){
  return `<div class="nikkei-options-metric"><span>${esc(label)}</span><b>${value}</b>${sub?`<small>${esc(sub)}</small>`:''}</div>`;
}

function rankHtml(rows,key,title,side){
  const ranked=rows.filter(r=>num(r[key])!==null&&Number(r[key])>0).sort((a,b)=>b[key]-a[key]).slice(0,5);
  return `<div class="nikkei-options-rank ${side}"><h4>${esc(title)}</h4>${ranked.length?ranked.map((r,i)=>`<div class="nikkei-options-rank-row"><em>${i+1}</em><span>${fmt(r.strike)}円</span><b>${signed(r[key],0,'枚')}</b></div>`).join(''):`<div class="nikkei-options-unavailable compact">OI増加データは取得待ちです。</div>`}</div>`;
}

function heatmapHtml(rows,current){
  if(!rows.length){
    return `<div class="nikkei-options-unavailable"><b>権利行使価格別建玉は取得待ちです。</b><span>JPXのストライク別Call/Put OIがデータ連携された時点で、ここに建玉集中帯を自動表示します。推測値やサンプル値は表示しません。</span></div>`;
  }
  const max=Math.max(1,...rows.flatMap(r=>[r.putOi||0,r.callOi||0]));
  return `<div class="nikkei-options-heatmap">
    <div class="nikkei-options-row head"><span>権利行使価格</span><span>Put OI</span><span>枚</span><span>Call OI</span><span>枚</span></div>
    ${rows.map(r=>{
      const cur=current!==null&&Math.abs(r.strike-current)<=125;
      return `<div class="nikkei-options-row ${cur?'nikkei-options-current':''}">
        <span class="nikkei-options-strike">${fmt(r.strike)}</span>
        <span class="nikkei-options-bar put"><i style="width:${Math.round(((r.putOi||0)/max)*100)}%"></i></span>
        <span class="nikkei-options-val">${num(r.putOi)===null?'—':fmt(r.putOi)}</span>
        <span class="nikkei-options-bar call"><i style="width:${Math.round(((r.callOi||0)/max)*100)}%"></i></span>
        <span class="nikkei-options-val">${num(r.callOi)===null?'—':fmt(r.callOi)}</span>
      </div>`;
    }).join('')}
    <div class="nikkei-options-legend"><span><i class="put"></i>Put＝ブルー</span><span><i class="call"></i>Call＝ピンク</span></div>
  </div>`;
}

function dataBadge(label,value,tone='neutral'){
  return `<div class="nikkei-options-summary-card ${tone}"><small>${esc(label)}</small><strong>${value}</strong></div>`;
}

function findLegacyOptionCard(root){
  return [...root.querySelectorAll('.nikkei-card')].find(card=>{
    if(card.classList.contains('nikkei-options-analysis'))return false;
    const title=(card.querySelector('.nikkei-section-title')?.textContent||'').replace(/^\s*\d+\.\s*/,'');
    return /オプション|ボラティリティ/.test(title);
  })||null;
}

function render(root,d,market){
  if(root.querySelector('.nikkei-options-analysis'))return;
  const opt=d?.options||{};
  const fut=market?.markets?.nikkei225_futures_ose||{};
  const current=num(fut.value)??num(d?.futures?.price)??num(opt.ivUnderlyingClose);
  const rows=normRows(opt);
  const bands=calcBands(rows,current);
  const metrics=calcMetrics(rows,current,opt);
  const iv=num(opt.iv??opt.baseVolatility);
  const upperPrimary=bands.upper??bands.topCall??null;
  const upperSecondary=bands.topCall??bands.upper??null;
  const lowerPrimary=bands.lower??bands.topPut??null;
  const lowerSecondary=bands.topPut??bands.lower??null;
  const upperText=rangeText(upperPrimary,upperSecondary);
  const lowerText=rangeText(lowerPrimary,lowerSecondary);
  const upperPoint=upperPrimary??upperSecondary;
  const lowerPoint=lowerPrimary??lowerSecondary;
  const gaugeLeft=current!==null&&lowerPoint!==null&&upperPoint!==null&&upperPoint!==lowerPoint?Math.max(5,Math.min(95,((current-lowerPoint)/(upperPoint-lowerPoint))*100)):50;
  const oiAsOf=opt.strikeOiAsOfDate||opt.openInterestAsOfDate||opt.optionChainAsOfDate||opt.asOfDate||opt.ivAsOfDate;
  const sourceLink=opt.sourceUrl?`<div class="nikkei-options-source">出典：<a href="${esc(opt.sourceUrl)}" target="_blank" rel="noopener">${esc(opt.sourceName||'JPX')}</a> / 基準日 ${esc(dateOnly(oiAsOf))}</div>`:'';
  const section=document.createElement('section');
  section.className='nikkei-card nikkei-options-analysis';
  section.innerHTML=`
    <div class="nikkei-section-head nikkei-options-section-head">
      <div class="nikkei-options-intro">
        <div>
          <h2 class="nikkei-section-title">日経225オプション需給</h2>
          <div class="nikkei-options-note">OSEの日経225オプションを、方向予想ではなく「建玉集中帯・OI増減・IV・Put/Call・SQ接近」からヘッジ圧力が変わりやすい価格帯として読みます。</div>
        </div>
        <span class="nikkei-freq daily">日次</span>
      </div>
    </div>
    <div class="nikkei-section-body">
      <div class="nikkei-options-summary-strip">
        ${dataBadge('現在値',current===null?'取得待ち':`${fmt(current)}円`,'current')}
        ${dataBadge('次回SQ',dateOnly(opt.nextSqDate)+(num(opt.businessDaysToSq)!==null?` / 残り${fmt(opt.businessDaysToSq)}営業日`:''),'sq')}
        ${dataBadge('上側Call集中',upperText,'call')}
        ${dataBadge('下側Put集中',lowerText,'put')}
      </div>

      <div class="nikkei-options-layout">
        <div class="nikkei-options-panel heatmap-panel">
          <div class="nikkei-options-panel-head"><h3>権利行使価格別 建玉ヒートマップ</h3><span>Call＝ピンク / Put＝ブルー</span></div>
          ${heatmapHtml(rows,current)}
          ${sourceLink}
        </div>
        <div class="nikkei-options-panel rank-panel">
          <h3>前日比 OI増減ランキング</h3>
          <div class="nikkei-options-rank-grid">${rankHtml(rows,'callChange','Call OI増加','call')}${rankHtml(rows,'putChange','Put OI増加','put')}</div>
          <div class="nikkei-note">残高の大きさだけでなく、どの権利行使価格で新しく建玉が増えたかを優先して確認します。</div>
        </div>
        <div class="nikkei-options-panel metrics-panel">
          <h3>IV・PCR・出来高</h3>
          <div class="nikkei-options-metrics">
            ${metric('基準IV',iv===null?'取得待ち':fmt(iv,2)+'%','JPX基準ボラティリティ')}
            ${metric('Put/Call OI比率',metrics.overallPcr===null?'取得待ち':fmt(metrics.overallPcr,2))}
            ${metric('ATM±2% PCR',metrics.atmPcr===null?'取得待ち':fmt(metrics.atmPcr,2))}
            ${metric('当日出来高',metrics.totalVol===null?'取得待ち':fmt(metrics.totalVol)+'枚')}
            ${metric('Skew',esc(metrics.skew))}
          </div>
          <div class="nikkei-note">PCRやIV単独では強弱を断定せず、建玉集中・OI増減・SQ残存日数とセットで見ます。</div>
        </div>
      </div>

      <div class="nikkei-options-sq">
        <div class="nikkei-options-panel">
          <h3>SQ・ヘッジ圧力の見方</h3>
          <div class="nikkei-options-bullets">
            <div class="nikkei-options-bullet call"><b>上側</b><span>${upperPoint===null?'Call建玉データ取得待ち':`${fmt(upperPoint)}円付近のCall集中を監視。価格接近時のヘッジフロー変化に注意。`}</span></div>
            <div class="nikkei-options-bullet put"><b>下側</b><span>${lowerPoint===null?'Put建玉データ取得待ち':`${fmt(lowerPoint)}円付近のPut集中を監視。下落時のデルタ変化拡大に注意。`}</span></div>
            <div class="nikkei-options-bullet sq"><b>SQ</b><span>次回SQ ${dateOnly(opt.nextSqDate)}${num(opt.businessDaysToSq)!==null?`（残り${fmt(opt.businessDaysToSq)}営業日）`:''}。SQ接近ほど建玉集中帯への価格吸着と反転の両方を重視。</span></div>
          </div>
        </div>
        <div class="nikkei-options-gauge">
          <b>ヘッジ圧力の位置関係</b>
          <div class="nikkei-options-gauge-side call">Call集中<br>${upperPoint===null?'—':fmt(upperPoint)}</div>
          <div class="nikkei-options-gauge-line"><i class="nikkei-options-gauge-dot" style="left:${gaugeLeft}%"></i></div>
          <div class="nikkei-options-gauge-labels"><span class="put">Put ${lowerPoint===null?'—':fmt(lowerPoint)}</span><span>現在 ${current===null?'—':fmt(current)}</span><span class="call">Call ${upperPoint===null?'—':fmt(upperPoint)}</span></div>
        </div>
      </div>

      <div class="nikkei-options-combined">
        <div class="nikkei-options-judge"><small>総合需給判定</small><strong>${esc(d?.assessment?.overall||'判定待ち')}</strong></div>
        <div class="nikkei-options-comment"><b>先物＋オプションの総合解釈</b><br>先物は「価格×建玉」で新規買い・買い戻し・新規売り・手仕舞いを判定し、オプションは重要価格帯とヘッジ感応度を補完します。Call建玉＝上値抵抗、Put建玉＝下値支持と機械的に決めず、OI増減・IV・SQまでの日数を同時に確認します。</div>
        <div class="nikkei-options-judge option"><small>オプション評価</small><strong>${esc(d?.assessment?.options||'判定待ち')}</strong></div>
      </div>

      <div class="nikkei-options-pricebands">
        <div class="nikkei-options-chip call"><b>上側Call集中</b><span>${upperText}。Call建玉の増減と価格接近時のヘッジ変化を監視。</span></div>
        <div class="nikkei-options-chip put"><b>下側Put集中</b><span>${lowerText}。下落局面でのPut建玉増減とヘッジ需要を監視。</span></div>
        <div class="nikkei-options-chip"><b>SQ/MSQ</b><span>次回SQ ${dateOnly(opt.nextSqDate)}。SQ接近ほどオプション需給の重要度を引き上げます。</span></div>
        <div class="nikkei-options-chip"><b>実務上の使い方</b><span>方向当てではなく価格帯分析。OSE建玉から日本市場のヘッジ圧力変化を読む用途に限定します。</span></div>
      </div>
    </div>`;

  const legacy=findLegacyOptionCard(root);
  if(legacy){
    legacy.replaceWith(section);
  }else{
    const grid=root.querySelector('.nikkei-grid');
    if(grid){
      const ai=grid.querySelector('.nikkei-ai');
      if(ai)grid.insertBefore(section,ai);else grid.appendChild(section);
    }else root.appendChild(section);
  }
}

async function init(){
  const root=document.querySelector(ROOT);if(!root)return;
  try{
    const [d,m]=await Promise.all([
      fetch(DATA_URL,{cache:'no-store'}).then(r=>r.json()),
      fetch(MARKET_URL,{cache:'no-store'}).then(r=>r.ok?r.json():{}).catch(()=>({}))
    ]);
    let tries=0;
    const timer=setInterval(()=>{
      tries++;
      if(root.querySelector('.nikkei-grid')){
        const legacy=findLegacyOptionCard(root);
        if(legacy||tries>10){clearInterval(timer);render(root,d,m)}
      }else if(tries>80){clearInterval(timer)}
    },100);
  }catch(e){console.error('options analysis',e)}
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
