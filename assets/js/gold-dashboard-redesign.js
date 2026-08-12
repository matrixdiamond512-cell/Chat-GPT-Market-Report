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
  const cards=[...grid.querySelectorAll('.gold-card')];
  cards.forEach(card=>{
    const title=card.querySelector('.gold-section-title')?.textContent?.trim()||'';
    card.classList.remove('gold-detail-wide','gold-detail-compact','gold-detail-summary');
    if(['COMEX先物需給','CFTC投機筋ポジション','中国・インド現物需要'].includes(title))card.classList.add('gold-detail-wide');
    else card.classList.add('gold-detail-compact');
  });
  const summary=grid.querySelector('[data-gold-supply-summary]');
  if(summary){summary.classList.remove('gold-detail-compact');summary.classList.add('gold-detail-summary')}
  let laneA=grid.querySelector('.gold-detail-lane-a'),laneB=grid.querySelector('.gold-detail-lane-b');
  if(!laneA){laneA=document.createElement('div');laneA.className='gold-detail-lane gold-detail-lane-a';grid.prepend(laneA)}
  if(!laneB){laneB=document.createElement('div');laneB.className='gold-detail-lane gold-detail-lane-b';grid.append(laneB)}
  const laneATitles=new Set(['需給サマリー','先物カーブ','中国・インド現物需要']);
  cards.forEach(card=>{
    const title=card.matches('[data-gold-supply-summary]')?'需給サマリー':card.querySelector('.gold-section-title')?.textContent?.trim()||'';
    (laneATitles.has(title)?laneA:laneB).appendChild(card);
  });
  grid.querySelectorAll(':scope > .gold-stack').forEach(stack=>{if(!stack.children.length)stack.remove()});
  return true;
}
if(!arrange()){
  const observer=new MutationObserver(()=>{if(arrange())observer.disconnect()});
  observer.observe(root,{childList:true,subtree:true});
  setTimeout(()=>{arrange();observer.disconnect()},15000);
}
window.addEventListener('resize',arrange,{passive:true});
})();
