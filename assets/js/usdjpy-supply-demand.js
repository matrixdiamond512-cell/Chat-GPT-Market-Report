(()=>{
'use strict';
const $=id=>document.getElementById(id);
const SOURCES={
  market:'data/market/latest.json',
  rates:'data/rates-bonds.json',
  volume:'data/usdjpy-volume.json',
  events:'data/events.json',
  config:'data/usdjpy-supply-demand.json'
};
const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const num=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
const signed=(v,d=2,suffix='')=>Number.isFinite(Number(v))?`${Number(v)>0?'+':''}${num(v,d)}${suffix}`:'—';
const dateOnly=v=>v?String(v).slice(0,10):'—';
const fmtJst=v=>{if(!v)return'—';try{return new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(v)).replaceAll('/','-')+' JST'}catch{return String(v)}};
const todayJst=()=>{
  const p=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
  const o=Object.fromEntries(p.map(x=>[x.type,x.value]));return`${o.year}-${o.month}-${o.day}`;
};
async function load(url){const r=await fetch(`${url}?v=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${url}:${r.status}`);return r.json()}
function rateBy(rates,name){return(rates?.rates||[]).find(x=>x.name===name)||null}
function marketBy(market,key){return market?.markets?.[key]||null}
function freshnessDays(asOf){if(!asOf)return Infinity;const t=Date.parse(`${asOf}T00:00:00+09:00`);return Number.isFinite(t)?Math.max(0,(Date.now()-t)/86400000):Infinity}
function setClass(el,val){if(!el)return;el.classList.remove('up','down','positive');if(Number(val)>0)el.classList.add('up');if(Number(val)<0)el.classList.add('down')}
function volumeLevel(r){const p=Number(r?.vs20Pct);if(!Number.isFinite(p))return{label:'—',cls:'normal'};if(p>=20)return{label:'活発',cls:'high'};if(p<=-20)return{label:'低調',cls:'low'};return{label:'平常',cls:'normal'}}
function impactClass(v){return v==='高'?'usd-event-high':v==='中'?'usd-event-mid':'usd-event-low'}
function countryShort(e){if(e?.country==='米国'||e?.currency==='USD')return'米';if(e?.country==='日本'||e?.currency==='JPY')return'日';return e?.currency||e?.country||'—'}
function safeTime(v){return/^\d{2}:\d{2}$/.test(v||'')?v:'未定'}
const metaDate=v=>v?fmtJst(v).replace(' JST',''):'—';
function addCardMeta(selector,asOf,acquired){
  document.querySelectorAll(selector).forEach(card=>{
    let meta=card.querySelector(':scope > .usd-card-meta');
    if(!meta){meta=document.createElement('div');meta.className='usd-card-meta';card.appendChild(meta)}
    meta.innerHTML=`<span>基準日 <b>${esc(metaDate(asOf))}</b></span><span>取得日 <b>${esc(metaDate(acquired))}</b></span>`;
  });
}

Promise.allSettled(Object.entries(SOURCES).map(async([k,u])=>[k,await load(u)]))
.then(results=>{
  const data={};const failed=[];
  for(const r of results){if(r.status==='fulfilled')data[r.value[0]]=r.value[1];else failed.push(String(r.reason||'取得失敗'))}
  render(data,failed);
}).catch(err=>render({},[String(err)]));

function render(data,failed){
  const market=data.market||{};
  const rates=data.rates||{};
  const volume=data.volume||{};
  const events=data.events||{};
  const cfg=data.config||{};
  const usd=marketBy(market,'usdjpy');
  const vix=marketBy(market,'vix');
  const recs=volume?.data?.records||[];
  const latestVol=recs[0]||null;
  const us2=rateBy(rates,'米2年債利回り');
  const us10=rateBy(rates,'米10年債利回り');
  const jp10=rateBy(rates,'日本10年国債利回り');
  const spread=(us10&&jp10)?Number(us10.value)-Number(jp10.value):null;
  const spreadChange=(us10&&jp10)?Number(us10.changeBp)-Number(jp10.changeBp):null;
  const cftc=cfg?.cftc||null;
  const cftcFresh=!!(cftc&&cftc.status==='confirmed'&&freshnessDays(cftc.asOf)<=10);
  const tw=cfg?.tradersWebFx||{};

  const core=[usd,latestVol,us10&&jp10,events?.events].filter(Boolean).length;
  const pageUpdate=[market.generatedAt,rates.generatedAt,volume.generatedAt,events.generatedAt,cfg.generatedAt].filter(Boolean).sort().at(-1);
  $('page-updated').textContent=fmtJst(pageUpdate);
  $('page-asof').textContent=usd?.asOf?`価格 ${fmtJst(usd.asOf).replace(' JST','')}`:(latestVol?.targetDate?`出来高 ${latestVol.targetDate}`:'取得不能');
  $('page-status').textContent=failed.length?`主要データ ${core}/4取得`:'主要データ取得済み';
  if(failed.length)$('page-status').classList.add('usd-error');

  $('kpi-price').textContent=usd?num(usd.value,2):'取得不能';
  if(usd){$('kpi-price-change').textContent=`${signed(usd.change,2)} / ${signed(usd.changePercent,2,'%')}`;setClass($('kpi-price'),usd.changePercent)}else $('kpi-price-change').textContent='market/latest.json';
  $('kpi-volume').textContent=latestVol?`${num(latestVol.spotVolume,0)} 百万USD`:'取得不能';
  $('kpi-volume-sub').textContent=latestVol?`20日平均 ${num(latestVol.avg20,0)} / 対象日 ${latestVol.targetDate}`:'日銀スポット出来高';
  $('kpi-spread').textContent=Number.isFinite(spread)?`${num(spread,2)}%`:'取得不能';
  $('kpi-spread-sub').textContent=Number.isFinite(spreadChange)?`前日比 ${signed(spreadChange,1,'bp')}`:'米10年－日本10年';
  if(Number.isFinite(spreadChange))$('kpi-spread').classList.add(spreadChange>0?'up':spreadChange<0?'down':'');

  if(cftc){
    const bias=Number(cftc.net)>0?'円ロング優勢':Number(cftc.net)<0?'円ショート優勢':'中立';
    $('kpi-cftc').textContent=cftcFresh?bias:`${bias}※参考`;
    $('kpi-cftc-sub').textContent=`${dateOnly(cftc.asOf)} / Net ${signed(cftc.net,0)}枚${cftcFresh?'':' / 更新要確認'}`;
  }else{$('kpi-cftc').textContent='取得待ち';$('kpi-cftc-sub').textContent='CFTC週次'}

  let score=0;
  let scoreParts=0;
  if(usd&&Number.isFinite(Number(usd.changePercent))){score+=Number(usd.changePercent)>0.15?1:Number(usd.changePercent)<-0.15?-1:0;scoreParts++}
  if(Number.isFinite(spreadChange)){score+=spreadChange>1?1:spreadChange<-1?-1:0;scoreParts++}
  if(latestVol&&Number.isFinite(Number(latestVol.vs20Pct))&&usd){const active=Math.abs(Number(latestVol.vs20Pct))<20?0:1;if(active&&Number(latestVol.vs20Pct)>20){score+=Number(usd.changePercent)>0?0.5:Number(usd.changePercent)<0?-0.5:0}scoreParts++}
  if(cftcFresh){score+=Number(cftc.net)<0?0.5:Number(cftc.net)>0?-0.5:0;scoreParts++}
  const judgement=score>=1.5?'ドル買い優勢':score>=0.5?'ややドル買い優勢':score<=-1.5?'ドル売り優勢':score<=-0.5?'ややドル売り優勢':'中立';
  const confidence=scoreParts>=4?'高め':scoreParts>=3?'中程度':scoreParts>=2?'やや低め':'低い';
  $('kpi-judgement').textContent=judgement;
  $('kpi-confidence').textContent=`信頼度：${confidence}`;
  const verdictCard=$('kpi-judgement').closest('.usd-verdict-main');
  verdictCard?.classList.remove('is-buy','is-sell','is-neutral');
  verdictCard?.classList.add(judgement.includes('ドル買い')?'is-buy':judgement.includes('ドル売り')?'is-sell':'is-neutral');
  if(judgement.includes('ドル買い'))$('kpi-judgement').classList.add('up');
  if(judgement.includes('ドル売り'))$('kpi-judgement').classList.add('down');

  const bullets=[];
  if(usd)bullets.push(`USD/JPYは${Number(usd.changePercent)>0?'上昇':'下落'}。現在 ${num(usd.value,2)}、前日比 ${signed(usd.changePercent,2,'%')}。`);
  if(Number.isFinite(spread))bullets.push(`日米10年金利差は ${num(spread,2)}%。前日比 ${signed(spreadChange,1,'bp')}で${spreadChange>0?'拡大':'縮小'}。`);
  if(latestVol){const lv=volumeLevel(latestVol);bullets.push(`東京スポット出来高は ${num(latestVol.spotVolume,0)}百万USD、20日平均比 ${signed(latestVol.vs20Pct,1,'%')}で「${lv.label}」。`)}
  if(cftc)bullets.push(`CFTC円先物は ${dateOnly(cftc.asOf)}時点でNet ${signed(cftc.net,0)}枚。${cftcFresh?'方向判定に使用。':'古いため参考表示のみ。'}`);
  if(tw.sourceUpdatedAt)bullets.push(`オーダー確認はトレーダーズ・ウェブFX無料ページ ${fmtJst(tw.sourceUpdatedAt)} 基準。`);
  $('summary-list').innerHTML=bullets.length?bullets.map(x=>`<li>${esc(x)}</li>`).join(''):'<li class="usd-error">中核データを取得できませんでした。</li>';

  $('volume-rows').innerHTML=recs.length?recs.slice(0,5).map(r=>{const lv=volumeLevel(r);return`<tr><td>${esc(r.targetDate)}</td><td>${num(r.close,2)}</td><td>${num(r.spotVolume,0)}</td><td class="${Number(r.vs20)>=0?'usd-positive':'usd-negative'}">${signed(r.vs20,0)}</td><td><span class="usd-pill ${lv.cls}">${lv.label}</span></td></tr>`}).join(''):'<tr><td colspan="5" class="usd-error">取得不能（日銀スポット出来高JSON）</td></tr>';
  if(latestVol){const direction=Number(latestVol.priceChangePct)>0?'価格は上昇':'価格は下落';const volDesc=Number(latestVol.vs20Pct)<=-20?'出来高は20日平均を大きく下回る':Number(latestVol.vs20Pct)>=20?'出来高は20日平均を大きく上回る':'出来高は20日平均近辺';$('volume-comment').textContent=`${direction}、${volDesc}。出来高単独で方向を断定せず、金利差・イベント・ポジションと合わせて判断します。`}

  const rateRows=[];
  const pushRate=(label,r,read)=>{if(r)rateRows.push(`<tr><td>${esc(label)}</td><td>${num(r.value,3)}%</td><td class="${Number(r.changeBp)>0?'up':Number(r.changeBp)<0?'down':''}">${signed(r.changeBp,1,'bp')}</td><td>${esc(read)}<br><small>${esc(r.asOf||'')}</small></td></tr>`)};
  pushRate('米2年',us2,'短期のFRB政策期待を反映');
  pushRate('米10年',us10,'上昇はドル支援、低下はドルの重しになりやすい');
  pushRate('日本10年',jp10,'上昇は円支援、低下は円の重しになりやすい');
  if(Number.isFinite(spread))rateRows.push(`<tr><td><b>日米10年差</b></td><td><b>${num(spread,3)}%</b></td><td class="${spreadChange>0?'up':spreadChange<0?'down':''}">${signed(spreadChange,1,'bp')}</td><td>${spreadChange>0?'金利差拡大はドル支援':'金利差縮小は円支援'}</td></tr>`);
  if(vix)rateRows.push(`<tr><td>VIX</td><td>${num(vix.value,2)}</td><td>${signed(vix.change,2)}</td><td>急上昇時はリスク回避の円買いに注意</td></tr>`);
  $('rates-rows').innerHTML=rateRows.length?rateRows.join(''):'<tr><td colspan="4" class="usd-error">取得不能（金利JSON）</td></tr>';

  renderCftc(cftc,cftcFresh);
  $('tradersweb-asof').textContent=tw.sourceUpdatedAt?fmtJst(tw.sourceUpdatedAt):'取得不能';
  if(tw.url)$('tradersweb-link').href=tw.url;
  renderEvents(events);
  renderScenarios({judgement,confidence,usd,latestVol,spread,spreadChange,cftc,cftcFresh});
  const compositeAsOf=usd?.asOf||latestVol?.targetDate||cftc?.asOf;
  addCardMeta('.usd-price-grid article',usd?.asOf,market.generatedAt);
  addCardMeta('.usd-volume-panel .usd-panel-body',latestVol?.targetDate,volume.generatedAt);
  addCardMeta('.usd-rates-panel .usd-panel-body',rates?.source?.asOfDate||rates?.asOfDate||us10?.asOf,rates.generatedAt);
  addCardMeta('.usd-orders-panel .usd-panel-body',tw.sourceUpdatedAt,tw.checkedAt||cfg.generatedAt);
  addCardMeta('.usd-scenario, .usd-watch',compositeAsOf,pageUpdate);
  addCardMeta('.usd-investor-summary .usd-source-row',compositeAsOf,pageUpdate);
  setTimeout(()=>addCardMeta('.usd-position-stat',cftc?.asOf,cftc?.checkedAt||cfg.generatedAt),900);
}

function renderCftc(cftc,fresh){
  if(!cftc){$('cftc-box').innerHTML='<h3>CFTC / IMM 円先物</h3><p class="usd-error">取得不能。週次データ取得タスクの連携が必要です。</p>';return}
  const delta=Number.isFinite(Number(cftc.previousNet))?Number(cftc.net)-Number(cftc.previousNet):null;
  $('cftc-box').innerHTML=`<h3>CFTC / IMM 円先物 <small>${esc(dateOnly(cftc.asOf))}</small></h3><table class="usd-position-table"><tr><th>Long</th><td>${num(cftc.long,0)}</td></tr><tr><th>Short</th><td>${num(cftc.short,0)}</td></tr><tr><th>Net</th><td class="${Number(cftc.net)>=0?'usd-positive':'usd-negative'}">${signed(cftc.net,0)}</td></tr><tr><th>前週比 Net</th><td>${Number.isFinite(delta)?signed(delta,0):'—'}</td></tr></table><p class="usd-position-note">${fresh?'最新週として方向判定に使用。':'更新日が古いため参考表示。総合判定の必須入力から除外。'}</p>`;
}

function renderEvents(events){
  const today=todayJst();
  const all=(events?.events||[]).filter(e=>e.date===today&&(e.isImportantEvent!==false)&&((e.focusMarkets||[]).includes('USD/JPY')||(e.affectedMarkets||[]).includes('USD/JPY')||['USD','JPY'].includes(e.currency)));
  all.sort((a,b)=>{const ta=safeTime(a.time),tb=safeTime(b.time);if(ta!==tb)return ta.localeCompare(tb);const pa=(a.country==='米国'||a.currency==='USD')?0:1;const pb=(b.country==='米国'||b.currency==='USD')?0:1;return pa-pb});
  const rows=all.slice(0,7).map(e=>`<tr><td>${esc(safeTime(e.time))}</td><td>${esc(countryShort(e))}</td><td>${esc(e.title||e.eventNameOriginal||'—')}${e.status==='released'?'<br><small>発表済み</small>':''}</td><td class="${impactClass(e.importanceLabel)}">${esc(e.importanceLabel||'—')}</td></tr>`).join('');
  $('event-rows').innerHTML=rows||'<tr><td colspan="4">本日のUSD/JPY重要イベントは取得されていません。</td></tr>';
}

function renderScenarios(x){
  const dollar=x.judgement.includes('ドル買い');
  const yen=x.judgement.includes('円買い');
  const neutral=!dollar&&!yen;
  $('scenario-main-title').textContent=x.judgement;
  $('scenario-main-text').textContent=dollar?'価格と金利差がドル側を支える構図。上値追いは出来高とイベント後の金利反応を確認して判断します。':yen?'価格または金利差が円側を支える構図。リスク回避と米金利低下が重なるかを確認します。':'価格と金利の方向が揃わず、材料待ち・レンジを基本にします。';
  const main=[];
  if(x.usd)main.push(`現在値 ${num(x.usd.value,2)} / 前日比 ${signed(x.usd.changePercent,2,'%')}`);
  if(Number.isFinite(x.spread))main.push(`日米10年差 ${num(x.spread,2)}% / ${signed(x.spreadChange,1,'bp')}`);
  if(x.latestVol)main.push(`東京出来高 20日平均比 ${signed(x.latestVol.vs20Pct,1,'%')}`);
  $('scenario-main-points').innerHTML=main.map(v=>`<li>${esc(v)}</li>`).join('');

  $('scenario-alt-title').textContent='横ばい・材料待ち';
  $('scenario-alt-text').textContent='金利差の方向と価格が食い違う場合、方向を追わず、次の主要イベントや出来高回復を待ちます。';
  $('scenario-alt-points').innerHTML='<li>金利差とUSD/JPYが逆方向なら追随を弱める</li><li>薄商いではブレイクの持続性を慎重に確認</li>';

  $('scenario-risk-title').textContent=dollar?'円買いへ反転する条件':yen?'ドル買いへ反転する条件':'レンジを崩す条件';
  $('scenario-risk-text').textContent=dollar?'米金利低下と日米金利差縮小、リスクオフが同時に進む場合はドル買い判断を見直します。':yen?'米金利上昇と日米金利差拡大、リスクオンが同時に進む場合は円買い判断を見直します。':'日米金利差が明確に拡大・縮小し、価格も同方向へ追随した場合に中立判断を解除します。';
  const risk=[Number.isFinite(x.spreadChange)?`金利差変化：${signed(x.spreadChange,1,'bp')}`:'金利差の再確認','重要イベント後の米2年・米10年の反応','東京スポット出来高の急増・急減'];
  $('scenario-risk-points').innerHTML=risk.map(v=>`<li>${esc(v)}</li>`).join('');

  const watch=['米2年・米10年と日米10年差の方向','東京スポット出来高の20日平均比','CFTC円先物の最新週への更新','トレーダーズ・ウェブFX無料ページの基準日時','重要イベント後のUSD/JPYと金利の整合性'];
  $('watch-list').innerHTML=watch.map(v=>`<li>${esc(v)}</li>`).join('');
}
})();
