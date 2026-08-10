(function(){
'use strict';
const root=document.querySelector('[data-arbitrage]');if(!root)return;
const ARB_URL='data/nikkei225-arbitrage.json';
const SUPPLY_URL='data/nikkei225-supply-demand.json';
const STOCKS_URL='data/stocks.json';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=v=>v===null||v===undefined||v===''?null:(Number.isFinite(Number(String(v).replace(/,/g,'')))?Number(String(v).replace(/,/g,'')):null);
const fmt=(v,d=0)=>n(v)===null?'取得不能':n(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const shares=v=>n(v)===null?'取得不能（データ未取得）':`${fmt(n(v)/100000,2)}億株`;
const signedShares=v=>n(v)===null?'取得不能（比較値未取得）':`${n(v)>0?'+':''}${fmt(n(v)/100000,2)}億株 ${n(v)>0?'↑':n(v)<0?'↓':'→'}`;
const signed=(v,suffix='',d=0)=>n(v)===null?'取得不能':`${n(v)>0?'+':''}${fmt(v,d)}${suffix}`;
const iso=v=>{const s=String(v||'').slice(0,10).replaceAll('/','-');return /^\d{4}-\d{2}-\d{2}$/.test(s)?s:'取得不能'};
const dateTime=v=>{if(!v)return'取得不能';try{return new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(v))+' JST'}catch(_){return String(v)}};
const tone=v=>n(v)>0?'positive':n(v)<0?'negative':'neutral';
function normalizeHistory(d){
 const rows=(Array.isArray(d?.history)?d.history:[]).map(x=>({date:iso(x.date),buy:n(x.buyBalance),sell:n(x.sellBalance),price:n(x.nikkei225Close)})).filter(x=>x.date!=='取得不能'&&x.buy!==null&&x.sell!==null).map(x=>({...x,net:x.buy-x.sell})).sort((a,b)=>a.date.localeCompare(b.date));
 return rows.filter((x,i)=>i===rows.length-1||x.date!==rows[i+1].date);
}
function analyze(d){
 const rows=normalizeHistory(d),asOf=iso(d?.asOfDate),latestHistory=rows.filter(x=>asOf==='取得不能'||x.date<=asOf).at(-1);
 const buy=n(d?.latest?.buyBalance)??latestHistory?.buy??null,sell=n(d?.latest?.sellBalance)??latestHistory?.sell??null,net=buy!==null&&sell!==null?buy-sell:null;
 let index=rows.findIndex(x=>x.date===asOf);if(index<0)index=rows.length-1;
 const current=index>=0?rows[index]:null;
 const delta=offset=>current&&index>=offset?current.net-rows[index-offset].net:null;
 const prev=delta(1),d5=delta(5),d20=delta(20),window52=rows.slice(Math.max(0,index-259),index+1),nets=window52.map(x=>x.net);
 const min52=nets.length?Math.min(...nets):null,max52=nets.length?Math.max(...nets):null;
 const range=net!==null&&min52!==null&&max52!==null&&max52!==min52?Math.max(0,Math.min(100,(net-min52)/(max52-min52)*100)):null;
 let status='中立',note='裁定残の変化は小さく、現時点で裁定取引による大きな需給の偏りは確認できません。';
 if(net===null||prev===null){status='判定不能';note='裁定需給の判定に必要な公表値または比較値が不足しています。欠損値は推測していません。'}
 else if(net<0){status='売り残優勢';note='裁定売り残が買い残を上回っています。売り残の解消方向を含め、次回公表値を確認します。'}
 else if(range!==null&&range>=85&&prev>0&&d5>0&&d20>0){status='過熱';note=`ネット裁定残は52週レンジの${fmt(range,0)}%位置。前回比・1週間・4週間とも増加しており、裁定ポジションの積み上がりに注意が必要です。`}
 else if(range!==null&&range>=70&&[prev,d5,d20].filter(v=>v!==null&&v>0).length>=2){status='やや過熱';note=`ネット裁定残は52週レンジの${fmt(range,0)}%位置。複数期間で増加しており、裁定ポジションの積み上がりに注意します。`}
 else if(prev<0&&d5!==null&&d5<0){status='解消進行';note=`ネット裁定残は前回比と1週間変化が減少。${range!==null&&range>=70?'高水準ですが、':''}裁定解消が進み、需給の重さは低下方向です。`}
 const price5=current&&index>=5&&current.price!==null&&rows[index-5].price!==null?current.price-rows[index-5].price:null;
 let combination='比較可能な同一基準日の株価データが不足しています。';
 if(price5!==null&&d5!==null){if(price5>0&&d5>0)combination='注意：日経225上昇と同時にネット裁定残も積み上がっています。';else if(price5<0&&d5<0)combination='裁定解消進行：株価調整とともにネット裁定残も減少しています。';else if(price5>0&&d5<0)combination='比較的健全な上昇：日経225上昇に対してネット裁定残は減少しています。';else if(price5<0&&d5>0)combination='需給悪化に注意：日経225下落中もネット裁定残が増えています。';else combination='日経225またはネット裁定残の方向感は限定的です。'}
 return{rows,index,current,buy,sell,net,prev,d5,d20,range,min52,max52,status,note,price5,combination};
}
function statusClass(s){return s==='過熱'?'hot':s==='やや過熱'?'warm':s==='解消進行'?'unwind':s==='売り残優勢'?'sell':'neutral'}
function kpi(label,value,sub,kind){return`<article class="arb-kpi ${kind}"><div class="arb-kpi-label">${esc(label)}</div><div class="arb-kpi-value">${value}</div><div class="arb-kpi-sub">${sub}</div></article>`}
function rowByLabel(stocks,label){return(stocks?.marketInternals?.japan?.rows||[]).find(r=>Array.isArray(r)&&String(r[0]).trim()===label)||null}
function parsePair(v){const m=String(v||'').match(/([\d,]+)\s*\/\s*([\d,]+)/);return m?[Number(m[1].replaceAll(',','')),Number(m[2].replaceAll(',',''))]:[null,null]}
function marketInternals(stocks,a){
 const breadth=rowByLabel(stocks,'値上がり銘柄 / 値下がり銘柄'),turnover=rowByLabel(stocks,'東証プライム売買代金'),[adv,dec]=parsePair(breadth?.[1]);
 let text='市場内部データが不足しているため、裁定残との組み合わせは判定できません。';
 if(adv!==null&&dec!==null&&a.price5!==null&&a.d5!==null){if(a.price5>0&&a.d5>0&&adv<=dec)text='日経225は上昇していますが市場の広がりは弱く、裁定残増加と合わせると指数主導色が強い可能性があります。';else if(a.price5>0&&adv>dec)text='指数上昇に加えて値上がり銘柄数も優勢です。裁定だけに依存した上昇とは断定しません。';else text='値上がり・値下がりの広がりと裁定残を併読し、指数だけの動きか確認します。'}
 return{adv,dec,turnover:turnover?.[1]||null,text,date:stocks?.marketInternals?.japan?.dataDate||''};
}
function specialEvents(supply){
 const sq=iso(supply?.options?.nextSqDate),days=n(supply?.options?.businessDaysToSq),month=sq!=='取得不能'?Number(sq.slice(5,7)):null,isMsq=[3,6,9,12].includes(month);
 return[{name:isMsq?'MSQ':'SQ',date:sq,note:days===null?'残存営業日数は取得不能':`あと${fmt(days)}営業日`},{name:'ロールオーバー期間',date:sq,note:sq==='取得不能'?'取得不能（SQ日程未取得）':'SQ接近時の限月移行を監視'},{name:'配当落ち',date:'取得不能',note:'既存データに確認済み日程なし'},{name:'限月交代',date:'取得不能',note:'確認済み日付は未収録'}];
}
function chartSvg(rows){
 if(rows.length<2)return'<div class="arb-empty">取得不能（比較可能な履歴不足）</div>';
 const W=1200,H=420,L=76,R=1115,T=32,B=338,pMin=Math.min(...rows.map(x=>x.price).filter(Number.isFinite)),pMax=Math.max(...rows.map(x=>x.price).filter(Number.isFinite)),balances=rows.flatMap(x=>[x.buy,x.sell,x.net]),bMin=Math.min(0,...balances),bMax=Math.max(0,...balances),pSpan=pMax-pMin||1,bSpan=bMax-bMin||1;
 const x=i=>L+i*(R-L)/(rows.length-1),yp=v=>T+(pMax-v)/pSpan*(B-T),yb=v=>T+(bMax-v)/bSpan*(B-T),line=fn=>rows.map((r,i)=>`${x(i)},${fn(r)}`).join(' '),ticks=[0,.25,.5,.75,1].map(t=>{const y=T+t*(B-T);return`<line class="arb-gridline" x1="${L}" y1="${y}" x2="${R}" y2="${y}"/><text x="${L-10}" y="${y+4}" text-anchor="end">${fmt(pMax-t*pSpan,0)}</text><text x="${R+10}" y="${y+4}">${fmt((bMax-t*bSpan)/100000,1)}</text>`}).join(''),step=(R-L)/(rows.length-1);
 const hits=rows.map((r,i)=>`<rect class="arb-hit" data-index="${i}" x="${Math.max(L,x(i)-step/2)}" y="${T}" width="${Math.max(5,step)}" height="${B-T}"><title>${r.date}｜日経225 ${fmt(r.price)}円｜買い ${shares(r.buy)}｜売り ${shares(r.sell)}｜ネット ${shares(r.net)}</title></rect>`).join('');
 return`<svg class="arb-main-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="日経225と裁定買い残、裁定売り残、ネット裁定残の推移">${ticks}<line class="arb-zero" x1="${L}" y1="${yb(0)}" x2="${R}" y2="${yb(0)}"/><polyline class="price" points="${line(r=>yp(r.price))}"/><polyline class="buy" points="${line(r=>yb(r.buy))}"/><polyline class="sell" points="${line(r=>yb(r.sell))}"/><polyline class="net" points="${line(r=>yb(r.net))}"/>${hits}<text class="axis-title" x="${L}" y="18">日経225（円）</text><text class="axis-title" x="${R}" y="18" text-anchor="end">裁定残（億株）</text><text x="${L}" y="375">${rows[0].date}</text><text x="${R}" y="375" text-anchor="end">${rows.at(-1).date}</text></svg>`;
}
function renderChart(allRows,period){
 const counts={4:20,13:65,26:130,52:260,156:780},usable=allRows.filter(x=>x.price!==null),rows=usable.slice(-counts[period]),host=root.querySelector('[data-chart-host]');if(!host)return;
 host.innerHTML=chartSvg(rows);host.dataset.rows=JSON.stringify(rows);root.querySelector('[data-chart-coverage]').textContent=period==='156'&&usable.length<780?`3年を選択中／保存済み${usable.length}取引日を表示`:`${period}週／${rows.length}取引日`;
 root.querySelectorAll('[data-period]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.period===String(period))));
 host.querySelectorAll('.arb-hit').forEach(hit=>hit.addEventListener('click',()=>{const r=rows[Number(hit.dataset.index)];root.querySelector('[data-chart-tooltip]').innerHTML=`<b>${esc(r.date)}</b><span>日経225 ${fmt(r.price)}円</span><span>買い ${shares(r.buy)}</span><span>売り ${shares(r.sell)}</span><span>ネット ${shares(r.net)}</span>`}));
}
function render(d,supply,stocks){
 const a=analyze(d),internal=marketInternals(stocks,a),arbMeta=supply?.arbitrage||{},sameDate=iso(arbMeta.asOfDate)===iso(d.asOfDate),published=sameDate&&arbMeta.fetchedAt?iso(arbMeta.fetchedAt):'取得不能',webUpdated=sameDate?supply?.generatedAt:null;
 const futures=n(supply?.futures?.price),spot=n(supply?.spot?.value),sameBasisDate=iso(supply?.futures?.asOfDate)===iso(supply?.spot?.asOfDate),basis=sameBasisDate&&futures!==null&&spot!==null?futures-spot:null,basisPct=basis!==null&&spot?basis/spot*100:null;
 const headDate=document.querySelector('[data-as-of]');if(headDate)headDate.textContent=iso(d.asOfDate);const headStatus=document.querySelector('[data-status]');if(headStatus)headStatus.textContent=d.sourceStatus||'取得不能';
 const events=specialEvents(supply),rangePos=a.range===null?0:a.range;
 root.innerHTML=`
 <section class="arb-overview">
  <article class="arb-judgement ${statusClass(a.status)}"><div class="arb-eyebrow">裁定需給判定</div><div class="arb-status">${esc(a.status)}</div><p>${esc(a.note)}</p><div class="arb-range"><div><b>52週レンジ位置</b><strong>${a.range===null?'取得不能':fmt(a.range,0)+'%'}</strong></div><div class="arb-range-track"><i style="left:${rangePos}%"></i></div><div class="arb-range-label"><span>低</span><span>高</span></div></div></article>
  ${kpi('ネット裁定残',shares(a.net),'買い残 − 売り残','net')}
  ${kpi('裁定買い残',shares(a.buy),`前回比 ${signedShares(n(d.latest?.buyChange))}`,'buy')}
  ${kpi('裁定売り残',shares(a.sell),`前回比 ${signedShares(n(d.latest?.sellChange))}`,'sell')}
  <div class="arb-deltas">${kpi('前回比',signedShares(a.prev),'直前取引日との差','delta')}${kpi('1週間変化',signedShares(a.d5),'5取引日前との差','delta')}${kpi('4週間変化',signedShares(a.d20),'20取引日前との差','delta')}</div>
 </section>
 <div class="arb-dates"><span><b>基準日</b>${iso(d.asOfDate)}</span><span><b>公表日</b>${published}</span><span><b>WEB更新日時</b>${dateTime(webUpdated)}</span><em>JPX公表値は原則として前々営業日分です</em></div>
 <section class="arb-panel arb-chart-panel"><div class="arb-panel-head"><div><h2>日経225 × 裁定残高 推移</h2><p>株価と裁定残の方向を同じ取引日で比較</p></div><div class="arb-periods" role="group" aria-label="表示期間">${[['4','4週'],['13','13週'],['26','26週'],['52','52週'],['156','3年']].map(x=>`<button type="button" data-period="${x[0]}" aria-pressed="${x[0]==='52'}">${x[1]}</button>`).join('')}</div></div><div class="arb-legend"><span class="price">日経225</span><span class="buy">裁定買い残</span><span class="sell">裁定売り残</span><span class="net">ネット裁定残</span><small data-chart-coverage></small></div><div data-chart-host></div><div class="arb-chart-tooltip" data-chart-tooltip><b>${iso(d.asOfDate)}</b><span>グラフをタップすると数値を表示します</span></div></section>
 <section class="arb-analysis-grid">
  <article class="arb-panel"><h2>株価との組み合わせ判定</h2><div class="arb-direction"><span>日経225 <b class="${tone(a.price5)}">${a.price5>0?'↑':a.price5<0?'↓':'→'}</b></span><span>ネット裁定残 <b class="${tone(a.d5)}">${a.d5>0?'↑':a.d5<0?'↓':'→'}</b></span></div><p class="arb-interpretation">${esc(a.combination)}</p><small>相関を断定せず、直近5取引日の方向を組み合わせて確認します。</small></article>
  <article class="arb-panel"><h2>裁定残 × 市場内部</h2><div class="arb-mini-grid">${kpi('値上がり銘柄数',internal.adv===null?'取得不能':fmt(internal.adv),'東証プライム','mini')}${kpi('値下がり銘柄数',internal.dec===null?'取得不能':fmt(internal.dec),'東証プライム','mini')}${kpi('200日線上銘柄比率','取得不能','既存データに未収録','mini')}${kpi('東証プライム売買代金',internal.turnover||'取得不能','既存市場内部データ','mini')}</div><p class="arb-interpretation">${esc(internal.text)}</p><small>市場内部基準日：${iso(internal.date)}</small></article>
  <article class="arb-panel"><h2>当日裁定需給の参考</h2><div class="arb-mini-grid">${kpi('日経225先物（期近）',futures===null?'取得不能':fmt(futures)+'円',`基準日 ${iso(supply?.futures?.asOfDate)}`,'mini')}${kpi('日経225現物',spot===null?'取得不能':fmt(spot,2),`基準日 ${iso(supply?.spot?.asOfDate)}`,'mini')}${kpi('ベーシス',basis===null?'取得不能（基準日不一致）':signed(basis,'円',2),'先物 − 現物','mini')}${kpi('ベーシス率',basisPct===null?'取得不能':signed(basisPct,'%',2),'参考値','mini')}</div><p class="arb-caution">これは当日裁定需給の参考値です。JPXの正式な当日裁定残高ではありません。</p></article>
  <article class="arb-panel"><h2>特殊需給イベント</h2><div class="arb-events">${events.map(e=>`<div><b>${esc(e.name)}</b><strong>${esc(e.date)}</strong><span>${esc(e.note)}</span></div>`).join('')}</div><p class="arb-interpretation">急増・急減が相場観によるものか、SQやロールなどの機械的要因かを区別するための確認欄です。</p></article>
 </section>
 <aside class="arb-panel arb-howto"><h2>このページの読み方</h2><ol><li>ネット裁定残の現在水準と52週レンジ位置を確認します。</li><li>前回比、5取引日、20取引日の順に、積み上がりか解消かを確認します。</li><li>日経225、市場内部、当日ベーシス、特殊イベントを併読します。</li><li>買い残が多いだけで暴落や弱気と断定しません。</li></ol><p>日次残高は株数ベースです。週次の金額ベース資料とは混在させません。</p></aside>
 <p class="arb-source">出典：<a href="${esc(d.sourcePageUrl||'https://www.jpx.co.jp/markets/statistics-equities/program/')}" target="_blank" rel="noopener">JPX 裁定取引の状況（日別）</a> ／ 日経225終値：<a href="${esc(d.nikkei225PriceSourceUrl||'https://finance.yahoo.com/quote/%5EN225/history/')}" target="_blank" rel="noopener">${esc(d.nikkei225PriceSourceName||'Yahoo Finance')}</a></p>`;
 root.querySelectorAll('[data-period]').forEach(b=>b.addEventListener('click',()=>renderChart(a.rows,b.dataset.period)));renderChart(a.rows,'52');
}
async function load(){try{const [d,supply,stocks]=await Promise.all([fetch(ARB_URL,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('裁定履歴を取得できません');return r.json()}),fetch(SUPPLY_URL,{cache:'no-store'}).then(r=>r.ok?r.json():{}),fetch(STOCKS_URL,{cache:'no-store'}).then(r=>r.ok?r.json():{})]);render(d,supply,stocks)}catch(err){root.innerHTML=`<section class="loading-card"><b>取得不能</b><p>${esc(err.message||'裁定取引データを読み込めませんでした')}</p></section>`}}
load();
})();
