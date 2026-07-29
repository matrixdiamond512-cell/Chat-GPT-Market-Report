(() => {
  const root = document.querySelector('.dashboard-card--events');
  const list = document.getElementById('dashboardEvents');
  if (!root || !list || document.getElementById('eventSurpriseSummary')) return;

  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const num = v => {
    if (v == null || v === '') return null;
    const n = Number(String(v).replace(/,/g, '').replace(/[%$¥€]/g, ''));
    return Number.isFinite(n) ? n : null;
  };
  const fmt = (v, u = '') => v == null || v === '' ? '—' : `${esc(v)}${esc(u)}`;
  const first = (...values) => values.find(v => v != null && v !== '') ?? '';

  const MARKETS = [
    {key:'usdjpy', label:'USD/JPY', icon:'💱'},
    {key:'eurusd', label:'EUR/USD', icon:'🇪🇺'},
    {key:'nikkei', label:'日経225先物', icon:'🇯🇵'},
    {key:'gold', label:'金', icon:'🟨'},
    {key:'oil', label:'原油', icon:'🛢️'},
    {key:'btc', label:'BTCUSD', icon:'₿'}
  ];

  const direction = event => {
    const a = num(event.actual), f = num(event.forecast);
    if (a == null || f == null) return {state:'pending', label:'結果待ち', diff:null};
    const diff = a - f;
    const base = Math.max(Math.abs(f), 1e-9);
    const ratio = Math.abs(diff / base);
    const size = ratio >= .1 ? '大' : ratio >= .03 ? '中' : '小';
    if (Math.abs(diff) < 1e-12) return {state:'neutral', label:'予想一致', diff:0, size:'小'};
    return {state:diff > 0 ? 'positive' : 'negative', label:`${diff > 0 ? '上振れ' : '下振れ'}（${size}）`, diff, size};
  };

  const marketRead = (event, state) => {
    const title = String(event.title || '');
    if (state === 'pending' || state === 'neutral') return state === 'pending' ? '発表後に市場反応を確認' : '予想通りで、初動は需給や同時刻の材料が主導しやすい';
    const up = state === 'positive';
    if (/CPI|PCE|PPI|雇用|賃金|GDP|小売|ISM|PMI/i.test(title)) return up ? '米金利・ドル上昇、株・金・BTCには逆風となる可能性' : '米金利・ドル低下、株・金・BTCには追い風となる可能性';
    if (/失業率|失業保険/i.test(title)) return up ? '景気減速懸念から米金利・ドル低下、株は内容次第' : '雇用の強さから米金利・ドル上昇を警戒';
    if (/原油|EIA|API|在庫/i.test(title)) return up ? '在庫増なら原油に下押し圧力。需要指標の場合は内容を個別確認' : '在庫減なら原油に上昇圧力。需要指標の場合は内容を個別確認';
    if (/日銀|日本|東京/i.test(title)) return up ? '円金利上昇・円高方向を警戒' : '円金利低下・円安方向を警戒';
    return 'イベントの性質により影響方向が異なるため、初動と金利・為替の反応を確認';
  };

  const normalizeImpact = value => {
    const raw = String(value ?? '').toLowerCase();
    if (/buy|bull|positive|up|買|強気|上昇/.test(raw)) return 'buy';
    if (/sell|bear|negative|down|売|弱気|下落/.test(raw)) return 'sell';
    return 'neutral';
  };

  const inferImpacts = event => {
    const explicit = event.marketImpacts || event.impacts || event.impactByMarket;
    if (explicit && typeof explicit === 'object') {
      return Object.fromEntries(MARKETS.map(m => [m.key, normalizeImpact(first(explicit[m.key], explicit[m.label]))]));
    }

    const title = String(event.title || '');
    const d = direction(event);
    if (d.state === 'pending' || d.state === 'neutral') return Object.fromEntries(MARKETS.map(m => [m.key, 'neutral']));
    let stronger = d.state === 'positive';
    if (/失業率|失業保険|原油在庫|EIA|API/i.test(title)) stronger = !stronger;

    const result = Object.fromEntries(MARKETS.map(m => [m.key, 'neutral']));
    if (/CPI|PCE|PPI|雇用|失業|賃金|GDP|小売|ISM|PMI|FOMC|FRB|パウエル/i.test(title)) {
      result.usdjpy = stronger ? 'buy' : 'sell';
      result.eurusd = stronger ? 'sell' : 'buy';
      result.nikkei = stronger ? 'sell' : 'buy';
      result.gold = stronger ? 'sell' : 'buy';
      result.btc = stronger ? 'sell' : 'buy';
    }
    if (/日銀|日本|東京|賃金.*日本|全国CPI/i.test(title)) {
      result.usdjpy = stronger ? 'sell' : 'buy';
      result.nikkei = stronger ? 'sell' : 'buy';
      result.gold = stronger ? 'neutral' : 'buy';
    }
    if (/原油|EIA|API|在庫|OPEC/i.test(title)) result.oil = stronger ? 'buy' : 'sell';
    return result;
  };

  const impactHeatmap = event => {
    const impacts = inferImpacts(event);
    const labels = {buy:'買い材料', sell:'売り材料', neutral:'中立'};
    return `<div class="event-impact-wrap"><div class="event-impact-title">6市場への想定影響</div><div class="event-impact-grid">${MARKETS.map(m => `<span class="event-impact-chip is-${impacts[m.key]}"><i>${m.icon}</i><b>${m.label}</b><small>${labels[impacts[m.key]]}</small></span>`).join('')}</div></div>`;
  };

  const reactionText = (event, key) => {
    const reaction = event.reaction || event.marketReaction || event.priceReaction || {};
    const aliases = {initial:['initial','immediate','firstMove','initialReaction','atRelease'],m30:['m30','after30m','thirtyMinutes','reaction30m'],hours:['hours','afterHours','after2h','later','followThrough']};
    for (const name of aliases[key]) {
      const value = first(reaction?.[name], event?.[name]);
      if (value) return typeof value === 'string' ? value : JSON.stringify(value);
    }
    return '';
  };

  const reactionRow = event => {
    const initial = reactionText(event, 'initial');
    const m30 = reactionText(event, 'm30');
    const hours = reactionText(event, 'hours');
    if (!initial && !m30 && !hours) return '<p class="event-data-note">市場反応データはまだ登録されていません。</p>';
    return `<div class="event-reaction-row"><span>初動<b>${esc(initial || '—')}</b></span><span>30分後<b>${esc(m30 || '—')}</b></span><span>数時間後<b>${esc(hours || '—')}</b></span></div>`;
  };

  const consistencyRead = event => {
    const explicit = first(event.reactionConsistency, event.consistency, event.marketInterpretation);
    if (explicit) return String(explicit);
    const initial = reactionText(event, 'initial');
    if (!initial) return '';
    return `理論上の反応：${marketRead(event, direction(event).state)}。実際の初動：${initial}`;
  };

  async function init() {
    try {
      const r = await fetch(`economic-calendar.json?surprise=${Date.now()}`, {cache:'no-store'});
      if (!r.ok) return;
      const payload = await r.json();
      const events = Array.isArray(payload?.events) ? payload.events : [];
      const now = new Date();
      const dated = events.map(e => ({...e,title:e.title || e.event || e.name || '',forecast:e.forecast ?? e.estimate ?? e.consensus,previous:e.previous ?? e.prev,actual:e.actual,unit:e.unit || '',dt:new Date(e.datetimeJst || `${e.date}T${e.time}:00+09:00`)})).filter(e => e.title && !Number.isNaN(e.dt.getTime())).sort((a, b) => a.dt - b.dt);
      const completed = dated.filter(e => e.dt <= now && e.actual != null && e.actual !== '').slice(-3).reverse();
      const upcoming = dated.find(e => e.dt > now);
      const panel = document.createElement('section');
      panel.id = 'eventSurpriseSummary';
      panel.className = 'event-surprise-summary';

      const completedHtml = completed.length ? completed.map(e => {
        const d = direction(e);
        const diff = d.diff == null ? '—' : `${d.diff > 0 ? '+' : ''}${d.diff.toLocaleString('ja-JP')}${esc(e.unit || '')}`;
        const consistency = consistencyRead(e);
        return `<article class="event-surprise-card is-${d.state}"><div class="surprise-head"><strong>${esc(e.title)}</strong><span>${d.label}</span></div><div class="surprise-values"><span>予想<b>${fmt(e.forecast,e.unit)}</b></span><span>結果<b>${fmt(e.actual,e.unit)}</b></span><span>予想差<b>${diff}</b></span></div><p>${esc(marketRead(e,d.state))}</p>${impactHeatmap(e)}${reactionRow(e)}${consistency ? `<p class="event-data-note"><strong>整合性：</strong>${esc(consistency)}</p>` : ''}</article>`;
      }).join('') : '<p class="event-surprise-empty">発表済みで予想と結果がそろったイベントはありません。</p>';

      const nextHtml = upcoming ? `<div class="next-event-compact"><span>次の発表</span><strong>${esc(upcoming.time || '')} ${esc(upcoming.title)}</strong><small>予想 ${fmt(upcoming.forecast,upcoming.unit)}｜前回 ${fmt(upcoming.previous,upcoming.unit)}</small></div>` : '';
      panel.innerHTML = `<div class="surprise-title"><div><span class="dashboard-label">発表結果・サプライズ</span><h3>予想との差と市場への意味</h3></div>${nextHtml}</div><div class="event-surprise-grid">${completedHtml}</div>`;
      list.insertAdjacentElement('beforebegin', panel);
    } catch (e) {
      console.warn('Event surprise panel unavailable:', e);
    }
  }

  init();
})();