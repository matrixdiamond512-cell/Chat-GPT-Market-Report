(() => {
  'use strict';

  const READY = 'data-preopen-board-reading-ready';

  function install() {
    const grid = document.querySelector('.session-grid');
    const tokyo = grid && grid.querySelector('.session-panel');
    if (!tokyo || tokyo.hasAttribute(READY)) return false;

    tokyo.setAttribute(READY, '');
    const block = document.createElement('section');
    block.className = 'preopen-board-reading';
    block.setAttribute('aria-label', '個別株の寄り前板から読み取るポイント');
    block.innerHTML = `
      <h3>個別株の寄り前板から読み取るポイント</h3>
      <div class="preopen-board-grid">
        <div class="preopen-board-point"><b>指数を動かす注文か</b>ファーストリテイリング、東京エレクトロン、ソフトバンクグループなど日経平均への寄与度が高い銘柄に買い・売り注文が集中すると、寄り付き直後の指数方向へ影響しやすくなります。</div>
        <div class="preopen-board-point"><b>市場全体へ広がっているか</b>買い気配または売り気配が複数業種の大型株へ広がれば市場全体の方向性が強く、少数銘柄だけなら指数主導の偏った動きと判断します。</div>
        <div class="preopen-board-point"><b>材料株だけの動きか</b>決算・上方修正・TOBなどの材料株だけに注文が集中している場合、個別要因が中心であり、TOPIXや市場全体の強弱には直結させません。</div>
        <div class="preopen-board-point"><b>寄り後も注文が残るか</b>寄り前の大幅な買い越し・売り越しが寄り後15分も維持され、日経225とTOPIXが同方向なら、板の偏りが実際の資金フローへつながった可能性が高まります。</div>
      </div>
      <p class="preopen-board-caution">注意：寄り前注文は8時55分以降に取消・変更されることがあります。板だけで方向を断定せず、寄り値と寄り後15分の値動きで確認します。</p>`;

    const judgement = tokyo.querySelector('.session-judgement');
    if (judgement) judgement.insertAdjacentElement('beforebegin', block);
    else tokyo.appendChild(block);
    return true;
  }

  function start() {
    if (install()) return;
    const root = document.querySelector('[data-stocks-root]') || document.body;
    const observer = new MutationObserver(() => {
      if (install()) observer.disconnect();
    });
    observer.observe(root, {childList: true, subtree: true});
    setTimeout(() => observer.disconnect(), 12000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
