(() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
  const arr = value => Array.isArray(value) ? value : (value ? [value] : []);
  const text = value => typeof value === 'string' ? value : (value?.text || value?.summary || value?.title || '');
  const dir = value => {
    const s = String(value || '').toLowerCase();
    if (/上昇|強気|買い|反発|up|bull/.test(s)) return 'up';
    if (/下落|弱気|売り|反落|down|bear/.test(s)) return 'down';
    return 'neutral';
  };
  const marketGroup = name => {
    if (/日経|株|NASDAQ|S&P|Dow|Russell/.test(name)) return '株式';
    if (/JPY|EUR|USD|ドル|ユーロ|円/.test(name)) return '為替';
    if (/金|原油|WTI|銀|プラチナ/.test(name)) return '商品';
    if (/BTC|暗号|仮想/.test(name)) return '暗号資産';
    return 'その他';
  };

  function buildHeatmap(report) {
    const groups = new Map();
    arr(report.markets).forEach(m => {
      const group = marketGroup(m.name || '');
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(dir(m.direction));
    });
    const cells = ['株式','為替','債券','商品','暗号資産'].map(group => {
      const states = groups.get(group) || [];
      let state = 'neutral';
      if (states.filter(x => x === 'up').length > states.filter(x => x === 'down').length) state = 'up';
      if (states.filter(x => x === 'down').length > states.filter(x => x === 'up').length) state = 'down';
      const label = state === 'up' ? '買い優勢' : state === 'down' ? '売り優勢' : '中立';
      return `<div class="heatmap-cell ${state}">${esc(group)}<br><small>${esc(label)}</small></div>`;
    }).join('');
    return `<article class="dashboard-card"><span class="dashboard-label">市場ヒートマップ</span><div class="market-heatmap">${cells}</div></article>`;
  }

  function findRate(report, pattern) {
    const source = [report.fullText, ...arr(report.news).map(text), ...arr(report.consistency).map(text)].join(' ');
    const match = source.match(pattern);
    return match ? Number(match[1]) : null;
  }

  function buildRates(report) {
    const us = findRate(report, /米(?:国)?10年(?:債)?(?:利回り)?[^0-9]{0,12}(\d+(?:\.\d+)?)%/);
    const jp = findRate(report, /日本10年(?:国債)?(?:利回り)?[^0-9]{0,12}(\d+(?:\.\d+)?)%/);
    const spread = us != null && jp != null ? us - jp : null;
    const rows = [
      ['米国10年', us, 6],
      ['日本10年', jp, 3],
      ['日米差', spread, 6]
    ].map(([label,value,max]) => {
      const width = value == null ? 0 : Math.min(100, Math.max(3, value / max * 100));
      return `<div class="rate-row"><span>${esc(label)}</span><div class="rate-track"><div class="rate-fill" style="width:${width}%"></div></div><strong>${value == null ? '取得不能' : `${value.toFixed(2)}%`}</strong></div>`;
    }).join('');
    const explanation = arr(report.news).map(text).find(x => /金利|債券/.test(x)) || arr(report.consistency).map(text).find(x => /金利|債券/.test(x)) || '金利変化の理由はレポート本文に記載がありません。';
    return `<article class="dashboard-card"><span class="dashboard-label">金利・日米金利差</span><div class="rate-bars">${rows}</div><p class="rate-note">${esc(explanation)}</p></article>`;
  }

  function buildFocus(report) {
    const changes = arr(report.changes).map(text).slice(0,2).join(' ');
    const handover = arr(report.handover).map(text).slice(0,2).join(' ');
    return `<article class="dashboard-card"><span class="dashboard-label">前回からの変化・次の注目</span><div class="dashboard-list"><p><strong>前回から：</strong>${esc(changes || '記載なし')}</p><p><strong>次に見る点：</strong>${esc(handover || '記載なし')}</p></div></article>`;
  }

  function injectPanels(report) {
    const markets = document.getElementById('dashboardMarkets');
    if (!markets || document.getElementById('dashboardOverviewGrid')) return;
    const wrapper = document.createElement('div');
    wrapper.id = 'dashboardOverviewGrid';
    wrapper.className = 'dashboard-overview-grid';
    wrapper.innerHTML = buildHeatmap(report) + buildRates(report) + buildFocus(report);
    markets.before(wrapper);

    const scenarios = document.createElement('div');
    scenarios.className = 'scenario-grid';
    scenarios.innerHTML = `
      <article class="scenario-card main"><h3>メインシナリオ</h3><p>${esc(report.mainScenario || '記載なし')}</p></article>
      <article class="scenario-card alt"><h3>代替シナリオ</h3><p>${esc(report.alternativeScenario || '記載なし')}</p></article>
      <article class="scenario-card risk"><h3>崩れる条件・リスク</h3><p>${esc(report.breakConditions || arr(report.riskManagement).map(text).join(' ') || '記載なし')}</p></article>`;
    markets.after(scenarios);
  }

  async function init() {
    try {
      const response = await fetch(`reports.json?overview=${Date.now()}`, {cache:'no-store'});
      if (!response.ok) return;
      const reports = await response.json();
      if (!Array.isArray(reports) || !reports.length) return;
      reports.sort((a,b) => `${b.date || ''} ${b.time || ''}`.localeCompare(`${a.date || ''} ${a.time || ''}`));
      injectPanels(reports[0]);
    } catch (_) {}
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true}); else init();
})();