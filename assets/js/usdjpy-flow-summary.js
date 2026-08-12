(()=>{
'use strict';
const root=document.querySelector('[data-usdjpy-flow-overview]');
if(!root)return;
const URL='data/usdjpy-flow-summary.json';
const n=v=>{if(v===null||v===undefined||v==='')return null;const x=Number(v);return Number.isFinite(x)?x:null};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const tone=v=>n(v)>0?'is-buy':n(v)<0?'is-sell':'';
const arrow=v=>n(v)>0?'↑':n(v)<0?'↓':'→';
function topDrivers(section){
  return (Array.isArray(section?.drivers)?section.drivers:[])
    .filter(x=>x&&['verified','calculated'].includes(x.status)&&n(x.score)!==null)
    .sort((a,b)=>Math.abs(Number(b.score))-Math.abs(Number(a.score))||String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')))
    .slice(0,3);
}
function evidence(section){
  const rows=topDrivers(section);
  if(!rows.length)return '<li class="is-muted"><span>→</span><b>方向材料</b><em>現時点では限定的</em></li>';
  return rows.map(x=>`<li><span class="usd-flow-arrow ${tone(x.score)}">${arrow(x.score)}</span><b>${esc(x.name)}</b><em>${esc(x.valueText||'横ばい')}</em></li>`).join('');
}
function render(data){
  if(!data||data.pageId!=='usdjpy-flow-summary'){
    root.innerHTML='<div class="usd-flow-empty">実需フローの表示データを準備しています。</div>';
    root.removeAttribute('aria-busy');return;
  }
  const real=data.realDemand||{},spec=data.speculative||{},combined=data.combined||{};
  const realScore=n(real.score),specScore=n(spec.score);
  const realLabel=realScore>0?'ドル買い優勢':realScore<0?'円買い優勢':'方向感は限定的';
  const specLabel=specScore>0?'ドル買い優勢':specScore<0?'円買い優勢':'中立';
  root.innerHTML=`<div class="usd-flow-head"><h2>実需・投機フローの要点</h2><p>方向判断に必要な主要材料を簡潔に表示</p></div>
    <div class="usd-flow-public-grid">
      <article class="usd-flow-public-card"><span>実需総合判定</span><strong class="${tone(realScore)}">${esc(realLabel)}</strong><ul>${evidence(real)}</ul></article>
      <article class="usd-flow-public-card"><span>投機フロー</span><strong class="${tone(specScore)}">${esc(specLabel)}</strong><ul>${evidence(spec)}</ul></article>
      <article class="usd-flow-public-card is-comment"><span>現在の読み方</span><strong>${esc(combined.leadingFlow&&combined.leadingFlow!=='保留'?`${combined.leadingFlow}主導`:'材料の一致を確認')}</strong><p>${esc(combined.sessionComment||'金利・出来高・オーダーの方向が一致するか確認します。')}</p></article>
    </div>`;
  root.removeAttribute('aria-busy');
}
fetch(`${URL}?v=${Date.now()}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json()}).then(render).catch(()=>{
  root.innerHTML='<div class="usd-flow-empty">実需フローの表示データを準備しています。</div>';
  root.removeAttribute('aria-busy');
});
})();
