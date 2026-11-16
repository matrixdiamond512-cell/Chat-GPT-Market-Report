(()=>{
'use strict';
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const num=(v,d=1)=>Number.isFinite(Number(v))?Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
const signed=(v,d=1,suffix='')=>Number.isFinite(Number(v))?`${Number(v)>0?'+':''}${num(v,d)}${suffix}`:'—';
const fmtJst=v=>{if(!v)return'—';try{return new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(v)).replaceAll('/','-')+' JST'}catch{return String(v)}};
const oku=v=>Number.isFinite(Number(v))?Number(v)/100:null;
const ratioPct=(value,avg)=>Number.isFinite(Number(value))&&Number.isFinite(Number(avg))&&Number(avg)!==0?Number(value)/Number(avg)*100:null;
const level=r=>{const p=Number(r?.vs20Pct);if(!Number.isFinite(p))return{label:'—',cls:'normal'};if(p>=20)return{label:'活発',cls:'high'};if(p<=-20)return{label:'低調',cls:'low'};return{label:'平常',cls:'normal'}};
async function load(url){const r=await fetch(`${url}?v=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${url}:${r.status}`);return r.json()}

function renderTradersWeb(tw){
  const ok=tw.status==='confirmed'&&tw.pageConfirmed!==false;
  const preserved=tw.status==='preserved_after_fetch_error'&&Number(tw?.keyLevels?.extractedRowCount)>0;
  const usable=ok||preserved;
  const freshness=tw.freshness==='today'?'当日情報':tw.freshness==='previous-session'?'前営業日情報':'鮮度注意';
  if($('tradersweb-asof')) $('tradersweb-asof').textContent=tw.sourceUpdatedAt?fmtJst(tw.sourceUpdatedAt):'取得不能';
  if($('tradersweb-checked')) $('tradersweb-checked').textContent=tw.checkedAt?fmtJst(tw.checkedAt):'—';
  if($('tradersweb-status')){
    $('tradersweb-status').textContent=ok?`取得済み・${freshness}`:preserved?'前回確認値・最新取得遅延':'取得確認できず';
    $('tradersweb-status').classList.toggle('usd-positive',ok);
    $('tradersweb-status').classList.toggle('usd-error',!usable);
  }

  const note=$('tradersweb-source-note');
  if(!note)return;
  const card=note.parentElement;
  if(!usable){
    card.innerHTML=`<h3>Traders Web FX 無料ページ</h3><p class="usd-error">注文水準を取得できませんでした。${tw.error?` 理由：${esc(tw.error)}`:''}</p>`;
    return;
  }

  const k=tw.keyLevels||{};
  const groups=[
    ['売り注文',k.sellOrders||[]],
    ['買い注文',k.buyOrders||[]],
    ['ストップ',k.stops||[]],
    ['NYカットOP',k.nyCutOptions||[]]
  ];
  const rows=[];
  for(const [label,items] of groups){
    for(const item of items){
      rows.push(`<tr><td><b>${esc(label)}</b></td><td><b>${esc(item.price)}円</b></td><td>${esc(item.description)}</td></tr>`);
    }
  }
  const ref=k.referenceSpot?`基準時点レート ${esc(k.referenceSpot)}円`:'基準時点レート —';
  const analysis=k.optionAnalysis||{};
  const analysisHtml=analysis.status==='calculated'?`<div class="usd-option-analysis"><div class="usd-option-analysis-head"><span>オプション分析</span><b>${esc(analysis.headline)}</b></div><p>${esc(analysis.summary)}</p><ul>${(analysis.points||[]).map(point=>`<li>${esc(point)}</li>`).join('')}</ul><small>分析値は取得済みの公開オーダー情報から自動計算。NYカット単独で方向を断定しません。</small></div>`:`<div class="usd-option-analysis unavailable"><b>オプション分析</b><p>${esc(analysis.summary||'分析対象のNYカット情報を取得できませんでした。')}</p></div>`;
  card.innerHTML=`
    <h3>主要オーダー水準 <small>無料公開データ・抜粋</small></h3>
    <p class="usd-position-note"><b>${freshness}</b> ｜ ${ref} ｜ 情報基準 ${esc(fmtJst(tw.sourceUpdatedAt))}</p>
    <div class="usd-table-wrap">
      <table class="usd-table">
        <thead><tr><th>区分</th><th>水準</th><th>内容</th></tr></thead>
        <tbody>${rows.length?rows.join(''):'<tr><td colspan="3" class="usd-error">主要水準を抽出できませんでした。</td></tr>'}</tbody>
      </table>
    </div>
    ${analysisHtml}
    <p class="usd-order-note">全掲載水準の転載ではなく、現在値に近い主要な売り・買い・ストップ・NYカットを需給判断用に抜粋しています。情報の基準日時を必ず確認してください。</p>`;
}

async function applyFix(){
  let volume={},cfg={};
  try{[volume,cfg]=await Promise.all([load('data/usdjpy-volume.json'),load('data/usdjpy-supply-demand.json')])}catch(e){console.warn('USDJPY UI fix:',e);return}

  const recs=volume?.data?.records||[];
  const latest=recs[0]||null;
  if(latest){
    const spotOku=oku(latest.spotVolume);
    const avgOku=oku(latest.avg20);
    const ratio=ratioPct(latest.spotVolume,latest.avg20);
    if($('kpi-volume')) $('kpi-volume').textContent=`${num(spotOku,1)}億ドル`;
    if($('kpi-volume-sub')) $('kpi-volume-sub').textContent=`20営業日平均 ${num(avgOku,1)}億ドル ｜ 平均の${num(ratio,1)}% ｜ 対象日 ${latest.targetDate||'—'}`;

    if($('volume-rows')){
      $('volume-rows').innerHTML=recs.slice(0,5).map(r=>{
        const lv=level(r);
        return `<tr><td>${esc(r.targetDate||'—')}</td><td>${num(r.close,2)}</td><td>${num(oku(r.spotVolume),1)}億ドル</td><td class="${Number(r.vs20Pct)>=0?'usd-positive':'usd-negative'}">${signed(r.vs20Pct,1,'%')}</td><td><span class="usd-pill ${lv.cls}">${lv.label}</span></td></tr>`;
      }).join('');
    }

    if($('volume-comment')){
      const direction=Number(latest.priceChangePct)>0?'価格は上昇':Number(latest.priceChangePct)<0?'価格は下落':'価格は横ばい';
      const volDesc=Number(latest.vs20Pct)<=-20?'出来高は20営業日平均を大きく下回る':Number(latest.vs20Pct)>=20?'出来高は20営業日平均を大きく上回る':'出来高は20営業日平均近辺';
      $('volume-comment').textContent=`${direction}。当日出来高は${num(spotOku,1)}億ドルで、20営業日平均${num(avgOku,1)}億ドルの${num(ratio,1)}%。${volDesc}ため、出来高単独で方向を断定せず、金利差・イベント・ポジションと合わせて判断します。`;
    }

    const items=[...document.querySelectorAll('#summary-list li')];
    const target=items.find(li=>li.textContent.includes('東京スポット出来高'));
    if(target){
      const lv=level(latest);
      target.textContent=`東京市場ドル円スポット出来高は${num(spotOku,1)}億ドル。20営業日平均${num(avgOku,1)}億ドルの${num(ratio,1)}%で「${lv.label}」。`;
    }
  }

  renderTradersWeb(cfg?.tradersWebFx||{});
}

window.addEventListener('load',()=>{
  setTimeout(applyFix,400);
  setTimeout(applyFix,1600);
});
})();
