(() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
  const first = (...values) => values.find(v => v != null && v !== '') ?? '';

  function latestCompletedEvent(events) {
    const now = new Date();
    return events
      .map(e => ({
        ...e,
        title: e.title || e.event || e.name || '',
        dt: new Date(e.datetimeJst || `${e.date}T${e.time}:00+09:00`)
      }))
      .filter(e => e.title && !Number.isNaN(e.dt.getTime()) && e.dt <= now && e.actual != null && e.actual !== '')
      .sort((a, b) => b.dt - a.dt)[0];
  }

  function number(value) {
    if (value == null || value === '') return null;
    const n = Number(String(value).replace(/,/g, '').replace(/[%$¥€]/g, ''));
    return Number.isFinite(n) ? n : null;
  }

  function surprise(event) {
    const actual = number(event.actual);
    const forecast = number(event.forecast ?? event.estimate ?? event.consensus);
    if (actual == null || forecast == null) return 0;
    return actual - forecast;
  }

  function flow(event) {
    const title = String(event.title || '');
    const positive = surprise(event) > 0;
    if (/CPI|PCE|PPI|雇用|賃金|GDP|小売|ISM|PMI|FOMC|FRB|パウエル/i.test(title)) {
      return positive
        ? [['指標上振れ','米金利上昇'],['米金利上昇','ドル高'],['ドル高','金・BTCに逆風'],['金利上昇','株式に逆風']]
        : [['指標下振れ','米金利低下'],['米金利低下','ドル安'],['ドル安','金・BTCに追い風'],['金利低下','株式に追い風']];
    }
    if (/日銀|日本|東京/i.test(title)) {
      return positive
        ? [['日本材料上振れ','日本金利上昇'],['日本金利上昇','円高'],['円高','USD/JPY下落'],['円高','日経先物に重し']]
        : [['日本材料下振れ','日本金利低下'],['日本金利低下','円安'],['円安','USD/JPY上昇'],['円安','日経先物を支援']];
    }
    if (/原油|EIA|API|在庫|OPEC/i.test(title)) {
      const inventory = /在庫|EIA|API/i.test(title);
      const oilHigher = inventory ? surprise(event) < 0 : positive;
      return oilHigher
        ? [['供給懸念・在庫減','原油高'],['原油高','期待インフレ上昇'],['期待インフレ上昇','金利上昇圧力'],['原油高','輸入国通貨に逆風']]
        : [['供給緩和・在庫増','原油安'],['原油安','期待インフレ低下'],['期待インフレ低下','金利低下余地'],['原油安','輸入国通貨を支援']];
    }
    return [];
  }

  function reactionText(event) {
    const reaction = event.reaction || event.marketReaction || event.priceReaction || {};
    return [
      first(reaction.initial, reaction.immediate, event.initial),
      first(reaction.m30, reaction.after30m, event.m30),
      first(reaction.hours, reaction.afterHours, event.hours)
    ].filter(Boolean).join(' ');
  }

  function verdict(event) {
    const explicit = first(event.verification, event.reactionVerdict, event.marketVerdict, event.reactionConsistency, event.consistency);
    if (explicit) return String(explicit);
    const text = reactionText(event);
    if (!text) return '検証待ち：市場反応データが未登録です';
    if (/逆|反対|巻き戻|往って来い|失速/.test(text)) return '理論と逆、または織り込み済みの可能性';
    if (/需給|ショートカバー|買い戻し|ガンマ|ポジション/.test(text)) return 'ニュースより需給・ポジションが主導';
    if (/継続|拡大|定着|追随/.test(text)) return '理論通りに反応が継続';
    return '初動は確認済み。持続性は要検証';
  }

  function render(event) {
    const host = document.getElementById('eventSurpriseSummary') || document.querySelector('.dashboard-card--events');
    if (!host || document.getElementById('crossAssetTransmission')) return;
    const nodes = flow(event);
    if (!nodes.length) return;
    const section = document.createElement('section');
    section.id = 'crossAssetTransmission';
    section.className = 'cross-asset-transmission';
    section.innerHTML = `
      <div class="cross-asset-head">
        <div><span class="dashboard-label">クロスアセット伝播</span><h3>材料 → 市場 → 価格反応</h3></div>
        <div class="cross-asset-verdict"><span>市場検証</span><strong>${esc(verdict(event))}</strong></div>
      </div>
      <p class="cross-asset-event">対象イベント：${esc(event.title)}</p>
      <div class="cross-asset-flow">${nodes.map((pair, index) => `<span class="cross-asset-step"><b>${esc(pair[0])}</b><i>→</i><strong>${esc(pair[1])}</strong></span>${index < nodes.length - 1 ? '<em>›</em>' : ''}`).join('')}</div>`;
    host.insertAdjacentElement('afterend', section);
  }

  async function init() {
    try {
      const response = await fetch(`economic-calendar.json?crossAsset=${Date.now()}`, {cache:'no-store'});
      if (!response.ok) return;
      const payload = await response.json();
      const events = Array.isArray(payload?.events) ? payload.events : [];
      const event = latestCompletedEvent(events);
      if (event) render(event);
    } catch (error) {
      console.warn('Cross-asset panel unavailable:', error);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();