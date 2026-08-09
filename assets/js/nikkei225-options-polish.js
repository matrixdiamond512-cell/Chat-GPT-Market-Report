(function(){
'use strict';

const ROOT='[data-nikkei-dashboard]';

function text(el){return (el?.textContent||'').trim();}

function compactOverview(root){
  const overview=root.querySelector('.nikkei-overview');
  if(!overview)return;
  for(const card of overview.querySelectorAll('.nikkei-summary')){
    const label=text(card.querySelector('.nikkei-summary-label'));
    if(label==='オプション需給')card.remove();
  }
  overview.classList.add('nikkei-overview-refined');
}

function moveOptionsAfterArbitrage(root,option){
  const grid=root.querySelector('.nikkei-grid');
  if(!grid||!option)return;
  const arbitrage=[...grid.children].find(el=>{
    const title=text(el.querySelector?.('.nikkei-section-title'));
    return /^4\.\s*/.test(title)&&/裁定/.test(title);
  });
  if(arbitrage&&arbitrage.nextElementSibling!==option){
    grid.insertBefore(option,arbitrage.nextSibling);
  }
}

function refineOptions(root){
  const option=root.querySelector('.nikkei-options-analysis');
  if(!option)return false;
  if(option.dataset.layoutPolished==='1')return true;

  const title=option.querySelector('.nikkei-section-title');
  if(title)title.textContent='5. オプション需給（OSE 日経225オプション）';

  const note=option.querySelector('.nikkei-options-note');
  if(note)note.textContent='方向予想ではなく、権利行使価格別の建玉集中、OI増減、IV・PCR、SQ接近を組み合わせて「ヘッジ圧力が変わりやすい価格帯」を確認します。';

  // 現在値は先物需給セクションに既出なので、オプション内では重複表示しない。
  option.querySelector('.nikkei-options-summary-card.current')?.remove();
  option.querySelector('.nikkei-options-summary-strip')?.classList.add('nikkei-options-summary-strip-refined');

  // CALL / PUT の役割が視覚的に分かるよう、ラベルを統一する。
  for(const card of option.querySelectorAll('.nikkei-options-summary-card.call small'))card.textContent='上側CALL集中';
  for(const card of option.querySelectorAll('.nikkei-options-summary-card.put small'))card.textContent='下側PUT集中';

  // ページ上部に総合需給判定があるため、オプション内の同じ判定カードは削除して補完解釈に集約。
  const combined=option.querySelector('.nikkei-options-combined');
  if(combined){
    const duplicate=[...combined.querySelectorAll('.nikkei-options-judge')].find(el=>/総合需給判定/.test(text(el.querySelector('small'))));
    duplicate?.remove();
    combined.classList.add('nikkei-options-combined-refined');
    const head=combined.querySelector('.nikkei-options-comment b');
    if(head)head.textContent='先物＋オプションの補完解釈';
  }

  // 上下集中帯は上部サマリーで示すため、下部はSQ/MSQと実務上の見方だけに絞る。
  const pricebands=option.querySelector('.nikkei-options-pricebands');
  if(pricebands){
    pricebands.querySelector('.nikkei-options-chip.call')?.remove();
    pricebands.querySelector('.nikkei-options-chip.put')?.remove();
    pricebands.classList.add('nikkei-options-pricebands-refined');
  }

  moveOptionsAfterArbitrage(root,option);
  option.dataset.layoutPolished='1';
  return true;
}

function fixReload(){
  const button=document.querySelector('[data-reload]');
  if(!button||button.dataset.optionsReloadFixed==='1')return;
  button.dataset.optionsReloadFixed='1';
  button.addEventListener('click',function(ev){
    // ベース画面だけの部分再描画でオプションセクションが消えるのを防ぎ、全モジュールを再初期化する。
    ev.preventDefault();
    ev.stopImmediatePropagation();
    window.location.reload();
  },true);
}

function apply(){
  const root=document.querySelector(ROOT);
  if(!root)return false;
  compactOverview(root);
  fixReload();
  return refineOptions(root);
}

function init(){
  apply();
  const root=document.querySelector(ROOT);
  if(!root)return;
  const observer=new MutationObserver(()=>apply());
  observer.observe(root,{childList:true,subtree:true});
  let tries=0;
  const timer=setInterval(()=>{
    tries++;
    if(apply()||tries>120)clearInterval(timer);
  },100);
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
