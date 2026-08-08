(function(){
'use strict';

const MOBILE_QUERY='(max-width: 767px)';

function findCardByTitle(titleText){
  const titles=[...document.querySelectorAll('.gold-section-title')];
  const title=titles.find(el=>String(el.textContent||'').trim()===titleText);
  return title?title.closest('.gold-card'):null;
}

function findSupplySummary(){
  return document.querySelector('[data-gold-supply-summary]');
}

function movePhysicalDemandBelowCentralBank(){
  const physical=findCardByTitle('中国・インド現物需要');
  const central=findCardByTitle('中央銀行');
  if(!physical||!central)return false;
  if(central.nextElementSibling===physical)return true;
  central.insertAdjacentElement('afterend',physical);
  return true;
}

function syncSupplySummaryPosition(){
  const summary=findSupplySummary();
  const comex=findCardByTitle('COMEX先物需給');
  const price=findCardByTitle('価格環境');
  if(!summary||!comex||!price)return false;

  if(window.matchMedia(MOBILE_QUERY).matches){
    if(comex.previousElementSibling!==summary){
      comex.insertAdjacentElement('beforebegin',summary);
    }
  }else if(price.previousElementSibling!==summary){
    price.insertAdjacentElement('beforebegin',summary);
  }
  return true;
}

function applyCardOrder(){
  const physicalDone=movePhysicalDemandBelowCentralBank();
  const summaryDone=syncSupplySummaryPosition();
  return physicalDone&&summaryDone;
}

function install(){
  const root=document.querySelector('[data-gold-dashboard]')||document.body;
  const media=window.matchMedia(MOBILE_QUERY);
  const onViewportChange=()=>syncSupplySummaryPosition();

  if(typeof media.addEventListener==='function')media.addEventListener('change',onViewportChange);
  else if(typeof media.addListener==='function')media.addListener(onViewportChange);

  if(applyCardOrder())return;

  const observer=new MutationObserver(()=>{
    if(applyCardOrder())observer.disconnect();
  });
  observer.observe(root,{childList:true,subtree:true});
  setTimeout(()=>observer.disconnect(),15000);
}

if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',install,{once:true});
}else{
  install();
}
})();
