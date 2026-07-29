(() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const arr = value => Array.isArray(value) ? value : (value ? [value] : []);
  const txt = value => typeof value === 'string' ? value : (value?.text || value?.summary || value?.title || '');
  const dir = value => {
    const s = String(value || '').toLowerCase();
    if (/上昇|強気|買い|反発|up|bull/.test(s)) return 'up';
    if (/下落|弱気|売り|反落|down|bear/.test(s)) return 'down';
    return 'neutral';
  };
  const key = report => `${report.date || ''} ${report.time || ''}`;
  const label = report => `${String(report.date || '').replaceAll('-','/')} ${report.time || ''}`.trim();
  const marketMap = report => new Map(arr(report.markets).map(m => [m.name, dir(m.direction)]));
  const themeTokens = report => {
    const source = [report.theme, report.leadingMarket, ...arr(report.tags), ...arr(report.news).map(txt), ...arr(report.changes).map(txt)].join(' ');
    const dictionary = [
      ['米金利',/米金利|米国債|米10年|FRB|FOMC/],['円',/円安|円高|ドル円|USD\/JPY|日銀/],['AI・半導体',/AI|半導体|NVIDIA|NASDAQ/],['原油',/原油|WTI|OPEC|ホルムズ/],['金',/金|ゴールド|安全資産/],['BTC',/BTC|ビットコイン|暗号資産/],['地政学',/地政学|戦争|制裁|中東|ロシア|ウクライナ/],['景気・物価',/CPI|PCE|雇用|GDP|PMI|景気|インフレ/]
    ];
    return dictionary.filter(([,re]) => re.test(source)).map(([name]) => name);
  };
  function findPrior(reports, current, days) {
    const base = new Date(`${current.date}T${current.time || '00:00'}:00+09:00`).getTime();
    const target = base - days * 86400000;
    return reports.slice(1).reduce((best, item) => {
      const t = new Date(`${item.date}T${item.time || '00:00'}:00+09:00`).getTime();
      const d = Math.abs(t - target);
      return !best || d < best.d ? {item,d} : best;
    }, null)?.item || null;
  }
  function compareMarkets(current, prior) {
    if (!prior) return [];
    const a = marketMap(current), b = marketMap(prior);
    const names = [...new Set([...a.keys(), ...b.keys()])];
    return names.map(name => ({name, before:b.get(name) || 'neutral', now:a.get(name) || 'neutral'})).filter(x => x.before !== x.now).slice(0,6);
  }
  const stateLabel = state => state === 'up' ? '強気' : state === 'down' ? '弱気' : '中立';
  function comparisonCard(title, current, prior) {
    if (!prior) return `<article class="comparison-card"><span class="dashboard-label">${esc(title)}</span><p class="comparison-empty">比較対象がありません。</p></article>`;
    const oldThemes = themeTokens(prior), newThemes = themeTokens(current);
    const added = newThemes.filter(x => !oldThemes.includes(x));
    const removed = oldThemes.filter(x => !newThemes.includes(x));
    const changed = compareMarkets(current, prior);
    return `<article class="comparison-card">
      <div class="comparison-head"><div><span class="dashboard-label">${esc(title)}</span><h3>${esc(label(prior))} → ${esc(label(current))}</h3></div><span class="comparison-badge">比較</span></div>
      <div class="comparison-columns">
        <section><h4>テーマの変化</h4><p><b>追加：</b>${esc(added.join('・') || '大きな追加なし')}</p><p><b>後退：</b>${esc(removed.join('・') || '大きな後退なし')}</p></section>
        <section><h4>主導市場</h4><p><b>前：</b>${esc(prior.leadingMarket || '記載なし')}</p><p><b>現在：</b>${esc(current.leadingMarket || '記載なし')}</p></section>
      </div>
      <div class="direction-changes">${changed.length ? changed.map(x => `<div><strong>${esc(x.name)}</strong><span class="state-${x.before}">${stateLabel(x.before)}</span><i>→</i><span class="state-${x.now}">${stateLabel(x.now)}</span></div>`).join('') : '<p>6市場の方向感に大きな変化はありません。</p>'}</div>
    </article>`;
  }
  async function init() {
    try {
      const response = await fetch(`reports.json?compare=${Date.now()}`, {cache:'no-store'});
      if (!response.ok) return;
      const reports = await response.json();
      if (!Array.isArray(reports) || reports.length < 2) return;
      reports.sort((a,b) => key(b).localeCompare(key(a)));
      const current = reports[0];
      const previous = reports[1];
      const week = findPrior(reports,current,7);
      const section = document.createElement('section');
      section.id = 'marketComparison';
      section.className = 'market-comparison-section';
      section.innerHTML = `<div class="section-heading"><div><p class="section-kicker">REGIME CHANGE</p><h2>相場テーマの変化</h2></div><p>直前レポートと約1週間前を比較</p></div><div class="comparison-grid">${comparisonCard('前回からの変化',current,previous)}${comparisonCard('1週間前との比較',current,week)}</div>`;
      const overview = document.getElementById('dashboardOverviewGrid');
      const markets = document.getElementById('dashboardMarkets');
      (overview || markets)?.insertAdjacentElement('afterend',section);
    } catch (_) {}
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',init,{once:true}); else init();
})();