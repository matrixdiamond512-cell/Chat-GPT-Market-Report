(function(){
'use strict';

const ROOT='[data-nikkei-dashboard]';

function text(el){return (el?.textContent||'').trim();}
function stripLeadingNumber(value){return String(value||'').replace(/^\s*\d+\.\s*/,'').trim();}

function titleText(card){
  return stripLeadingNumber(card?.querySelector?.('.nikkei-section-title')?.textContent||'');
}

function stripSectionNumbers(root){
  let changed=false;
  for(const title of root.querySelectorAll('.nikkei-section-title')){
    const next=stripLeadingNumber(title.textContent);
    if(next&&next!==title.textContent.trim()){
      title.textContent=next;
      changed=true;
    }
  }
  return changed;
}

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
    const title=titleText(el);
    return /裁定/.test(title);
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
  if(title)title.textContent='オプション需給（OSE 日経225オプション）';

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

function arrangeParticipantCards(root){
  const grid=root.querySelector('.nikkei-grid');
  if(!grid)return false;
  const cards=[...grid.children].filter(el=>el.classList?.contains('nikkei-card'));
  const participant=cards.find(card=>/^取引参加者別手口/.test(titleText(card)));
  const openInterest=cards.find(card=>/^取引参加者別\s*建玉上位/.test(titleText(card)));
  const analysis=root.querySelector('[data-participant-analysis]');
  let changed=false;

  for(const card of [participant,openInterest]){
    if(!card)continue;
    card.classList.remove('nikkei-span-4','nikkei-span-5','nikkei-span-7','nikkei-span-8','nikkei-span-12');
    card.classList.add('nikkei-span-6','nikkei-participant-pair-card');
  }

  if(participant&&openInterest&&participant.parentElement===grid&&openInterest.parentElement===grid&&participant.nextElementSibling!==openInterest){
    grid.insertBefore(openInterest,participant.nextSibling);
    changed=true;
  }

  if(analysis){
    analysis.classList.remove('nikkei-span-4','nikkei-span-5','nikkei-span-6','nikkei-span-7','nikkei-span-8');
    analysis.classList.add('nikkei-span-12');
    const anchor=openInterest||participant;
    if(anchor&&analysis.parentElement===grid&&analysis.previousElementSibling!==anchor){
      grid.insertBefore(analysis,anchor.nextSibling);
      changed=true;
    }
  }

  return changed;
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
  const refined=refineOptions(root);
  const arranged=arrangeParticipantCards(root);
  const stripped=stripSectionNumbers(root);
  return refined||arranged||stripped;
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
