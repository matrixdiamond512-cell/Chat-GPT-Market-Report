(() => {
  'use strict';

  const DATA_URL = 'tokyo-usdjpy-volume.json';
  const heatmapEl = document.getElementById('flowHeatmap');
  const summaryEl = document.getElementById('fixingSummary');
  const rangeEl = document.getElementById('rangeFilter');
  const gotoEl = document.getElementById('gotoFilter');

  if (!heatmapEl || !summaryEl || !rangeEl || !gotoEl) return;

  const fmtInt = new Intl.NumberFormat('ja-JP');
  const fmtPct = value => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`;
  const weekdayNames = ['日', '月', '火', '水', '木', '金', '土'];

  let allRows = [];

  const average = rows => rows.length ? rows.reduce((sum, row) => sum + row.volume, 0) / rows.length : null;
  const avgField = (rows, key) => rows.length ? rows.reduce((sum, row) => sum + Number(row[key] || 0), 0) / rows.length : null;

  function visibleRows() {
    let rows = [...allRows];
    const filter = gotoEl.value;
    if (filter === 'goto') rows = rows.filter(row => row.gotoBi === true);
    if (filter === 'early') rows = rows.filter(row => row.gotoBi === true && row.gotoBiType === '前倒し');
    if (filter === 'month-end') rows = rows.filter(row => row.gotoBi === true && row.gotoBiType === '月末');
    if (filter === 'unset') rows = rows.filter(row => row.gotoBi == null);
    if (rangeEl.value !== 'all') rows = rows.slice(-Number(rangeEl.value));
    return rows;
  }

  function rowType(row) {
    if (row.gotoBi === false) return '通常日';
    if (row.gotoBi !== true) return '未入力';
    return row.gotoBiType || '通常ゴトー日';
  }

  function heatColor(value, min, max) {
    if (value == null) return 'rgba(238,243,246,.7)';
    const ratio = max === min ? 0.5 : Math.max(0, Math.min(1, (value - min) / (max - min)));
    const alpha = 0.14 + ratio * 0.56;
    return `rgba(47,126,169,${alpha.toFixed(2)})`;
  }

  function renderHeatmap(rows) {
    const types = ['通常日', '通常ゴトー日', '前倒し', '月末', '月初'];
    const days = [1, 2, 3, 4, 5];
    const cells = [];

    types.forEach(type => {
      days.forEach(day => {
        const matched = rows.filter(row => rowType(row) === type && new Date(`${row.date}T00:00:00`).getDay() === day);
        cells.push({ type, day, matched, avg: average(matched) });
      });
    });

    const values = cells.map(cell => cell.avg).filter(value => value != null);
    const min = values.length ? Math.min(...values) : 0;
    const max = values.length ? Math.max(...values) : 1;

    let html = '<div class="heatmap-head"></div>';
    days.forEach(day => { html += `<div class="heatmap-head">${weekdayNames[day]}曜日</div>`; });

    types.forEach(type => {
      html += `<div class="heatmap-label">${type}</div>`;
      days.forEach(day => {
        const cell = cells.find(item => item.type === type && item.day === day);
        const text = cell.avg == null ? '—' : `${fmtInt.format(Math.round(cell.avg))}`;
        html += `<div class="heatmap-cell" style="background:${heatColor(cell.avg, min, max)}"><strong>${text}</strong><small>${cell.matched.length}日</small></div>`;
      });
    });

    heatmapEl.innerHTML = html;
  }

  function scoreDemand(rows) {
    const latest = rows[rows.length - 1];
    if (!latest) return null;

    const weekday = new Date(`${latest.date}T00:00:00`).getDay();
    const sameWeekday = rows.filter(row => new Date(`${row.date}T00:00:00`).getDay() === weekday);
    const sameType = rows.filter(row => rowType(row) === rowType(latest));
    const baseline = average(rows.filter(row => row.gotoBi === false)) || average(rows) || latest.volume;
    const sameWeekdayAvg = average(sameWeekday) || baseline;
    const sameTypeAvg = average(sameType) || baseline;

    const volumeFactor = Math.max(-1, Math.min(1, latest.volume / baseline - 1));
    const weekdayFactor = Math.max(-1, Math.min(1, sameWeekdayAvg / baseline - 1));
    const typeFactor = Math.max(-1, Math.min(1, sameTypeAvg / baseline - 1));
    const changeFactor = Math.max(-1, Math.min(1, latest.dayChange));
    const vs20Factor = Math.max(-1, Math.min(1, latest.vs20d));

    let score = 50;
    score += volumeFactor * 18;
    score += weekdayFactor * 12;
    score += typeFactor * 14;
    score += changeFactor * 9;
    score += vs20Factor * 12;
    if (latest.gotoBi === true) score += 6;
    if (latest.gotoBiType === '前倒し' || latest.gotoBiType === '月末') score += 4;
    score = Math.round(Math.max(0, Math.min(100, score)));

    return { latest, weekday, baseline, sameWeekdayAvg, sameTypeAvg, score };
  }

  function renderSummary(rows) {
    const result = scoreDemand(rows);
    if (!result) {
      summaryEl.innerHTML = '<p class="empty">分析対象データがありません。</p>';
      return;
    }

    const { latest, weekday, baseline, sameWeekdayAvg, sameTypeAvg, score } = result;
    const level = score >= 67 ? 'high' : score >= 45 ? 'mid' : 'low';
    const label = score >= 67 ? '強まりやすい' : score >= 45 ? '中立圏' : '弱まりやすい';
    const surgeRateRows = rows.filter(row => row.vs20d >= 0.15 || row.dayChange >= 0.20);
    const sameCondition = rows.filter(row => rowType(row) === rowType(latest) && new Date(`${row.date}T00:00:00`).getDay() === weekday);
    const sameConditionSurges = sameCondition.filter(row => row.vs20d >= 0.15 || row.dayChange >= 0.20);
    const surgeRate = sameCondition.length ? sameConditionSurges.length / sameCondition.length : null;
    const typePremium = baseline ? sameTypeAvg / baseline - 1 : null;
    const weekdayPremium = baseline ? sameWeekdayAvg / baseline - 1 : null;

    summaryEl.innerHTML = `
      <article class="fixing-card">
        <h4>仲値需要スコア</h4>
        <div class="fixing-score ${level}">${score}/100</div>
        <p>${label}。最新行の出来高、20営業日平均との差、曜日、手入力区分を組み合わせた統計スコアです。</p>
      </article>
      <article class="fixing-card">
        <h4>最新条件</h4>
        <p><strong>${latest.date}・${weekdayNames[weekday]}曜日</strong><br>${rowType(latest)}<br>出来高 ${fmtInt.format(latest.volume)} 百万ドル<br>前日比 ${fmtPct(latest.dayChange)}／20日比 ${fmtPct(latest.vs20d)}</p>
      </article>
      <article class="fixing-card">
        <h4>過去統計との比較</h4>
        <p>同曜日平均：${fmtInt.format(Math.round(sameWeekdayAvg))} 百万ドル（${fmtPct(weekdayPremium)}）<br>同区分平均：${fmtInt.format(Math.round(sameTypeAvg))} 百万ドル（${fmtPct(typePremium)}）<br>同条件の急増率：${surgeRate == null ? 'データ不足' : `${(surgeRate * 100).toFixed(1)}%`}<br>全体急増日：${surgeRateRows.length}日</p>
      </article>`;
  }

  function render() {
    const rows = visibleRows();
    renderHeatmap(rows);
    renderSummary(rows);
  }

  async function init() {
    try {
      const response = await fetch(`${DATA_URL}?advanced=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      allRows = data
        .filter(row => row && row.date && Number.isFinite(Number(row.volume)))
        .map(row => ({
          ...row,
          volume: Number(row.volume),
          dayChange: Number(row.dayChange || 0),
          vs20d: Number(row.vs20d || 0)
        }))
        .sort((a, b) => a.date.localeCompare(b.date));
      render();
    } catch (error) {
      console.error(error);
      heatmapEl.innerHTML = '<p class="empty">ヒートマップを生成できませんでした。</p>';
      summaryEl.innerHTML = '<p class="empty">仲値需要サマリーを生成できませんでした。</p>';
    }
  }

  rangeEl.addEventListener('change', render);
  gotoEl.addEventListener('change', render);
  init();
})();
