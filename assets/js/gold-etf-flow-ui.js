(function(){
'use strict';

const DEFAULT_RANGE='66';
const CARD_ATTR='data-gold-etf-ui-ready';

function parseValue(text){
  const value=Number(String(text||'').replace(/[^0-9+\-.]/g,''));
  return Number.isFinite(value)?value:null;
}

function getChartCard(){
  const card=document.querySelector('.gold-etf-enhanced');
  if(!card)return null;
  return card.querySelector('.gold-etf-chart-card:not(.cumulative)');
}

function getSelectedRangeLabel(card){
  const active=card.querySelector('[data-etf-range].active');
  return active?String(active.textContent||'').trim():'3か月';
}

function updateSummary(chartCard){
  const meta=chartCard.querySelector('[data-etf-chart-meta]');
  if(!meta)return;
  const values=[...chartCard.querySelectorAll('[data-etf-bar] .value-text')]
    .map(el=>parseValue(el.textContent))
    .filter(v=>v!==null);
  const total=values.reduce((sum,v)=>sum+v,0);
  const rangeLabel=getSelectedRangeLabel(chartCard);
  const totalEl=meta.querySelector('[data-etf-period-total]');
  const statusEl=meta.querySelector('[data-etf-flow-status]');
  if(totalEl){
    totalEl.textContent=values.length?`${total>0?'+':''}${total.toFixed(2)} t`:'取得待ち';
    totalEl.classList.toggle('flow-positive',total>0);
    totalEl.classList.toggle('flow-negative',total<0);
  }
  if(statusEl){
    const status=total>0?'資金流入優勢':total<0?'資金流出優勢':'中立';
    statusEl.textContent=values.length?`${rangeLabel}：${status}`:'取得待ち';
    statusEl.classList.toggle('flow-positive',total>0);
    statusEl.classList.toggle('flow-negative',total<0);
  }
}

function ensureMeta(chartCard){
  if(chartCard.querySelector('[data-etf-chart-meta]'))return;
  const head=chartCard.querySelector('.gold-etf-chart-head');
  if(!head)return;
  const meta=document.createElement('div');
  meta.className='gold-etf-chart-meta';
  meta.setAttribute('data-etf-chart-meta','');
  meta.innerHTML='<div class="gold-etf-chart-summary"><span>期間累計 <strong data-etf-period-total>取得待ち</strong></span><span>ETF需給 <strong data-etf-flow-status>取得待ち</strong></span></div><div class="gold-etf-chart-legend"><span class="gold-etf-legend-item"><i class="gold-etf-legend-swatch inflow"></i>ピンク＝純流入</span><span class="gold-etf-legend-item"><i class="gold-etf-legend-swatch outflow"></i>ブルー＝純流出</span><span class="gold-etf-chart-unit">単位：トン（t）</span></div>';
  head.insertAdjacentElement('afterend',meta);
}

function applyDefaultRange(chartCard){
  const owner=chartCard.closest('.gold-etf-enhanced');
  if(!owner||owner.hasAttribute(CARD_ATTR))return;
  const button=chartCard.querySelector(`[data-etf-range="${DEFAULT_RANGE}"]`);
  if(!button)return;
  owner.setAttribute(CARD_ATTR,'');
  setTimeout(()=>{
    button.click();
    setTimeout(()=>updateSummary(chartCard),30);
  },0);
}

function enhance(){
  const chartCard=getChartCard();
  if(!chartCard)return false;
  ensureMeta(chartCard);
  applyDefaultRange(chartCard);
  updateSummary(chartCard);
  return true;
}

function install(){
  enhance();
  const root=document.querySelector('[data-gold-dashboard]')||document.body;
  const observer=new MutationObserver(()=>{enhance();});
  observer.observe(root,{childList:true,subtree:true,characterData:true});
  setTimeout(()=>observer.disconnect(),20000);
  document.addEventListener('click',event=>{
    const button=event.target.closest&&event.target.closest('[data-etf-range]');
    if(!button)return;
    const chartCard=button.closest('.gold-etf-chart-card');
    if(!chartCard)return;
    setTimeout(()=>updateSummary(chartCard),40);
  },true);
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});
else install();
})();
