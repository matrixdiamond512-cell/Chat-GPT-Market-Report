(function(){
'use strict';
const root=document.querySelector('[data-nikkei-dashboard]');
if(!root)return;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>{if(v===null||v===undefined||v==='')return null;const x=Number(String(v).replace(/,/g,''));return Number.isFinite(x)?x:null};
const fmt=(v,d=2)=>num(v)===null?'取得待ち':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=3,suffix='')=>num(v)===null?'—':`${Number(v)>0?'+':''}${Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d})}${suffix}`;
const date=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得待ち';

// IMPORTANT: target only the canonical card 9 inside .nikkei-grid.
// Do not use a broad text search because the top demand-summary card also contains
// the words 空売り・信用需給 and 信用買い残 in its explanatory text.
function findCanonicalCard(){
  const cards=[...root.querySelectorAll('.nikkei-grid > .nikkei-card')];
  return cards.find(card=>{
    const title=card.querySelector('.nikkei-section-title');
    return title && /^(?:\d+\.\s*)?空売り・信用需給/.test((title.textContent||'').trim());
  })||null;
}
function sourceBlock(x,fallback){
  if(!x)return'';
  const url=x.sourceFileUrl||x.sourceUrl||'';
  if(!url&&!x.asOfDate)return'';
  return `<div class="nikkei-source">出典：${url?`<a href="${esc(url)}" target="_blank" rel="noopener">${esc(x.sourceName||fallback)}</a>`:esc(x.sourceName||fallback)}${x.asOfDate?` / 基準日 ${esc(date(x.asOfDate))}`:''}</div>`;
}
function apply(d){
  const m=d&&d.margin||{};
  const s=d&&d.shortSelling||{};
  const card=findCanonicalCard();
  if(!card)return false;

  const title=card.querySelector('.nikkei-section-title');
  if(title)title.textContent='空売り・信用需給';
  const body=card.querySelector('.nikkei-section-body');
  if(!body)return false;

  const shortRatio=num(s.ratio),avg5=num(s.avg5),avg20=num(s.avg20);
  const buy=num(m.buyBalance),sell=num(m.sellBalance),ratio=num(m.ratio),buyCh=num(m.buyChange),sellCh=num(m.sellChange);
  const imbalance=buy!==null&&sell!==null?buy-sell:null;

  let shortComment='空売り比率は単独で弱気判定せず、5日・20日平均との位置関係から短期の売り圧力を確認します。';
  if(shortRatio!==null&&avg5!==null){
    if(shortRatio>avg5)shortComment=`空売り比率 ${fmt(shortRatio,1)}% は5日平均 ${fmt(avg5,1)}%を上回っています。短期の売り圧力が平常より強い可能性があります。`;
    else if(shortRatio<avg5)shortComment=`空売り比率 ${fmt(shortRatio,1)}% は5日平均 ${fmt(avg5,1)}%を下回っています。直近の空売り圧力は5日平均より弱めです。`;
    else shortComment=`空売り比率 ${fmt(shortRatio,1)}% は5日平均と同水準です。`;
  }

  let marginComment='信用買い残と売り残をセットで確認し、戻り売り圧力と買い戻し余地を両面から評価します。';
  if(ratio!==null){
    if(ratio>=8) marginComment=`信用倍率 ${fmt(ratio,2)}倍。買い残が売り残を大きく上回り、戻り局面では信用買いの整理が上値を重くする可能性があります。`;
    else if(ratio<=2) marginComment=`信用倍率 ${fmt(ratio,2)}倍。売り残の比率が相対的に高く、上昇時は買い戻しが加速する余地があります。`;
    else marginComment=`信用倍率 ${fmt(ratio,2)}倍。買い残と売り残の双方を見ながら、上値の重さと買い戻し余地を評価します。`;
  }

  body.innerHTML=`
   <div class="nikkei-mini-grid">
    <div class="nikkei-mini-card"><div class="nikkei-mini-label">空売り比率</div><div class="nikkei-mini-value">${shortRatio===null?'取得待ち':fmt(shortRatio,1)+'%'}</div><div class="nikkei-note">日次 / ${esc(date(s.asOfDate))}</div></div>
    <div class="nikkei-mini-card"><div class="nikkei-mini-label">5日平均</div><div class="nikkei-mini-value">${avg5===null?'取得待ち':fmt(avg5,1)+'%'}</div><div class="nikkei-note">空売り比率との比較</div></div>
    <div class="nikkei-mini-card"><div class="nikkei-mini-label">20日平均</div><div class="nikkei-mini-value">${avg20===null?'取得待ち':fmt(avg20,1)+'%'}</div><div class="nikkei-note">${avg20===null?'標本不足時は取得待ち':'中期平均との差'}</div></div>
   </div>
   <div class="nikkei-callout">${esc(shortComment)}</div>

   <div class="nikkei-table-scroll" style="margin-top:10px"><table class="nikkei-table">
    <thead><tr><th>信用需給</th><th>残高</th><th>前週比 / 読み方</th></tr></thead>
    <tbody>
     <tr><td><b>信用買い残</b></td><td class="num">${buy===null?'取得待ち':fmt(buy,3)+'兆円'}</td><td class="num">${signed(buyCh,3,'兆円')}</td></tr>
     <tr><td><b>信用売り残</b></td><td class="num">${sell===null?'取得待ち':fmt(sell,3)+'兆円'}</td><td class="num">${signed(sellCh,3,'兆円')}</td></tr>
     <tr><td><b>信用倍率</b></td><td class="num">${ratio===null?'取得待ち':fmt(ratio,2)+'倍'}</td><td>買い残 ÷ 売り残</td></tr>
     <tr><td>買い残－売り残</td><td class="num">${imbalance===null?'取得待ち':fmt(imbalance,3)+'兆円'}</td><td>需給の偏り</td></tr>
    </tbody>
   </table></div>
   <div class="nikkei-callout">${esc(marginComment)}</div>
   <div class="nikkei-callout"><b>このカードから読むこと：</b> 空売り比率は短期の売り圧力、信用買い残は将来の戻り売り圧力、信用売り残は将来の買い戻し余地を示す補助材料です。3つを同時に見て判断します。</div>
   ${sourceBlock(s,'JPX 空売り集計')}
   ${sourceBlock(m,'JPX 信用取引現在高')}`;
  return true;
}
fetch('data/nikkei225-supply-demand.json',{cache:'no-store'})
 .then(r=>r.ok?r.json():Promise.reject(new Error('data load failed')))
 .then(d=>{
   let n=0;
   const t=setInterval(()=>{
     if(apply(d)||++n>80)clearInterval(t);
   },100);
   apply(d);
 })
 .catch(()=>{});
})();
