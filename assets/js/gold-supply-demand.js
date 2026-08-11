(function(){
'use strict';
const root=document.querySelector('[data-gold-dashboard]');if(!root)return;
const GOLD_URL='data/gold-supply-demand.json';
const MARKET_URL='data/market/latest.json';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const fmt=(v,d=2)=>n(v)===null?'取得待ち':Number(v).toLocaleString('en-US',{maximumFractionDigits:d});
const signed=(v,d=2,suffix='')=>n(v)===null?'—':`${Number(v)>0?'+':''}${Number(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d})}${suffix}`;
const intSigned=v=>n(v)===null?'—':`${Number(v)>0?'+':''}${Math.round(Number(v)).toLocaleString('en-US')}`;
const dateText=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得待ち';
const dtText=v=>{if(!v)return'取得待ち';try{return new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(v)).replace(/\//g,'/').replace(' ',' ')+' JST'}catch(_){return String(v)}};
const statusKind=s=>s==='verified'?'good':['stale','preserved_after_fetch_error','degraded'].includes(s)?'warn':'muted';
const badge=(s,label)=>`<span class="gold-badge ${statusKind(s)}">${esc(label||({verified:'確認済み',stale:'前回確認値',preserved_after_fetch_error:'取得失敗・前回値',degraded:'一部遅延',unavailable:'取得不能'}[s]||s||'取得待ち'))}</span>`;
const source=(x)=>x&&x.sourceUrl?`<div class="gold-source-line">出典：<a href="${esc(x.sourceUrl)}" target="_blank" rel="noopener">${esc(x.sourceName||'情報源')}</a></div>`:'';
const valClass=v=>n(v)>0?'up':n(v)<0?'down':'';
const item=(obj,key)=>obj&&typeof obj==='object'?(obj[key]||{}):{};
function impact(change,inverse=false){if(n(change)===null)return['判定保留',''];const positive=inverse?Number(change)<0:Number(change)>0;const negative=inverse?Number(change)>0:Number(change)<0;return positive?['金にプラス','up']:negative?['金にマイナス','down']:['中立',''];}
function activeMatrix(interp){return {
 'ショートカバー中心の可能性':0,
 '新規ロング流入の可能性':1,
 'ロング清算の可能性':2,
 '新規ショート流入の可能性':3
}[interp];}
function render(g,market){
 const mg=item(market.markets,'gold'), usdMarket=item(market.markets,'usdjpy');
 const marketOK=mg.verificationStatus==='verified'&&n(mg.value)!==null;
 const c=g.comex||{}, cot=g.cftc||{}, etf=g.etf||{}, physical=g.physical||{}, curve=g.curve||{}, cb=g.centralBank||{}, env=g.environment||{}, a=g.assessment||{}, ds=g.dataStatus||{};
 const usd=env.usdjpy&&env.usdjpy.status==='verified'?env.usdjpy:usdMarket;
 const connected=Number(ds.connected||0), total=Number(ds.total||7);
 const headStatus=document.querySelector('[data-source-status]');if(headStatus)headStatus.textContent=`${connected}/${total} ${connected===total?'連携済み':'連携中'}`;
 const headUpdated=document.querySelector('[data-updated]');if(headUpdated)headUpdated.textContent=dtText(g.generatedAt||market.generatedAt);
 const headAsOf=document.querySelector('[data-as-of]');if(headAsOf)headAsOf.textContent=marketOK?dateText(mg.asOf):dateText(c.asOfDate);
 const price=marketOK?fmt(mg.value,2):'取得待ち';
 const pricePct=marketOK?signed(mg.changePercent,2,'%'):'—';
 const pcls=marketOK?valClass(mg.changePercent):'';
 const score=n(a.score);
 const matrixItems=[
   ['価格上昇＋建玉減少','ショートカバー中心の可能性'],
   ['価格上昇＋建玉増加','新規ロング流入の可能性'],
   ['価格下落＋建玉減少','ロング清算の可能性'],
   ['価格下落＋建玉増加','新規ショート流入の可能性']
 ];
 const active=activeMatrix(c.interpretation);
 const etfRows=[['SPDR Gold Shares (GLD)',etf.gld||{},'日次'],['iShares Gold Trust (IAU)',etf.iau||{},'日次'],['世界金ETF',etf.global||{},'週次・月次']];
 const ry=env.realYield10y||{}, db=env.dollarBroad||{};
 const [ryImpact,ryCls]=impact(ry.change,true),[dbImpact,dbCls]=impact(db.change,true),[usdImpact,usdCls]=impact(usd.change,true);
 const cbValue=n(cb.netPurchasesTonnes)!==null?`${signed(cb.netPurchasesTonnes,0,'t')}`:'取得待ち';
 root.innerHTML=`
 <section class="gold-overview" aria-label="需給サマリー">
  <article class="gold-card gold-summary-card accent">
   <div class="gold-summary-source">${esc(mg.sourceName||'市場データ')}</div><div class="gold-summary-label">金価格（COMEX先物）</div>
   <div class="gold-summary-value ${pcls}">${esc(price)}</div><div class="gold-summary-sub">前回比 ${esc(pricePct)} / ${esc(mg.unit||'USD/oz')}　基準 ${esc(marketOK?dtText(mg.asOf):'取得待ち')}</div>
  </article>
  <article class="gold-card gold-summary-card ${/買い/.test(a.shortTerm||'')?'positive':'neutral'}"><div class="gold-summary-label">短期需給</div><div class="gold-summary-value small ${/買い/.test(a.shortTerm||'')?'up':/売り/.test(a.shortTerm||'')?'down':''}">${esc(a.shortTerm||'判定待ち')}</div><div class="gold-summary-sub">COMEX・CFTC・ETF・実質金利・ドルを合成</div></article>
  <article class="gold-card gold-summary-card ${/強い|買い需要/.test(a.structural||'')?'positive':'neutral'}"><div class="gold-summary-label">構造的需給</div><div class="gold-summary-value small ${/強い|買い需要/.test(a.structural||'')?'up':/弱い/.test(a.structural||'')?'down':''}">${esc(a.structural||'判定待ち')}</div><div class="gold-summary-sub">中央銀行・中国/インド現物需要を短期と分離</div></article>
  <article class="gold-card gold-summary-card accent"><div class="gold-summary-label">総合判定（スコア）</div><div class="gold-score-wrap"><div><div class="gold-summary-value small">${score===null?'—':`${Math.round(score)}/100`}</div><div class="gold-summary-sub">${score===null?'確認済み短期項目が3つ揃うまで採点しません':'確認済みデータのみで計算'}</div></div><div class="gold-score-ring" style="--score-angle:${score===null?0:score*3.6}deg"></div></div></article>
 </section>
 <div class="gold-content-grid">
  <div class="gold-stack">
   <article class="gold-card"><div class="gold-section-head"><h2 class="gold-section-title">COMEX先物需給</h2><span class="gold-frequency">日次</span></div><div class="gold-section-body gold-comex-grid">
    <div><div class="gold-note" style="margin:0 0 8px">価格と建玉（OI）の基準日を揃えられた場合だけ、上昇・下落の中身を判定します。</div><div class="gold-matrix-wrap"><div class="gold-matrix-top">建玉（OI）　← 減少　｜　増加 →</div><div class="gold-matrix-side">価格　上昇 / 下落</div><div class="gold-matrix">${matrixItems.map((x,i)=>`<div class="gold-matrix-cell ${i===1?'good':i===3?'bad':''} ${active===i?'active':''}"><strong>${esc(x[0])}</strong><span>${esc(x[1])}</span></div>`).join('')}</div></div></div>
    <div><table class="gold-metric-table"><tbody>
     <tr><th>基準日</th><td colspan="2">${esc(dateText(c.asOfDate))} ${badge(c.status)}</td></tr>
     <tr><th>同日価格</th><td>${n(c.alignedPrice)===null?'取得待ち':fmt(c.alignedPrice,2)}</td><td class="${valClass(c.alignedPriceChangePercent)}">${signed(c.alignedPriceChangePercent,2,'%')}</td></tr>
     <tr><th>出来高</th><td colspan="2">${n(c.volume)===null?'取得待ち':fmt(c.volume,0)} 枚</td></tr>
     <tr><th>建玉（OI）</th><td>${n(c.openInterest)===null?'取得待ち':fmt(c.openInterest,0)} 枚</td><td class="${valClass(c.openInterestChange)}">${intSigned(c.openInterestChange)} 枚</td></tr>
     <tr><th>判定</th><td colspan="2"><b>${esc(c.interpretation||'基準日一致価格の取得待ち')}</b></td></tr>
    </tbody></table>${source(c)}</div>
   </div></article>
   <article class="gold-card"><div class="gold-section-head"><h2 class="gold-section-title">CFTC投機筋ポジション</h2><span class="gold-frequency">週次</span></div><div class="gold-section-body">
    <div class="gold-cot-strip"><div class="gold-cot-cell"><div class="label">基準日</div><div class="value">${esc(dateText(cot.asOfDate))}</div><div class="sub">${badge(cot.status)}</div></div><div class="gold-cot-cell"><div class="label">Managed Money Long</div><div class="value">${fmt(cot.managedMoneyLong,0)}</div><div class="sub">枚</div></div><div class="gold-cot-cell"><div class="label">Short</div><div class="value">${fmt(cot.managedMoneyShort,0)}</div><div class="sub">枚</div></div><div class="gold-cot-cell"><div class="label">Net</div><div class="value ${valClass(cot.managedMoneyNet)}">${fmt(cot.managedMoneyNet,0)}</div><div class="sub">枚</div></div><div class="gold-cot-cell"><div class="label">Net 前週比</div><div class="value ${valClass(cot.managedMoneyNetChange)}">${intSigned(cot.managedMoneyNetChange)}</div><div class="sub">${esc(cot.judgement||'判定待ち')}</div></div></div>${source(cot)}
   </div></article>
   <article class="gold-card"><div class="gold-section-head"><h2 class="gold-section-title">ETF資金フロー</h2><span class="gold-frequency">日次 / 週次</span></div><div class="gold-section-body gold-table-scroll"><table class="gold-data-table"><thead><tr><th>ETF</th><th>基準日</th><th>金保有量</th><th>前回比</th><th>状態</th></tr></thead><tbody>${etfRows.map(([name,x])=>`<tr><td><b>${esc(name)}</b></td><td>${esc(dateText(x.asOfDate))}</td><td class="num">${n(x.tonnes)===null?'取得待ち':fmt(x.tonnes,2)+' t'}</td><td class="num ${valClass(x.changeTonnes)}">${n(x.changeTonnes)===null?'—':signed(x.changeTonnes,2,' t')}</td><td>${badge(x.status)}</td></tr>`).join('')}</tbody></table><div class="gold-note">GLD・IAUは金保有量を使用します。IAUの発行済口数、AUM、推定資金フローはページの正本から除外しました。</div></div></article>
   <article class="gold-card"><div class="gold-section-head"><h2 class="gold-section-title">中国・インド現物需要</h2><span class="gold-frequency">週次</span></div><div class="gold-section-body"><div class="gold-physical-grid">${[['中国',physical.china||{}],['インド',physical.india||{}]].map(([name,x])=>`<div class="gold-country"><div class="gold-country-head"><div class="gold-country-title">${esc(name)}プレミアム</div>${badge(x.status||physical.status)}</div><div class="gold-country-value ${valClass(x.premiumUsdOz)}">${n(x.premiumUsdOz)===null?'取得待ち':signed(x.premiumUsdOz,2,' $/oz')}</div><div class="gold-note">基準日 ${esc(dateText(x.asOfDate||physical.asOfDate))} / 前回比 ${n(x.change)===null?'—':signed(x.change,2,' $/oz')}</div></div>`).join('')}</div>${source(physical)}<div class="gold-note">WGCが公開する5日移動平均の理論プレミアム/ディスカウントを方向性指標として使用します。ログイン等で取得不能なら推測しません。</div></div></article>
  </div>
  <aside class="gold-stack">
   <article class="gold-card"><div class="gold-section-head"><h2 class="gold-section-title">価格環境</h2><span class="gold-frequency">日次</span></div><div class="gold-section-body"><div class="gold-env-list">
    <div class="gold-env-row"><div class="gold-env-name">米10年実質金利</div><div class="gold-env-value">${n(ry.value)===null?'取得待ち':fmt(ry.value,2)+'%'}</div><div class="gold-env-impact ${ryCls}">${esc(ryImpact)}</div></div>
    <div class="gold-env-row"><div class="gold-env-name">米ドル実効指数（Broad）</div><div class="gold-env-value">${n(db.value)===null?'取得待ち':fmt(db.value,2)}</div><div class="gold-env-impact ${dbCls}">${esc(dbImpact)}</div></div>
    <div class="gold-env-row"><div class="gold-env-name">USD/JPY</div><div class="gold-env-value">${n(usd.value)===null?'取得待ち':fmt(usd.value,2)}</div><div class="gold-env-impact ${usdCls}">${esc(usdImpact)}</div></div>
   </div><div class="gold-note">DXYではなく、無料で安定取得できるFREDの米ドル実効指数（Broad）を採用します。価格環境は需給そのものとは分離して表示します。</div></div></article>
   <article class="gold-card"><div class="gold-section-head"><h2 class="gold-section-title">先物カーブ</h2><span class="gold-frequency">日次〜週次</span></div><div class="gold-section-body"><div class="gold-curve"><div class="gold-curve-line"><span class="gold-curve-marker" style="left:${curve.state==='Backwardation'?'15%':curve.state==='Flat'?'50%':curve.state==='Contango'?'84%':'50%'}"></span></div><div class="gold-curve-labels"><span>Backwardation</span><span>Flat</span><span>Contango</span></div></div><div style="margin-top:8px">${curve.state?badge(curve.status,curve.state):badge(curve.status,'取得待ち')}</div><div class="gold-note">安定した無料公開データ経路を確認できるまで、カーブを推測表示しません。</div></div></article>
   <article class="gold-card"><div class="gold-section-head"><h2 class="gold-section-title">中央銀行</h2><span class="gold-frequency">月次</span></div><div class="gold-section-body"><div class="gold-central"><div><b>世界中央銀行の純購入量</b><div class="gold-note">基準月 ${esc(cb.period||'取得待ち')} / 短期シグナルとは分離</div></div><div class="gold-central-main">${esc(cbValue)}</div></div>${source(cb)}</div></article>
   <article class="gold-card"><div class="gold-section-head"><h2 class="gold-section-title">更新頻度</h2></div><div class="gold-section-body"><div class="gold-frequency-list"><div class="gold-frequency-row"><b>随時</b><span>金価格 / USD/JPY</span></div><div class="gold-frequency-row"><b>日次</b><span>COMEX出来高・建玉 / GLD / IAU / 実質金利 / 米ドル指数</span></div><div class="gold-frequency-row"><b>週次</b><span>CFTC / 中国・インド現物プレミアム</span></div><div class="gold-frequency-row"><b>月次</b><span>世界金ETF集計 / 中央銀行</span></div></div></div></article>
  </aside>
 </div>
 <article class="gold-card gold-ai"><div class="gold-section-head"><h2 class="gold-section-title">AI総合解説</h2><span class="gold-frequency">確認済みデータのみ</span></div><div class="gold-section-body"><div class="gold-ai-grid">${(g.aiSummary||[]).length?(g.aiSummary||[]).map((t,i)=>`<div class="gold-ai-point"><span class="gold-ai-num">${i+1}</span><span>${esc(t)}</span></div>`).join(''):'<div class="gold-ai-empty">分析に必要な確認済みデータを取得中です。</div>'}</div></div></article>
 <div class="gold-watchbar"><div class="gold-watch-item gold-watch-title">このページで見ること</div><div class="gold-watch-item">誰が買っているか</div><div class="gold-watch-item">短期と構造の違い</div><div class="gold-watch-item">価格ドライバーと需給の切り分け</div></div>`;
}
function fail(err){root.innerHTML=`<div class="gold-error"><b>ゴールド需給データを読み込めませんでした。</b><div>${esc(err&&err.message?err.message:err)}</div></div>`;}
async function load(){try{const [gr,mr]=await Promise.all([fetch(GOLD_URL+'?v='+Date.now(),{cache:'no-store'}),fetch(MARKET_URL+'?v='+Date.now(),{cache:'no-store'})]);if(!gr.ok||!mr.ok)throw new Error(`HTTP ${gr.status}/${mr.status}`);render(await gr.json(),await mr.json());}catch(e){fail(e)}}
document.querySelector('[data-reload]')?.addEventListener('click',load);
load();
})();
