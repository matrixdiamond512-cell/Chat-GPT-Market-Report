(() => {
  "use strict";

  const DATA_URL = "data/sector-performance.json";
  const STYLE_ID = "stock-sector-decliners-style";
  let payload = null;
  let applying = false;

  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[char]));

  const rows = value => Array.isArray(value) ? value.slice(0, 5) : [];
  const number = value => {
    const match = String(value ?? "").replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
    return match ? Number(match[0]) : 0;
  };

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      .sector-mover-group + .sector-mover-group{margin-top:12px;padding-top:12px;border-top:2px solid #dce5f2}
      .sector-mover-heading{display:flex;align-items:center;justify-content:space-between;margin:0 0 4px;padding:2px 0 5px;font-size:14px;font-weight:1000}
      .sector-mover-heading.up{color:#008453}.sector-mover-heading.down{color:#e00022}
      .sector-mover-source{color:#68758a;font-size:10.5px;font-weight:800}
      .sector-row .bar.down-bar,.sector-row .bar.jp.down-bar{background:linear-gradient(90deg,#d60021,#f15b70)}
      .sector-data-missing{margin:8px 0;padding:10px;border:1px dashed #b8c8df;border-radius:6px;background:#f8fbff;color:#49617e;font-size:12px;font-weight:850}
      @media(max-width:760px){.sector-mover-source{display:none}}
    `;
    document.head.appendChild(style);
  }

  function formatChange(item) {
    if (item.change) return String(item.change);
    if (item.changePct == null || item.changePct === "") return "取得不能";
    const value = Number(item.changePct);
    if (!Number.isFinite(value)) return String(item.changePct);
    return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
  }

  function groupHtml(items, kind, sourceLabel) {
    const list = rows(items);
    const title = kind === "down" ? "下落率TOP5" : "上昇率TOP5";
    if (!list.length) {
      return `<div class="sector-mover-group"><h3 class="sector-mover-heading ${kind}"><span>${title}</span></h3><p class="sector-data-missing">取得不能（${title}データがありません）</p></div>`;
    }
    const max = Math.max(...list.map(item => Math.abs(number(formatChange(item)))), 0);
    return `<div class="sector-mover-group">
      <h3 class="sector-mover-heading ${kind}"><span>${title}</span><span class="sector-mover-source">${esc(sourceLabel || "")}</span></h3>
      ${list.map((item, index) => {
        const change = formatChange(item);
        const width = max ? Math.max(8, Math.round(Math.abs(number(change)) / max * 100)) : 0;
        return `<div class="sector-row">
          <span class="rank">${index + 1}</span>
          <b>${esc(item.name)}</b>
          <span class="bar-track"><span class="bar ${kind === "down" ? "down-bar" : ""}" style="width:${width}%"></span></span>
          <b class="num ${kind === "down" ? "down" : "up"}">${esc(change)}</b>
          <span class="sector-note">${esc(item.note || "前営業日終値比")}</span>
        </div>`;
      }).join("")}
    </div>`;
  }

  function replacePanel(panel, section) {
    if (!panel || !section) return false;
    const title = panel.querySelector(".panel-title");
    const body = panel.querySelector(".panel-body");
    if (!title || !body) return false;
    const flag = section.flag === "US" ? "🇺🇸" : "🇯🇵";
    title.innerHTML = `<span class="flag">${flag}</span>${esc(section.title || "セクター・業種")}`;
    body.innerHTML = groupHtml(section.gainers, "up", section.sourceLabel) + groupHtml(section.losers, "down", section.sourceLabel);
    panel.dataset.sectorMoverApplied = String(payload.generatedAt || "1");
    return true;
  }

  function apply() {
    if (!payload || applying) return;
    const section = document.querySelector('section[aria-label="セクター・業種"]');
    if (!section) return;
    const panels = section.querySelectorAll(":scope > .panel");
    if (panels.length < 2) return;
    applying = true;
    try {
      injectStyle();
      replacePanel(panels[0], payload.markets && payload.markets.us);
      replacePanel(panels[1], payload.markets && payload.markets.japan);
    } finally {
      applying = false;
    }
  }

  async function load() {
    try {
      const response = await fetch(`${DATA_URL}?ts=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      payload = await response.json();
      apply();
    } catch (error) {
      console.error("sector performance load failed", error);
    }
  }

  new MutationObserver(apply).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("DOMContentLoaded", load);
  setInterval(load, 15 * 60 * 1000);
})();
