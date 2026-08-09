(function(){
'use strict';

function enhanceArbitrageCard(){
  const cards=[...document.querySelectorAll('.nikkei-card')];
  const card=cards.find(el=>el.querySelector('.nikkei-section-title')?.textContent.trim()==='裁定取引');
  if(!card || card.querySelector('.nikkei-arbitrage-explainer')) return;

  const body=card.querySelector('.nikkei-section-body');
  if(!body) return;

  const explainer=document.createElement('div');
  explainer.className='nikkei-arbitrage-explainer';
  explainer.innerHTML=`
    <div class="nikkei-arb-explainer-title">このデータを見る理由</div>
    <p class="nikkei-arb-explainer-lead">裁定取引は、先物の値動きが現物株へどのように波及し、日経225の需給を動かしているかを見るためのデータです。</p>
    <div class="nikkei-arb-flow" aria-label="裁定取引と日経225需給の関係">
      <div class="nikkei-arb-flow-step"><b>日経225先物</b><span>先物価格が動く</span></div>
      <div class="nikkei-arb-flow-arrow" aria-hidden="true">↓</div>
      <div class="nikkei-arb-flow-step"><b>先物と現物の価格差（ベーシス）</b><span>価格差が拡大・縮小</span></div>
      <div class="nikkei-arb-flow-arrow" aria-hidden="true">↓</div>
      <div class="nikkei-arb-flow-step"><b>裁定取引</b><span>価格差を利用した売買が発生</span></div>
      <div class="nikkei-arb-flow-arrow" aria-hidden="true">↓</div>
      <div class="nikkei-arb-flow-step"><b>現物225銘柄への機械的な買い・売り</b><span>裁定の組成・解消が現物へ波及</span></div>
      <div class="nikkei-arb-flow-arrow" aria-hidden="true">↓</div>
      <div class="nikkei-arb-flow-step is-final"><b>日経225の需給</b><span>現物市場の買い圧力・売り圧力を確認</span></div>
    </div>
    <div class="nikkei-arb-reading-guide">
      <span><b>買い残増加</b>：裁定買いの積み上がりを確認</span>
      <span><b>買い残減少</b>：裁定解消に伴う現物売り圧力の可能性を確認</span>
      <span><b>売り残増加</b>：裁定売りの積み上がりを確認</span>
    </div>
    <p class="nikkei-arb-caution">※ 裁定残だけで上昇・下落を断定せず、先物建玉・海外投資家・オプション・SQ/MSQと合わせて判断します。</p>`;

  const callout=body.querySelector('.nikkei-callout');
  if(callout) body.insertBefore(explainer,callout);
  else body.appendChild(explainer);
}

const observer=new MutationObserver(enhanceArbitrageCard);
observer.observe(document.documentElement,{childList:true,subtree:true});
enhanceArbitrageCard();
})();
