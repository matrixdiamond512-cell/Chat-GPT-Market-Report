(() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
  const arr = value => Array.isArray(value) ? value : (value ? [value] : []);
  const firstText = (...values) => values.find(value => typeof value === 'string' && value.trim()) || '';
  const directionClass = value => {
    const text = String(value || '').toLowerCase();
    if (/上昇|強気|買い|反発|up|bull/.test(text)) return 'up';
    if (/下落|弱気|売り|反落|down|bear/.test(text)) return 'down';
    return 'neutral';
  };
  const detail = (label, value, wide = false) => `<div class="market-detail${wide ? ' market-detail--wide' : ''}"><strong>${esc(label)}</strong><p>${esc(value || 'レポートに記載なし')}</p></div>`;
  const outlook = (label, value) => `<div class="outlook-row"><b>${esc(label)}</b><span>${esc(value || 'レポートに記載なし')}</span></div>`;

  const marketKey = name => {
    const text = String(name || '').toLowerCase();
    if (/usd.?jpy|ドル.?円/.test(text)) return 'usdjpy';
    if (/eur.?usd|ユーロ.?ドル/.test(text)) return 'eurusd';
    if (/日経|nikkei/.test(text)) return 'nikkei';
    if (/金|gold/.test(text)) return 'gold';
    if (/原油|wti|oil/.test(text)) return 'oil';
    if (/btc|bitcoin|ビットコイン/.test(text)) return 'btc';
    return '';
  };

  function boughtReason(market) {
    return firstText(market.boughtReason, market.buyReason, market.bullishReason, market.upReason, market.positiveDriver);
  }
  function soldReason(market) {
    return firstText(market.soldReason, market.sellReason, market.bearishReason, market.downReason, market.negativeDriver);
  }
  function shortOutlook(market) {
    return firstText(market.shortTermOutlook, market.shortOutlook, market.outlook, market.material);
  }
  function mediumOutlook(market) {
    return firstText(market.mediumTermOutlook, market.mediumOutlook, market.mainScenario);
  }
  function keyEvent(market) {
    return firstText(market.keyEvent, market.event, market.focusEvent, market.nextEvent);
  }

  function applyEventImpacts(detail) {
    const impacts = detail?.impacts || {};
    document.querySelectorAll('.ticker-card[data-market-key]').forEach(card => {
      const key = card.dataset.marketKey;
      const impact = impacts[key];
      let badge = card.querySelector('.event-impact-badge');
      if (!impact) {
        badge?.remove();
        return;
      }
      if (!badge) {
        badge = document.createElement('div');
        badge.className = 'event-impact-badge';
        card.querySelector('.ticker-top')?.insertAdjacentElement('afterend', badge);
      }
      badge.className = `event-impact-badge is-${impact.state || 'neutral'}`;
      badge.innerHTML = `<span>イベント影響</span><strong>${esc(impact.label || '中立')}</strong><small>${esc(impact.reason || '')}</small>`;
    });
  }

  function renderMarketCards(report) {
    const root = document.getElementById('dashboardMarkets');
    if (!root || !report) return;
    const markets = arr(report.markets).slice(0, 6);
    root.innerHTML = markets.map(market => {
      const state = directionClass(market.direction);
      const key = marketKey(market.name);
      return `<article class="ticker-card market-${state}" data-market-key="${esc(key)}">
        <div class="ticker-top">
          <h3>${esc(market.name || '市場')}</h3>
          <span class="direction ${state}">${esc(market.direction || '中立')}</span>
        </div>
        <p class="ticker-price">${esc(market.price || '—')}</p>
        <p class="ticker-change">${esc(market.change || '前日比の記載なし')}</p>
        <div class="market-detail-grid">
          ${detail('買われた理由', boughtReason(market))}
          ${detail('売られた理由', soldReason(market))}
          <div class="market-detail market-detail--wide"><strong>見通し</strong><div class="outlook-stack">
            ${outlook('短期', shortOutlook(market))}
            ${outlook('中期', mediumOutlook(market))}
          </div></div>
          ${detail('注目イベント', keyEvent(market), true)}
          ${detail('シナリオが崩れる条件', firstText(market.breakCondition, market.invalidation, market.breakConditions), true)}
        </div>
      </article>`;
    }).join('') || '<p class="empty">6市場データがありません。</p>';
    if (window.__latestEventImpactSummary) applyEventImpacts(window.__latestEventImpactSummary);
  }

  function loadModule(src, marker) {
    if (document.querySelector(`script[data-${marker}]`)) return;
    const script = document.createElement('script');
    script.src = `${src}?v=2&cache=${Date.now()}`;
    script.dataset[marker.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = 'true';
    script.async = true;
    document.head.appendChild(script);
  }

  async function loadLatestReport() {
    try {
      const response = await fetch(`reports.json?dashboard=${Date.now()}`, {cache: 'no-store'});
      if (!response.ok) throw new Error('reports.jsonを取得できませんでした');
      const reports = await response.json();
      if (!Array.isArray(reports) || !reports.length) return;
      reports.sort((a, b) => `${b.date || ''} ${b.time || ''}`.localeCompare(`${a.date || ''} ${a.time || ''}`));
      renderMarketCards(reports[0]);
      loadModule('dashboard-market-score.js', 'market-score');
      loadModule('dashboard-event-surprise.js', 'event-surprise');
    } catch (error) {
      const root = document.getElementById('dashboardMarkets');
      if (root && !root.children.length) root.innerHTML = `<p class="empty">${esc(error.message)}</p>`;
    }
  }

  window.addEventListener('market-event-impact', event => applyEventImpacts(event.detail));

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', loadLatestReport, {once:true});
  else loadLatestReport();
})();