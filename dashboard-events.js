(() => {
  const container = document.getElementById("dashboardEvents");
  if (!container) return;

  const escapeHtml = (value = "") => String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[char]));

  const asArray = value => Array.isArray(value) ? value : (value ? [value] : []);

  function normalizeEvent(event) {
    if (typeof event === "string") {
      const match = event.match(/^\s*(\d{1,2}:\d{2}|未定|終日)\s*[　 ]*(.*)$/);
      return {
        time: match ? match[1] : "—",
        title: match ? match[2] : event,
        importance: /FOMC|日銀|ECB|CPI|PCE|雇用統計|GDP|政策金利|記者会見/i.test(event) ? 3 : 2,
        impact: ""
      };
    }

    const title = event?.title || event?.name || event?.event || event?.text || event?.summary || "イベント名なし";
    const importanceRaw = event?.importance ?? event?.priority ?? event?.level ?? event?.rank ?? 2;
    let importance = Number(importanceRaw);
    if (!Number.isFinite(importance)) {
      const text = String(importanceRaw).toLowerCase();
      importance = /high|最重要|重要度3|★★★|赤/.test(text) ? 3 : /low|低|重要度1|★$/.test(text) ? 1 : 2;
    }
    return {
      time: event?.time || event?.jst || event?.datetime || event?.dateTime || "—",
      title,
      importance: Math.max(1, Math.min(3, importance)),
      impact: event?.impact || event?.markets || event?.affectedMarkets || event?.note || ""
    };
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
      container.innerHTML = '<p class="event-empty">このレポートにはイベント予定の登録がありません。</p>';
      return;
    }

    container.innerHTML = normalized.slice(0, 8).map(event => {
      const level = importanceLabel(event.importance);
      const impact = Array.isArray(event.impact) ? event.impact.join("・") : event.impact;
      return `<div class="event-row">
        <time class="event-time">${escapeHtml(event.time)}</time>
        <div class="event-main">
          <div class="event-title-row">
            <strong>${escapeHtml(event.title)}</strong>
            <span class="event-level ${level.className}">${level.text}</span>
          </div>
          ${impact ? `<small>影響：${escapeHtml(impact)}</small>` : ""}
        </div>
      </div>`;
    }).join("");
  }

  async function loadEvents() {
    try {
      const response = await fetch(`reports.json?events=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error("イベントデータを取得できませんでした");
      const reports = await response.json();
      const latest = asArray(reports)
        .filter(report => /^\d{4}-\d{2}-\d{2}$/.test(report?.date || ""))
        .sort((a, b) => `${b.date} ${b.time || ""}`.localeCompare(`${a.date} ${a.time || ""}`))[0];
      render(latest?.events || []);
    } catch (error) {
      container.innerHTML = `<p class="event-empty">${escapeHtml(error.message)}</p>`;
    }
  }

  loadEvents();
})();