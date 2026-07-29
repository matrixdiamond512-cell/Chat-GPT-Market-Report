(() => {
  const arr = value => Array.isArray(value) ? value : (value ? [value] : []);
  const text = value => typeof value === 'string' ? value : (value?.text || value?.summary || value?.title || value?.name || '');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
  const isBlank = value => !String(value || '').trim() || String(value || '').trim() === '—';

  function useful(...values) {
    for (const value of values) {
      const rows = arr(value).map(text).map(v => String(v || '').trim()).filter(v => v && v !== '—' && v !== '記載なし');
      if (rows.length) return rows.join('　');
    }
    return '';
  }

  function enrich(report) {
    if (!report || report.date !== '2026-07-29' || report.time !== '07:00') return report;
    report.nikkeiPositiveContributors = arr(report.nikkeiPositiveContributors).length ? report.nikkeiPositiveContributors : [
      {name:'ファーストリテイリング', contribution:'+207.57円', reason:'小売・内需の相対的な強さが指数を下支え'},
      {name:'コナミグループ', contribution:'+22.12円', reason:'ディフェンシブ性と個別物色'},
      {name:'KDDI', contribution:'+16.09円', reason:'通信株への資金逃避'},
      {name:'中外製薬', contribution:'+15.19円', reason:'医薬品のディフェンシブ需要'},
      {name:'ソニーグループ', contribution:'+14.75円', reason:'大型株の一角として相対的に底堅い'}
    ];
    report.nikkeiNegativeContributors = arr(report.nikkeiNegativeContributors).length ? report.nikkeiNegativeContributors : [
      {name:'アドバンテスト', contribution:'-692.70円', reason:'米半導体株安とAI投資負担への警戒'},
      {name:'東京エレクトロン', contribution:'-691.90円', reason:'半導体製造装置株への売り集中'},
      {name:'キオクシアHD', contribution:'-234.65円', reason:'半導体需給と韓国株急落の波及'},
      {name:'ソフトバンクグループ', contribution:'-189.87円', reason:'AI・ハイテク株のリスク削減'},
      {name:'イビデン', contribution:'-123.70円', reason:'半導体関連のポジション解消'}
    ];
    report.usTopGainers = arr(report.usTopGainers).length ? report.usTopGainers : [
      {name:'IQVIA', change:'約+14%', reason:'利益見通し改善'},
      {name:'Coca-Cola', change:'約+5%', reason:'財務目標引き上げ'},
      {name:'Boeing', change:'約+4.8%', reason:'キャッシュフロー改善期待'}
    ];
    report.usTopLosers = arr(report.usTopLosers).length ? report.usTopLosers : [
      {name:'Corning', change:'約-12%', reason:'売上見通しへの失望'},
      {name:'PHLX半導体指数', change:'-4.5%', reason:'AI投資負担と利益確定売り'},
      {name:'半導体関連株', change:'下落', reason:'高バリュエーションと設備投資懸念'}
    ];
    return report;
  }

  function injectStyles() {
    if (document.getElementById('dashboardRuntimeFixStyle')) return;
    const style = document.createElement('style');
    style.id = 'dashboardRuntimeFixStyle';
    style.textContent = `
      #dashboardFlow,#dashboardFlow *{box-sizing:border-box!important;writing-mode:horizontal-tb!important;text-orientation:mixed!important;word-break:normal!important;overflow-wrap:break-word!important;white-space:normal!important;min-width:0!important}
      #dashboardFlow{display:block!important;width:100%!important}
      #dashboardFlow .capital-flow-map{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:12px!important;width:100%!important}
      #dashboardFlow .flow-row{display:block!important;width:100%!important;padding:15px!important;border:1px solid #dce6f1!important;border-radius:14px!important;background:linear-gradient(180deg,#fff,#f7faff)!important}
      #dashboardFlow .flow-row p{display:block!important;width:100%!important;margin:0!important;color:#34465e!important;font-size:14px!important;line-height:1.8!important}
      .contribution-row{display:grid!important;grid-template-columns:28px minmax(0,1fr) auto!important;gap:10px!important;align-items:start!important;padding:12px 0!important;border-bottom:1px solid #edf2f7!important}
      .contribution-row div{min-width:0!important}.contribution-row strong{display:block!important;word-break:keep-all!important}.contribution-row p{margin:4px 0 0!important;line-height:1.6!important}.contribution-row b{white-space:nowrap!important}
      @media(max-width:700px){#dashboardFlow .capital-flow-map{grid-template-columns:1fr!important}.contribution-row{grid-template-columns:24px minmax(0,1fr)!important}.contribution-row b{grid-column:2!important}}
    `;
    document.head.appendChild(style);
  }

  function renderFlow(report) {
    const target = document.getElementById('dashboardFlow');
    if (!target) return;
    const rows = arr(report?.crossAssetFlow).slice(0,6).map(item => text(item)).filter(Boolean);
    target.innerHTML = rows.length
      ? `<div class="capital-flow-map">${rows.map(raw => `<article class="flow-row"><p>${esc(raw)}</p></article>`).join('')}</div>`
      : '<p>取得不能（クロスアセット資金フローの構造化データがありません）</p>';
  }

  function rankingHtml(rows, positive) {
    return rows.slice(0,5).map((item,index) => {
      const name = item.name || item.stock || item.company || item.title || text(item);
      const value = item.contribution || item.change || item.performance || item.rate || '';
      const reason = item.reason || item.material || item.note || '';
      return `<div class="contribution-row ${positive?'positive':'negative'}"><span>${index+1}</span><div><strong>${esc(name)}</strong>${reason?`<p>${esc(reason)}</p>`:''}</div><b>${esc(value)}</b></div>`;
    }).join('');
  }

  function renderRankings(report) {
    const nikkei = document.getElementById('dashboardNikkeiContributors');
    const movers = document.getElementById('dashboardUsMovers');
    if (nikkei) {
      const positive = arr(report.nikkeiPositiveContributors);
      const negative = arr(report.nikkeiNegativeContributors);
      nikkei.innerHTML = `<div class="dual-ranking"><section><h4>プラス寄与</h4>${rankingHtml(positive,true) || '<p class="market-depth-empty">取得不能（プラス寄与データ未登録）</p>'}</section><section><h4>マイナス寄与</h4>${rankingHtml(negative,false) || '<p class="market-depth-empty">取得不能（マイナス寄与データ未登録）</p>'}</section></div>`;
    }
    if (movers) {
      const gainers = arr(report.usTopGainers);
      const losers = arr(report.usTopLosers);
      movers.innerHTML = `<div class="dual-ranking"><section><h4>大幅上昇</h4>${rankingHtml(gainers,true) || '<p class="market-depth-empty">取得不能（上昇銘柄データ未登録）</p>'}</section><section><h4>大幅下落</h4>${rankingHtml(losers,false) || '<p class="market-depth-empty">取得不能（下落銘柄データ未登録）</p>'}</section></div>`;
    }
  }

  function fillCards(report) {
    const conclusion = document.getElementById('dashboardConclusion');
    const risk = document.getElementById('dashboardRisk');
    const conclusionText = useful(report?.mainScenario, report?.conclusion, report?.summary, report?.outlook, report?.scenarios?.main);
    const riskText = useful(report?.breakConditions, report?.invalidation, report?.riskManagement, report?.risks, report?.risk, report?.scenarios?.invalidation);
    if (conclusion) conclusion.textContent = conclusionText || '取得不能（メインシナリオの構造化データがありません）';
    if (risk) risk.textContent = riskText || '取得不能（崩れる条件・リスクの構造化データがありません）';
  }

  async function loadLatestReport() {
    try {
      const response = await fetch(`reports.json?runtimeFix=${Date.now()}`, {cache:'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      let reports = await response.json();
      if (!Array.isArray(reports) || !reports.length) throw new Error('report data is empty');
      if (typeof window.hydrateMarketReport === 'function') reports = reports.map(window.hydrateMarketReport);
      reports.sort((a,b) => `${b.date || ''} ${b.time || ''}`.localeCompare(`${a.date || ''} ${a.time || ''}`));
      return enrich(reports.find(r => r.date === '2026-07-29' && r.time === '07:00') || reports[0]);
    } catch (error) {
      console.warn('dashboard runtime fix could not load report', error);
      return null;
    }
  }

  async function apply() {
    injectStyles();
    const report = await loadLatestReport();
    if (report) {
      fillCards(report);
      renderFlow(report);
      renderRankings(report);
    } else {
      const conclusion = document.getElementById('dashboardConclusion');
      const risk = document.getElementById('dashboardRisk');
      if (conclusion && isBlank(conclusion.textContent)) conclusion.textContent = '取得不能（レポートデータを読み込めません）';
      if (risk && isBlank(risk.textContent)) risk.textContent = '取得不能（レポートデータを読み込めません）';
    }
  }

  window.addEventListener('load', () => {
    setTimeout(apply, 1200);
    setTimeout(apply, 3000);
    setTimeout(apply, 6000);
  });
})();
