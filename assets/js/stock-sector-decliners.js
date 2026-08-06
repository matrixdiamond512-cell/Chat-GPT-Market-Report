(() => {
  "use strict";

  const DATA_URL = "data/sector-performance.json";
  const NIKKEI_URL = "data/nikkei-metrics.json";
  const STYLE_ID = "stock-sector-decliners-style";
  let payload = null;
  let nikkeiPayload = null;
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
      tr[data-nikkei-metric] td:first-child{color:#071f56}
      tr[data-nikkei-metric] td:nth-child(2){font-weight:1000}
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
    const applied = String(payload.generatedAt || "1");
    if (panel.dataset.sectorMoverApplied === applied && body.querySelector(".sector-mover-group")) return true;
    const flag = section.flag === "US" ? "🇺🇸" : "🇯🇵";
    title.innerHTML = `<span class="flag">${flag}</span>${esc(section.title || "セクター・業種")}`;
    body.innerHTML = groupHtml(section.gainers, "up", section.sourceLabel) + groupHtml(section.losers, "down", section.sourceLabel);
    panel.dataset.sectorMoverApplied = applied;
    return true;
  }

  function metricClass(value) {
    const text = String(value || "").trim();
    if (text.startsWith("+")) return "up";
    if (text.startsWith("-") || text.startsWith("−")) return "down";
    return "muted";
  }

  function applyNikkeiMetrics() {
    if (!nikkeiPayload || !nikkeiPayload.metrics) return;
    const section = document.querySelector('section[aria-label="主要指数と市場内部"]');
    if (!section) return;
    const panels = section.querySelectorAll(":scope > .panel");
    const panel = panels[1];
    const tbody = panel && panel.querySelector("table tbody");
    if (!tbody) return;

    const applied = String(nikkeiPayload.generatedAt || nikkeiPayload.dataAsOf || "1");
    if (panel.dataset.nikkeiMetricsApplied === applied && tbody.querySelector('tr[data-nikkei-metric]')) return;

    tbody.querySelectorAll('tr[data-nikkei-metric]').forEach(row => row.remove());
    const names = [
      "日経225予想PER",
      "日経225予想EPS",
      "日経225 25日乖離率",
      "日経225 200日乖離率"
    ];
    Array.from(tbody.querySelectorAll("tr")).forEach(row => {
      const name = row.cells[0] ? row.cells[0].textContent.trim() : "";
      if (names.includes(name)) row.remove();
    });

    const html = names.map(name => {
      const item = nikkeiPayload.metrics[name] || {};
      const value = item.display || item.raw || "取得不能";
      return `<tr data-nikkei-metric="${esc(name)}">
        <td>${esc(name)}</td>
        <td class="num ${metricClass(value)}">${esc(value)}</td>
        <td class="num muted">—</td>
        <td class="comment">${esc(item.evaluation || `基準日 ${nikkeiPayload.dataAsOf || "取得不能"}`)}</td>
      </tr>`;
    }).join("");

    const anchor = Array.from(tbody.querySelectorAll("tr")).find(row =>
      row.cells[0] && row.cells[0].textContent.trim() === "騰落レシオ（25日）"
    );
    if (anchor) anchor.insertAdjacentHTML("afterend", html);
    else tbody.insertAdjacentHTML("beforeend", html);
    panel.dataset.nikkeiMetricsApplied = applied;
  }

  function apply() {
    if (applying) return;
    applying = true;
    try {
      injectStyle();
      if (payload) {
        const section = document.querySelector('section[aria-label="セクター・業種"]');
        if (section) {
          const panels = section.querySelectorAll(":scope > .panel");
          if (panels.length >= 2) {
            replacePanel(panels[0], payload.markets && payload.markets.us);
            replacePanel(panels[1], payload.markets && payload.markets.japan);
          }
        }
      }
      applyNikkeiMetrics();
    } finally {
      applying = false;
    }
  }

  async function load() {
    const timestamp = Date.now();
    const [sectorResult, nikkeiResult] = await Promise.allSettled([
      fetch(`${DATA_URL}?ts=${timestamp}`, { cache: "no-store" }).then(response => {
        if (!response.ok) throw new Error(`sector HTTP ${response.status}`);
        return response.json();
      }),
      fetch(`${NIKKEI_URL}?ts=${timestamp}`, { cache: "no-store" }).then(response => {
        if (!response.ok) throw new Error(`nikkei HTTP ${response.status}`);
        return response.json();
      })
    ]);

    if (sectorResult.status === "fulfilled") payload = sectorResult.value;
    else console.error("sector performance load failed", sectorResult.reason);
    if (nikkeiResult.status === "fulfilled") nikkeiPayload = nikkeiResult.value;
    else console.error("nikkei metrics load failed", nikkeiResult.reason);
    apply();
  }

  new MutationObserver(apply).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("DOMContentLoaded", load);
  setInterval(load, 15 * 60 * 1000);
})();