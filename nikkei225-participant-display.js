(function(){
'use strict';
const root=document.querySelector('[data-nikkei-dashboard]');if(!root)return;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const fmt=v=>num(v)===null?'—':Number(v).toLocaleString('ja-JP');
const signed=(v,suffix='')=>num(v)===null?'—':`${Number(v)>0?'+':''}${Number(v).toLocaleString('ja-JP')}${suffix}`;
const date=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得待ち';
const norm=v=>String(v??'').normalize('NFKC').replace(/\s+/g,'').trim();
const titleText=card=>String(card?.querySelector('.nikkei-section-title')?.textContent||'').replace(/^\s*\d+\.\s*/,'').trim();
function findCard(re){return [...root.querySelectorAll('.nikkei-card')].find(x=>re.test(titleText(x)));}
function source(x){return x&&x.sourceFileUrl?`<div class="nikkei-source">出典：<a href="${esc(x.sourceFileUrl)}" target="_blank" rel="noopener">JPX公式ファイル</a> / 基準日 ${esc(date(x.asOfDate))}</div>`:'';}
function rank(items,key){const rows=(items||[]).slice(0,5);if(!rows.length)return'<div class="nikkei-empty">取得待ち</div>';return rows.map((x,i)=>`<div class="nikkei-rank-row"><span>${esc(x.rank||i+1)}位</span><span>${esc(x.name||'—')}</span><b>${num(x[key])===null?'—':fmt(x[key])+'枚'}</b></div>`).join('');}
function ratio(a,b){const x=num(a),y=num(b);return x!==null&&y!==null&&y!==0?x/y:null;}
function marketRead(m){
 const p=num(m?.priceWeekChange),oi=num(m?.openInterestWeekChange);
 if(p===null||oi===null)return '前週比を判定できる価格・市場全体建玉がまだそろっていません。';
 if(p>0&&oi>0)return '先物価格が前週比で上昇し、市場全体の建玉も増加しています。ポジション増を伴う上昇で、単純なショートカバーだけではなく新規ポジション形成も伴った可能性があります。';
 if(p>0&&oi<0)return '先物価格は上昇しましたが、市場全体の建玉は減少しています。新規買いの積み上がりより、ポジション解消やショートカバーの寄与が相対的に大きかった可能性があります。';
 if(p<0&&oi>0)return '先物価格が下落し、市場全体の建玉は増加しています。ポジション増を伴う下落で、新規売り側の参加が増えた可能性があります。';
 if(p<0&&oi<0)return '先物価格が下落し、市場全体の建玉も減少しています。新規ショートの積み上がりより、ロング手仕舞いなどポジション解消の色が強い可能性があります。';
 return '価格または市場全体建玉の前週変化が小さく、方向性は中立です。';
}
function weekChangeText(buyers,sellers,contractsMatch){
 if(!contractsMatch)return '限月が前週から切り替わっているため、参加者別建玉の単純な前週差は表示しません。';
 const rows=[...(buyers||[]).map(x=>({...x,side:'買超'})),...(sellers||[]).map(x=>({...x,side:'売超'}))].filter(x=>num(x.weekChange)!==null);
 if(!rows.length)return '前週の上位表にも連続して登場した参加者が少なく、上位ランキングだけでは前週差を確定できません。順位外だった参加者を0枚とは扱いません。';
 rows.sort((a,b)=>Math.abs(num(b.weekChange))-Math.abs(num(a.weekChange)));
 return rows.slice(0,3).map(x=>`${esc(x.name||'—')}（${x.side}） ${esc(signed(x.weekChange,'枚'))}`).join('、')+'。上位表に連続掲載された範囲での比較です。';
}
function analysisHtml(part,poi,comp){
 const same=comp&&comp.asOfDate&&comp.status!=='unavailable';
 const turnover=same?(comp.turnover||{}):part;
 const oi=same?(comp.openInterest||{}):poi;
 const leaders=(turnover.leaders||[]).slice(0,5),buyers=(oi.buyers||[]).slice(0,5),sellers=(oi.sellers||[]).slice(0,5);
 const topBuy=buyers[0]||{},topSell=sellers[0]||{},secondBuy=buyers[1]||{},secondSell=sellers[1]||{};
 const buyN=num(topBuy.openInterest),sellN=num(topSell.openInterest);
 const haveTop=buyN!==null&&sellN!==null;
 const gap=haveTop?Math.abs(buyN-sellN):null;
 const balanceRatio=haveTop&&Math.min(buyN,sellN)>0?Math.max(buyN,sellN)/Math.min(buyN,sellN):null;
 const nearlyBalanced=balanceRatio!==null&&balanceRatio<=1.10;
 const buyLead=ratio(topBuy.openInterest,secondBuy.openInterest),sellLead=ratio(topSell.openInterest,secondSell.openInterest);
 const leaderMap=new Map(leaders.map(x=>[norm(x.name),x]));
 const overlapBuy=buyers.filter(x=>leaderMap.has(norm(x.name)));
 const overlapSell=sellers.filter(x=>leaderMap.has(norm(x.name)));
 const topText=haveTop
  ?`基準日 ${esc(date(same?comp.asOfDate:poi.asOfDate))} の週次建玉では、買超1位が<strong>${esc(topBuy.name||'—')} ${fmt(buyN)}枚</strong>、売超1位が<strong>${esc(topSell.name||'—')} ${fmt(sellN)}枚</strong>です。${nearlyBalanced?`最大規模はほぼ同水準（差 ${fmt(gap)}枚）ですが、市場全体が中立という意味ではありません。`:`最大規模には ${fmt(gap)}枚の差があります。上位2社だけで市場全体の方向は判断しません。`}`
  :'買超・売超の最大建玉を比較できるデータがそろっていません。';
 const concentration=[];
 if(buyLead!==null)concentration.push(`買超1位は2位の約${buyLead.toFixed(1)}倍`);
 if(sellLead!==null)concentration.push(`売超1位は2位の約${sellLead.toFixed(1)}倍`);
 const concentrateText=concentration.length?`${concentration.join('、')}で、上位1社への集中が目立ちます。証券会社名は最終投資家を直接示さず、顧客注文・自己勘定・裁定・ヘッジを含みます。`:'上位参加者への集中度は、2位以下のデータがそろった時点で比較します。';
 const overlap=[];
 overlapBuy.forEach(x=>overlap.push(`${esc(x.name)}（買超上位）`));
 overlapSell.forEach(x=>overlap.push(`${esc(x.name)}（売超上位）`));
 const overlapText=leaders.length
  ?(overlap.length?`${overlap.join('、')}が、<strong>同じ基準日の取引高上位</strong>にも登場しています。これはその日に活発だったことを示しますが、取引高自体には売買方向がないため、買い越し・売り越しとは読み替えません。`:`同じ基準日の取引高上位5社と建玉上位5社に重複はありません。取引高は当日の活動量として確認します。`)
  :'同一基準日の取引高データは取得待ちです。';
 const market=comp?.market||{};
 const marketText=same&&market
  ?`同じ ${esc(date(comp.asOfDate))} の日経225先物は<strong>${num(market.price)===null?'取得待ち':fmt(market.price)+'円'}</strong>${num(market.priceWeekChange)!==null?`（前週比 ${esc(signed(market.priceWeekChange,'円'))}）`:''}、市場全体の建玉は<strong>${num(market.openInterest)===null?'取得待ち':fmt(market.openInterest)+'枚'}</strong>${num(market.openInterestWeekChange)!==null?`（前週比 ${esc(signed(market.openInterestWeekChange,'枚'))}）`:''}です。${esc(marketRead(market))}`
  :'同一基準日の先物価格・市場全体建玉は取得待ちです。';
 const changeText=same?weekChangeText(buyers,sellers,comp.contractsMatch):'現在は日次と週次の基準日が一致していないため、参加者別の前週変化を分析判定には使いません。';
 const summary=same
  ?`分析は<strong>${esc(date(comp.asOfDate))}に基準日を統一</strong>しています。週次建玉、同日の取引高、同日の先物価格、市場全体建玉を同じ日で比較し、最新日次データを混在させません。${comp.error?` 一部取得注意：${esc(comp.error)}`:''}`
  :'同一基準日データがまだ生成されていないため、日次と週次を分離表示しています。分析判定には混在させません。';
 return `<div class="nikkei-participant-analysis-grid">
   <div class="nikkei-analysis-item"><div class="nikkei-analysis-kicker">同一基準日・週次建玉</div><h3>最大建玉と集中度</h3><p>${topText}<br>${concentrateText}</p></div>
   <div class="nikkei-analysis-item"><div class="nikkei-analysis-kicker">前週比較</div><h3>参加者別建玉の変化</h3><p>${changeText}</p></div>
   <div class="nikkei-analysis-item"><div class="nikkei-analysis-kicker">同日取引高 × 建玉</div><h3>活発だった参加者との重なり</h3><p>${overlapText}</p></div>
   <div class="nikkei-analysis-item"><div class="nikkei-analysis-kicker">価格 × 市場全体建玉</div><h3>需給構造の判定</h3><p>${marketText}</p></div>
  </div>
  <div class="nikkei-analysis-summary"><b>今回の需給判断</b><span>${summary}</span></div>
  <div class="nikkei-analysis-meta">分析基準日：${esc(date(same?comp.asOfDate:poi.asOfDate))}${same&&comp.previousAsOfDate?` / 前週比較：${esc(date(comp.previousAsOfDate))}`:''} / 対象限月：${esc((same?comp.contract:poi.contract)||'取得待ち')} / 最新日次取引高は別カードで ${esc(date(part.asOfDate))} を表示</div>`;
}
function upsertAnalysis(part,poi,comp,anchor){
 if(!anchor)return;
 let card=root.querySelector('[data-participant-analysis]');
 if(!card){
  anchor.insertAdjacentHTML('afterend',`<article class="nikkei-card nikkei-span-12 nikkei-participant-analysis" data-participant-analysis><div class="nikkei-section-head"><div><h2 class="nikkei-section-title">取引参加者データから読み取れること</h2><div class="nikkei-analysis-subtitle">週次建玉の基準日に、取引高・先物価格・市場全体建玉をそろえて分析</div></div><span class="nikkei-freq weekly">同一基準日分析</span></div><div class="nikkei-section-body" data-participant-analysis-body></div></article>`);
  card=root.querySelector('[data-participant-analysis]');
 }
 const body=card?.querySelector('[data-participant-analysis-body]');
 if(body)body.innerHTML=analysisHtml(part,poi,comp);
}
function apply(d){
 const part=d.participantFlow||{}, poi=d.participantOpenInterest||{}, comp=d.sameDateParticipantAnalysis||{};
 let participantCard=null,oiCard=null;
 if(part.status==='verified'&&Array.isArray(part.leaders)&&part.leaders.length){
  participantCard=findCard(/^取引参加者別手口/);
  if(participantCard){
   const title=participantCard.querySelector('.nikkei-section-title');if(title)title.textContent='取引参加者別手口（取引高上位）';
   const body=participantCard.querySelector('.nikkei-section-body');if(body)body.innerHTML=`<div class="nikkei-table-scroll"><table class="nikkei-table"><thead><tr><th>順位</th><th>取引参加者</th><th>取引高</th></tr></thead><tbody>${part.leaders.slice(0,5).map((x,i)=>`<tr><td>${esc(x.rank||i+1)}位</td><td>${esc(x.name||'—')}</td><td class="num">${fmt(x.volume)}枚</td></tr>`).join('')}</tbody></table></div><div class="nikkei-callout">期近：${esc(part.contract||'—')}。${esc(part.comment||'日次ファイルは取引高上位であり、売買方向を示しません。')} このカードは最新日次データを表示し、下の分析カードでは週次建玉の基準日に合わせた別の日次データを使用します。</div>${source(part)}`;
  }
 }
 if(poi.status==='verified'&&(poi.buyers?.length||poi.sellers?.length)){
  oiCard=findCard(/^取引参加者別 建玉上位/);
  if(oiCard){
   const title=oiCard.querySelector('.nikkei-section-title');if(title)title.textContent='取引参加者別 建玉上位（売超・買超）';
   const body=oiCard.querySelector('.nikkei-section-body');if(body)body.innerHTML=`<div class="nikkei-rank-grid"><div class="nikkei-rank-box"><div class="nikkei-rank-title">買超参加者</div>${rank(poi.buyers,'openInterest')}</div><div class="nikkei-rank-box"><div class="nikkei-rank-title">売超参加者</div>${rank(poi.sellers,'openInterest')}</div></div><div class="nikkei-callout">対象限月：${esc(poi.contract||'—')}。${esc(poi.comment||'週次の売超・買超上位を表示します。')} 分析カードはこの基準日に他データをそろえます。</div>${source(poi)}`;
  }
 }
 if(poi.status==='verified')upsertAnalysis(part,poi,comp,oiCard||findCard(/^取引参加者別 建玉上位/));
}
fetch('data/nikkei225-supply-demand.json',{cache:'no-store'}).then(r=>r.ok?r.json():Promise.reject()).then(d=>{let n=0;const t=setInterval(()=>{apply(d);if(root.querySelector('.nikkei-section-title')||++n>40)clearInterval(t)},100);apply(d)}).catch(()=>{});
})();
