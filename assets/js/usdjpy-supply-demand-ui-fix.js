(()=>{
'use strict';
const $=id=>document.getElementById(id);
const num=(v,d=1)=>Number.isFinite(Number(v))?Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
const signed=(v,d=1,suffix='')=>Number.isFinite(Number(v))?`${Number(v)>0?'+':''}${num(v,d)}${suffix}`:'—';
const fmtJst=v=>{if(!v)return'—';try{return new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(v)).replaceAll('/','-')+' JST'}catch{return String(v)}};
const oku=v=>Number.isFinite(Number(v))?Number(v)/100:null;
const ratioPct=(value,avg)=>Number.isFinite(Number(value))&&Number.isFinite(Number(avg))&&Number(avg)!==0?Number(value)/Number(avg)*100:null;
const level=r=>{const p=Number(r?.vs20Pct);if(!Number.isFinite(p))return{label:'—',cls:'normal'};if(p>=20)return{label:'活発',cls:'high'};if(p<=-20)return{label:'低調',cls:'low'};return{label:'平常',cls:'normal'}};
async function load(url){const r=await fetch(`${url}?v=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${url}:${r.status}`);return r.json()}

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
        return `<tr><td>${r.targetDate||'—'}</td><td>${num(r.close,2)}</td><td>${num(oku(r.spotVolume),1)}億ドル</td><td class="${Number(r.vs20Pct)>=0?'usd-positive':'usd-negative'}">${signed(r.vs20Pct,1,'%')}</td><td><span class="usd-pill ${lv.cls}">${lv.label}</span></td></tr>`;
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

  const tw=cfg?.tradersWebFx||{};
  if($('tradersweb-asof')) $('tradersweb-asof').textContent=tw.sourceUpdatedAt?fmtJst(tw.sourceUpdatedAt):'取得不能';
  if($('tradersweb-checked')) $('tradersweb-checked').textContent=tw.checkedAt?fmtJst(tw.checkedAt):'—';
  if($('tradersweb-status')){
    const ok=tw.status==='confirmed'&&tw.pageConfirmed!==false;
    $('tradersweb-status').textContent=ok?'無料ページ取得確認済み':'取得確認できず';
    $('tradersweb-status').classList.toggle('usd-positive',ok);
    $('tradersweb-status').classList.toggle('usd-error',!ok);
  }
  if($('tradersweb-source-note')){
    $('tradersweb-source-note').textContent=tw.status==='confirmed'
      ?'無料ページのUSD/JPYオーダー掲載と更新日時を自動確認済みです。注文水準そのものは提供元の利用条件により転載せず、参照元ページで確認します。'
      :`トレーダーズ・ウェブFX無料ページを確認できませんでした。${tw.error?`理由：${tw.error}`:''}`;
  }
}

window.addEventListener('load',()=>{
  setTimeout(applyFix,400);
  setTimeout(applyFix,1600);
});
})();
