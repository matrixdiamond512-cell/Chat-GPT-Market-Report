(() => {
  "use strict";

  const NIKKEI_URL = "data/nikkei-metrics.json";
  const SECTOR_URL = "data/sector-performance.json";
  const HISTORY_INDEX_URL = "data/history/stocks/index.json";
  const HISTORY_BASE_URL = "data/history/stocks/";
  const params = new URLSearchParams(location.search);
  const requestedDate = /^\d{4}-\d{2}-\d{2}$/.test(params.get("date") || "") ? params.get("date") : "";
  const METRIC_ORDER = [
    "日経VI",
    "日経225予想PER",
    "日経225予想EPS",
    "日経225 25日乖離率",
    "日経225 200日乖離率"
  ];

  let nikkeiPayload = null;
  let sectorPayload = null;
  let historyIndex = null;
  let busy = false;

  const arr = value => Array.isArray(value) ? value : [];
  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));
  const cls = value => {
    const text = String(value ?? "").trim();
    if (text.startsWith("+") || /上昇|買い|改善|強/.test(text)) return "up";
    if (text.startsWith("-") || text.startsWith("−") || /下落|売り|悪化|弱/.test(text)) return "down";
    return "muted";
  };
  const number = value => {
    const match = String(value ?? "").replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
    return match ? Number(match[0]) : 0;
  };
  const flag = code => code === "US" ? "🇺🇸" : code === "JP" ? "🇯🇵" : "";

  function injectStyles() {
    if (document.getElementById("stocks-overlay-style")) return;
    const style = document.createElement("style");
    style.id = "stocks-overlay-style";
    style.textContent = `
      tr[data-stock-metric] td:first-child{color:#071f56;font-weight:1000}
      tr[data-stock-metric] td:nth-child(2){font-weight:1000}
      .sector-mover-group+.sector-mover-group{margin-top:12px;padding-top:12px;border-top:2px solid #dce5f2}
      .sector-mover-heading{display:flex;align-items:center;justify-content:space-between;margin:0 0 6px;font-size:14px;font-weight:1000}
      .sector-mover-heading.up{color:#008453}.sector-mover-heading.down{color:#e00022}
      .sector-mover-source{color:#68758a;font-size:10.5px;font-weight:800}
      .sector-row .bar.down-bar,.sector-row .bar.jp.down-bar{background:linear-gradient(90deg,#d60021,#f15b70)}
      .sector-data-missing{margin:8px 0;padding:10px;border:1px dashed #b8c8df;border-radius:6px;background:#f8fbff;color:#49617e;font-size:12px;font-weight:850}
      .stocks-date-control{display:flex;align-items:center;justify-content:center;gap:8px;max-width:1640px;margin:0 auto 12px;padding:2px 20px 8px}
      .stocks-date-button{display:grid;place-items:center;width:42px;height:42px;border:1px solid #bfd0e9;border-radius:7px;background:#fff;color:#073674;font-size:25px;font-weight:1000;cursor:pointer}
      .stocks-date-button:disabled{color:#9aabc1;background:#f3f6fa;cursor:not-allowed}
      .stocks-date-input{width:270px;height:42px;border:1px solid #bfd0e9;border-radius:7px;background:#fff;color:#001f56;padding:0 14px;font:1000 16px/1 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans JP","Yu Gothic UI",Meiryo,sans-serif;text-align:center;color-scheme:light}
      .stocks-date-status{max-width:1640px;margin:-8px auto 10px;padding:0 20px;color:#68758a;font-size:11px;font-weight:800;text-align:center}
      .stocks-history-error{border:1px dashed #d5a8aa;border-radius:7px;padding:18px;background:#fff7f7;color:#8b1b25;font-weight:900}
      @media(max-width:760px){.sector-mover-source{display:none}.stocks-date-control{padding-left:12px;padding-right:12px}.stocks-date-input{width:min(68vw,270px)}}
    `;
    document.head.appendChild(style);
  }

  async function loadJson(url) {
    const response = await fetch(`${url}${url.includes("?") ? "&" : "?"}ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`${url} HTTP ${response.status}`);
    return response.json();
  }

  function metricHtml(name, item) {
    const value = item?.display || item?.raw || "取得不能";
    const change = item?.change || "—";
    const evaluation = item?.evaluation || `基準日 ${nikkeiPayload?.dataAsOf || "取得不能"}`;
    return `<tr data-stock-metric="${esc(name)}"><td>${esc(name)}</td><td class="num ${cls(value)}">${esc(value)}</td><td class="num ${cls(change)}">${esc(change)}</td><td class="comment">${esc(evaluation)}</td></tr>`;
  }

  function japanMarketBody() {
    const sections = Array.from(document.querySelectorAll("section"));
    const section = sections.find(node => (node.getAttribute("aria-label") || "").includes("主要指数と市場内部"));
    if (!section) return null;
    const panels = Array.from(section.querySelectorAll("article.panel"));
    const panel = panels.find(node => /日本/.test(node.querySelector(".panel-title")?.textContent || "")) || panels[1];
    return panel?.querySelector("tbody") || null;
  }

  function applyNikkeiMetrics() {
    if (!nikkeiPayload?.metrics || busy) return false;
    const tbody = japanMarketBody();
    if (!tbody) return false;
    const panel = tbody.closest(".panel");
    const key = String(nikkeiPayload.generatedAt || nikkeiPayload.dataAsOf || "1");
    if (panel?.dataset.nikkeiMetricsApplied === key && tbody.querySelector('[data-stock-metric="日経VI"]')) return true;

    busy = true;
    try {
      Array.from(tbody.rows).forEach(row => {
        const name = row.cells[0]?.textContent.trim() || "";
        if (METRIC_ORDER.includes(name) || row.hasAttribute("data-stock-metric")) row.remove();
      });

      const growthRow = Array.from(tbody.rows).find(row => row.cells[0]?.textContent.trim() === "グロース250");
      const vi = metricHtml("日経VI", nikkeiPayload.metrics["日経VI"] || {});
      if (growthRow) growthRow.insertAdjacentHTML("afterend", vi);
      else tbody.insertAdjacentHTML("afterbegin", vi);

      const valuationHtml = METRIC_ORDER.slice(1).map(name => metricHtml(name, nikkeiPayload.metrics[name] || {})).join("");
      const ratioRow = Array.from(tbody.rows).find(row => row.cells[0]?.textContent.trim() === "騰落レシオ（25日）");
      if (ratioRow) ratioRow.insertAdjacentHTML("afterend", valuationHtml);
      else tbody.insertAdjacentHTML("beforeend", valuationHtml);

      if (panel) panel.dataset.nikkeiMetricsApplied = key;
      return true;
    } finally {
      busy = false;
    }
  }

  function sectorGroup(items, kind, sourceLabel) {
    const list = arr(items).slice(0, 5);
    const title = kind === "down" ? "下落率TOP5" : "上昇率TOP5";
    if (!list.length) return `<div class="sector-mover-group"><h3 class="sector-mover-heading ${kind}">${title}</h3><p class="sector-data-missing">取得不能（${title}データがありません）</p></div>`;
    const max = Math.max(...list.map(item => Math.abs(number(item.change ?? item.changePct))), 0);
    return `<div class="sector-mover-group"><h3 class="sector-mover-heading ${kind}"><span>${title}</span><span class="sector-mover-source">${esc(sourceLabel || "")}</span></h3>${list.map((item, index) => {
      const raw = item.change ?? item.changePct;
      const change = typeof raw === "number" ? `${raw > 0 ? "+" : ""}${raw.toFixed(2)}%` : String(raw || "取得不能");
      const width = max ? Math.max(8, Math.round(Math.abs(number(change)) / max * 100)) : 0;
      return `<div class="sector-row"><span class="rank">${index + 1}</span><b>${esc(item.name)}</b><span class="bar-track"><span class="bar ${kind === "down" ? "down-bar" : ""}" style="width:${width}%"></span></span><b class="num ${kind === "down" ? "down" : "up"}">${esc(change)}</b><span class="sector-note">${esc(item.note || "前営業日終値比")}</span></div>`;
    }).join("")}</div>`;
  }

  function applySectors() {
    if (!sectorPayload?.markets || busy) return false;
    const section = Array.from(document.querySelectorAll("section")).find(node => (node.getAttribute("aria-label") || "").includes("セクター・業種"));
    if (!section) return false;
    const panels = Array.from(section.querySelectorAll("article.panel"));
    if (panels.length < 2) return false;

    ["us", "japan"].forEach((key, index) => {
      const market = sectorPayload.markets[key];
      const panel = panels[index];
      const body = panel?.querySelector(".panel-body");
      const title = panel?.querySelector(".panel-title");
      if (!market || !body || !title) return;
      const appliedKey = String(sectorPayload.generatedAt || "1");
      if (panel.dataset.sectorApplied === appliedKey && body.textContent.includes("下落率TOP5")) return;
      title.innerHTML = `<span class="flag">${flag(market.flag || (key === "us" ? "US" : "JP"))}</span>${esc(market.title || "セクター・業種")}`;
      body.innerHTML = sectorGroup(market.gainers, "up", market.sourceLabel) + sectorGroup(market.losers, "down", market.sourceLabel);
      panel.dataset.sectorApplied = appliedKey;
    });
    return true;
  }

  function applyLatest() {
    applyNikkeiMetrics();
    applySectors();
  }

  function entries() {
    return arr(historyIndex?.dates).map(item => typeof item === "string" ? { date: item } : item).filter(item => /^\d{4}-\d{2}-\d{2}$/.test(item.date || "")).sort((a, b) => String(b.date).localeCompare(String(a.date)));
  }

  function go(date) {
    if (!date) return;
    const url = new URL(location.href);
    url.searchParams.set("date", date);
    location.href = url.toString();
  }

  function injectCalendar() {
    const root = document.querySelector("[data-stocks-root]");
    if (!root || document.querySelector("[data-stocks-calendar]")) return;
    const list = entries();
    const selected = requestedDate || historyIndex?.latestDate || list[0]?.date || nikkeiPayload?.dataAsOf || "";
    const index = list.findIndex(item => item.date === selected);
    const older = index >= 0 ? list[index + 1]?.date : list.find(item => item.date < selected)?.date;
    const newer = index > 0 ? list[index - 1]?.date : list.slice().reverse().find(item => item.date > selected)?.date;
    const control = document.createElement("section");
    control.className = "stocks-date-control";
    control.dataset.stocksCalendar = "1";
    control.innerHTML = `<button type="button" class="stocks-date-button" data-stock-prev ${older ? "" : "disabled"}>‹</button><input type="date" class="stocks-date-input" data-stock-date value="${esc(selected)}"><button type="button" class="stocks-date-button" data-stock-next ${newer ? "" : "disabled"}>›</button>`;
    root.parentNode.insertBefore(control, root);
    const status = document.createElement("div");
    status.className = "stocks-date-status";
    status.textContent = requestedDate ? `保存済み株式市場分析：${selected.replace(/-/g, "/")}` : list.length ? `最新表示。保存済み履歴はカレンダーから選択できます（最新保存日 ${selected.replace(/-/g, "/")}）` : "最新表示。履歴データは次回保存から追加されます。";
    root.parentNode.insertBefore(status, root);
    control.querySelector("[data-stock-prev]")?.addEventListener("click", () => go(older));
    control.querySelector("[data-stock-next]")?.addEventListener("click", () => go(newer));
    control.querySelector("[data-stock-date]")?.addEventListener("change", event => go(event.target.value));
  }

  async function loadHistory() {
    if (!requestedDate) return false;
    const root = document.querySelector("[data-stocks-root]");
    try {
      const data = await loadJson(`${HISTORY_BASE_URL}${requestedDate}.json`);
      const markets = [data?.marketInternals?.us, data?.marketInternals?.japan];
      if (!root || !markets[1]) return false;
      root.innerHTML = `<section class="pair-grid" aria-label="主要指数と市場内部">${markets.map(market => `<article class="panel"><h2 class="panel-title"><span class="flag">${flag(market?.flag)}</span>${esc(market?.title || "取得不能")}</h2><div class="table-wrap"><table class="market-table"><thead><tr>${arr(market?.columns).map(col => `<th>${esc(col)}</th>`).join("")}</tr></thead><tbody>${arr(market?.rows).map(row => `<tr>${arr(row).map((cell, idx) => `<td class="${idx === 1 || idx === 2 ? `num ${cls(cell)}` : idx === 3 ? "comment" : ""}">${esc(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></article>`).join("")}</section>`;
      document.querySelector("[data-updated]").textContent = `表示日：${requestedDate.replace(/-/g, "/")} / データ状態：履歴保存済み`;
      return true;
    } catch (_) {
      if (root) root.insertAdjacentHTML("afterbegin", `<div class="stocks-history-error">${requestedDate.replace(/-/g, "/")}の保存データがありません。最新表示を確認してください。</div>`);
      return false;
    }
  }

  async function init() {
    injectStyles();
    const results = await Promise.allSettled([loadJson(NIKKEI_URL), loadJson(SECTOR_URL), loadJson(HISTORY_INDEX_URL)]);
    if (results[0].status === "fulfilled") nikkeiPayload = results[0].value;
    if (results[1].status === "fulfilled") sectorPayload = results[1].value;
    if (results[2].status === "fulfilled") historyIndex = results[2].value;
    injectCalendar();
    await loadHistory();
    applyLatest();

    const root = document.querySelector("[data-stocks-root]") || document.body;
    const observer = new MutationObserver(() => {
      if (!busy) setTimeout(applyLatest, 0);
    });
    observer.observe(root, { childList: true, subtree: true });

    let attempts = 0;
    const timer = setInterval(() => {
      applyLatest();
      attempts += 1;
      if (attempts >= 60) clearInterval(timer);
    }, 500);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();