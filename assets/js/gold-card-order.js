(function(){
'use strict';

function findCardByTitle(titleText){
  const titles=[...document.querySelectorAll('.gold-section-title')];
  const title=titles.find(el=>String(el.textContent||'').trim()===titleText);
  return title?title.closest('.gold-card'):null;
}

function movePhysicalDemandBelowCentralBank(){
  const physical=findCardByTitle('中国・インド現物需要');
  const central=findCardByTitle('中央銀行');
  if(!physical||!central)return false;
  if(central.nextElementSibling===physical)return true;
  central.insertAdjacentElement('afterend',physical);
  return true;
}

function install(){
  if(movePhysicalDemandBelowCentralBank())return;
  const root=document.querySelector('[data-gold-dashboard]')||document.body;
  const observer=new MutationObserver(()=>{
    if(movePhysicalDemandBelowCentralBank())observer.disconnect();
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
