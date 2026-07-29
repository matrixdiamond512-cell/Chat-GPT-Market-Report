(() => {
  const asArray = value => Array.isArray(value) ? value : (value ? [value] : []);
  const textOf = value => typeof value === 'string' ? value : (value?.text || value?.summary || value?.title || '');
  const useful = value => {
    const text = String(value || '').trim();
    return text && text !== '—' && text !== '記載なし';
  };
  const firstText = (...values) => {
    for (const value of values) {
      const rows = asArray(value).map(textOf).map(v => String(v || '').trim()).filter(useful);
      if (rows.length) return rows.join('　');
    }
    return '';
  };

  function setText(id, value, fallback) {
    const node = document.getElementById(id);
    if (!node) return;
    node.textContent = useful(value) ? value : fallback;
  }

  function renderFlow(report) {
    const host = document.getElementById('dashboardFlow');
    if (!host) return;
    const rows = asArray(report.crossAssetFlow).map(textOf).map(v => String(v || '').trim()).filter(useful);
    const items = rows.length ? rows : ['取得不能（クロスアセット資金フローの構造化データがありません）'];
    host.className = 'dashboard-flow-cards';
    host.innerHTML = items.map((text, index) => `
      <article class="dashboard-flow-card flow-${index + 1}">
        <span class="dashboard-flow-arrow" aria-hidden="true">→</span>
        <p>${text.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]))}</p>
      </article>`).join('');
  }

  function applyReport(report) {
    if (!report) return;
    const conclusion = firstText(report.mainScenario, report.conclusion, report.summary, report.outlook, report.scenarios?.main);
    const risk = firstText(report.breakConditions, report.invalidation, report.riskManagement, report.risks, report.risk, report.scenarios?.invalidation);
    setText('dashboardConclusion', conclusion, '取得不能（メインシナリオがレポートに登録されていません）');
    setText('dashboardRisk', risk, '取得不能（崩れる条件・リスクがレポートに登録されていません）');
    renderFlow(report);
  }

  async function loadLatest() {
    try {
      const response = await fetch(`reports.json?finalFix=${Date.now()}`, {cache: 'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const reports = await response.json();
      if (!Array.isArray(reports) || !reports.length) throw new Error('No reports');
      reports.sort((a, b) => `${b.date || ''} ${b.time || ''}`.localeCompare(`${a.date || ''} ${a.time || ''}`));
      const report = reports.find(r => r.date === '2026-07-29' && r.time === '07:00') || reports[0];
      applyReport(report);
      setTimeout(() => applyReport(report), 500);
      setTimeout(() => applyReport(report), 1500);
    } catch (error) {
      setText('dashboardConclusion', '', '取得不能（レポートデータの読み込みに失敗しました）');
      setText('dashboardRisk', '', '取得不能（レポートデータの読み込みに失敗しました）');
      const host = document.getElementById('dashboardFlow');
      if (host) host.innerHTML = '<article class="dashboard-flow-card"><p>取得不能（クロスアセット資金フローの読み込みに失敗しました）</p></article>';
      console.warn('dashboard-final-fix failed', error);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', loadLatest, {once: true});
  else loadLatest();
})();
