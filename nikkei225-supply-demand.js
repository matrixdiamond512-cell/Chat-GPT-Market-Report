(function(){
'use strict';
const root=document.querySelector('[data-nikkei-dashboard]');if(!root)return;
const DATA_URL='data/nikkei225-supply-demand.json';
const ARBITRAGE_URL='data/nikkei225-arbitrage.json';
const MARKET_URL='data/market/latest.json';
const STOCKS_URL='data/stocks.json';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>{if(v===null||v===undefined||v==='')return null;const x=Number(String(v).replace(/,/g,''));return Number.isFinite(x)?x:null};
const fmt=(v,d=0)=>num(v)===null?'取得待ち':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=0,suffix='')=>num(v)===null?'—':`${Number(v)>0?'+':''}${Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d})}${suffix}`;
const dateOnly=v=>{if(!v)return'取得待ち';const s=String(v).slice(0,10);return /^\d{4}-\d{2}-\d{2}$/.test(s)?s.replaceAll('-','/'):String(v)};
const localDate=v=>{if(!v)return'';try{return new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(v))}catch(_){return String(v).slice(0,10)}};
const dtText=v=>{if(!v)return'取得待ち';try{return new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(v))+' JST'}catch(_){return String(v)}};
const cls=v=>num(v)>0?'nikkei-up':num(v)<0?'nikkei-down':'';
const freq=(label,kind='daily')=>`<span class="nikkei-freq ${esc(kind)}">${esc(label)}</span>`;
const source=x=>{if(!x)return'';const link=x.sourceUrl?`<a href="${esc(x.sourceUrl)}" target="_blank" rel="noopener">${esc(x.sourceName||'情報源')}</a>`:esc(x.sourceName||'情報源未登録');const updated=x.fetchedAt||x.lastSuccessAt||x.checkedAt||x.updatedAt;return`<div class="nikkei-source">出典：${link} / 基準日 ${esc(dateOnly(x.asOfDate||x.sourceDate))} / 最終取得 ${esc(updated?dtText(updated):'取得日時なし')} / ${esc(x.frequency||'更新頻度未設定')} / ${esc(x.status||'状態未設定')}</div>`};
const value=(v,suffix='',d=0)=>num(v)===null?'<span class="nikkei-empty">取得待ち</span>':`${fmt(v,d)}${esc(suffix)}`;
const change=(v,suffix='',d=0)=>num(v)===null?'—':`<span class="${cls(v)}">${esc(signed(v,d,suffix))}</span>`;
function jpRow(stocks,label){const rows=stocks?.marketInternals?.japan?.rows||[];return rows.find(r=>Array.isArray(r)&&String(r[0]).trim()===label)||null;}
function parseFirstNumber(v){if(v===null||v===undefined)return null;const m=String(v).replace(/,/g,'').match(/-?\d+(?:\.\d+)?/);return m?Number(m[0]):null;}
function futureInterpret(priceChange,oiChange){if(num(priceChange)===null||num(oiChange)===null)return{label:'建玉データ待ち',index:-1,bias:'neutral'};if(priceChange>0&&oiChange>0)return{label:'価格上昇＋建玉増加 → 新規ロング流入の可能性',index:0,bias:'buy'};if(priceChange>0&&oiChange<0)return{label:'価格上昇＋建玉減少 → ショートカバーの可能性',index:1,bias:'buy'};if(priceChange<0&&oiChange>0)return{label:'価格下落＋建玉増加 → 新規ショート流入の可能性',index:2,bias:'sell'};if(priceChange<0&&oiChange<0)return{label:'価格下落＋建玉減少 → ロング手仕舞いの可能性',index:3,bias:'sell'};return{label:'価格または建玉の変化が小さく方向判定は中立',index:-1,bias:'neutral'};}
function summaryClass(text){if(/強気|買い優勢|買い/.test(text||''))return'nikkei-status-good';if(/弱い|売り優勢|売り/.test(text||''))return'nikkei-status-bad';if(/警戒/.test(text||''))return'nikkei-status-warn';if(/中立/.test(text||''))return'nikkei-status-purple';return'';}
function rankRows(items,side){const rows=(items||[]).slice(0,3);if(!rows.length)return'<div class="nikkei-rank-row"><span>—</span><span class="nikkei-empty">取得待ち</span><span>—</span></div>';return rows.map((x,i)=>`<div class="nikkei-rank-row"><span>${i+1}位</span><span>${esc(x.name||'—')}</span><b>${num(x.volume)===null?'—':fmt(x.volume,0)+'枚'}</b></div>`).join('');}
function percentile(values,p){const xs=values.filter(v=>Number.isFinite(v)).sort((a,b)=>a-b);if(!xs.length)return null;const i=(xs.length-1)*p;const lo=Math.floor(i),hi=Math.ceil(i);return lo===hi?xs[lo]:xs[lo]+(xs[hi]-xs[lo])*(i-lo);}
function arbitrageAnalysis(arb,detail){
 const buy=num(arb.buyBalance),sell=num(arb.sellBalance),buyChange=num(arb.buyChange),sellChange=num(arb.sellChange);
 const balancesReady=buy!==null&&sell!==null;
 const changesReady=buyChange!==null&&sellChange!==null;
 const net=balancesReady?buy-sell:null;
 const netChange=changesReady?buyChange-sellChange:null;
 const previousBuy=buy!==null&&buyChange!==null?buy-buyChange:null;
 const previousSell=sell!==null&&sellChange!==null?sell-sellChange:null;
 const previousNet=previousBuy!==null&&previousSell!==null?previousBuy-previousSell:null;
 const rows=(Array.isArray(detail?.history)?detail.history:[]).map(x=>({date:String(x.date||'').slice(0,10),buy:num(x.buyBalance),sell:num(x.sellBalance),price:num(x.nikkei225Close)})).filter(x=>/^\d{4}-\d{2}-\d{2}$/.test(x.date)&&x.buy!==null&&x.sell!==null).map(x=>({...x,net:x.buy-x.sell})).sort((a,b)=>a.date.localeCompare(b.date));
 const unique=rows.filter((x,i)=>i===rows.length-1||x.date!==rows[i+1].date);
 const latestDate=String(arb.asOfDate||'').slice(0,10);
 const throughLatest=unique.filter(x=>!latestDate||x.date<=latestDate).slice(-260);
 const spanDays=throughLatest.length>1?(new Date(throughLatest.at(-1).date)-new Date(throughLatest[0].date))/86400000:0;
 const historyReady=throughLatest.length>=13&&spanDays>=84;
 const nets=throughLatest.map(x=>x.net);
 const netChanges=throughLatest.slice(1).map((x,i)=>x.net-throughLatest[i].net);
 const quiet=historyReady?percentile(netChanges.map(Math.abs),.25):null;
 const latestIndex=throughLatest.length-1;
 const oneWeek=latestIndex>=5?throughLatest[latestIndex].net-throughLatest[latestIndex-5].net:null;
 const fourWeeks=latestIndex>=20?throughLatest[latestIndex].net-throughLatest[latestIndex-20].net:null;
 const rangeMin=historyReady?Math.min(...nets):null,rangeMax=historyReady?Math.max(...nets):null;
 const rangePosition=rangeMin!==null&&rangeMax!==null&&rangeMax!==rangeMin?(net-rangeMin)/(rangeMax-rangeMin)*100:null;
 let status='中立';
 if(!balancesReady||!changesReady)status='判定不能（データ不足）';
 else if(net<0)status='売り残優勢';
 else if(!historyReady)status='中立';
 else if(rangePosition>=85&&netChange>0&&oneWeek>0&&fourWeeks>0)status='過熱';
 else if(rangePosition>=70&&[netChange,oneWeek,fourWeeks].filter(v=>v!==null&&v>0).length>=2)status='やや過熱';
 else if(netChange<0&&oneWeek!==null&&oneWeek<0)status='解消進行';
 const latest=throughLatest.at(-1),previous=throughLatest.at(-2);
 const priceChange=latest&&previous&&latest.date===latestDate&&latest.price!==null&&previous.price!==null?latest.price-previous.price:null;
 let interpretation='裁定残の変化は小さく、現時点では裁定需給による大きな偏りは確認されません。';
 if(status==='判定不能（データ不足）')interpretation='裁定需給の判定に必要なデータが不足しています。欠損値は推測で補完していません。';
 else if(status==='売り残優勢')interpretation='裁定売り残が買い残を上回っています。売り残の解消方向を含め、次回公表値を確認します。';
 else if(status==='解消進行')interpretation=priceChange!==null&&priceChange<0?'株価調整とともにネット裁定残が減少。裁定解消が進み、需給の重さは低下方向です。':'高水準のネット裁定残が減少に転じ、裁定解消が進んでいます。需給の重さは低下方向です。';
 else if(status==='過熱'||status==='やや過熱')interpretation=priceChange!==null&&priceChange>0?'日経225上昇と同時にネット裁定残も増加。上昇継続の一方、裁定ポジションの積み上がりに注意。':'ネット裁定残が高水準で増加しています。方向を弱気と断定せず、積み上がりの継続に注意します。';
 else if(netChange!==null&&quiet!==null&&Math.abs(netChange)>quiet)interpretation=netChange>0?'ネット裁定残は前回から増加していますが、現時点では過熱を示す条件はそろっていません。':'ネット裁定残は前回から減少し、裁定ポジションは解消方向です。';
 return{buy,sell,buyChange,sellChange,net,netChange,previousNet,oneWeek,fourWeeks,status,interpretation};
}
function arbStatusClass(status){if(status==='過熱')return'is-hot';if(status==='やや過熱')return'is-warm';if(status==='解消進行')return'is-unwinding';if(status==='売り残優勢')return'is-sell';return'is-neutral';}
function arbValue(v){return num(v)===null?'<span class="nikkei-empty">取得不能（データ未取得）</span>':`${fmt(v,0)}千株`;}
function arbChange(v){if(num(v)===null)return'<span class="nikkei-empty">取得不能（前回値未取得）</span>';const arrow=v>0?'↑':v<0?'↓':'→';return`<span class="${cls(v)}">${esc(signed(v,0,'千株'))} ${arrow}</span>`;}
function render(d,market,stocks,arbDetail){
 const fut=market?.markets?.nikkei225_futures_ose||{};
 const futures=d.futures||{};
 const sessions=d.sessions||{};
 const arb=d.arbitrage||{};
 const arbView=arbitrageAnalysis(arb,arbDetail);
 const opt=d.options||{};
 const part=d.participantFlow||{};
 const foreign=d.foreignInvestors||{};
 const poi=d.participantOpenInterest||{};
 const short=d.shortSelling||{};
 const margin=d.margin||{};
 const assess=d.assessment||{};
 const marketVerified=fut.verificationStatus==='verified'&&num(fut.value)!==null;
 const price=marketVerified?num(fut.value):num(futures.price);
 const priceChange=marketVerified?num(fut.change):num(futures.priceChange);
 const pricePct=marketVerified?num(fut.changePercent):num(futures.priceChangePercent);
 const oiChange=num(futures.openInterestChange);
 const interp=futureInterpret(priceChange,oiChange);
 const spotRow=jpRow(stocks,'日経225');
 const spot=num(d.spot?.value)??(spotRow?parseFirstNumber(spotRow[1]):null);
 const spotDate=d.spot?.asOfDate||stocks?.marketInternals?.japan?.dataDate||'';
 const futDate=marketVerified?localDate(fut.asOf):futures.asOfDate||'';
 const basisReady=num(spot)!==null&&num(price)!==null&&spotDate&&futDate&&spotDate===futDate;
 const basis=basisReady?price-spot:null;
 const overall=assess.overall||((interp.index>=0)?(interp.bias==='buy'?'やや買い優勢':'やや売り優勢'):'判定保留');
 const shortTerm=assess.shortTerm||(interp.index>=0?(interp.bias==='buy'?'強気':'弱気'):'判定待ち');
 const overallBias=/買い/.test(overall)?'buy':/売り/.test(overall)?'sell':'neutral';
 const generated=[d.generatedAt,market?.generatedAt,stocks?.updatedAt].filter(Boolean).sort().pop();
 const headStatus=document.querySelector('[data-source-status]');if(headStatus)headStatus.textContent=d.sourceStatus||'構造実装済み・専門データ連携待ち';
 const headUpdated=document.querySelector('[data-updated]');if(headUpdated)headUpdated.textContent=dtText(generated);
 const headAsOf=document.querySelector('[data-as-of]');if(headAsOf)headAsOf.textContent=marketVerified?dateOnly(futDate):dateOnly(futures.asOfDate);
 const matrix=[['価格↑ × 建玉↑','新規買い','buy'],['価格↑ × 建玉↓','買い戻し','cover'],['価格↓ × 建玉↑','新規売り','sell'],['価格↓ × 建玉↓','手仕舞い','close']];
 const overallReason=assess.reason||'先物価格だけでは需給を断定しません。建玉・裁定・オプション・投資主体の基準日を分けて確認します。';
 const basisNote=basisReady?'現物と先物の基準日が一致した単純ベーシスです。':'現物と先物の基準日が一致しないため、単純ベーシスは計算しません。';
 root.innerHTML=`
 <section class="nikkei-overview" aria-label="需給サマリー">
  <article class="nikkei-card nikkei-total"><div class="nikkei-total-kicker">総合需給判定</div><div class="nikkei-total-value ${overallBias}">${esc(overall)}</div><div class="nikkei-total-reason">${esc(overallReason)}</div></article>
  <article class="nikkei-card nikkei-summary">${freq('日次','daily')}<div class="nikkei-summary-label">短期先物需給</div><div class="nikkei-summary-value ${summaryClass(shortTerm)}">${esc(shortTerm)}</div><div class="nikkei-summary-sub">価格×建玉で新規買い・買い戻しを区別</div></article>
  <article class="nikkei-card nikkei-summary">${freq('前々営業日','delayed')}<div class="nikkei-summary-label">裁定需給</div><div class="nikkei-summary-value arbitrage-summary-status ${arbStatusClass(arbView.status)}">${esc(arbView.status)}</div><div class="nikkei-summary-sub">ネット残と直近の増減を複合判定</div></article>
  <article class="nikkei-card nikkei-summary">${freq('日次','daily')}<div class="nikkei-summary-label">オプション需給</div><div class="nikkei-summary-value ${summaryClass(assess.options)}">${esc(assess.options||'判定待ち')}</div><div class="nikkei-summary-sub">Put/Call・IV・SQ接近を分離評価</div></article>
  <article class="nikkei-card nikkei-summary">${freq('週次','weekly')}<div class="nikkei-summary-label">海外投資家</div><div class="nikkei-summary-value ${summaryClass(assess.foreign)}">${esc(assess.foreign||'判定待ち')}</div><div class="nikkei-summary-sub">現物・日経225先物・TOPIX先物を併読</div></article>
 </section>
 <section class="nikkei-grid">
  <article class="nikkei-card nikkei-span-7"><div class="nikkei-section-head"><h2 class="nikkei-section-title">日経225先物需給</h2>${freq('日次','daily')}</div><div class="nikkei-section-body nikkei-futures-layout">
   <div class="nikkei-table-scroll"><table class="nikkei-table"><thead><tr><th>項目</th><th>本日値</th><th>前日比</th></tr></thead><tbody>
    <tr><td><b>日経225先物（期近）</b></td><td class="num nikkei-value">${value(price,'円',0)}</td><td class="num">${change(priceChange,'円',0)}${num(pricePct)!==null?` <span class="${cls(pricePct)}">(${esc(signed(pricePct,2,'%'))})</span>`:''}</td></tr>
    <tr><td>出来高</td><td class="num">${value(futures.volume,'枚',0)}</td><td class="num">${change(futures.volumeChangePercent,'%',1)}</td></tr>
    <tr><td>建玉残高</td><td class="num">${value(futures.openInterest,'枚',0)}</td><td class="num">${change(futures.openInterestChange,'枚',0)}</td></tr>
    <tr><td>日経225mini出来高</td><td class="num">${value(futures.miniVolume,'枚',0)}</td><td class="num">${change(futures.miniVolumeChangePercent,'%',1)}</td></tr>
    <tr><td>日経225mini建玉</td><td class="num">${value(futures.miniOpenInterest,'枚',0)}</td><td class="num">${change(futures.miniOpenInterestChange,'枚',0)}</td></tr>
   </tbody></table>${source(futures)}</div>
   <div><div class="nikkei-matrix-title">価格 × 建玉の読み方</div><div class="nikkei-matrix">${matrix.map((x,i)=>`<div class="nikkei-matrix-cell ${x[2]} ${interp.index===i?'active':''}"><strong>${esc(x[0])}</strong><span>= ${esc(x[1])}</span></div>`).join('')}</div><div class="nikkei-current-read">本日の判定：${esc(interp.label)}</div></div>
  </div></article>
  <article class="nikkei-card nikkei-span-5"><div class="nikkei-section-head"><h2 class="nikkei-section-title">日中 vs ナイトセッション</h2>${freq('日次','daily')}</div><div class="nikkei-section-body"><div class="nikkei-session-grid">
   <div class="nikkei-session"><div class="nikkei-session-label">日中</div><div class="nikkei-session-value ${cls(sessions.dayChange)}">${num(sessions.dayChange)===null?'取得待ち':esc(signed(sessions.dayChange,0,'円'))}</div><div class="nikkei-session-sub">主導：${esc(sessions.dayDriver||'判定待ち')}</div></div>
   <div class="nikkei-session"><div class="nikkei-session-label">ナイト</div><div class="nikkei-session-value ${cls(sessions.nightChange)}">${num(sessions.nightChange)===null?'取得待ち':esc(signed(sessions.nightChange,0,'円'))}</div><div class="nikkei-session-sub">主導：${esc(sessions.nightDriver||'判定待ち')}</div></div>
   </div><div class="nikkei-note">${esc(sessions.comment||'東京時間と海外時間を分け、どの時間帯が先物を主導したか確認します。')}</div>${source(sessions)}</div></article>
  <article class="nikkei-card nikkei-span-5"><div class="nikkei-section-head"><h2 class="nikkei-section-title">現物・先物ベーシス</h2>${freq('日次','daily')}</div><div class="nikkei-section-body"><div class="nikkei-basis-grid">
   <div class="nikkei-basis-item"><div class="nikkei-basis-label">日経225現物</div><div class="nikkei-basis-value">${value(spot,'',2)}</div><div class="nikkei-note">基準日 ${esc(dateOnly(spotDate))}</div></div>
   <div class="nikkei-basis-item"><div class="nikkei-basis-label">日経225先物（期近）</div><div class="nikkei-basis-value">${value(price,'',0)}</div><div class="nikkei-note">基準日 ${esc(dateOnly(futDate))}</div></div>
   <div class="nikkei-basis-item"><div class="nikkei-basis-label">単純ベーシス</div><div class="nikkei-basis-value ${cls(basis)}">${num(basis)===null?'—':esc(signed(basis,2,'円'))}</div><div class="nikkei-note">${esc(basisReady?(basis>0?'先物プレミアム':'先物ディスカウント'):'基準日不一致')}</div></div>
   </div><div class="nikkei-note">${esc(basisNote)}</div></div></article>
  <article class="nikkei-card nikkei-span-7 arbitrage-summary-card"><div class="nikkei-section-head"><h2 class="nikkei-section-title">裁定取引</h2>${freq('前々営業日','delayed')}</div><div class="nikkei-section-body">
   <div class="arbitrage-summary-head"><div><div class="arbitrage-summary-kicker">ネット裁定残</div><div class="arbitrage-summary-net">${arbValue(arbView.net)}</div><div class="arbitrage-summary-previous">前回 ${arbValue(arbView.previousNet)} / ${arbChange(arbView.netChange)}</div></div><div class="arbitrage-summary-badge ${arbStatusClass(arbView.status)}"><span>裁定需給</span><strong>${esc(arbView.status)}</strong></div></div>
   <div class="arbitrage-summary-balances"><div><span>裁定買い残</span><strong>${arbValue(arbView.buy)}</strong><small>前回比 ${arbChange(arbView.buyChange)}</small></div><div><span>裁定売り残</span><strong>${arbValue(arbView.sell)}</strong><small>前回比 ${arbChange(arbView.sellChange)}</small></div></div>
   <div class="arbitrage-summary-interpretation">${esc(arbView.interpretation)}</div>
   <div class="arbitrage-summary-meta"><span>基準日：${esc(arb.asOfDate?String(arb.asOfDate).slice(0,10):'取得不能（基準日未取得）')}</span>${arb.fetchedAt?`<span>更新：${esc(dtText(arb.fetchedAt))}</span>`:''}</div>
   <a class="arbitrage-summary-link" href="nikkei225-arbitrage.html">詳しく見る <span aria-hidden="true">→</span> 裁定取引分析</a>${source(arb)}
  </div></article>
  <article class="nikkei-card nikkei-span-5"><div class="nikkei-section-head"><h2 class="nikkei-section-title">オプション・SQ需給</h2>${freq('日次','daily')}</div><div class="nikkei-section-body"><div class="nikkei-mini-grid">
   <div class="nikkei-mini-card"><div class="nikkei-mini-label">次回SQ</div><div class="nikkei-mini-value">${esc(opt.nextSqDate?dateOnly(opt.nextSqDate):'取得待ち')}</div><div class="nikkei-note">${num(opt.businessDaysToSq)===null?'営業日数待ち':`あと ${fmt(opt.businessDaysToSq,0)} 営業日`}</div></div>
   <div class="nikkei-mini-card"><div class="nikkei-mini-label">Put / Call</div><div class="nikkei-mini-value">${num(opt.putCallRatio)===null?'取得待ち':fmt(opt.putCallRatio,2)}</div><div class="nikkei-note">出来高または建玉の定義を明示</div></div>
   <div class="nikkei-mini-card"><div class="nikkei-mini-label">IV</div><div class="nikkei-mini-value">${num(opt.iv)===null?'取得待ち':fmt(opt.iv,1)+'%'}</div><div class="nikkei-note">前回比 ${num(opt.ivChange)===null?'—':signed(opt.ivChange,1,'pt')}</div></div>
   </div><div class="nikkei-callout">${esc(opt.comment||'SQ接近時はヘッジ・ロール・手仕舞いの影響を通常時より重く見ます。')}</div>${source(opt)}</div></article>
  <article class="nikkei-card nikkei-span-6"><div class="nikkei-section-head"><h2 class="nikkei-section-title">取引参加者別手口</h2>${freq('日次','daily')}</div><div class="nikkei-section-body"><div class="nikkei-rank-grid"><div class="nikkei-rank-box"><div class="nikkei-rank-title">売り上位</div>${rankRows(part.sellers,'sell')}</div><div class="nikkei-rank-box"><div class="nikkei-rank-title">買い上位</div>${rankRows(part.buyers,'buy')}</div></div><div class="nikkei-note">手口は最終投資家を直接示すものではありません。証券会社名から投資家の国籍や最終顧客を断定しません。</div>${source(part)}</div></article>
  <article class="nikkei-card nikkei-span-6"><div class="nikkei-section-head"><h2 class="nikkei-section-title">海外投資家の週次需給</h2>${freq('週次','weekly')}</div><div class="nikkei-section-body"><div class="nikkei-table-scroll"><table class="nikkei-table"><thead><tr><th>市場</th><th>差引</th><th>評価</th></tr></thead><tbody>
   <tr><td>現物株</td><td class="num">${num(foreign.cashNet)===null?'取得待ち':change(foreign.cashNet,'億円',0)}</td><td>${esc(foreign.cashNote||'現物の方向を確認')}</td></tr>
   <tr><td>日経225先物</td><td class="num">${num(foreign.nikkeiFuturesNet)===null?'取得待ち':change(foreign.nikkeiFuturesNet,'億円',0)}</td><td>${esc(foreign.nikkeiNote||'ヘッジ・短期売買を確認')}</td></tr>
   <tr><td>TOPIX先物</td><td class="num">${num(foreign.topixFuturesNet)===null?'取得待ち':change(foreign.topixFuturesNet,'億円',0)}</td><td>${esc(foreign.topixNote||'大型株全体との整合性を確認')}</td></tr>
   </tbody></table></div><div class="nikkei-callout">${esc(foreign.comment||'週次データを当日の主体と断定せず、現物と先物の組み合わせからポジション構造を読みます。')}</div>${source(foreign)}</div></article>
  <article class="nikkei-card nikkei-span-6"><div class="nikkei-section-head"><h2 class="nikkei-section-title">取引参加者別 建玉上位</h2>${freq('週次','weekly')}</div><div class="nikkei-section-body"><div class="nikkei-rank-grid"><div class="nikkei-rank-box"><div class="nikkei-rank-title">買い建玉上位</div>${rankRows(poi.buyers,'buy')}</div><div class="nikkei-rank-box"><div class="nikkei-rank-title">売り建玉上位</div>${rankRows(poi.sellers,'sell')}</div></div><div class="nikkei-note">${esc(poi.comment||'上位参加者への集中度と前週からの増減を確認します。')}</div>${source(poi)}</div></article>
  <article class="nikkei-card nikkei-span-6"><div class="nikkei-section-head"><h2 class="nikkei-section-title">空売り・信用需給</h2>${freq('日次 / 週次','weekly')}</div><div class="nikkei-section-body"><div class="nikkei-mini-grid">
   <div class="nikkei-mini-card"><div class="nikkei-mini-label">空売り比率</div><div class="nikkei-mini-value">${num(short.ratio)===null?'取得待ち':fmt(short.ratio,1)+'%'}</div><div class="nikkei-note">5日平均 ${num(short.avg5)===null?'—':fmt(short.avg5,1)+'%'} / 20日平均 ${num(short.avg20)===null?'—':fmt(short.avg20,1)+'%'}</div></div>
   <div class="nikkei-mini-card"><div class="nikkei-mini-label">信用買い残</div><div class="nikkei-mini-value">${num(margin.buyBalance)===null?'取得待ち':fmt(margin.buyBalance,2)+'兆円'}</div><div class="nikkei-note">週次</div></div>
   <div class="nikkei-mini-card"><div class="nikkei-mini-label">信用倍率</div><div class="nikkei-mini-value">${num(margin.ratio)===null?'取得待ち':fmt(margin.ratio,2)+'倍'}</div><div class="nikkei-note">信用売り残 ${num(margin.sellBalance)===null?'—':fmt(margin.sellBalance,2)+'兆円'}</div></div>
   </div><div class="nikkei-callout">${esc(short.comment||margin.comment||'空売りは平均との比較、信用は買い残の重さを補助指標として確認します。')}</div>${source(short)}${source(margin)}</div></article>
 </section>
 <article class="nikkei-card nikkei-ai"><div class="nikkei-section-head"><h2 class="nikkei-section-title">AI需給コメント / 次の監視ポイント</h2>${freq('更新時判定','daily')}</div><div class="nikkei-section-body nikkei-ai-grid">
  <div class="nikkei-watch">${(d.watchpoints||['先物建玉の増加継続が本物の上昇か確認','裁定買い残が増えるかどうか','SQ接近でオプション主導の振れに注意','海外投資家の週次データで現物買い継続を確認']).map((x,i)=>`<div class="nikkei-watch-item"><span class="nikkei-watch-num">${i+1}</span><span>${esc(x)}</span></div>`).join('')}</div>
  <div class="nikkei-comment">${esc(assess.comment||`現在、日経225先物の価格は${marketVerified?'市場データ基盤から確認済み':'取得待ち'}です。一方、建玉・裁定・オプション・投資主体の専門データは取得状況を個別に表示します。価格だけで需給方向を決めず、価格×建玉、日中対ナイト、裁定、オプション、海外投資家の順に確認してください。`)}</div>
  <div class="nikkei-freshness"><div class="nikkei-fresh-row"><b>先物・手口</b>${freq('日次','daily')}</div><div class="nikkei-fresh-row"><b>裁定</b>${freq('前々営業日','delayed')}</div><div class="nikkei-fresh-row"><b>投資主体・建玉</b>${freq('週次','weekly')}</div><div class="nikkei-fresh-row"><b>信用</b>${freq('週次','weekly')}</div></div>
 </div></article>
 <div class="nikkei-footer-note">日次・前々営業日・週次データを同じ鮮度として扱いません。取得できない項目は推測値で埋めず「取得待ち」と表示します。</div>`;
}
async function load(){root.innerHTML='<section class="nikkei-loading">日経225需給データを読み込み中です。</section>';try{const [dr,mr,sr,ar]=await Promise.allSettled([fetch(DATA_URL,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('specialized '+r.status);return r.json()}),fetch(MARKET_URL,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('market '+r.status);return r.json()}),fetch(STOCKS_URL,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('stocks '+r.status);return r.json()}),fetch(ARBITRAGE_URL,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('arbitrage '+r.status);return r.json()})]);const d=dr.status==='fulfilled'?dr.value:{};const m=mr.status==='fulfilled'?mr.value:{};const s=sr.status==='fulfilled'?sr.value:{};const a=ar.status==='fulfilled'?ar.value:{};render(d,m,s,a)}catch(err){root.innerHTML=`<section class="nikkei-error"><b>日経225需給ページの読み込みに失敗しました。</b><div>${esc(err.message||err)}</div></section>`}}
document.querySelector('[data-reload]')?.addEventListener('click',load);load();
})();
