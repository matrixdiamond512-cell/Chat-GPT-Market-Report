(function(){
'use strict';

const DEFAULT_RANGE='66';
const READY_ATTR='data-gold-etf-ui-ready';

function parseValue(text){
  const value=Number(String(text||'').replace(/[^0-9+\-.]/g,''));
  return Number.isFinite(value)?value:null;
}

function getDailyChartCard(root){
  return root?root.querySelector('.gold-etf-chart-card:not(.cumulative)'):null;
}

function getSelectedRangeLabel(card){
  const active=card.querySelector('[data-etf-range].active');
  return active?String(active.textContent||'').trim():'3か月';
}

function ensureMeta(chartCard){
  if(!chartCard||chartCard.querySelector('[data-etf-chart-meta]'))return;
  const head=chartCard.querySelector('.gold-etf-chart-head');
  if(!head)return;
  const meta=document.createElement('div');
  meta.className='gold-etf-chart-meta';
  meta.setAttribute('data-etf-chart-meta','');
  meta.innerHTML='<div class="gold-etf-chart-summary"><span>期間累計 <strong data-etf-period-total>取得待ち</strong></span><span>ETF需給 <strong data-etf-flow-status>取得待ち</strong></span></div><div class="gold-etf-chart-legend"><span class="gold-etf-legend-item"><i class="gold-etf-legend-swatch inflow"></i>ピンク＝純流入</span><span class="gold-etf-legend-item"><i class="gold-etf-legend-swatch outflow"></i>ブルー＝純流出</span><span class="gold-etf-chart-unit">単位：トン（t）</span></div>';
  head.insertAdjacentElement('afterend',meta);
}

function updateSummary(chartCard){
  const meta=chartCard&&chartCard.querySelector('[data-etf-chart-meta]');
  if(!meta)return;
  const values=[...chartCard.querySelectorAll('[data-etf-bar] .value-text')]
    .map(el=>parseValue(el.textContent))
    .filter(v=>v!==null);
  const total=values.reduce((sum,v)=>sum+v,0);
  const totalEl=meta.querySelector('[data-etf-period-total]');
  const statusEl=meta.querySelector('[data-etf-flow-status]');
  const positive=total>0;
  const negative=total<0;
  if(totalEl){
    totalEl.textContent=values.length?`${positive?'+':''}${total.toFixed(2)} t`:'取得待ち';
    totalEl.classList.toggle('flow-positive',positive);
    totalEl.classList.toggle('flow-negative',negative);
  }
  if(statusEl){
    const status=positive?'資金流入優勢':negative?'資金流出優勢':'中立';
    statusEl.textContent=values.length?`${getSelectedRangeLabel(chartCard)}：${status}`:'取得待ち';
    statusEl.classList.toggle('flow-positive',positive);
    statusEl.classList.toggle('flow-negative',negative);
  }
}

function applyOnce(){
  const root=document.querySelector('.gold-etf-enhanced');
  if(!root)return false;
  const daily=getDailyChartCard(root);
  if(!daily)return false;

  const cumulative=root.querySelector('.gold-etf-chart-card.cumulative');
  if(cumulative&&daily.nextElementSibling!==cumulative){
    daily.insertAdjacentElement('afterend',cumulative);
  }

  ensureMeta(daily);

  if(!root.hasAttribute(READY_ATTR)){
    root.setAttribute(READY_ATTR,'');
    const button=daily.querySelector(`[data-etf-range="${DEFAULT_RANGE}"]`);
    if(button&&!button.classList.contains('active')){
      setTimeout(()=>button.click(),0);
    }
  }

  setTimeout(()=>updateSummary(daily),60);
  return true;
}

function install(){
  if(!applyOnce()){
    const root=document.querySelector('[data-gold-dashboard]')||document.body;
    const observer=new MutationObserver(()=>{
      if(applyOnce())observer.disconnect();
    });
    observer.observe(root,{childList:true,subtree:true});
    setTimeout(()=>observer.disconnect(),12000);
  }

  document.addEventListener('click',event=>{
    const button=event.target.closest&&event.target.closest('[data-etf-range]');
    if(!button)return;
    const chartCard=button.closest('.gold-etf-chart-card');
    if(!chartCard)return;
    setTimeout(()=>updateSummary(chartCard),60);
  },true);
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});
else install();
})();
