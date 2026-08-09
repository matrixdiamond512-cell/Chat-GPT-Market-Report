(function(){
'use strict';

const DATA_URL='data/nikkei225-options-latest.json';
const ROOT='[data-nikkei-dashboard]';
let live=null;

const fmt=v=>Number.isFinite(Number(v))?Number(v).toLocaleString('ja-JP'):'—';
const monthLabel=v=>{const s=String(v||'');return /^\d{6}$/.test(s)?`${Number(s.slice(4,6))}月限`:'期近限月'};

function setText(el,value){if(el)el.textContent=value;}

function apply(){
  if(!live)return false;
  const root=document.querySelector(ROOT);
  const option=root?.querySelector('.nikkei-options-analysis');
  if(!option)return false;

  const upper=live.upperCallConcentrationStrike;
  const lower=live.lowerPutConcentrationStrike;
  setText(option.querySelector('.nikkei-options-summary-card.call strong'),Number.isFinite(Number(upper))?`${fmt(upper)}円`:'取得待ち');
  setText(option.querySelector('.nikkei-options-summary-card.put strong'),Number.isFinite(Number(lower))?`${fmt(lower)}円`:'取得待ち');

  const gaugeCall=option.querySelector('.nikkei-options-gauge-side.call');
  if(gaugeCall&&Number.isFinite(Number(upper)))gaugeCall.innerHTML=`Call集中<br>${fmt(upper)}`;
  const labels=option.querySelectorAll('.nikkei-options-gauge-labels span');
  if(labels.length>=3){
    if(Number.isFinite(Number(lower)))labels[0].textContent=`Put ${fmt(lower)}`;
    if(Number.isFinite(Number(upper)))labels[2].textContent=`Call ${fmt(upper)}`;
  }

  const panelHead=option.querySelector('.heatmap-panel .nikkei-options-panel-head h3');
  if(panelHead)panelHead.textContent=`権利行使価格別 建玉ヒートマップ（${monthLabel(live.optionContractMonth)}）`;
  const panelHint=option.querySelector('.heatmap-panel .nikkei-options-panel-head span');
  if(panelHint)panelHint.textContent='PUT＝ブルー / CALL＝ピンク';

  for(const metric of option.querySelectorAll('.nikkei-options-metric')){
    const label=metric.querySelector('span');
    if(label?.textContent.trim()==='Put/Call OI比率')label.textContent='Put/Call OI比率（表示範囲）';
  }

  const metrics=option.querySelector('.nikkei-options-metrics');
  if(metrics&&!metrics.querySelector('.nikkei-options-volume-pcr')&&Number.isFinite(Number(live.publishedPutCallVolumeRatio))){
    const row=document.createElement('div');
    row.className='nikkei-options-metric nikkei-options-volume-pcr';
    row.innerHTML=`<span>Put/Call 出来高比率</span><b>${Number(live.publishedPutCallVolumeRatio).toFixed(3)}</b><small>前営業日 ${Number(live.publishedPutCallVolumeRatioPrevious).toFixed(3)}</small>`;
    metrics.appendChild(row);
  }

  if(!option.querySelector('.nikkei-options-live-source')){
    const source=document.createElement('div');
    source.className='nikkei-options-live-source';
    source.innerHTML=`<b>建玉データ</b><span>基準日 ${live.asOfDate||'—'} / ${live.strikeOiCoverage||'権利行使価格別建玉'}</span><span>一次情報：JPX大阪取引所日報。現在はJPX公表データの公開集計をフォールバックとして利用。</span>`;
    option.querySelector('.heatmap-panel')?.appendChild(source);
  }

  option.dataset.liveOptionsApplied='1';
  return true;
}

async function init(){
  try{
    const r=await fetch(DATA_URL,{cache:'no-store'});
    if(!r.ok)return;
    live=await r.json();
  }catch(e){console.warn('nikkei225 options live polish',e);return;}
  apply();
  const root=document.querySelector(ROOT);
  if(!root)return;
  const obs=new MutationObserver(()=>apply());
  obs.observe(root,{childList:true,subtree:true});
  let tries=0;
  const timer=setInterval(()=>{tries++;if(apply()||tries>100)clearInterval(timer)},100);
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
