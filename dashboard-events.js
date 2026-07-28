(() => {
  const container = document.getElementById("dashboardEvents");
  const filter = document.getElementById("eventMarketFilter");
  const countdown = document.getElementById("eventCountdown");
  const heatmap = document.getElementById("eventHeatmap");
  if (!container) return;

  const escapeHtml = (value = "") => String(value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[char]));
  const asArray = value => Array.isArray(value) ? value : (value ? [value] : []);
  const MARKETS = ["USD/JPY", "EUR/USD", "日経225先物", "金", "原油", "BTCUSD"];
  const HIGH_IMPACT = /FOMC|政策金利|日銀金融政策決定会合|ECB理事会|BOE政策金利|CPI|PCE|雇用統計|非農業部門雇用者数|GDP|パウエル議長会見|植田総裁会見/i;
  const EVENT_WORDS = /FOMC|金融政策決定会合|政策金利|ECB理事会|BOE|FRB議長|日銀総裁|CPI|PPI|PCE|GDP|PMI|ISM|雇用統計|失業率|JOLTS|小売売上高|耐久財受注|消費者信頼感|国債入札|要人発言|講演|記者会見|決算発表|オプションカット|NYカット|東京仲値|ゴトー日|SQ|MSQ|清算日|原油在庫統計|OPEC|EIA|API/i;
  const NON_EVENT_WORDS = /前回からの変化|材料と値動き|整合性|需給|ポジション|資金フロー|引き継ぎ|シナリオ|リスク管理|見通し|方向感|買い優勢|売り優勢|上値|下値|サポート|レジスタンス|可能性|警戒|注目点|市場は|投資家は/i;

  let allEvents = [];
  let reportDate = "";
  let timerId = null;

  function inferImpact(text) {
    const impacts = new Set();
    if (/米|FRB|FOMC|CPI|PCE|雇用|GDP|ISM|PMI|国債入札|パウエル/i.test(text)) ["USD/JPY","EUR/USD","日経225先物","金"].forEach(x => impacts.add(x));
    if (/日銀|植田|東京仲値|ゴトー日|日本|SQ|MSQ/i.test(text)) ["USD/JPY","日経225先物"].forEach(x => impacts.add(x));
    if (/ECB|ユーロ/i.test(text)) impacts.add("EUR/USD");
    if (/原油|OPEC|EIA|API|在庫/i.test(text)) ["原油","USD/JPY","日経225先物"].forEach(x => impacts.add(x));
    if (/暗号|BTC|ビットコイン|ETF/i.test(text)) impacts.add("BTCUSD");
    if (/決算|NVIDIA|Apple|Microsoft|Amazon|Meta|Tesla|半導体/i.test(text)) ["日経225先物","BTCUSD"].forEach(x => impacts.add(x));
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

  function normalizeEvent(event) {
    if (typeof event === "string") {
      const source = event.replace(/^\s*[・●■◆-]\s*/, "").trim();
      const match = source.match(/^\s*(\d{1,2}:\d{2}|未定|終日)\s*[｜|：:\-–—　 ]*\s*(.*)$/);
      const time = match ? match[1] : "—";
      const body = (match ? match[2] : source).trim();
      const pieces = body.split(/\s*[｜|]\s*/).filter(Boolean);
      const title = pieces.shift() || "";
      const comment = pieces.join("｜");
      return {
        time,
        title,
        comment,
        importance: parseImportance(null, title),
        impact: inferImpact(title)
      };
    }

    const title = String(event?.title || event?.name || event?.event || event?.text || "").trim();
    const comment = String(event?.comment || event?.note || event?.focus || event?.marketComment || event?.consensus || event?.description || "").trim();
    const impact = event?.impact || event?.markets || event?.affectedMarkets || inferImpact(title);
    return {
      time: event?.time || event?.jst || event?.datetime || event?.dateTime || "—",
      title,
      comment,
      importance: parseImportance(event?.importance ?? event?.priority ?? event?.level ?? event?.rank, title),
      impact: asArray(impact)
    };
  }

  function isActualEvent(event) {
    if (!event.title || event.title.length > 140) return false;
    const hasTime = /^(?:\d{1,2}:\d{2}|未定|終日)$/.test(String(event.time));
    const hasEventName = EVENT_WORDS.test(event.title);
    if (!hasTime && !hasEventName) return false;
    if (NON_EVENT_WORDS.test(event.title) && !hasEventName) return false;
    return true;
  }

  function extractEvents(report) {
    // 重要イベント欄は、レポートのイベント専用フィールドだけを使用する。
    // ニュース、需給、引き継ぎ、リスク管理などからの推測抽出は行わない。
    const explicit = [
      ...asArray(report?.events),
      ...asArray(report?.importantEvents),
      ...asArray(report?.calendarEvents)
    ];
    const seen = new Set();
    return explicit.map(normalizeEvent).filter(isActualEvent).filter(event => {
      const key = `${event.time}|${event.title}`.replace(/\s+/g, "").toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function importanceLabel(level) {
    return level >= 3 ? {text:"最重要",className:"event-level--high"} : level === 2 ? {text:"重要",className:"event-level--medium"} : {text:"参考",className:"event-level--low"};
  }

  function timeToMinutes(value) {
    const match = String(value).match(/(\d{1,2}):(\d{2})/);
    return match ? Number(match[1]) * 60 + Number(match[2]) : 9999;
  }

  function eventDateTime(event) {
    if (!reportDate) return null;
    const match = String(event.time).match(/(\d{1,2}):(\d{2})/);
    if (!match) return null;
    return new Date(`${reportDate}T${String(match[1]).padStart(2,"0")}:${match[2]}:00+09:00`);
  }

  function filteredEvents() {
    const selected = filter?.value || "all";
    return selected === "all" ? allEvents : allEvents.filter(event => asArray(event.impact).includes(selected));
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

  function renderEvents(events) {
    const sorted = [...events].sort((a,b) => timeToMinutes(a.time) - timeToMinutes(b.time));
    if (!sorted.length) {
      container.innerHTML = '<p class="event-empty">このレポートには、時刻・名称を確認できる重要イベントが登録されていません。</p>';
      return;
    }
    const now = new Date();
    container.innerHTML = sorted.slice(0,10).map(event => {
      const level = importanceLabel(event.importance);
      const impact = asArray(event.impact).join("・");
      const dt = eventDateTime(event);
      const status = dt && dt < now ? " is-past" : "";
      return `<div class="event-row${status}">
        <time class="event-time">${escapeHtml(event.time)}</time>
        <div class="event-main">
          <div class="event-title-row"><strong>${escapeHtml(event.title)}</strong><span class="event-level ${level.className}">${level.text}</span></div>
          ${impact ? `<small class="event-impact">影響市場：${escapeHtml(impact)}</small>` : ""}
          ${event.comment ? `<p class="event-comment">${escapeHtml(event.comment)}</p>` : ""}
        </div>
      </div>`;
    }).join("");
  }

  function updateCountdown() {
    if (!countdown) return;
    const now = new Date();
    const upcoming = filteredEvents().map(event => ({event,dt:eventDateTime(event)})).filter(x => x.dt && x.dt > now).sort((a,b) => a.dt - b.dt)[0];
    if (!upcoming) {
      countdown.textContent = allEvents.length ? "本日の時刻指定イベントは終了しました" : "イベント専用データなし";
      return;
    }
    const diff = upcoming.dt - now;
    const hours = Math.floor(diff / 3600000);
    const minutes = Math.max(0,Math.ceil((diff % 3600000) / 60000));
    countdown.textContent = `次のイベントまで ${hours ? `${hours}時間` : ""}${minutes}分｜${upcoming.event.time} ${upcoming.event.title}`;
  }

  function renderAll() {
    const events = filteredEvents();
    renderEvents(events);
    renderHeatmap(allEvents);
    updateCountdown();
  }

  async function loadEvents() {
    try {
      const response = await fetch(`reports.json?events=${Date.now()}`, {cache:"no-store"});
      if (!response.ok) throw new Error("イベントデータを取得できませんでした");
      const reportItems = await response.json();
      const latest = asArray(reportItems).filter(report => /^\d{4}-\d{2}-\d{2}$/.test(report?.date || "")).sort((a,b) => `${b.date} ${b.time || ""}`.localeCompare(`${a.date} ${a.time || ""}`))[0];
      reportDate = latest?.date || "";
      allEvents = extractEvents(latest).sort((a,b) => timeToMinutes(a.time) - timeToMinutes(b.time));
      renderAll();
      filter?.addEventListener("change",renderAll);
      if (timerId) clearInterval(timerId);
      timerId = setInterval(() => { updateCountdown(); renderEvents(filteredEvents()); },60000);
    } catch (error) {
      container.innerHTML = `<p class="event-empty">${escapeHtml(error.message)}</p>`;
      if (countdown) countdown.textContent = "イベント情報を取得できませんでした";
    }
  }

  loadEvents();
})();
