(() => {
  const tabs = [...document.querySelectorAll('[data-report-view]')];
  const latest = document.getElementById('latestReport');
  if (!latest || !tabs.length) return;

  let activeView = 'text';

  function currentReport() {
    if (typeof reports === 'undefined' || !Array.isArray(reports)) return null;
    return reports.find(report => reportKey(report) === selectedKey) || reports[0] || null;
  }

  function summaryList(items = [], limit = 4) {
    const rows = asArray(items).slice(0, limit);
    return rows.length
      ? `<ul>${rows.map(item => `<li>${esc(itemText(item))}</li>`).join('')}</ul>`
      : '<p class="report-summary-empty">記載なし</p>';
  }

  function summaryPanel(title, content, modifier = '') {
    return `<section class="report-summary-panel ${modifier}"><h4>${esc(title)}</h4>${content}</section>`;
  }

  function marketSummary(report) {
    const selectedMarket = marketFilter?.value || 'all';
    const markets = asArray(report.markets).filter(market => selectedMarket === 'all' || market.name === selectedMarket);
    if (!markets.length) return '<p class="report-summary-empty">該当市場の記載がありません。</p>';
    return markets.map(market => `
      <article class="report-summary-market">
        <div class="report-summary-market-head">
          <strong>${esc(market.name || '市場')}</strong>
          <span class="direction ${directionClass(market.direction)}">${esc(market.direction || '中立')}</span>
        </div>
        ${market.price ? `<p class="report-summary-price">${esc(market.price)} ${market.change ? `<small>${esc(market.change)}</small>` : ''}</p>` : ''}
        <p><b>材料：</b>${esc(market.material || market.outlook || '記載なし')}</p>
        ${market.positioning ? `<p><b>需給：</b>${esc(market.positioning)}</p>` : ''}
        ${market.levels ? `<p><b>注目水準：</b>${esc(market.levels)}</p>` : ''}
        ${market.mainScenario ? `<p><b>メイン：</b>${esc(market.mainScenario)}</p>` : ''}
        <p><b>崩れる条件：</b>${esc(market.breakCondition || '記載なし')}</p>
      </article>`).join('');
  }

  function renderSummary(report) {
    const title = report.title || `マーケットレポート｜${report.date || ''} ${report.time || ''}`;
    const scenario = [
      report.mainScenario ? `<p><b>メイン：</b>${esc(report.mainScenario)}</p>` : '',
      report.alternativeScenario ? `<p><b>代替：</b>${esc(report.alternativeScenario)}</p>` : '',
      report.breakConditions ? `<p><b>崩れる条件：</b>${esc(report.breakConditions)}</p>` : ''
    ].join('') || '<p class="report-summary-empty">記載なし</p>';

    latest.innerHTML = `
      <article class="report-summary-dashboard">
        <header class="report-summary-head">
          <div>
            <span class="report-summary-kicker">INFOGRAPHIC DASHBOARD</span>
            <h3>${esc(title)}</h3>
          </div>
          <span class="time-badge ${timeClass(report.time)}">${esc(report.time || '時刻不明')}</span>
        </header>
        <section class="report-summary-theme">
          <span>今日の相場テーマ</span>
          <strong>${esc(report.theme || '記載なし')}</strong>
        </section>
        <div class="report-summary-grid">
          ${summaryPanel('今日の主導市場', `<p>${esc(report.leadingMarket || '記載なし')}</p>`, 'report-summary-panel--leader')}
          ${summaryPanel('前回からの変化', summaryList(report.changes))}
          ${summaryPanel('材料と値動きの整合性', summaryList(report.consistency))}
          ${summaryPanel('ポジションの偏り', summaryList(report.positioning))}
          ${summaryPanel('重要ニュース', summaryList(report.news), 'report-summary-panel--wide')}
          ${summaryPanel('クロスアセット資金フロー', summaryList(report.crossAssetFlow), 'report-summary-panel--wide')}
          ${summaryPanel('セクター・業種動向', summaryList(report.sectors))}
          ${summaryPanel('今後のイベント', summaryList(report.events))}
          ${summaryPanel('次の時間帯への引き継ぎ', summaryList(report.handover), 'report-summary-panel--wide')}
          ${summaryPanel('全体シナリオ', scenario, 'report-summary-panel--wide')}
          ${summaryPanel('リスク管理', summaryList(report.riskManagement), 'report-summary-panel--wide')}
        </div>
        <section class="report-summary-markets">
          <h4>6市場の売買判断</h4>
          <div class="report-summary-market-grid">${marketSummary(report)}</div>
        </section>
      </article>`;
  }

  function renderActiveView() {
    const report = currentReport();
    if (!report) return;
    if (activeView === 'summary') {
      renderSummary(report);
    } else {
      latest.innerHTML = reportCard(report, marketFilter?.value || 'all');
    }
    tabs.forEach(tab => {
      const selected = tab.dataset.reportView === activeView;
      tab.classList.toggle('is-active', selected);
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
  }

  tabs.forEach(tab => tab.addEventListener('click', () => {
    activeView = tab.dataset.reportView;
    renderActiveView();
  }));

  tabs.forEach((tab, index) => tab.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const nextIndex = event.key === 'ArrowRight'
      ? (index + 1) % tabs.length
      : (index - 1 + tabs.length) % tabs.length;
    tabs[nextIndex].focus();
    tabs[nextIndex].click();
  }));

  if (typeof openReport === 'function') {
    const originalOpenReport = openReport;
    openReport = function(date, time) {
      originalOpenReport(date, time);
      if (activeView === 'summary') renderActiveView();
    };
  }

  marketFilter?.addEventListener('change', () => {
    if (currentReport()) renderActiveView();
  });
})();
