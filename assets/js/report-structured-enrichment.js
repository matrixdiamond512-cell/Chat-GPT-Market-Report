/* Enrich sparse report.html output from canonical reports/YYYY-MM-DD_HH-MM.json.
 * Created 2026-08-18 JST.
 * The index reports.json remains the navigation source; the canonical per-slot file
 * is used to restore detailed sections when the index/fullText is abbreviated.
 */
(() => {
  const app = document.getElementById('app');
  if (!app) return;

  const esc = (value = '') => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  const clean = (value = '') => String(value ?? '').replace(/\r/g, '').trim();
  const list = value => Array.isArray(value) ? value.map(clean).filter(Boolean) : [];
  const hasText = value => clean(value).length > 0;

  function currentKey() {
    const params = new URLSearchParams(location.search);
    const date = params.get('date');
    const time = params.get('time');
    return date && time ? { date, time, key: `${date}_${time.replace(':', '-')}` } : null;
  }

  function richValue(value) {
    if (Array.isArray(value)) {
      const items = list(value);
      return items.length ? `<ul>${items.map(item => `<li>${esc(item)}</li>`).join('')}</ul>` : '';
    }
    const text = clean(value);
    if (!text) return '';
    return text.split(/\n+/).map(line => `<p>${esc(line)}</p>`).join('');
  }

  function section(title, value, className = '') {
    const body = richValue(value);
    if (!body) return '';
    return `<section class="section sop-section structured-section ${className}" data-sop-title="${esc(title)}"><h2>${esc(title)}</h2>${body}</section>`;
  }

  function marketDetails(markets) {
    if (!Array.isArray(markets) || !markets.length) return '';
    const cards = markets.map(market => {
      if (!market || !hasText(market.name)) return '';
      const rows = [
        ['現在値・確認値', market.price],
        ['方向性', market.direction],
        ['見通し', market.outlook],
        ['材料', market.material],
        ['需給・ポジション', market.positioning],
        ['注目水準', market.levels],
        ['メインシナリオ', market.mainScenario],
        ['代替シナリオ', market.alternativeScenario],
        ['崩れる条件', market.breakCondition],
        ['リスク', market.risk]
      ].filter(([, value]) => hasText(value));
      if (!rows.length) return '';
      return `<article class="market-outlook-card"><h3>${esc(market.name)}</h3><dl>${rows.map(([label, value]) => `<div><dt>${esc(label)}</dt><dd>${esc(clean(value))}</dd></div>`).join('')}</dl></article>`;
    }).filter(Boolean).join('');
    if (!cards) return '';
    return `<section class="section sop-section structured-section" data-sop-title="個別市場見通し"><h2>個別市場見通し</h2><div class="market-outlook-grid">${cards}</div></section>`;
  }

  function existingTitles(article) {
    return new Set([...article.querySelectorAll('.sop-section')]
      .map(node => clean(node.dataset.sopTitle || node.querySelector('h2')?.textContent))
      .filter(Boolean));
  }

  function canonicalSections(report, titles) {
    const blocks = [];
    const add = (title, value, className = '') => {
      if (titles.has(title)) return;
      const html = section(title, value, className);
      if (html) blocks.push({ title, html });
    };

    add('今日の相場テーマ', report.theme, 'theme-section');
    add('前回からの変化', report.changes);
    add('材料と値動きの整合性', report.consistency);
    add('今日の主導市場', report.leadingMarket);
    add('需給・ポジション', report.positioning);
    add('重要ニュース', report.news);
    add('クロスアセット資金フロー', report.crossAssetFlow);
    add('今後の重要イベント', report.events);
    add('次の時間帯への引き継ぎ', report.handover);
    if (!titles.has('個別市場見通し')) {
      const html = marketDetails(report.markets);
      if (html) blocks.push({ title: '個別市場見通し', html });
    }
    add('メインシナリオ', report.mainScenario);
    add('代替シナリオ', report.alternativeScenario);
    add('シナリオが崩れる条件', report.breakConditions);
    add('リスク管理', report.riskManagement);
    return blocks;
  }

  function insertInStandardOrder(article, report) {
    const titles = existingTitles(article);
    const blocks = canonicalSections(report, titles);
    if (!blocks.length) return false;

    const marketSection = [...article.querySelectorAll('.sop-section')]
      .find(node => /主要市場データ|市場データ|前営業日終値|終値一覧|主要価格/.test(node.dataset.sopTitle || node.querySelector('h2')?.textContent || ''));

    const beforeMarket = new Set(['今日の相場テーマ', '前回からの変化']);
    const before = blocks.filter(block => beforeMarket.has(block.title));
    const after = blocks.filter(block => !beforeMarket.has(block.title));

    if (marketSection && before.length) {
      marketSection.insertAdjacentHTML('beforebegin', before.map(block => block.html).join(''));
    } else if (before.length) {
      article.insertAdjacentHTML('afterbegin', before.map(block => block.html).join(''));
    }
    if (after.length) article.insertAdjacentHTML('beforeend', after.map(block => block.html).join(''));
    return true;
  }

  async function enrich() {
    const info = currentKey();
    if (!info) return;
    if (app.dataset.structuredEnrichedKey === info.key) return;

    const article = app.querySelector('.report-body');
    if (!article) return;

    app.dataset.structuredEnrichedKey = info.key;
    try {
      const response = await fetch(`reports/${info.key}.json?ts=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const report = await response.json();
      if (!report || report.date !== info.date || report.time !== info.time) throw new Error('canonical slot mismatch');

      const changed = insertInStandardOrder(article, report);
      if (changed) {
        const status = document.getElementById('reportStatus');
        if (status) status.textContent = '本文詳細を表示中｜canonical report統合表示';
      }
    } catch (error) {
      console.warn('[report-structured-enrichment] canonical detail load failed:', error);
      app.dataset.structuredEnrichedKey = '';
    }
  }

  let scheduled = false;
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      enrich();
    });
  };

  new MutationObserver(schedule).observe(app, { childList: true, subtree: true });
  window.addEventListener('popstate', schedule);
  schedule();
})();
