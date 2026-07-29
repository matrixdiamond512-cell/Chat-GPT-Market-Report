(() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
  const arr = value => Array.isArray(value) ? value : (value ? [value] : []);
  const text = value => typeof value === 'string' ? value : (value?.text || value?.summary || value?.title || value?.name || '');
  const dir = value => {
    const s = String(value || '').toLowerCase();
    if (/上昇|強気|買い|反発|up|bull|プラス/.test(s)) return 'up';
    if (/下落|弱気|売り|反落|down|bear|マイナス/.test(s)) return 'down';
    return 'neutral';
  };
  const marketGroup = name => {
    if (/日経|株|NASDAQ|S&P|Dow|Russell/.test(name)) return '株式';
    if (/JPY|EUR|USD|ドル|ユーロ|円/.test(name)) return '為替';
    if (/金|原油|WTI|銀|プラチナ/.test(name)) return '商品';
    if (/BTC|暗号|仮想/.test(name)) return '暗号資産';
    return 'その他';
  };
  const impactMarkets = source => {
    const s = String(source || '');
    const out = [];
    if (/米金利|米国債|FRB|FOMC|CPI|PCE|雇用/.test(s)) out.push('米金利','USD/JPY','米国株','金');
    if (/日銀|円|日本国債|財政/.test(s)) out.push('USD/JPY','日経225先物');
    if (/半導体|AI|NVIDIA|NASDAQ/.test(s)) out.push('米国株','日経225先物');
    if (/原油|OPEC|中東|ホルムズ/.test(s)) out.push('原油','金','USD/JPY');
    if (/BTC|ビットコイン|暗号資産|ETF/.test(s)) out.push('BTCUSD');
    if (/ECB|ユーロ/.test(s)) out.push('EUR/USD');
    return [...new Set(out)].slice(0,4);
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
    const rows = [['米国10年',us,6],['日本10年',jp,3],['日米差',spread,6]].map(([label,value,max]) => {
      const width = value == null ? 0 : Math.min(100,Math.max(3,value/max*100));
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

  function renderNews(report) {
    const target = document.getElementById('dashboardNews');
    if (!target) return;
    const rows = arr(report.news).slice(0,6).map((item,index) => {
      const headline = text(item);
      const effect = item?.impact || item?.marketImpact || item?.effect || '';
      const markets = arr(item?.markets || item?.affectedMarkets).length ? arr(item.markets || item.affectedMarkets) : impactMarkets(`${headline} ${effect}`);
      return `<article class="news-impact-row"><span class="news-rank">${index+1}</span><div><strong>${esc(headline || 'ニュース記載なし')}</strong><p>${esc(effect || '市場への影響は本文の材料・値動きから確認してください。')}</p>${markets.length ? `<div class="impact-tags">${markets.map(m=>`<span>${esc(m)}</span>`).join('')}</div>` : ''}</div></article>`;
    });
    target.innerHTML = rows.length ? rows.join('') : '<p>記載なし</p>';
  }

  function renderFlow(report) {
    const target = document.getElementById('dashboardFlow');
    if (!target) return;
    const rows = arr(report.crossAssetFlow).slice(0,6).map((item,index) => {
      const raw = text(item);
      const parts = raw.split(/(?:→|⇒|から|へ)/).map(x=>x.trim()).filter(Boolean);
      const from = item?.from || parts[0] || '流出元不明';
      const to = item?.to || parts[1] || '流入先不明';
      const reason = item?.reason || item?.note || (parts.length > 2 ? parts.slice(2).join(' ') : raw);
      return `<div class="flow-row"><span class="flow-node flow-from">${esc(from)}</span><span class="flow-arrow">→</span><span class="flow-node flow-to">${esc(to)}</span><p>${esc(reason && reason !== raw ? reason : raw)}</p></div>`;
    });
    target.innerHTML = rows.length ? `<div class="capital-flow-map">${rows.join('')}</div>` : '<p>記載なし</p>';
  }

  function normalizeRows(source) {
    return arr(source).map(item => typeof item === 'string' ? {name:item} : item).filter(Boolean);
  }
  function sectorHtml(rows) {
    return rows.slice(0,8).map(item => {
      const name = item.name || item.sector || item.industry || item.title || text(item);
      const change = item.change || item.performance || item.rate || item.value || '';
      const reason = item.reason || item.material || item.note || item.comment || '';
      const state = dir(`${change} ${reason}`);
      return `<div class="sector-row ${state}"><div><strong>${esc(name)}</strong>${reason ? `<p>${esc(reason)}</p>` : ''}</div><span>${esc(change || (state==='up'?'買い優勢':state==='down'?'売り優勢':'中立'))}</span></div>`;
    }).join('');
  }
  function renderSectors(report) {
    const us = document.getElementById('dashboardUsSectors');
    const jp = document.getElementById('dashboardJapanSectors');
    const all = normalizeRows(report.sectors);
    const usRows = normalizeRows(report.usSectors || report.usSectorsPerformance || all.filter(x=>/米|US|S&P|NASDAQ/i.test(JSON.stringify(x))));
    const jpRows = normalizeRows(report.japanSectors || report.tokyoSectors || all.filter(x=>/東証|東京|日本|日経/i.test(JSON.stringify(x))));
    if (us) us.innerHTML = sectorHtml(usRows.length ? usRows : all.slice(0,6)) || '<p class="market-depth-empty">レポートに米国セクター情報がありません。</p>';
    if (jp) jp.innerHTML = sectorHtml(jpRows.length ? jpRows : all.slice(0,6)) || '<p class="market-depth-empty">レポートに東京市場セクター情報がありません。</p>';
  }

  function rankingHtml(rows, positive=true) {
    return rows.slice(0,5).map((item,index) => {
      const name = item.name || item.stock || item.company || item.title || text(item);
      const value = item.contribution || item.change || item.performance || item.rate || '';
      const reason = item.reason || item.material || item.note || '';
      return `<div class="contribution-row ${positive?'positive':'negative'}"><span>${index+1}</span><div><strong>${esc(name)}</strong>${reason?`<p>${esc(reason)}</p>`:''}</div><b>${esc(value)}</b></div>`;
    }).join('');
  }
  function renderContributors(report) {
    const target = document.getElementById('dashboardNikkeiContributors');
    if (!target) return;
    const positive = normalizeRows(report.nikkeiPositiveContributors || report.positiveContributors || report.nikkeiContributors?.positive);
    const negative = normalizeRows(report.nikkeiNegativeContributors || report.negativeContributors || report.nikkeiContributors?.negative);
    target.innerHTML = `<div class="dual-ranking"><section><h4>プラス寄与</h4>${rankingHtml(positive,true) || '<p class="market-depth-empty">記載なし</p>'}</section><section><h4>マイナス寄与</h4>${rankingHtml(negative,false) || '<p class="market-depth-empty">記載なし</p>'}</section></div>`;
  }
  function renderMovers(report) {
    const target = document.getElementById('dashboardUsMovers');
    if (!target) return;
    const gainers = normalizeRows(report.usTopGainers || report.usGainers || report.usMovers?.gainers);
    const losers = normalizeRows(report.usTopLosers || report.usLosers || report.usMovers?.losers);
    target.innerHTML = `<div class="dual-ranking"><section><h4>大幅上昇</h4>${rankingHtml(gainers,true) || '<p class="market-depth-empty">記載なし</p>'}</section><section><h4>大幅下落</h4>${rankingHtml(losers,false) || '<p class="market-depth-empty">記載なし</p>'}</section></div>`;
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
    scenarios.innerHTML = `<article class="scenario-card main"><h3>メインシナリオ</h3><p>${esc(report.mainScenario || '記載なし')}</p></article><article class="scenario-card alt"><h3>代替シナリオ</h3><p>${esc(report.alternativeScenario || '記載なし')}</p></article><article class="scenario-card risk"><h3>崩れる条件・リスク</h3><p>${esc(report.breakConditions || arr(report.riskManagement).map(text).join(' ') || '記載なし')}</p></article>`;
    markets.after(scenarios);
  }

  async function init() {
    try {
      const response = await fetch(`reports.json?overview=${Date.now()}`, {cache:'no-store'});
      if (!response.ok) return;
      const reports = await response.json();
      if (!Array.isArray(reports) || !reports.length) return;
      reports.sort((a,b) => `${b.date || ''} ${b.time || ''}`.localeCompare(`${a.date || ''} ${a.time || ''}`));
      const report = reports[0];
      injectPanels(report); renderNews(report); renderFlow(report); renderSectors(report); renderContributors(report); renderMovers(report);
    } catch (_) {}
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true}); else init();
})();