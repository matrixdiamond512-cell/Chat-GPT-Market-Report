(function(){
'use strict';
const root=document.querySelector('[data-nikkei-dashboard]');if(!root)return;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
const fmt=v=>Number(v).toLocaleString('ja-JP');
const date=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得待ち';
const norm=v=>String(v??'').normalize('NFKC').replace(/\s+/g,'').trim();
function findCard(re){return [...root.querySelectorAll('.nikkei-card')].find(x=>re.test(x.querySelector('.nikkei-section-title')?.textContent||''));}
function source(x){return x&&x.sourceFileUrl?`<div class="nikkei-source">出典：<a href="${esc(x.sourceFileUrl)}" target="_blank" rel="noopener">JPX公式ファイル</a> / 基準日 ${esc(date(x.asOfDate))}</div>`:'';}
function rank(items,key){const rows=(items||[]).slice(0,5);if(!rows.length)return'<div class="nikkei-empty">取得待ち</div>';return rows.map((x,i)=>`<div class="nikkei-rank-row"><span>${esc(x.rank||i+1)}位</span><span>${esc(x.name||'—')}</span><b>${Number.isFinite(Number(x[key]))?fmt(x[key])+'枚':'—'}</b></div>`).join('');}
function dayGap(a,b){if(!a||!b)return null;const x=new Date(`${String(a).slice(0,10)}T00:00:00Z`),y=new Date(`${String(b).slice(0,10)}T00:00:00Z`);if(!Number.isFinite(x.getTime())||!Number.isFinite(y.getTime()))return null;return Math.round(Math.abs(x-y)/86400000);}
function ratio(a,b){const x=Number(a),y=Number(b);return Number.isFinite(x)&&Number.isFinite(y)&&y!==0?x/y:null;}
function analysisHtml(part,poi){
 const leaders=(part.leaders||[]).slice(0,5),buyers=(poi.buyers||[]).slice(0,5),sellers=(poi.sellers||[]).slice(0,5);
 const topBuy=buyers[0]||{},topSell=sellers[0]||{},secondBuy=buyers[1]||{},secondSell=sellers[1]||{};
 const buyN=Number(topBuy.openInterest),sellN=Number(topSell.openInterest);
 const haveTop=Number.isFinite(buyN)&&Number.isFinite(sellN);
 const gap=haveTop?Math.abs(buyN-sellN):null;
 const balanceRatio=haveTop&&Math.min(buyN,sellN)>0?Math.max(buyN,sellN)/Math.min(buyN,sellN):null;
 const nearlyBalanced=balanceRatio!==null&&balanceRatio<=1.10;
 const buyLead=ratio(topBuy.openInterest,secondBuy.openInterest),sellLead=ratio(topSell.openInterest,secondSell.openInterest);
 const leaderMap=new Map(leaders.map(x=>[norm(x.name),x.name]));
 const overlap=buyers.filter(x=>leaderMap.has(norm(x.name))).map(x=>x.name);
 const gapDays=dayGap(part.asOfDate,poi.asOfDate);
 const dateMismatch=part.asOfDate&&poi.asOfDate&&String(part.asOfDate).slice(0,10)!==String(poi.asOfDate).slice(0,10);
 const topText=haveTop
  ?`週次建玉では、買超1位が<strong>${esc(topBuy.name||'—')} ${fmt(buyN)}枚</strong>、売超1位が<strong>${esc(topSell.name||'—')} ${fmt(sellN)}枚</strong>です。${nearlyBalanced?`最大規模はほぼ同水準（差 ${fmt(gap)}枚）ですが、これは市場全体が中立という意味ではありません。`:`最大規模には ${fmt(gap)}枚の差があります。市場全体の強弱は上位2社だけでは判断できません。`}`
  :'買超・売超の最大建玉を比較できるデータがそろっていません。';
 const concentration=[];
 if(buyLead!==null)concentration.push(`買超1位は2位の約${buyLead.toFixed(1)}倍`);
 if(sellLead!==null)concentration.push(`売超1位は2位の約${sellLead.toFixed(1)}倍`);
 const concentrateText=concentration.length
  ?`${concentration.join('、')}で、両サイドとも上位1社への建玉集中が目立ちます。ただし、その建玉が自己勘定か顧客注文か、裁定・ヘッジかはこのデータだけでは分かりません。`
  :'上位参加者への建玉集中度は、2位以下のデータがそろった時点で比較します。';
 const overlapText=overlap.length
  ?`<strong>${overlap.map(esc).join('、')}</strong>は、週次の買超上位と日次の取引高上位の両方に登場しています。${dateMismatch?`ただし基準日は週次 ${esc(date(poi.asOfDate))}、日次 ${esc(date(part.asOfDate))}${gapDays!==null?`（${gapDays}日差）`:''}で異なるため、日次時点でも買超を維持していたとは判断できません。`:'基準日が同じ場合でも、取引高だけでは当日の売買方向は分かりません。'}`
  :`週次の買超上位と日次取引高上位に共通する参加者は上位5社では確認できません。${dateMismatch?`基準日も週次 ${esc(date(poi.asOfDate))}、日次 ${esc(date(part.asOfDate))}で異なります。`:''}`;
 const activityText=leaders.length
  ?`日次取引高では<strong>${esc(leaders[0].name||'—')}</strong>が1位です。これは「その日に売買・執行が活発だった」ことを示すデータで、買い越し・売り越しの方向は示しません。`
  :'日次の取引高上位データは取得待ちです。';
 return `<div class="nikkei-participant-analysis-grid">
   <div class="nikkei-analysis-item"><div class="nikkei-analysis-kicker">週次建玉</div><h3>最大建玉の偏り</h3><p>${topText}</p></div>
   <div class="nikkei-analysis-item"><div class="nikkei-analysis-kicker">集中度</div><h3>上位1社への集中</h3><p>${concentrateText}</p></div>
   <div class="nikkei-analysis-item"><div class="nikkei-analysis-kicker">日次 × 週次</div><h3>同じ参加者が両方に登場しているか</h3><p>${overlapText}</p></div>
   <div class="nikkei-analysis-item"><div class="nikkei-analysis-kicker">日次取引高</div><h3>当日の活動量</h3><p>${activityText}</p></div>
  </div>
  <div class="nikkei-analysis-summary"><b>このデータの読み方</b><span>「誰が活発か」と「どこに建玉が偏っているか」は確認できます。ただし、取引参加者名は最終投資家を直接示さず、日次取引高から売買方向も判断できません。需給判断では、同一基準日の建玉前週比・先物価格・市場全体の建玉と合わせて確認します。</span></div>
  <div class="nikkei-analysis-meta">比較基準：日次 ${esc(date(part.asOfDate))} / 週次 ${esc(date(poi.asOfDate))} / 対象限月：${esc(poi.contract||part.contract||'取得待ち')}</div>`;
}
function upsertAnalysis(part,poi,anchor){
 if(!anchor)return;
 let card=root.querySelector('[data-participant-analysis]');
 if(!card){
  anchor.insertAdjacentHTML('afterend',`<article class="nikkei-card nikkei-span-12 nikkei-participant-analysis" data-participant-analysis><div class="nikkei-section-head"><div><h2 class="nikkei-section-title">取引参加者データから読み取れること</h2><div class="nikkei-analysis-subtitle">日次の取引高上位と週次の建玉上位を、基準日を分けて解釈</div></div><span class="nikkei-freq weekly">分析</span></div><div class="nikkei-section-body" data-participant-analysis-body></div></article>`);
  card=root.querySelector('[data-participant-analysis]');
 }
 const body=card?.querySelector('[data-participant-analysis-body]');
 if(body)body.innerHTML=analysisHtml(part,poi);
}
function apply(d){
 const part=d.participantFlow||{}, poi=d.participantOpenInterest||{};
 let participantCard=null,oiCard=null;
 if(part.status==='verified'&&Array.isArray(part.leaders)&&part.leaders.length){
  participantCard=findCard(/^6\. 取引参加者別手口/);
  if(participantCard){
   const title=participantCard.querySelector('.nikkei-section-title');if(title)title.textContent='6. 取引参加者別手口（取引高上位）';
   const body=participantCard.querySelector('.nikkei-section-body');if(body)body.innerHTML=`<div class="nikkei-table-scroll"><table class="nikkei-table"><thead><tr><th>順位</th><th>取引参加者</th><th>取引高</th></tr></thead><tbody>${part.leaders.slice(0,5).map((x,i)=>`<tr><td>${esc(x.rank||i+1)}位</td><td>${esc(x.name||'—')}</td><td class="num">${fmt(x.volume)}枚</td></tr>`).join('')}</tbody></table></div><div class="nikkei-callout">期近：${esc(part.contract||'—')}。${esc(part.comment||'日次ファイルは取引高上位であり、売買方向を示しません。')}</div>${source(part)}`;
  }
 }
 if(poi.status==='verified'&&(poi.buyers?.length||poi.sellers?.length)){
  oiCard=findCard(/^8\. 取引参加者別 建玉上位/);
  if(oiCard){
   const title=oiCard.querySelector('.nikkei-section-title');if(title)title.textContent='8. 取引参加者別 建玉上位（売超・買超）';
   const body=oiCard.querySelector('.nikkei-section-body');if(body)body.innerHTML=`<div class="nikkei-rank-grid"><div class="nikkei-rank-box"><div class="nikkei-rank-title">買超参加者</div>${rank(poi.buyers,'openInterest')}</div><div class="nikkei-rank-box"><div class="nikkei-rank-title">売超参加者</div>${rank(poi.sellers,'openInterest')}</div></div><div class="nikkei-callout">対象限月：${esc(poi.contract||'—')}。${esc(poi.comment||'週次の売超・買超上位を表示します。')}</div>${source(poi)}`;
  }
 }
 if(part.status==='verified'&&poi.status==='verified')upsertAnalysis(part,poi,oiCard||findCard(/^8\. 取引参加者別 建玉上位/));
}
fetch('data/nikkei225-supply-demand.json',{cache:'no-store'}).then(r=>r.ok?r.json():Promise.reject()).then(d=>{let n=0;const t=setInterval(()=>{apply(d);if(root.querySelector('.nikkei-section-title')||++n>40)clearInterval(t)},100);apply(d)}).catch(()=>{});
})();
