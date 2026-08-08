(function(){
'use strict';
const root=document.querySelector('[data-nikkei-dashboard]');
if(!root)return;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const fmt=(v,d=2)=>num(v)===null?'取得待ち':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=3,suffix='')=>num(v)===null?'—':`${Number(v)>0?'+':''}${Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d})}${suffix}`;
const date=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得待ち';
function findCard(){return [...root.querySelectorAll('.nikkei-card')].find(x=>/空売り.*信用|信用.*需給|信用買い残/.test(x.textContent||''));}
function apply(d){
 const m=d&&d.margin||{};
 if(m.status!=='verified')return;
 const card=findCard();if(!card)return;
 const title=card.querySelector('.nikkei-section-title');
 if(title)title.textContent='9. 空売り・信用需給（買い残・売り残対比）';
 const body=card.querySelector('.nikkei-section-body');if(!body)return;
 const buy=num(m.buyBalance),sell=num(m.sellBalance),ratio=num(m.ratio),buyCh=num(m.buyChange),sellCh=num(m.sellChange);
 const imbalance=buy!==null&&sell!==null?buy-sell:null;
 let comment='信用買い残と売り残をセットで確認します。買い残だけでは上値の重さは分かっても、売り方の買い戻し余地を評価できません。';
 if(ratio!==null){
   if(ratio>=8) comment=`信用倍率 ${fmt(ratio,2)}倍。買い残が売り残を大きく上回り、戻り局面では信用買いの整理が上値を重くする可能性があります。`;
   else if(ratio<=2) comment=`信用倍率 ${fmt(ratio,2)}倍。売り残の比率が相対的に高く、上昇時は買い戻しが加速する余地があります。`;
   else comment=`信用倍率 ${fmt(ratio,2)}倍。買い残と売り残の双方を見ながら、買いの重さと買い戻し余地を評価します。`;
 }
 body.innerHTML=`
  <div class="nikkei-table-scroll"><table class="nikkei-table">
   <thead><tr><th>項目</th><th>残高</th><th>前週比</th></tr></thead>
   <tbody>
    <tr><td><b>信用買い残</b></td><td class="num">${buy===null?'取得待ち':fmt(buy,3)+'兆円'}</td><td class="num">${signed(buyCh,3,'兆円')}</td></tr>
    <tr><td><b>信用売り残</b></td><td class="num">${sell===null?'取得待ち':fmt(sell,3)+'兆円'}</td><td class="num">${signed(sellCh,3,'兆円')}</td></tr>
    <tr><td><b>信用倍率</b></td><td class="num">${ratio===null?'取得待ち':fmt(ratio,2)+'倍'}</td><td class="num">買い残 ÷ 売り残</td></tr>
    <tr><td>買い残－売り残</td><td class="num">${imbalance===null?'取得待ち':fmt(imbalance,3)+'兆円'}</td><td class="num">需給の偏り</td></tr>
   </tbody>
  </table></div>
  <div class="nikkei-callout">${esc(comment)}</div>
  <div class="nikkei-source">出典：<a href="${esc(m.sourceFileUrl||m.sourceUrl||'#')}" target="_blank" rel="noopener">${esc(m.sourceName||'JPX 信用取引現在高')}</a> / 基準日 ${esc(date(m.asOfDate))}</div>`;
}
fetch('data/nikkei225-supply-demand.json',{cache:'no-store'})
 .then(r=>r.ok?r.json():Promise.reject())
 .then(d=>{let n=0;const t=setInterval(()=>{apply(d);if(findCard()||++n>50)clearInterval(t)},100);apply(d)})
 .catch(()=>{});
})();
