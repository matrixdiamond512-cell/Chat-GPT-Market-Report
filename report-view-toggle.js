(() => {
  const tabs = [...document.querySelectorAll('[data-report-view]')];
  const latest = document.getElementById('latestReport');
  if (!latest || !tabs.length) return;

  let activeView = 'summary';

  function currentReport() {
    if (typeof reports === 'undefined' || !Array.isArray(reports)) return null;
    return reports.find(report => reportKey(report) === selectedKey) || reports[0] || null;
  }

  function renderParagraphs(items = [], emptyText = '記載なし') {
    const rows = asArray(items).filter(Boolean);
    return rows.length
      ? rows.map(item => `<p>${esc(itemText(item))}</p>`).join('')
      : `<p class="report-reader-empty">${esc(emptyText)}</p>`;
  }

  function readerSection(title, body, id = '') {
    return `<section class="report-reader-section"${id ? ` id="${esc(id)}"` : ''}><h2>${esc(title)}</h2><div class="report-reader-copy">${body}</div></section>`;
  }

  function readerMarket(market) {
    return `<section class="report-reader-market">
      <div class="report-reader-market-title"><h3>${esc(market.name || '市場')}</h3><span class="direction ${directionClass(market.direction)}">${esc(market.direction || '中立')}</span></div>
      ${market.price ? `<p class="report-reader-market-price"><strong>${esc(market.price)}</strong>${market.change ? ` <span>${esc(market.change)}</span>` : ''}</p>` : ''}
      <p><strong>現状・材料：</strong>${esc(market.material || market.outlook || '記載なし')}</p>
      ${market.positioning ? `<p><strong>需給・ポジション：</strong>${esc(market.positioning)}</p>` : ''}
      ${market.levels ? `<p><strong>注目水準：</strong>${esc(market.levels)}</p>` : ''}
      ${market.mainScenario ? `<p><strong>メインシナリオ：</strong>${esc(market.mainScenario)}</p>` : ''}
      ${market.alternativeScenario ? `<p><strong>代替シナリオ：</strong>${esc(market.alternativeScenario)}</p>` : ''}
      <p><strong>見方が崩れる条件：</strong>${esc(market.breakCondition || '記載なし')}</p>
      ${market.risk ? `<p><strong>リスク：</strong>${esc(market.risk)}</p>` : ''}
    </section>`;
  }

  function renderSources(items = []) {
    const rows = asArray(items).filter(Boolean);
    if (!rows.length) return '<p class="report-reader-empty">記載なし</p>';
    return `<ul class="report-reader-sources">${rows.map(source => {
      if (typeof source === 'string') return `<li>${esc(source)}</li>`;
      const label = esc(source.name || source.title || '情報源');
      const note = source.note ? ` — ${esc(source.note)}` : '';
      return source.url ? `<li><a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${label}</a>${note}</li>` : `<li>${label}${note}</li>`;
    }).join('')}</ul>`;
  }

  function renderFullText(report) {
    const title = report.title || `マーケットレポート｜${report.date || ''} ${report.time || ''}`;
    const dateLabel = `${(report.date || '').replaceAll('-', '/')} ${report.time || ''}`.trim();
    const markets = asArray(report.markets).filter(Boolean);
    const selectedMarket = marketFilter?.value || 'all';
    const visibleMarkets = markets.filter(market => selectedMarket === 'all' || market.name === selectedMarket);
    latest.innerHTML = `<article class="report-reader">
      <header class="report-reader-header"><p class="report-reader-kicker">MARKET REPORT · FULL TEXT</p><h1>${esc(title)}</h1><p class="report-reader-meta">${esc(dateLabel)}｜セクション別表示</p></header>
      <nav class="report-reader-toc" aria-label="本文内目次"><a href="#reader-theme">相場テーマ</a><a href="#reader-news">重要ニュース</a><a href="#reader-flow">資金フロー</a><a href="#reader-markets">個別市場</a><a href="#reader-scenario">シナリオ</a><a href="#reader-risk">リスク</a></nav>
      ${readerSection('1. 今日の相場テーマ', `<p class="report-reader-lead">${esc(report.theme || '記載なし')}</p>`, 'reader-theme')}
      ${readerSection('2. 今日の主導市場', `<p>${esc(report.leadingMarket || '記載なし')}</p>`)}
      ${readerSection('3. 前回からの変化', renderParagraphs(report.changes))}
      ${readerSection('4. 材料と値動きの整合性', renderParagraphs(report.consistency))}
      ${readerSection('5. ポジションの偏り', renderParagraphs(report.positioning))}
      ${readerSection('6. 重要ニュース', renderParagraphs(report.news), 'reader-news')}
      ${readerSection('7. クロスアセット資金フロー', renderParagraphs(report.crossAssetFlow), 'reader-flow')}
      ${readerSection('8. セクター・業種動向', renderParagraphs(report.sectors))}
      ${readerSection('9. 今後のイベント', renderParagraphs(report.events))}
      ${readerSection('10. 次の時間帯への引き継ぎ', renderParagraphs(report.handover))}
      <section class="report-reader-section" id="reader-markets"><h2>11. 個別市場見通し</h2><div class="report-reader-markets">${visibleMarkets.length ? visibleMarkets.map(readerMarket).join('') : '<p class="report-reader-empty">該当市場の記載がありません。</p>'}</div></section>
      ${readerSection('12. 全体シナリオ', `${report.mainScenario ? `<p><strong>メインシナリオ：</strong>${esc(report.mainScenario)}</p>` : ''}${report.alternativeScenario ? `<p><strong>代替シナリオ：</strong>${esc(report.alternativeScenario)}</p>` : ''}${report.breakConditions ? `<p><strong>シナリオが崩れる条件：</strong>${esc(report.breakConditions)}</p>` : ''}` || '<p class="report-reader-empty">記載なし</p>', 'reader-scenario')}
      ${readerSection('13. リスク管理', renderParagraphs(report.riskManagement), 'reader-risk')}
      ${readerSection('14. 主な情報源', renderSources(report.sources))}
    </article>`;
  }

  function summaryList(items = [], limit = 4) {
    const rows = asArray(items).filter(Boolean).slice(0, limit);
    return rows.length ? `<ul>${rows.map(item => `<li>${esc(itemText(item))}</li>`).join('')}</ul>` : '<p class="report-summary-empty">記載なし</p>';
  }

  function summaryPanel(title, content, modifier = '') {
    return `<section class="report-summary-panel ${modifier}"><h4>${esc(title)}</h4>${content}</section>`;
  }

  function marketSummary(report) {
    const selectedMarket = marketFilter?.value || 'all';
    const markets = asArray(report.markets).filter(market => selectedMarket === 'all' || market.name === selectedMarket);
    if (!markets.length) return '<p class="report-summary-empty">該当市場の記載がありません。</p>';
    return markets.map(market => `<article class="report-summary-market">
      <div class="report-summary-market-head"><strong>${esc(market.name || '市場')}</strong><span class="direction ${directionClass(market.direction)}">${esc(market.direction || '中立')}</span></div>
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
    const scenario = [report.mainScenario ? `<p><b>メイン：</b>${esc(report.mainScenario)}</p>` : '',report.alternativeScenario ? `<p><b>代替：</b>${esc(report.alternativeScenario)}</p>` : '',report.breakConditions ? `<p><b>崩れる条件：</b>${esc(report.breakConditions)}</p>` : ''].join('') || '<p class="report-summary-empty">記載なし</p>';
    latest.innerHTML = `<article class="report-summary-dashboard">
      <header class="report-summary-head"><div><span class="report-summary-kicker">30-SECOND MARKET VIEW</span><h3>${esc(title)}</h3></div><span class="time-badge ${timeClass(report.time)}">${esc(report.time || '時刻不明')}</span></header>
      <section class="report-summary-theme"><span>今日の相場テーマ</span><strong>${esc(report.theme || '記載なし')}</strong></section>
      <div class="report-summary-grid">
        ${summaryPanel('今日の主導市場', `<p>${esc(report.leadingMarket || '記載なし')}</p>`, 'report-summary-panel--leader')}
        ${summaryPanel('前回からの変化', summaryList(report.changes,3))}
        ${summaryPanel('材料と値動きの整合性', summaryList(report.consistency,3))}
        ${summaryPanel('ポジションの偏り', summaryList(report.positioning,3))}
        ${summaryPanel('重要ニュース', summaryList(report.news,4), 'report-summary-panel--wide')}
        ${summaryPanel('クロスアセット資金フロー', summaryList(report.crossAssetFlow,4), 'report-summary-panel--wide')}
        ${summaryPanel('セクター・業種動向', summaryList(report.sectors,4))}
        ${summaryPanel('今後のイベント', summaryList(report.events,4))}
        ${summaryPanel('次の時間帯への引き継ぎ', summaryList(report.handover,4), 'report-summary-panel--wide')}
        ${summaryPanel('全体シナリオ', scenario, 'report-summary-panel--wide')}
        ${summaryPanel('リスク管理', summaryList(report.riskManagement,4), 'report-summary-panel--wide')}
      </div>
      <section class="report-summary-markets"><h4>6市場の売買判断</h4><div class="report-summary-market-grid">${marketSummary(report)}</div></section>
    </article>`;
  }

  function renderActiveView() {
    const report = currentReport();
    if (!report) return;
    activeView === 'summary' ? renderSummary(report) : renderFullText(report);
    tabs.forEach(tab => { const selected = tab.dataset.reportView === activeView; tab.classList.toggle('is-active', selected); tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1; });
  }

  tabs.forEach(tab => tab.addEventListener('click', () => { activeView = tab.dataset.reportView; renderActiveView(); }));
  tabs.forEach((tab, index) => tab.addEventListener('keydown', event => { if (!['ArrowLeft','ArrowRight'].includes(event.key)) return; event.preventDefault(); const nextIndex = event.key === 'ArrowRight' ? (index + 1) % tabs.length : (index - 1 + tabs.length) % tabs.length; tabs[nextIndex].focus(); tabs[nextIndex].click(); }));
  if (typeof openReport === 'function') { const originalOpenReport = openReport; openReport = function(date,time){ originalOpenReport(date,time); activeView='summary'; renderActiveView(); }; }
  marketFilter?.addEventListener('change', () => { if (currentReport()) renderActiveView(); });
  const waitForInitialReport = setInterval(() => { if (!currentReport()) return; clearInterval(waitForInitialReport); renderActiveView(); },100);
  setTimeout(() => clearInterval(waitForInitialReport),10000);
})();