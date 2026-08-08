(function(){
'use strict';
const root=document.querySelector('[data-gold-dashboard]');
if(!root)return;
const DATA_URL='data/gold-supply-demand.json';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>{const x=Number(v);return Number.isFinite(x)?x:null;};
const fmt=(v,d=0)=>num(v)===null?'取得待ち':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=0,suffix='')=>num(v)===null?'—':`${Number(v)>0?'+':''}${Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d})}${suffix}`;
const dateOnly=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得待ち';
const changeClass=v=>num(v)>0?'up':num(v)<0?'down':'';
const matrix=[
  ['価格↑ × 建玉↑','新規買い','buy'],
  ['価格↑ × 建玉↓','買い戻し','cover'],
  ['価格↓ × 建玉↑','新規売り','sell'],
  ['価格↓ × 建玉↓','手仕舞い','close']
];
function interpretationIndex(text){
  if(!text)return-1;
  if(/新規ロング|新規買い/.test(text))return 0;
  if(/ショートカバー|買い戻し/.test(text))return 1;
  if(/新規ショート|新規売り/.test(text))return 2;
  if(/ロング清算|ロング手仕舞い|手仕舞い/.test(text))return 3;
  return-1;
}
function interpretationLabel(c){
  const text=c.interpretation||'';
  if(/新規ロング|新規買い/.test(text))return'価格上昇＋建玉増加 → 新規ロング流入の可能性';
  if(/ショートカバー|買い戻し/.test(text))return'価格上昇＋建玉減少 → ショートカバーの可能性';
  if(/新規ショート|新規売り/.test(text))return'価格下落＋建玉増加 → 新規ショート流入の可能性';
  if(/ロング清算|ロング手仕舞い|手仕舞い/.test(text))return'価格下落＋建玉減少 → ロング手仕舞いの可能性';
  return'基準日一致価格の取得待ち';
}
function sourceLine(c){
  const name=esc(c.sourceName||'CME Group');
  const date=esc(dateOnly(c.asOfDate));
  if(c.sourceUrl)return`<div class="gold-comex-source">出典：<a href="${esc(c.sourceUrl)}" target="_blank" rel="noopener">${name}</a> / 基準日 ${date}</div>`;
  return`<div class="gold-comex-source">出典：${name} / 基準日 ${date}</div>`;
}
function renderCard(c){
  const title=[...root.querySelectorAll('.gold-section-title')].find(x=>x.textContent.trim()==='COMEX先物需給');
  if(!title)return false;
  const article=title.closest('.gold-card');
  const body=article&&article.querySelector('.gold-section-body');
  if(!body||body.dataset.comexNikkeiApplied==='1')return !!body;
  const idx=interpretationIndex(c.interpretation);
  const waiting=idx<0;
  body.className='gold-section-body gold-comex-nikkei-layout';
  body.dataset.comexNikkeiApplied='1';
  body.innerHTML=`
    <div class="gold-comex-table-wrap">
      <table class="gold-comex-table">
        <thead><tr><th>項目</th><th>本日値</th><th>前日比</th></tr></thead>
        <tbody>
          <tr><td><b>COMEX金先物（中心限月）</b></td><td class="num gold-comex-main-value">${num(c.alignedPrice)===null?'取得待ち':fmt(c.alignedPrice,2)+' USD'}</td><td class="num gold-comex-change ${changeClass(c.alignedPriceChangePercent)}">${num(c.alignedPriceChangePercent)===null?'—':signed(c.alignedPriceChangePercent,2,'%')}</td></tr>
          <tr><td>出来高</td><td class="num">${num(c.volume)===null?'取得待ち':fmt(c.volume,0)+'枚'}</td><td class="num">—</td></tr>
          <tr><td>建玉残高</td><td class="num">${num(c.openInterest)===null?'取得待ち':fmt(c.openInterest,0)+'枚'}</td><td class="num gold-comex-change ${changeClass(c.openInterestChange)}">${num(c.openInterestChange)===null?'—':signed(c.openInterestChange,0,'枚')}</td></tr>
        </tbody>
      </table>
      ${sourceLine(c)}
      ${c.note?`<div class="gold-comex-status-note">${esc(c.note)}</div>`:''}
    </div>
    <div>
      <div class="gold-comex-matrix-title">価格 × 建玉の読み方</div>
      <div class="gold-comex-matrix">${matrix.map((x,i)=>`<div class="gold-comex-matrix-cell ${x[2]} ${idx===i?'active':''}"><strong>${esc(x[0])}</strong><span>= ${esc(x[1])}</span></div>`).join('')}</div>
      <div class="gold-comex-current-read ${waiting?'waiting':''}">本日の判定：${esc(interpretationLabel(c))}</div>
    </div>`;
  return true;
}
let data=null;
let applied=false;
function tryApply(){if(applied||!data)return;if(renderCard(data.comex||{})){applied=true;observer.disconnect();}}
const observer=new MutationObserver(tryApply);
observer.observe(root,{childList:true,subtree:true});
fetch(DATA_URL,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}).then(d=>{data=d;tryApply();}).catch(()=>{});
tryApply();
})();
