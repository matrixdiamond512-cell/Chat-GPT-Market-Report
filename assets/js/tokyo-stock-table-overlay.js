(() => {
  "use strict";

  const DATA_URL = "data/market/tokyo-stock-table.json";
  const requestedDate = new URLSearchParams(location.search).get("date") || "";
  let payload = null;
  let applying = false;

  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));

  const cls = value => {
    const text = String(value ?? "").trim();
    if (text.startsWith("+") || /上昇|買い|改善|強/.test(text)) return "up";
    if (text.startsWith("-") || text.startsWith("−") || /下落|売り|悪化|弱/.test(text)) return "down";
    return "muted";
  };

  const displayDate = value => /^\d{4}-\d{2}-\d{2}$/.test(String(value || ""))
    ? String(value).replace(/-/g, "/")
    : "取得不能";

  function eligible() {
    if (!payload?.table || !payload?.dataDate) return false;
    return !requestedDate || requestedDate === payload.snapshotDate;
  }

  function japanPanel() {
    const section = Array.from(document.querySelectorAll("section"))
      .find(node => (node.getAttribute("aria-label") || "").includes("主要指数と市場内部"));
    if (!section) return null;
    const panels = Array.from(section.querySelectorAll("article.panel"));
    return panels.find(node => /日本/.test(node.querySelector(".panel-title")?.textContent || "")) || panels[1] || null;
  }

  function tableHtml(table) {
    const columns = Array.isArray(table.columns) ? table.columns : [];
    const rows = Array.isArray(table.rows) ? table.rows : [];
    return `<div class="table-wrap"><table class="market-table"><thead><tr>${columns.map(column => `<th>${esc(column)}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${row.map((cell, index) => `<td class="${index === 1 || index === 2 ? `num ${cls(cell)}` : index === 3 ? "comment" : ""}">${esc(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  }

  function replaceDateText(node, pattern, replacement) {
    if (!node) return;
    const text = node.textContent || "";
    node.textContent = pattern.test(text) ? text.replace(pattern, replacement) : `${text} / ${replacement}`;
  }

  function apply() {
    if (!eligible() || applying) return false;
    const panel = japanPanel();
    if (!panel) return false;
    const key = `${payload.snapshotDate}|${payload.dataDate}|${payload.fetchedAt}`;
    if (panel.dataset.tokyoVerifiedOverlay === key) return true;

    applying = true;
    try {
      const title = panel.querySelector(".panel-title");
      if (title) {
        title.innerHTML = `<span class="flag">🇯🇵</span>${esc(payload.table.title || "主要指数と市場内部（日本）")}<span class="stocks-market-date">東京市場 基準日 ${esc(displayDate(payload.dataDate))}</span>`;
      }
      const oldWrap = panel.querySelector(".table-wrap");
      if (oldWrap) oldWrap.outerHTML = tableHtml(payload.table);
      else panel.insertAdjacentHTML("beforeend", tableHtml(payload.table));
      panel.dataset.tokyoVerifiedOverlay = key;

      replaceDateText(
        document.querySelector("[data-updated]"),
        /東京市場\s+\d{4}\/\d{2}\/\d{2}/,
        `東京市場 ${displayDate(payload.dataDate)}`
      );
      replaceDateText(
        document.querySelector(".stocks-date-status"),
        /東京市場データ\s+\d{4}\/\d{2}\/\d{2}/,
        `東京市場データ ${displayDate(payload.dataDate)}`
      );
      return true;
    } finally {
      applying = false;
    }
  }

  async function start() {
    try {
      const response = await fetch(`${DATA_URL}?ts=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      payload = await response.json();
      if (!eligible()) return;
      apply();
      const root = document.querySelector("[data-stocks-root]") || document.body;
      const observer = new MutationObserver(() => {
        if (!applying) setTimeout(apply, 0);
      });
      observer.observe(root, { childList: true, subtree: true });
      let attempts = 0;
      const timer = setInterval(() => {
        apply();
        attempts += 1;
        if (attempts >= 60) clearInterval(timer);
      }, 500);
    } catch (error) {
      console.error("Tokyo stock table overlay failed:", error);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
