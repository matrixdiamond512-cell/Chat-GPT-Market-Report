(()=>{
'use strict';
const root=document.querySelector('[data-usdjpy-flow-overview]');
if(!root)return;
const URL='data/usdjpy-flow-summary.json';
const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const scoreText=v=>n(v)===null?'—':`${Number(v)>0?'+':''}${Number(v).toLocaleString('ja-JP',{maximumFractionDigits:2})}`;
const dateText=v=>v?String(v).slice(0,10).replaceAll('-','/'):'—';
const statusLabel={verified:'確認済み',stale:'期限切れ',degraded:'参考',unavailable:'取得不能'};
const tone=v=>n(v)>0?'is-buy':n(v)<0?'is-sell':'';
const arrow=v=>n(v)>0?'↑':n(v)<0?'↓':'→';
const compare=(now,prev)=>{if(n(now)===null||n(prev)===null)return'';const delta=Number(now)-Number(prev);return delta===0?'前回比：変化なし':`前回 ${scoreText(prev)} → 今回 ${scoreText(now)}（${Math.abs(now)>Math.abs(prev)?'強まった':Math.abs(now)<Math.abs(prev)?'弱まった':'方向変化'}）`};

function topDrivers(section){
  return (Array.isArray(section?.drivers)?section.drivers:[])
    .filter(x=>x&&x.status==='verified'&&n(x.score)!==null)
    .sort((a,b)=>Math.abs(Number(b.score))-Math.abs(Number(a.score))||String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')))
    .slice(0,3);
}
function latestMeta(section){
  const rows=(section?.drivers||[]).filter(x=>x.status==='verified');
  const dates=rows.map(x=>x.asOf).filter(Boolean).sort();
  const updates=rows.map(x=>x.updatedAt).filter(Boolean).sort();
  return `基準：${dateText(dates.at(-1))}${updates.length?`／更新 ${String(updates.at(-1)).replace('T',' ').slice(0,16)}`:''}`;
}
function evidence(section){
  const rows=topDrivers(section);
  if(!rows.length)return '<li class="is-muted">採点可能な確認済み根拠がありません。</li>';
  return rows.map(x=>`<li><span class="usd-flow-arrow ${tone(x.score)}">${arrow(x.score)}</span>${esc(x.name)}：${esc(x.valueText||scoreText(x.score))}<span class="usd-flow-status">${esc(statusLabel[x.status]||x.status)}・${esc(x.frequency||'')}</span></li>`).join('');
}
function card(kind,label,section,previous,extra=''){
  const score=n(section?.score),hold=score===null;
  return `<article class="usd-flow-card ${kind==='combined'?'is-combined':''}">
    <span class="usd-flow-label">${esc(label)}</span>
    <strong class="usd-flow-judgement ${tone(score)}">${esc(section?.judgement||'判定保留')}</strong>
    <span class="usd-flow-score ${tone(score)}">${hold?'判定保留':scoreText(score)}</span>
    ${extra}
    ${kind==='combined'?'':`<ul class="usd-flow-evidence">${evidence(section)}</ul>`}
    ${kind==='real'?`<div class="usd-flow-split">短期実需 ${scoreText(section?.shortTermScore)}／構造実需 ${scoreText(section?.structuralScore)}／確認済み ${Number(section?.verifiedCount||0)}カテゴリー</div>`:''}
    ${kind==='spec'?`<div class="usd-flow-split">確認済み ${Number(section?.verifiedCount||0)}カテゴリー（CFTCはUSD/JPY方向へ符号変換）</div>`:''}
    ${kind==='combined'?'':`<div class="usd-flow-meta">${esc(latestMeta(section))}</div>`}
    <div class="usd-flow-previous">${esc(compare(score,previous))}</div>
  </article>`;
}
function render(data){
  if(!data||data.pageId!=='usdjpy-flow-summary'){
    root.innerHTML='<div class="usd-flow-empty">フロー履歴なし。この日付には実需・投機フロー判定が保存されていません。</div>';
    root.removeAttribute('aria-busy');return;
  }
  const real=data.realDemand||{},spec=data.speculative||{},combined=data.combined||{},prev=data.previous||{};
  const combinedExtra=`<div class="usd-flow-lead">主導：${esc(combined.leadingFlow||'保留')}／関係：${esc(combined.relationship||'判定保留')}</div>`;
  root.innerHTML=`<div class="usd-flow-head"><h2>実需 × 投機 フロー総合判定</h2><p>公開データから実需と投機を分離評価し、現在どちらのフローがUSD/JPYを主導しているかを確認</p></div>
    <div class="usd-flow-grid">
      ${card('real','実需フロー',real,prev.realDemand)}
      ${card('spec','投機フロー',spec,prev.speculative)}
      ${card('combined','フロー総合判定',combined,prev.combined,combinedExtra)}
    </div>
    <div class="usd-flow-relationship"><h3>実需と投機の関係</h3><p>${esc(combined.comment||'判定保留')}</p><p class="usd-flow-session">${esc(combined.sessionComment||'')}</p></div>`;
  root.removeAttribute('aria-busy');
}
fetch(`${URL}?v=${Date.now()}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json()}).then(render).catch(err=>{
  root.innerHTML=`<div class="usd-flow-empty">${window.__USDJPY_HISTORY_MODE__?'フロー履歴なし':'実需・投機フローを読み込めませんでした'}。${esc(err?.message||err)}</div>`;
  root.removeAttribute('aria-busy');
});
})();
