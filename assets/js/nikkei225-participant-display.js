(function(){
'use strict';
const root=document.querySelector('[data-nikkei-dashboard]');if(!root)return;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>Number(v).toLocaleString('ja-JP');
const date=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得待ち';
function findCard(re){return [...root.querySelectorAll('.nikkei-card')].find(x=>re.test(x.querySelector('.nikkei-section-title')?.textContent||''));}
function source(x){return x&&x.sourceFileUrl?`<div class="nikkei-source">出典：<a href="${esc(x.sourceFileUrl)}" target="_blank" rel="noopener">JPX公式ファイル</a> / 基準日 ${esc(date(x.asOfDate))}</div>`:'';}
function rank(items,key){const rows=(items||[]).slice(0,5);if(!rows.length)return'<div class="nikkei-empty">取得待ち</div>';return rows.map((x,i)=>`<div class="nikkei-rank-row"><span>${esc(x.rank||i+1)}位</span><span>${esc(x.name||'—')}</span><b>${Number.isFinite(Number(x[key]))?fmt(x[key])+'枚':'—'}</b></div>`).join('');}
function apply(d){
 const part=d.participantFlow||{}, poi=d.participantOpenInterest||{};
 if(part.status==='verified'&&Array.isArray(part.leaders)&&part.leaders.length){
  const card=findCard(/^6\. 取引参加者別手口/);
  if(card){
   const title=card.querySelector('.nikkei-section-title');if(title)title.textContent='6. 取引参加者別手口（取引高上位）';
   const body=card.querySelector('.nikkei-section-body');if(body)body.innerHTML=`<div class="nikkei-table-scroll"><table class="nikkei-table"><thead><tr><th>順位</th><th>取引参加者</th><th>取引高</th></tr></thead><tbody>${part.leaders.slice(0,5).map((x,i)=>`<tr><td>${esc(x.rank||i+1)}位</td><td>${esc(x.name||'—')}</td><td class="num">${fmt(x.volume)}枚</td></tr>`).join('')}</tbody></table></div><div class="nikkei-callout">期近：${esc(part.contract||'—')}。${esc(part.comment||'日次ファイルは取引高上位であり、売買方向を示しません。')}</div>${source(part)}`;
  }
 }
 if(poi.status==='verified'&&(poi.buyers?.length||poi.sellers?.length)){
  const card=findCard(/^8\. 取引参加者別 建玉上位/);
  if(card){
   const title=card.querySelector('.nikkei-section-title');if(title)title.textContent='8. 取引参加者別 建玉上位（売超・買超）';
   const body=card.querySelector('.nikkei-section-body');if(body)body.innerHTML=`<div class="nikkei-rank-grid"><div class="nikkei-rank-box"><div class="nikkei-rank-title">買超参加者</div>${rank(poi.buyers,'openInterest')}</div><div class="nikkei-rank-box"><div class="nikkei-rank-title">売超参加者</div>${rank(poi.sellers,'openInterest')}</div></div><div class="nikkei-callout">対象限月：${esc(poi.contract||'—')}。${esc(poi.comment||'週次の売超・買超上位を表示します。')}</div>${source(poi)}`;
  }
 }
}
fetch('data/nikkei225-supply-demand.json',{cache:'no-store'}).then(r=>r.ok?r.json():Promise.reject()).then(d=>{let n=0;const t=setInterval(()=>{apply(d);if(root.querySelector('.nikkei-section-title')||++n>40)clearInterval(t)},100);apply(d)}).catch(()=>{});
})();
