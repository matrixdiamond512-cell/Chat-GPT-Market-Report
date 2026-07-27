(() => {
  'use strict';

  const DATA_URL = 'tokyo-usdjpy-volume.json';
  const STORAGE_KEY = 'tokyoFlowTradeChecklistV1';
  const predictionEl = document.getElementById('todayPrediction');
  const checklistEl = document.getElementById('tradeChecklist');
  const summaryEl = document.getElementById('checklistSummary');
  const saveBtn = document.getElementById('saveChecklist');
  const resetBtn = document.getElementById('resetChecklist');

  if (!predictionEl || !checklistEl || !summaryEl || !saveBtn || !resetBtn) return;

  const fmtInt = new Intl.NumberFormat('ja-JP');
  const fmtPct = value => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`;
  const weekdayNames = ['日', '月', '火', '水', '木', '金', '土'];

  const items = [
    { id: 'goto', label: 'ゴトー日・前倒し', weight: 3, note: 'ゴトー日、前倒し、月末の手入力条件' },
    { id: 'tokyoVolume', label: '東京出来高', weight: 3, note: '前日比と20営業日平均との差' },
    { id: 'realDemand', label: '実需フロー', weight: 4, note: '輸入・輸出、仲値前のドル需要' },
    { id: 'usYield', label: '米金利', weight: 3, note: '米10年債・短期金利の方向' },
    { id: 'rateSpread', label: '日米金利差', weight: 3, note: '金利差拡大はドル円上昇要因になりやすい' },
    { id: 'nyOption', label: 'NYオプション', weight: 2, note: '大口カット水準と現在値の位置関係' },
    { id: 'imm', label: 'IMM・投機筋', weight: 2, note: '円売り・円買いポジションの偏り' },
    { id: 'carry', label: '円キャリー', weight: 3, note: 'キャリー継続か巻き戻しか' },
    { id: 'intervention', label: '介入警戒', weight: 4, inverse: true, note: '警戒上昇はドル円ロングの抑制要因' },
    { id: 'riskSentiment', label: 'リスク選好', weight: 2, note: '株高・ボラ低下は円売り要因になりやすい' }
  ];

  const options = [
    { value: '2', label: '強いドル買い要因' },
    { value: '1', label: 'ややドル買い' },
    { value: '0', label: '中立・不明' },
    { value: '-1', label: 'ややドル売り' },
    { value: '-2', label: '強いドル売り要因' }
  ];

  let rows = [];

  function average(list) {
    return list.length ? list.reduce((sum, row) => sum + row.volume, 0) / list.length : null;
  }

  function rowType(row) {
    if (row.gotoBi === false) return '通常日';
    if (row.gotoBi !== true) return '未入力';
    return row.gotoBiType || '通常ゴトー日';
  }

  function computePrediction() {
    const latest = rows[rows.length - 1];
    if (!latest) return null;

    const normal = rows.filter(row => row.gotoBi === false);
    const baseline = average(normal) || average(rows) || latest.volume;
    const weekday = new Date(`${latest.date}T00:00:00`).getDay();
    const sameWeekday = rows.filter(row => new Date(`${row.date}T00:00:00`).getDay() === weekday);
    const sameType = rows.filter(row => rowType(row) === rowType(latest));
    const weekdayAvg = average(sameWeekday) || baseline;
    const typeAvg = average(sameType) || baseline;

    let score = 50;
    const reasons = [];
    const volumeGap = latest.volume / baseline - 1;
    const weekdayGap = weekdayAvg / baseline - 1;
    const typeGap = typeAvg / baseline - 1;

    score += Math.max(-18, Math.min(18, volumeGap * 22));
    score += Math.max(-10, Math.min(10, weekdayGap * 15));
    score += Math.max(-12, Math.min(12, typeGap * 18));
    score += Math.max(-9, Math.min(9, latest.dayChange * 12));
    score += Math.max(-12, Math.min(12, latest.vs20d * 15));

    if (latest.gotoBi === true) {
      score += 6;
      reasons.push(`${rowType(latest)}として手入力されています`);
    }
    if (latest.gotoBiType === '前倒し' || latest.gotoBiType === '月末') {
      score += 4;
      reasons.push(`${latest.gotoBiType}要因を加点しています`);
    }
    if (latest.vs20d >= 0.15) reasons.push(`出来高は20営業日平均を${fmtPct(latest.vs20d)}上回っています`);
    else if (latest.vs20d <= -0.15) reasons.push(`出来高は20営業日平均を${fmtPct(latest.vs20d)}下回っています`);
    if (latest.dayChange >= 0.20) reasons.push(`前日比${fmtPct(latest.dayChange)}の出来高増加です`);
    else if (latest.dayChange <= -0.20) reasons.push(`前日比${fmtPct(latest.dayChange)}の出来高減少です`);

    score = Math.round(Math.max(0, Math.min(100, score)));
    const signal = score >= 72 ? '強い' : score >= 60 ? 'やや強い' : score >= 42 ? '中立' : score >= 30 ? 'やや弱い' : '弱い';
    const css = score >= 60 ? 'buy' : score >= 42 ? 'neutral' : 'weak';

    return { latest, weekday, baseline, weekdayAvg, typeAvg, score, signal, css, reasons };
  }

  function renderPrediction() {
    const result = computePrediction();
    if (!result) {
      predictionEl.textContent = '分析対象データがありません。';
      return;
    }

    const { latest, weekday, baseline, weekdayAvg, typeAvg, score, signal, css, reasons } = result;
    predictionEl.innerHTML = `
      <span class="status-note">最新登録行に基づく統計判定</span>
      <div class="signal ${css}">仲値需要：${signal}</div>
      <strong>${score}/100</strong>
      <p>${latest.date}（${weekdayNames[weekday]}）・${rowType(latest)}<br>
      出来高 ${fmtInt.format(latest.volume)} 百万ドル／通常日平均 ${fmtInt.format(Math.round(baseline))}<br>
      同曜日平均 ${fmtInt.format(Math.round(weekdayAvg))}／同区分平均 ${fmtInt.format(Math.round(typeAvg))}</p>
      <p>${reasons.length ? reasons.map(reason => `・${reason}`).join('<br>') : '・特筆すべき出来高偏差はありません'}</p>
      <p><small>これは方向を断定する売買シグナルではなく、仲値前後の需要環境を整理する統計補助です。</small></p>`;
  }

  function renderChecklist(saved = {}) {
    checklistEl.innerHTML = items.map(item => {
      const value = saved[item.id] ?? '0';
      return `
        <div class="check-row">
          <label for="check-${item.id}">${item.label}</label>
          <select id="check-${item.id}" data-id="${item.id}" aria-label="${item.label}">
            ${options.map(option => `<option value="${option.value}" ${String(value) === option.value ? 'selected' : ''}>${option.label}</option>`).join('')}
          </select>
          <span class="status-note">${item.note}</span>
        </div>`;
    }).join('');

    checklistEl.querySelectorAll('select').forEach(select => select.addEventListener('change', updateChecklistSummary));
    updateChecklistSummary();
  }

  function getChecklistValues() {
    const values = {};
    checklistEl.querySelectorAll('select').forEach(select => { values[select.dataset.id] = select.value; });
    return values;
  }

  function updateChecklistSummary() {
    let weighted = 0;
    let max = 0;
    const positives = [];
    const negatives = [];

    items.forEach(item => {
      const select = checklistEl.querySelector(`[data-id="${item.id}"]`);
      if (!select) return;
      let value = Number(select.value);
      if (item.inverse) value *= -1;
      weighted += value * item.weight;
      max += 2 * item.weight;
      if (value >= 1) positives.push(item.label);
      if (value <= -1) negatives.push(item.label);
    });

    const normalized = max ? Math.round(weighted / max * 100) : 0;
    const judgment = normalized >= 35 ? 'ドル買い優勢' : normalized >= 12 ? 'ややドル買い' : normalized > -12 ? '中立' : normalized > -35 ? 'ややドル売り' : 'ドル売り優勢';
    summaryEl.innerHTML = `総合判定：${judgment}（${normalized > 0 ? '+' : ''}${normalized}）<br><small>買い要因：${positives.join('、') || 'なし'}／売り要因：${negatives.join('、') || 'なし'}</small>`;
  }

  function saveChecklist() {
    const payload = {
      savedAt: new Date().toISOString(),
      values: getChecklistValues()
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    saveBtn.textContent = '保存しました';
    setTimeout(() => { saveBtn.textContent = 'チェック内容を保存'; }, 1500);
  }

  function loadChecklist() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return parsed && parsed.values ? parsed.values : {};
    } catch (error) {
      console.warn('チェックリスト保存データを読み込めませんでした', error);
      return {};
    }
  }

  function resetChecklist() {
    localStorage.removeItem(STORAGE_KEY);
    renderChecklist({});
  }

  async function init() {
    renderChecklist(loadChecklist());
    try {
      const response = await fetch(`${DATA_URL}?decision=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      rows = data
        .filter(row => row && row.date && Number.isFinite(Number(row.volume)))
        .map(row => ({
          ...row,
          volume: Number(row.volume),
          dayChange: Number(row.dayChange || 0),
          vs20d: Number(row.vs20d || 0)
        }))
        .sort((a, b) => a.date.localeCompare(b.date));
      renderPrediction();
    } catch (error) {
      console.error(error);
      predictionEl.textContent = '仲値需要予測を生成できませんでした。';
    }
  }

  saveBtn.addEventListener('click', saveChecklist);
  resetBtn.addEventListener('click', resetChecklist);
  init();
})();
