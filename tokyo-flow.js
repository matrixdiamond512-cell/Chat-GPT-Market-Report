(() => {
  'use strict';

  const DATA_URL = 'tokyo-usdjpy-volume.json';
  const state = { all: [], filtered: [] };

  const els = {
    status: document.getElementById('flowStatus'),
    range: document.getElementById('rangeFilter'),
    goto: document.getElementById('gotoFilter'),
    latestVolume: document.getElementById('latestVolume'),
    latestDate: document.getElementById('latestDate'),
    latestDayChange: document.getElementById('latestDayChange'),
    latestVs20d: document.getElementById('latestVs20d'),
    gotoCount: document.getElementById('gotoCount'),
    gotoAverage: document.getElementById('gotoAverage'),
    gotoAverageCount: document.getElementById('gotoAverageCount'),
    normalAverage: document.getElementById('normalAverage'),
    normalAverageCount: document.getElementById('normalAverageCount'),
    gotoPremium: document.getElementById('gotoPremium'),
    weekdayStats: document.getElementById('weekdayStats'),
    typeStats: document.getElementById('typeStats'),
    surgeList: document.getElementById('surgeList'),
    tableBody: document.getElementById('flowTableBody'),
    canvas: document.getElementById('flowChart')
  };

  const fmtInt = new Intl.NumberFormat('ja-JP');
  const fmtPct = value => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`;
  const fmtDate = value => {
    const d = new Date(`${value}T00:00:00`);
    return new Intl.DateTimeFormat('ja-JP', { month: 'numeric', day: 'numeric', weekday: 'short' }).format(d);
  };
  const average = rows => rows.length ? rows.reduce((sum, row) => sum + row.volume, 0) / rows.length : null;

  function badgeClass(type) {
    if (type === '前倒し') return 'early';
    if (type === '月末') return 'month-end';
    if (type === '月初') return 'month-start';
    if (type) return 'normal';
    return 'unknown';
  }

  function badgeLabel(row) {
    if (row.gotoBi === true) return row.gotoBiType || '通常ゴトー日';
    if (row.gotoBi === false) return '対象外';
    return '未入力';
  }

  function applyFilters() {
    let rows = [...state.all];
    const range = els.range.value;
    const filter = els.goto.value;

    if (filter === 'goto') rows = rows.filter(r => r.gotoBi === true);
    if (filter === 'early') rows = rows.filter(r => r.gotoBi === true && r.gotoBiType === '前倒し');
    if (filter === 'month-end') rows = rows.filter(r => r.gotoBi === true && r.gotoBiType === '月末');
    if (filter === 'unset') rows = rows.filter(r => r.gotoBi == null);
    if (range !== 'all') rows = rows.slice(-Number(range));

    state.filtered = rows;
    renderKpis();
    renderStatistics();
    renderTable();
    drawChart();
    els.status.textContent = `${rows.length}営業日を表示`;
  }

  function renderKpis() {
    const rows = state.filtered;
    const latest = rows[rows.length - 1];
    if (!latest) {
      els.latestVolume.textContent = '—';
      els.latestDate.textContent = '該当データなし';
      els.latestDayChange.textContent = '—';
      els.latestVs20d.textContent = '—';
      els.gotoCount.textContent = '0';
      return;
    }
    els.latestVolume.textContent = `${fmtInt.format(latest.volume)} 百万ドル`;
    els.latestDate.textContent = fmtDate(latest.date);
    els.latestDayChange.textContent = fmtPct(latest.dayChange);
    els.latestVs20d.textContent = fmtPct(latest.vs20d);
    els.gotoCount.textContent = String(rows.filter(r => r.gotoBi === true).length);
  }

  function renderStatistics() {
    const rows = state.filtered;
    const gotoRows = rows.filter(r => r.gotoBi === true);
    const normalRows = rows.filter(r => r.gotoBi === false);
    const gotoAvg = average(gotoRows);
    const normalAvg = average(normalRows);

    els.gotoAverage.textContent = gotoAvg == null ? '—' : `${fmtInt.format(Math.round(gotoAvg))} 百万ドル`;
    els.gotoAverageCount.textContent = `${gotoRows.length}営業日`;
    els.normalAverage.textContent = normalAvg == null ? '—' : `${fmtInt.format(Math.round(normalAvg))} 百万ドル`;
    els.normalAverageCount.textContent = `${normalRows.length}営業日`;
    els.gotoPremium.textContent = gotoAvg == null || normalAvg == null || normalAvg === 0 ? '—' : fmtPct(gotoAvg / normalAvg - 1);

    renderWeekdayStats(rows);
    renderTypeStats(gotoRows);
    renderSurges(rows);
  }

  function renderWeekdayStats(rows) {
    const names = ['日', '月', '火', '水', '木', '金', '土'];
    const groups = [1, 2, 3, 4, 5].map(day => {
      const matches = rows.filter(row => new Date(`${row.date}T00:00:00`).getDay() === day);
      return { day, rows: matches, avg: average(matches) };
    });
    const max = Math.max(1, ...groups.map(group => group.avg || 0));
    els.weekdayStats.innerHTML = groups.map(group => `
      <article class="weekday-card">
        <b>${names[group.day]}曜日</b>
        <div class="weekday-bar"><span style="width:${group.avg == null ? 0 : (group.avg / max * 100).toFixed(1)}%"></span></div>
        <small>${group.avg == null ? 'データなし' : `${fmtInt.format(Math.round(group.avg))} 百万ドル／${group.rows.length}日`}</small>
      </article>`).join('');
  }

  function renderTypeStats(rows) {
    if (!rows.length) {
      els.typeStats.innerHTML = '<p class="empty">手入力されたゴトー日データがありません。</p>';
      return;
    }
    const groups = new Map();
    rows.forEach(row => {
      const key = row.gotoBiType || '通常ゴトー日';
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(row);
    });
    els.typeStats.innerHTML = [...groups.entries()]
      .sort((a, b) => average(b[1]) - average(a[1]))
      .map(([type, group]) => `
        <article class="analysis-card">
          <span>${escapeHtml(type)}</span>
          <strong>${fmtInt.format(Math.round(average(group)))} 百万ドル</strong>
          <small>${group.length}営業日・20日平均との差平均 ${fmtPct(group.reduce((sum, row) => sum + row.vs20d, 0) / group.length)}</small>
        </article>`).join('');
  }

  function renderSurges(rows) {
    const surges = rows
      .filter(row => row.vs20d >= 0.15 || row.dayChange >= 0.20)
      .sort((a, b) => Math.max(b.vs20d, b.dayChange) - Math.max(a.vs20d, a.dayChange))
      .slice(0, 8);
    if (!surges.length) {
      els.surgeList.innerHTML = '<p class="empty">表示期間内に顕著な出来高急増日はありません。</p>';
      return;
    }
    els.surgeList.innerHTML = surges.map(row => `
      <article class="surge-item">
        <span>${escapeHtml(row.date)}</span>
        <span>${row.gotoBi === true ? `<span class="surge-tag">${escapeHtml(badgeLabel(row))}</span> ` : ''}${escapeHtml(row.memo || '出来高増加')}</span>
        <strong>${fmtInt.format(row.volume)} 百万ドル<br><small>前日比 ${fmtPct(row.dayChange)}／20日比 ${fmtPct(row.vs20d)}</small></strong>
      </article>`).join('');
  }

  function renderTable() {
    const rows = [...state.filtered].reverse();
    els.tableBody.innerHTML = rows.map(row => `
      <tr class="${row.gotoBi === true ? 'goto-row' : ''}">
        <td>${escapeHtml(row.date)}</td>
        <td>${fmtInt.format(row.volume)}</td>
        <td>${fmtPct(row.dayChange)}</td>
        <td>${fmtPct(row.vs20d)}</td>
        <td><span class="badge ${badgeClass(row.gotoBiType)}">${escapeHtml(badgeLabel(row))}</span></td>
        <td title="${escapeHtml(row.memo || '')}">${escapeHtml(row.memo || '—')}</td>
      </tr>`).join('');
  }

  function drawChart() {
    const canvas = els.canvas;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(320, Math.floor(rect.width * dpr));
    canvas.height = Math.max(280, Math.floor(rect.height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const width = rect.width;
    const height = rect.height;
    ctx.clearRect(0, 0, width, height);
    const rows = state.filtered;
    if (!rows.length) {
      ctx.fillStyle = '#687789';
      ctx.font = '14px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText('該当するデータがありません', width / 2, height / 2);
      return;
    }

    const pad = { top: 22, right: 52, bottom: 56, left: 58 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;
    const maxVolume = Math.max(...rows.map(r => r.volume)) * 1.12;
    const pctLimit = Math.max(0.5, ...rows.flatMap(r => [Math.abs(r.dayChange), Math.abs(r.vs20d)])) * 1.15;
    const step = plotW / rows.length;
    const barW = Math.max(4, Math.min(22, step * 0.58));

    ctx.font = '11px system-ui';
    ctx.textBaseline = 'middle';
    ctx.strokeStyle = '#e5ebf0';
    ctx.fillStyle = '#687789';
    ctx.lineWidth = 1;

    for (let i = 0; i <= 4; i++) {
      const y = pad.top + plotH * i / 4;
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width - pad.right, y); ctx.stroke();
      ctx.textAlign = 'right';
      ctx.fillText(Math.round(maxVolume * (1 - i / 4)).toLocaleString('ja-JP'), pad.left - 8, y);
    }

    const zeroY = pad.top + plotH / 2;
    ctx.strokeStyle = '#c7d2db';
    ctx.beginPath(); ctx.moveTo(pad.left, zeroY); ctx.lineTo(width - pad.right, zeroY); ctx.stroke();
    ctx.textAlign = 'left';
    ctx.fillStyle = '#687789';
    ctx.fillText(`+${(pctLimit * 100).toFixed(0)}%`, width - pad.right + 6, pad.top);
    ctx.fillText('0%', width - pad.right + 6, zeroY);
    ctx.fillText(`-${(pctLimit * 100).toFixed(0)}%`, width - pad.right + 6, pad.top + plotH);

    rows.forEach((row, i) => {
      const x = pad.left + step * i + step / 2;
      if (row.gotoBi === true) {
        ctx.fillStyle = 'rgba(92, 166, 111, .12)';
        ctx.fillRect(x - step / 2, pad.top, step, plotH);
      }
      const h = row.volume / maxVolume * plotH;
      ctx.fillStyle = '#2f7ea9';
      ctx.fillRect(x - barW / 2, pad.top + plotH - h, barW, h);
    });

    drawLine(ctx, rows, pad, step, plotH, pctLimit, 'dayChange', '#d08c26');
    drawLine(ctx, rows, pad, step, plotH, pctLimit, 'vs20d', '#8b5fbf');

    const labelEvery = Math.max(1, Math.ceil(rows.length / 10));
    ctx.fillStyle = '#687789';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    rows.forEach((row, i) => {
      if (i % labelEvery !== 0 && i !== rows.length - 1) return;
      const x = pad.left + step * i + step / 2;
      ctx.save();
      ctx.translate(x, pad.top + plotH + 10);
      ctx.rotate(-Math.PI / 5);
      ctx.fillText(row.date.slice(5).replace('-', '/'), 0, 0);
      ctx.restore();
    });
  }

  function drawLine(ctx, rows, pad, step, plotH, limit, key, color) {
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    rows.forEach((row, i) => {
      const x = pad.left + step * i + step / 2;
      const y = pad.top + plotH / 2 - row[key] / limit * (plotH / 2);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
    rows.forEach((row, i) => {
      const x = pad.left + step * i + step / 2;
      const y = pad.top + plotH / 2 - row[key] / limit * (plotH / 2);
      ctx.beginPath(); ctx.arc(x, y, 2.3, 0, Math.PI * 2); ctx.fill();
    });
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  }

  async function init() {
    try {
      const response = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      state.all = data
        .filter(row => row && row.date && Number.isFinite(Number(row.volume)))
        .map(row => ({ ...row, volume: Number(row.volume), dayChange: Number(row.dayChange || 0), vs20d: Number(row.vs20d || 0) }))
        .sort((a, b) => a.date.localeCompare(b.date));
      applyFilters();
    } catch (error) {
      console.error(error);
      els.status.textContent = 'データを読み込めませんでした';
      els.tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center">JSONの読み込みに失敗しました。</td></tr>';
      drawChart();
    }
  }

  els.range.addEventListener('change', applyFilters);
  els.goto.addEventListener('change', applyFilters);
  window.addEventListener('resize', () => window.requestAnimationFrame(drawChart));
  init();
})();
