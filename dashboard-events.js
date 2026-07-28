(() => {
  const container = document.getElementById("dashboardEvents");
  if (!container) return;

  const escapeHtml = (value = "") => String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[char]));
  const asArray = value => Array.isArray(value) ? value : (value ? [value] : []);
  const itemText = item => typeof item === "string" ? item : (item?.text || item?.summary || item?.title || item?.name || "");

  const HIGH_IMPACT = /FOMC|政策金利|日銀会合|金融政策決定会合|ECB理事会|BOE|CPI|PCE|雇用統計|非農業部門雇用者数|GDP|パウエル議長|植田総裁|記者会見/i;
  const EVENT_WORDS = /FOMC|日銀|ECB|BOE|FRB|政策金利|CPI|PPI|PCE|GDP|PMI|ISM|雇用統計|失業率|JOLTS|小売売上高|耐久財|消費者信頼感|国債入札|要人発言|講演|記者会見|決算|オプションカット|NYカット|仲値|ゴトー日|SQ|MSQ|清算|在庫統計|OPEC|EIA|API/i;

  function inferImpact(text) {
    const impacts = new Set();
    if (/米|FRB|FOMC|CPI|PCE|雇用|GDP|ISM|PMI|国債入札|パウエル/i.test(text)) ["USD/JPY", "EUR/USD", "日経225先物", "金"].forEach(x => impacts.add(x));
    if (/日銀|植田|仲値|ゴトー日|日本|SQ|MSQ/i.test(text)) ["USD/JPY", "日経225先物"].forEach(x => impacts.add(x));
    if (/ECB|ユーロ/i.test(text)) impacts.add("EUR/USD");
    if (/原油|OPEC|EIA|API|在庫/i.test(text)) ["原油", "USD/JPY", "日経225先物"].forEach(x => impacts.add(x));
    if (/暗号|BTC|ビットコイン|ETF/i.test(text)) impacts.add("BTCUSD");
    if (/決算|NVIDIA|Apple|Microsoft|Amazon|Meta|Tesla|半導体/i.test(text)) ["日経225先物", "BTCUSD"].forEach(x => impacts.add(x));
    return [...impacts];
  }

  function normalizeEvent(event) {
    if (typeof event === "string") {
      const match = event.match(/^\s*(\d{1,2}:\d{2}|未定|終日)\s*[　 ]*(.*)$/);
      const title = match ? match[2] : event;
      return { time: match ? match[1] : "—", title, importance: HIGH_IMPACT.test(title) ? 3 : 2, impact: inferImpact(title) };
    }
    const title = event?.title || event?.name || event?.event || event?.text || event?.summary || "イベント名なし";
    const importanceRaw = event?.importance ?? event?.priority ?? event?.level ?? event?.rank ?? (HIGH_IMPACT.test(title) ? 3 : 2);
    let importance = Number(importanceRaw);
    if (!Number.isFinite(importance)) {
      const text = String(importanceRaw).toLowerCase();
      importance = /high|最重要|重要度3|★★★|赤/.test(text) ? 3 : /low|低|重要度1|★$/.test(text) ? 1 : 2;
    }
    return {
      time: event?.time || event?.jst || event?.datetime || event?.dateTime || "—",
      title,
      importance: Math.max(1, Math.min(3, importance)),
      impact: event?.impact || event?.markets || event?.affectedMarkets || inferImpact(title)
    };
  }

  function recurringEvents(dateString) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dateString || "")) return [];
    const date = new Date(`${dateString}T00:00:00+09:00`);
    const day = date.getDate();
    const weekday = date.getDay();
    const events = [];
    if ([5, 10, 15, 20, 25, 30].includes(day) && weekday >= 1 && weekday <= 5) {
      events.push({ time: "09:55", title: "東京仲値・ゴトー日需給", importance: 2, impact: ["USD/JPY"] });
    }
    const nextDay = new Date(date); nextDay.setDate(day + 1);
    if (nextDay.getMonth() !== date.getMonth() && weekday >= 1 && weekday <= 5) {
      events.push({ time: "終日", title: "月末フロー・リバランス", importance: 2, impact: ["USD/JPY", "EUR/USD", "日経225先物", "金"] });
    }
    if (weekday === 5 && day >= 8 && day <= 14) {
      const month = date.getMonth() + 1;
      events.push({ time: "09:00", title: month % 3 === 0 ? "メジャーSQ（MSQ）" : "SQ", importance: month % 3 === 0 ? 3 : 2, impact: ["日経225先物", "USD/JPY"] });
    }
    return events;
  }

  function extractEvents(report) {
    const explicit = asArray(report?.events);
    const textSources = [
      ...asArray(report?.handover),
      ...asArray(report?.news),
      ...asArray(report?.changes),
      ...asArray(report?.riskManagement)
    ].map(itemText).filter(Boolean);

    const inferred = [];
    textSources.forEach(text => {
      if (!EVENT_WORDS.test(text)) return;
      const chunks = text.split(/[。\n]|(?=\d{1,2}:\d{2})/).map(x => x.trim()).filter(Boolean);
      chunks.filter(chunk => EVENT_WORDS.test(chunk)).forEach(chunk => {
        const match = chunk.match(/(\d{1,2}:\d{2})/);
        inferred.push({ time: match ? match[1] : "—", title: chunk.replace(/^・/, ""), importance: HIGH_IMPACT.test(chunk) ? 3 : 2, impact: inferImpact(chunk) });
      });
    });

    const combined = [...explicit, ...inferred, ...recurringEvents(report?.date)].map(normalizeEvent);
    const seen = new Set();
    return combined.filter(event => {
      const key = `${event.time}|${event.title}`.replace(/\s+/g, "");
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function importanceLabel(level) {
    if (level >= 3) return { text: "最重要", className: "event-level--high" };
    if (level === 2) return { text: "重要", className: "event-level--medium" };
    return { text: "参考", className: "event-level--low" };
  }
  function timeToMinutes(value) {
    const match = String(value).match(/(\d{1,2}):(\d{2})/);
    return match ? Number(match[1]) * 60 + Number(match[2]) : 9999;
  }

  function render(events) {
    const normalized = asArray(events).map(normalizeEvent).sort((a, b) => timeToMinutes(a.time) - timeToMinutes(b.time));
    if (!normalized.length) {
      container.innerHTML = '<p class="event-empty">重要イベントを抽出できませんでした。最新レポートの「events」「重要ニュース」「次の時間帯への引き継ぎ」に予定を記載すると自動表示されます。</p>';
      return;
    }
    container.innerHTML = normalized.slice(0, 10).map(event => {
      const level = importanceLabel(event.importance);
      const impact = Array.isArray(event.impact) ? event.impact.join("・") : event.impact;
      return `<div class="event-row"><time class="event-time">${escapeHtml(event.time)}</time><div class="event-main"><div class="event-title-row"><strong>${escapeHtml(event.title)}</strong><span class="event-level ${level.className}">${level.text}</span></div>${impact ? `<small>影響：${escapeHtml(impact)}</small>` : ""}</div></div>`;
    }).join("");
  }

  async function loadEvents() {
    try {
      const response = await fetch(`reports.json?events=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error("イベントデータを取得できませんでした");
      const reports = await response.json();
      const latest = asArray(reports).filter(report => /^\d{4}-\d{2}-\d{2}$/.test(report?.date || "")).sort((a, b) => `${b.date} ${b.time || ""}`.localeCompare(`${a.date} ${a.time || ""}`))[0];
      render(extractEvents(latest));
    } catch (error) {
      container.innerHTML = `<p class="event-empty">${escapeHtml(error.message)}</p>`;
    }
  }
  loadEvents();
})();