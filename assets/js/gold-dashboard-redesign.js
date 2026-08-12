(()=>{
'use strict';
const root=document.querySelector('[data-gold-dashboard]');
if(!root)return;
function arrange(){
  const grid=root.querySelector('.gold-content-grid');
  const cftc=root.querySelector('[data-cftc-history-card]');
  const etf=root.querySelector('[data-gold-etf-enhanced],.gold-etf-enhanced');
  if(!grid||!cftc||!etf)return false;
  let charts=root.querySelector('.gold-fullwidth-charts');
  if(!charts){charts=document.createElement('section');charts.className='gold-fullwidth-charts';charts.setAttribute('aria-label','ゴールド需給チャート');grid.insertAdjacentElement('beforebegin',charts)}
  if(cftc.parentElement!==charts)charts.appendChild(cftc);
  if(etf.parentElement!==charts)charts.appendChild(etf);
  return true;
}
if(!arrange()){
  const observer=new MutationObserver(()=>{if(arrange())observer.disconnect()});
  observer.observe(root,{childList:true,subtree:true});
  setTimeout(()=>{arrange();observer.disconnect()},15000);
}
window.addEventListener('resize',arrange,{passive:true});
})();
