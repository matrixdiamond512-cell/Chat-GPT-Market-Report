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

  function injectStyles() {
    if (document.getElementById('dashboardRuntimeFixStyle')) return;
    const style = document.createElement('style');
    style.id = 'dashboardRuntimeFixStyle';
    style.textContent = `
      #dashboardFlow,
      #dashboardFlow * { box-sizing:border-box!important; writing-mode:horizontal-tb!important; text-orientation:mixed!important; word-break:normal!important; overflow-wrap:anywhere!important; white-space:normal!important; min-width:0!important; }
      #dashboardFlow { display:block!important; width:100%!important; }
      #dashboardFlow .capital-flow-map { display:grid!important; grid-template-columns:repeat(2,minmax(0,1fr))!important; gap:12px!important; width:100%!important; }
      #dashboardFlow .flow-row { display:grid!important; grid-template-columns:minmax(0,1fr) auto minmax(0,1fr)!important; gap:10px!important; align-items:center!important; width:100%!important; padding:15px!important; border:1px solid #dce6f1!important; border-radius:14px!important; background:linear-gradient(180deg,#fff,#f7faff)!important; }
      #dashboardFlow .flow-node { display:block!important; width:auto!important; max-width:100%!important; padding:10px 12px!important; border-radius:10px!important; font-size:14px!important; line-height:1.7!important; }
      #dashboardFlow .flow-from { background:#fff0f2!important; color:#9f2d42!important; }
      #dashboardFlow .flow-to { background:#eaf7f0!important; color:#17784c!important; }
      #dashboardFlow .flow-arrow { display:block!important; color:#2f6fd6!important; font-size:22px!important; font-weight:900!important; text-align:center!important; }
      #dashboardFlow .flow-row p { grid-column:1/-1!important; display:block!important; width:100%!important; margin:6px 0 0!important; padding:10px 12px!important; border-radius:9px!important; background:#f5f8fc!important; color:#34465e!important; font-size:14px!important; line-height:1.8!important; }
      @media(max-width:700px){
        #dashboardFlow .capital-flow-map { grid-template-columns:minmax(0,1fr)!important; }
        #dashboardFlow .flow-row { grid-template-columns:minmax(0,1fr)!important; padding:14px!important; }
        #dashboardFlow .flow-arrow { transform:rotate(90deg); line-height:1; }
        #dashboardFlow .flow-row p { grid-column:1!important; }
      }
    `;
    document.head.appendChild(style);
  }

  function renderFlow(report) {
    const target = document.getElementById('dashboardFlow');
    if (!target) return;
    const rows = arr(report?.crossAssetFlow).slice(0,6).map(item => {
      const raw = text(item);
      const parts = raw.split(/(?:→|⇒|から|へ)/).map(v => v.trim()).filter(Boolean);
      const from = item?.from || parts[0] || '流出元';
      const to = item?.to || parts[1] || '流入先';
      const reason = item?.reason || item?.note || raw;
      return `<article class="flow-row"><span class="flow-node flow-from">${esc(from)}</span><span class="flow-arrow">→</span><span class="flow-node flow-to">${esc(to)}</span><p>${esc(reason)}</p></article>`;
    });
    target.innerHTML = rows.length
      ? `<div class="capital-flow-map">${rows.join('')}</div>`
      : '<p>取得不能（クロスアセット資金フローの構造化データがありません）</p>';
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
      return reports[0];
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
  });
})();
