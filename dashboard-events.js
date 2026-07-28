(() => {
  const container = document.getElementById("dashboardEvents");
  const filter = document.getElementById("eventMarketFilter");
  const countdown = document.getElementById("eventCountdown");
  const heatmap = document.getElementById("eventHeatmap");
  const eventLabel = document.querySelector(".dashboard-card--events .dashboard-label");
  if (!container) return;

  const escapeHtml = (value = "") => String(value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[char]));
  const asArray = value => Array.isArray(value) ? value : (value ? [value] : []);
  const clean = value => String(value ?? "").trim();
  const MARKETS = ["USD/JPY", "EUR/USD", "日経225先物", "金", "原油", "BTCUSD"];
  const HIGH_IMPACT = /FOMC|政策金利|日銀金融政策決定会合|ECB理事会|BOE政策金利|CPI|PCE|雇用統計|非農業部門雇用者数|GDP|パウエル議長会見|植田総裁会見/i;
  const EVENT_WORDS = /FOMC|金融政策決定会合|政策金利|ECB理事会|BOE|FRB議長|日銀総裁|CPI|PPI|PCE|GDP|PMI|ISM|雇用統計|失業率|JOLTS|小売売上高|耐久財受注|消費者信頼感|国債入札|要人発言|講演|記者会見|決算発表|オプションカット|NYカット|東京仲値|ゴトー日|SQ|MSQ|清算日|原油在庫統計|OPEC|EIA|API/i;
  const NON_EVENT_WORDS = /前回からの変化|材料と値動き|整合性|需給|ポジション|資金フロー|引き継ぎ|シナリオ|リスク管理|見通し|方向感|買い優勢|売り優勢|上値|下値|サポート|レジスタンス|可能性|警戒|注目点|市場は|投資家は/i;

  let allEvents = [];
  let targetDate = "";
  let sourceMode = "none";
  let sourceMeta = null;
  let timerId = null;

  function todayJst() {
    return new Intl.DateTimeFormat("en-CA", {timeZone:"Asia/Tokyo", year:"numeric", month:"2-digit", day:"2-digit"}).format(new Date());
  }

  function formatDate(dateString) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dateString || "")) return dateString || "";
    const [y,m,d] = dateString.split("-");
    return `${y}/${m}/${d}`;
  }

  function inferImpact(text) {
    const impacts = new Set();
    if (/米|FRB|FOMC|CPI|PCE|雇用|GDP|ISM|PMI|国債入札|パウエル/i.test(text)) ["USD/JPY","EUR/USD","日経225先物","金","BTCUSD"].forEach(x => impacts.add(x));
    if (/日銀|植田|東京仲値|ゴトー日|日本|SQ|MSQ/i.test(text)) ["USD/JPY","日経225先物"].forEach(x => impacts.add(x));
    if (/ECB|ユーロ/i.test(text)) ["EUR/USD","金"].forEach(x => impacts.add(x));
    if (/原油|OPEC|EIA|API|在庫/i.test(text)) ["原油","USD/JPY","日経225先物"].forEach(x => impacts.add(x));
    if (/暗号|BTC|ビットコイン|ETF/i.test(text)) impacts.add("BTCUSD");
    return [...impacts];
  }

  function parseImportance(raw, title) {
    if (raw == null || raw === "") return HIGH_IMPACT.test(title) ? 3 : 2;
    const numeric = Number(raw);
    if (Number.isFinite(numeric)) return Math.max(1, Math.min(3, numeric));
    const text = String(raw).toLowerCase();
    if (/high|最重要|重要度3|★★★|赤/.test(text)) return 3;
    if (/low|低|重要度1|★$/.test(text)) return 1;
    return 2;
  }

  function normalizeExternalEvent(event) {
    const title = clean(event?.title || event?.event || event?.name);
    const date = clean(event?.date || String(event?.datetimeJst || "").slice(0,10));
    const time = clean(event?.time || String(event?.datetimeJst || "").slice(11,16) || "—");
    return {
      date,
      time,
      datetimeJst: clean(event?.datetimeJst) || (date && /^\d{1,2}:\d{2}$/.test(time) ? `${date}T${time}:00+09:00` : ""),
      country: clean(event?.country),
      title,
      importance: parseImportance(event?.importance, title),
      impact: asArray(event?.impact || event?.markets || inferImpact(title)),
      actual: event?.actual,
      forecast: event?.forecast ?? event?.estimate ?? event?.consensus,
      previous: event?.previous ?? event?.prev,
      unit: clean(event?.unit),
      comment: clean(event?.comment || event?.note),
      source: clean(event?.source || "Financial Modeling Prep")
    };
  }

  function normalizeReportEvent(event, reportDate) {
    if (typeof event === "string") {
      const source = event.replace(/^\s*[・●■◆-]\s*/, "").trim();
      const match = source.match(/^\s*(\d{1,2}:\d{2}|未定|終日)\s*[｜|：:\-–—　 ]*\s*(.*)$/);
      const time = match ? match[1] : "—";
      const body = (match ? match[2] : source).trim();
      const pieces = body.split(/\s*[｜|]\s*/).filter(Boolean);
      const title = pieces.shift() || "";
      return {date:reportDate,time,title,comment:pieces.join("｜"),importance:parseImportance(null,title),impact:inferImpact(title),country:"",actual:null,forecast:null,previous:null,unit:"",source:"レポート本文"};
    }
    const title = clean(event?.title || event?.name || event?.event || event?.text);
    const time = clean(event?.time || event?.jst || event?.datetime || event?.dateTime || "—");
    return {
      date: clean(event?.date || reportDate),
      time,
      datetimeJst: clean(event?.datetimeJst),
      country: clean(event?.country),
      title,
      comment: clean(event?.comment || event?.note || event?.focus || event?.marketComment),
      importance: parseImportance(event?.importance ?? event?.priority ?? event?.level ?? event?.rank,title),
      impact: asArray(event?.impact || event?.markets || event?.affectedMarkets || inferImpact(title)),
      actual:event?.actual,forecast:event?.forecast,previous:event?.previous,unit:clean(event?.unit),source:"レポート本文"
    };
  }

  function isActualEvent(event) {
    if (!event.title || event.title.length > 140) return false;
    const hasTime = /^(?:\d{1,2}:\d{2}|未定|終日|—)$/.test(String(event.time));
    const hasEventName = EVENT_WORDS.test(event.title);
    if (!hasTime && !hasEventName) return false;
    if (NON_EVENT_WORDS.test(event.title) && !hasEventName) return false;
    return true;
  }

  function uniqueEvents(events) {
    const seen = new Set();
    return events.filter(isActualEvent).filter(event => {
      const key = `${event.date}|${event.time}|${event.country}|${event.title}`.replace(/\s+/g,"").toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function selectTargetDate(events) {
    const today = todayJst();
    const dates = [...new Set(events.map(event => event.date).filter(Boolean))].sort();
    if (dates.includes(today)) return today;
    return dates.find(date => date > today) || dates.at(-1) || today;
  }

  function importanceLabel(level) {
    return level >= 3 ? {text:"最重要",className:"event-level--high"} : level === 2 ? {text:"重要",className:"event-level--medium"} : {text:"参考",className:"event-level--low"};
  }

  function timeToMinutes(value) {
    const match = String(value).match(/(\d{1,2}):(\d{2})/);
    return match ? Number(match[1]) * 60 + Number(match[2]) : 9999;
  }

  function eventDateTime(event) {
    if (event.datetimeJst) {
      const parsed = new Date(event.datetimeJst);
      if (!Number.isNaN(parsed.getTime())) return parsed;
    }
    const match = String(event.time).match(/(\d{1,2}):(\d{2})/);
    if (!event.date || !match) return null;
    return new Date(`${event.date}T${String(match[1]).padStart(2,"0")}:${match[2]}:00+09:00`);
  }

  function filteredEvents() {
    const selected = filter?.value || "all";
    const dateEvents = allEvents.filter(event => event.date === targetDate && event.importance >= 2);
    return selected === "all" ? dateEvents : dateEvents.filter(event => asArray(event.impact).includes(selected));
  }

  function sourceNote() {
    let note = document.getElementById("eventSourceNote");
    if (!note) {
      note = document.createElement("p");
      note.id = "eventSourceNote";
      note.className = "event-source-note";
      heatmap?.parentNode?.insertBefore(note, heatmap);
    }
    if (sourceMode === "external") {
      const updated = sourceMeta?.updatedAt ? `｜更新 ${clean(sourceMeta.updatedAt).replace("T"," ").slice(0,16)}` : "";
      note.innerHTML = `<span class="event-source-badge is-external">外部カレンダー</span> Financial Modeling Prep${escapeHtml(updated)}｜日本時間表示`;
    } else if (sourceMode === "report") {
      note.innerHTML = '<span class="event-source-badge is-fallback">代替表示</span> 外部カレンダー未取得のため、レポート内のイベント専用欄を表示';
    } else {
      note.innerHTML = '<span class="event-source-badge is-error">未接続</span> 外部経済指標カレンダーを取得できていません';
    }
  }

  function renderHeatmap(events) {
    if (!heatmap) return;
    const scores = Object.fromEntries(MARKETS.map(m => [m,0]));
    events.forEach(event => asArray(event.impact).forEach(market => { if (market in scores) scores[market] += event.importance; }));
    const max = Math.max(1,...Object.values(scores));
    heatmap.innerHTML = MARKETS.map(market => {
      const score = scores[market];
      const level = score === 0 ? "none" : score / max >= .67 ? "high" : score / max >= .34 ? "medium" : "low";
      return `<button type="button" class="heat-chip heat-${level}" data-market="${escapeHtml(market)}"><span>${escapeHtml(market)}</span><strong>${score}</strong></button>`;
    }).join("");
    heatmap.querySelectorAll(".heat-chip").forEach(button => button.addEventListener("click", () => {
      if (filter) filter.value = button.dataset.market;
      renderAll();
    }));
  }

  function formatNumber(value, unit) {
    if (value == null || value === "") return "—";
    return `${escapeHtml(value)}${escapeHtml(unit || "")}`;
  }

  function renderEvents(events) {
    const sorted = [...events].sort((a,b) => timeToMinutes(a.time) - timeToMinutes(b.time) || b.importance - a.importance);
    if (!sorted.length) {
      container.innerHTML = `<p class="event-empty">${escapeHtml(formatDate(targetDate))}に該当する重要イベントはありません。</p>`;
      return;
    }
    const now = new Date();
    container.innerHTML = sorted.slice(0,12).map(event => {
      const level = importanceLabel(event.importance);
      const impact = asArray(event.impact).join("・");
      const dt = eventDateTime(event);
      const status = dt && dt < now ? " is-past" : "";
      const hasFigures = [event.previous,event.forecast,event.actual].some(value => value != null && value !== "");
      return `<article class="event-row${status}">
        <time class="event-time">${escapeHtml(event.time)}</time>
        <span class="event-country">${escapeHtml(event.country || "—")}</span>
        <div class="event-main">
          <div class="event-title-row"><strong>${escapeHtml(event.title)}</strong><span class="event-level ${level.className}">${level.text}</span></div>
          ${impact ? `<small class="event-impact">影響市場：${escapeHtml(impact)}</small>` : ""}
          ${event.comment ? `<p class="event-comment">${escapeHtml(event.comment)}</p>` : ""}
        </div>
        ${hasFigures ? `<div class="event-figures"><span>前回<strong>${formatNumber(event.previous,event.unit)}</strong></span><span>予想<strong>${formatNumber(event.forecast,event.unit)}</strong></span><span>結果<strong class="${event.actual != null && event.actual !== "" ? "has-actual" : ""}">${formatNumber(event.actual,event.unit)}</strong></span></div>` : '<div class="event-figures is-empty">数値発表なし</div>'}
      </article>`;
    }).join("");
  }

  function updateCountdown() {
    if (!countdown) return;
    const now = new Date();
    const upcoming = filteredEvents().map(event => ({event,dt:eventDateTime(event)})).filter(x => x.dt && x.dt > now).sort((a,b) => a.dt - b.dt)[0];
    if (upcoming) {
      const diff = upcoming.dt - now;
      const hours = Math.floor(diff / 3600000);
      const minutes = Math.max(0,Math.ceil((diff % 3600000) / 60000));
      countdown.textContent = `次のイベントまで ${hours ? `${hours}時間` : ""}${minutes}分｜${upcoming.event.time} ${upcoming.event.title}`;
      return;
    }
    if (targetDate > todayJst()) {
      const first = filteredEvents().sort((a,b) => timeToMinutes(a.time)-timeToMinutes(b.time))[0];
      countdown.textContent = first ? `次回 ${formatDate(targetDate)} ${first.time}｜${first.title}` : `次回対象日 ${formatDate(targetDate)}`;
    } else {
      countdown.textContent = allEvents.length ? "本日の時刻指定イベントは終了しました" : "イベントデータなし";
    }
  }

  function renderAll() {
    const events = filteredEvents();
    if (eventLabel) eventLabel.textContent = `重要イベント｜${formatDate(targetDate)}`;
    sourceNote();
    renderEvents(events);
    renderHeatmap(allEvents.filter(event => event.date === targetDate && event.importance >= 2));
    updateCountdown();
  }

  async function loadExternalCalendar() {
    const response = await fetch(`economic-calendar.json?ts=${Date.now()}`, {cache:"no-store"});
    if (!response.ok) throw new Error("economic-calendar.json を取得できませんでした");
    const payload = await response.json();
    const events = uniqueEvents(asArray(payload?.events).map(normalizeExternalEvent)).filter(event => event.date);
    if (!events.length) throw new Error(payload?.status === "not_configured" ? "FMP_API_KEY が未設定です" : "外部カレンダーにイベントがありません");
    sourceMeta = payload;
    sourceMode = "external";
    return events;
  }

  async function loadReportFallback() {
    const response = await fetch(`reports.json?events=${Date.now()}`, {cache:"no-store"});
    if (!response.ok) throw new Error("レポートイベントを取得できませんでした");
    const reportItems = await response.json();
    const latest = asArray(reportItems).filter(report => /^\d{4}-\d{2}-\d{2}$/.test(report?.date || "")).sort((a,b) => `${b.date} ${b.time || ""}`.localeCompare(`${a.date} ${a.time || ""}`))[0];
    const explicit = [...asArray(latest?.events),...asArray(latest?.importantEvents),...asArray(latest?.calendarEvents)];
    const events = uniqueEvents(explicit.map(event => normalizeReportEvent(event,latest?.date || todayJst())));
    sourceMode = events.length ? "report" : "none";
    return events;
  }

  async function loadEvents() {
    let events = [];
    try {
      events = await loadExternalCalendar();
    } catch (externalError) {
      console.warn("External economic calendar unavailable:", externalError);
      try {
        events = await loadReportFallback();
      } catch (fallbackError) {
        console.warn("Report event fallback unavailable:", fallbackError);
        sourceMode = "none";
      }
    }
    allEvents = events;
    targetDate = selectTargetDate(allEvents);
    renderAll();
    filter?.addEventListener("change",renderAll);
    if (timerId) clearInterval(timerId);
    timerId = setInterval(() => { updateCountdown(); renderEvents(filteredEvents()); },60000);
  }

  loadEvents();
})();
