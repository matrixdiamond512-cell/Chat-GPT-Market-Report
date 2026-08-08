(() => {
  "use strict";

  const STOCKS_URL = "data/stocks.json";
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

  let latestStocksPayload = null;
  let nikkeiPayload = null;
  let sectorPayload = null;
  let historyIndex = null;
  let historyPayload = null;
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
  const dateOnly = value => {
    const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
    return match ? `${match[1]}-${match[2]}-${match[3]}` : "";
  };
  const displayDate = value => {
    const date = dateOnly(value);
    return date ? date.replace(/-/g, "/") : "取得不能";
  };
  const displayDateTime = value => {
    const text = String(value || "");
    const match = text.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
    if (match) return `${match[1]}/${match[2]}/${match[3]} ${match[4]}:${match[5]}`;
    return displayDate(text);
  };

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
      .stocks-date-control{display:flex;align-items:center;justify-content:center;gap:8px;max-width:1640px;margin:0 auto 8px;padding:2px 20px 8px}
      .stocks-date-button{display:grid;place-items:center;width:42px;height:42px;border:1px solid #bfd0e9;border-radius:7px;background:#fff;color:#073674;font-size:25px;font-weight:1000;cursor:pointer}
      .stocks-date-button:disabled{color:#9aabc1;background:#f3f6fa;cursor:not-allowed}
      .stocks-date-input{width:270px;height:42px;border:1px solid #bfd0e9;border-radius:7px;background:#fff;color:#001f56;padding:0 14px;font:1000 16px/1 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans JP","Yu Gothic UI",Meiryo,sans-serif;text-align:center;color-scheme:light}
      .stocks-date-status{max-width:1640px;margin:-5px auto 10px;padding:0 20px;color:#314a6b;font-size:12px;font-weight:900;text-align:center;line-height:1.6}
      .stocks-market-date{margin-left:auto;padding:2px 8px;border:1px solid rgba(255,255,255,.7);border-radius:999px;background:rgba(255,255,255,.14);font-size:11px;font-weight:1000;white-space:nowrap}
      .stocks-card-meta{display:flex;flex-wrap:wrap;gap:6px 10px;padding:7px 12px;border-bottom:1px solid #e3ebf7;background:#f7faff;color:#52647f;font-size:11px;font-weight:900;line-height:1.45}
      .stocks-card-meta span{display:inline-flex;align-items:center;padding:2px 7px;border:1px solid #d7e2f1;border-radius:999px;background:#fff;white-space:nowrap}
      .info-card>.stocks-card-meta,.analysis-card>.stocks-card-meta,.bridge>.stocks-card-meta{margin:0 0 10px;padding:0;border:0;background:transparent}
      .info-card>.stocks-card-meta span,.analysis-card>.stocks-card-meta span,.bridge>.stocks-card-meta span{background:#f7faff}
      .stocks-history-error{border:1px dashed #d5a8aa;border-radius:7px;padding:18px;background:#fff7f7;color:#8b1b25;font-weight:900}
      @media(max-width:760px){.sector-mover-source{display:none}.stocks-date-control{padding-left:12px;padding-right:12px}.stocks-date-input{width:min(68vw,270px)}.panel-title{flex-wrap:wrap}.stocks-market-date{margin-left:34px}.stocks-card-meta{padding-left:10px;padding-right:10px}}
    `;
    document.head.appendChild(style);
  }

  async function loadJson(url) {
    const response = await fetch(`${url}${url.includes("?") ? "&" : "?"}ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`${url} HTTP ${response.status}`);
    return response.json();
  }

  function marketDatesOf(data) {
    const explicit = data?.marketDates || {};
    return {
      us: explicit.us || data?.marketInternals?.us?.dataDate || data?.usBreadth?.marketDate || "",
      japan: explicit.japan || data?.marketInternals?.japan?.dataDate || data?.nikkeiMetricsAsOf || ""
    };
  }

  function mainMarketPanels() {
    const section = Array.from(document.querySelectorAll("section"))
      .find(node => (node.getAttribute("aria-label") || "").includes("主要指数と市場内部"));
    return section ? Array.from(section.querySelectorAll("article.panel")) : [];
  }

  function applyMarketDateLabels(data) {
    if (!data) return false;
    const dates = marketDatesOf(data);
    const panels = mainMarketPanels();
    if (panels.length < 2) return false;
    [[panels[0], dates.us, "米国市場"], [panels[1], dates.japan, "東京市場"]].forEach(([panel, date, label]) => {
      const title = panel?.querySelector(".panel-title");
      if (!title) return;
      title.querySelector(".stocks-market-date")?.remove();
      title.insertAdjacentHTML("beforeend", `<span class="stocks-market-date">${esc(label)} 基準日 ${esc(displayDate(date))}</span>`);
    });
    const status = document.querySelector("[data-updated]");
    if (status) {
      const prefix = requestedDate ? `保存日 ${displayDate(requestedDate)}` : `更新日時 ${displayDateTime(data.updatedAt || data.savedAt || data.generatedAt)}`;
      status.textContent = `${prefix} / 米国市場 ${displayDate(dates.us)} / 東京市場 ${displayDate(dates.japan)}`;
    }
    const calendarStatus = document.querySelector(".stocks-date-status");
    if (calendarStatus) {
      calendarStatus.textContent = `${requestedDate ? `保存済み株式市場分析 ${displayDate(requestedDate)}` : "最新表示"}｜米国市場データ ${displayDate(dates.us)}｜東京市場データ ${displayDate(dates.japan)}`;
    }
    return true;
  }

  function metricHtml(name, item) {
    const value = item?.display || item?.raw || "取得不能";
    const change = item?.change || "—";
    const evaluation = item?.evaluation || `基準日 ${nikkeiPayload?.dataAsOf || "取得不能"}`;
    return `<tr data-stock-metric="${esc(name)}"><td>${esc(name)}</td><td class="num ${cls(value)}">${esc(value)}</td><td class="num ${cls(change)}">${esc(change)}</td><td class="comment">${esc(evaluation)}</td></tr>`;
  }

  function japanMarketBody() {
    const panels = mainMarketPanels();
    const panel = panels.find(node => /日本/.test(node.querySelector(".panel-title")?.textContent || "")) || panels[1];
    return panel?.querySelector("tbody") || null;
  }

  function applyNikkeiMetrics() {
    if (requestedDate || !nikkeiPayload?.metrics || busy) return false;
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
    if (requestedDate || !sectorPayload?.markets || busy) return false;
    const section = Array.from(document.querySelectorAll("section"))
      .find(node => (node.getAttribute("aria-label") || "").includes("セクター・業種"));
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

  function firstItemDate(source) {
    const pools = [source?.gainers, source?.losers, source?.top, source?.bottom, source?.rows, source?.items];
    for (const pool of pools) {
      for (const item of arr(pool)) {
        if (item && typeof item === "object") {
          const value = item.asOf || item.dataDate || item.marketDate || item.date;
          if (value) return value;
        }
      }
    }
    return "";
  }

  function metaOf(source, marketKey, data, updateOverride) {
    const marketDates = marketDatesOf(data || {});
    const pageBasis = data?.dataAsOf || data?.dataDate || data?.asOf || data?.marketDate || requestedDate || "";
    const directBasis = source?.dataDate || source?.asOf || source?.dataAsOf || source?.marketDate || source?.date || firstItemDate(source);
    const basis = directBasis || (marketKey ? marketDates[marketKey] : pageBasis);
    const update = source?.updatedAt || source?.generatedAt || source?.savedAt || updateOverride || data?.updatedAt || data?.savedAt || data?.generatedAt || "";
    return {
      basis: displayDate(basis),
      updated: displayDateTime(update),
      basisFallback: !directBasis && Boolean(basis)
    };
  }

  function metaHtml(meta) {
    const basisLabel = meta.basisFallback && meta.basis !== "取得不能" ? `${meta.basis}（ページ基準）` : meta.basis;
    return `<span>基準日 ${esc(basisLabel)}</span><span>更新日時 ${esc(meta.updated)}</span>`;
  }

  function upsertCardMeta(card, source, marketKey, data, updateOverride) {
    if (!card) return false;
    const html = metaHtml(metaOf(source || {}, marketKey, data || {}, updateOverride));
    let node = Array.from(card.children || []).find(child => child.classList?.contains("stocks-card-meta"));
    if (!node) {
      node = document.createElement("div");
      node.className = "stocks-card-meta";
      const heading = Array.from(card.children || []).find(child => /^H[1-6]$/.test(child.tagName || ""));
      if (heading) heading.insertAdjacentElement("afterend", node);
      else card.insertAdjacentElement("afterbegin", node);
    }
    if (node.innerHTML !== html) node.innerHTML = html;
    return true;
  }

  function sectionPanels(label) {
    const section = Array.from(document.querySelectorAll("section"))
      .find(node => (node.getAttribute("aria-label") || "").includes(label));
    return section ? Array.from(section.querySelectorAll(":scope > article.panel")) : [];
  }

  function applySessionMeta(data) {
    const cards = Array.from(document.querySelectorAll(".session-grid > .session-panel"));
    if (!cards.length) return;
    const sources = [
      data?.sessionAnalysis?.tokyoOpen || data?.marketInternals?.japan || {},
      data?.sessionAnalysis?.usPremarket || data?.marketInternals?.us || {}
    ];
    const markets = ["japan", "us"];
    cards.slice(0, 2).forEach((card, index) => {
      const meta = metaOf(sources[index], markets[index], data || {});
      let node = card.querySelector(".session-meta");
      if (!node) {
        node = document.createElement("div");
        node.className = "session-meta";
        card.querySelector(".session-header")?.insertAdjacentElement("afterend", node);
      }
      const html = `<span>基準日 ${esc(meta.basisFallback && meta.basis !== "取得不能" ? `${meta.basis}（ページ基準）` : meta.basis)}</span><span>更新日時 ${esc(meta.updated)}</span>`;
      if (node && node.innerHTML !== html) node.innerHTML = html;
    });
  }

  function applyAllCardMeta(data) {
    if (!data) return false;
    applySessionMeta(data);

    const pairSpecs = [
      ["主要指数と市場内部", [data?.marketInternals?.us, data?.marketInternals?.japan], ["us", "japan"], [null, null]],
      ["大幅上昇・下落銘柄", [data?.movers?.us, data?.movers?.japan], ["us", "japan"], [null, null]],
      ["セクター・業種", [requestedDate ? data?.sectors?.us : (sectorPayload?.markets?.us || data?.sectors?.us), requestedDate ? data?.sectors?.japan : (sectorPayload?.markets?.japan || data?.sectors?.japan)], ["us", "japan"], [requestedDate ? null : sectorPayload?.generatedAt, requestedDate ? null : sectorPayload?.generatedAt]],
      ["指数寄与度", [data?.contributions?.us, data?.contributions?.japan], ["us", "japan"], [null, null]]
    ];
    pairSpecs.forEach(([label, sources, markets, updates]) => {
      const panels = sectionPanels(label);
      panels.slice(0, 2).forEach((panel, index) => upsertCardMeta(panel, sources[index] || {}, markets[index], data, updates[index]));
    });

    const judgementItems = [data?.judgement?.conclusion, data?.judgement?.reason, data?.judgement?.risk, data?.judgement?.watch];
    Array.from(document.querySelectorAll(".bottom-cards > .info-card")).forEach((card, index) => {
      upsertCardMeta(card, judgementItems[index] || {}, null, data);
    });

    Array.from(document.querySelectorAll(".analysis-grid > .analysis-card")).forEach((card, index) => {
      upsertCardMeta(card, arr(data?.analysisCards)[index] || {}, null, data);
    });

    const bridge = document.querySelector(".bridge");
    if (bridge) upsertCardMeta(bridge, data?.sessionAnalysis?.bridge || {}, null, data);
    return true;
  }

  function applyLatest() {
    if (requestedDate) return;
    applyNikkeiMetrics();
    applySectors();
    applyMarketDateLabels(latestStocksPayload);
    applyAllCardMeta(latestStocksPayload);
  }

  const panel = (s, body) => `<article class="panel"><h2 class="panel-title"><span class="flag">${flag(s?.flag)}</span>${esc((s?.title || "取得不能").replace("（上昇率TOP5）", ""))}</h2>${body}</article>`;
  const table = (cols, rows, cn = "") => `<div class="table-wrap"><table class="${cn}"><thead><tr>${arr(cols).map(x => `<th>${esc(x)}</th>`).join("")}</tr></thead><tbody>${arr(rows).map(row => `<tr>${arr(row).map((cell, index) => `<td class="${index === 1 || index === 2 ? `num ${cls(cell)}` : index === 3 ? "comment" : ""}">${esc(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  const market = s => panel(s, table(s?.columns, s?.rows, "market-table"));
  const rankRows = (items, type) => arr(items).map(item => `<tr>${type === "mover" ? `<td class="num">${esc(item.rank)}</td>` : ""}<td>${esc(item.name)}${item.reason ? `<span class="reason">${esc(item.reason)}</span>` : ""}</td>${type === "mover" ? `<td class="num">${esc(item.close)}</td><td class="num ${cls(item.change)}">${esc(item.change)}</td>` : `<td class="num ${cls(item.contribution)}">${esc(item.contribution)}</td>`}</tr>`).join("");
  const moverTable = (title, items, kind) => `<div class="table-wrap"><h3 class="mini-title ${kind}">${title}</h3><table class="rank-table"><thead><tr><th>順位</th><th>銘柄名</th><th>終値</th><th>騰落率</th></tr></thead><tbody>${rankRows(items, "mover")}</tbody></table></div>`;
  const movers = s => panel(s, `<div class="panel-body split">${moverTable("大幅上昇（上位5）", s?.gainers, "up")}${moverTable("大幅下落（下位5）", s?.losers, "down")}</div>`);
  const snapshotSector = s => panel(s, `<div class="panel-body">${sectorGroup(s?.gainers || s?.rows, "up", s?.sourceLabel)}${sectorGroup(s?.losers, "down", s?.sourceLabel)}</div>`);
  const contributionTable = (title, items, kind) => `<div class="table-wrap"><h3 class="mini-title ${kind}">${title}</h3><table class="rank-table"><thead><tr><th>銘柄名</th><th>寄与度</th></tr></thead><tbody>${rankRows(items, "contribution")}</tbody></table></div>`;
  const contributions = s => panel(s, `<div class="panel-body split">${contributionTable("寄与度上位 5 銘柄", s?.top, "up")}${contributionTable("寄与度下位 5 銘柄", s?.bottom, "down")}</div>`);
  const listHtml = items => `<ul>${arr(items).map(item => `<li>${esc(item)}</li>`).join("")}</ul>`;
  const card = (item, className, icon, body) => `<article class="info-card ${className}"><h2><span class="icon">${icon}</span>${esc(item?.title)}</h2>${body}</article>`;
  const judgement = value => { const conclusion = value?.conclusion || {}; return `<section class="bottom-cards">${card(conclusion, "conclusion", "✓", `<p class="conclusion-main">${esc(conclusion.main)}</p><p class="conclusion-sub">${esc(conclusion.sub)}</p>`)}${card(value?.reason, "reason-card", "▮", listHtml(value?.reason?.items))}${card(value?.risk, "risk", "!", listHtml(value?.risk?.items))}${card(value?.watch, "watch", "◎", listHtml(value?.watch?.items))}</section>`; };
  const analyses = items => `<section class="analysis-grid">${arr(items).map(item => `<article class="analysis-card"><h2>${esc(item.title)}</h2>${item.items ? listHtml(item.items) : `<p>${esc(item.body)}</p>`}</article>`).join("")}</section>`;

  function renderSnapshot(data) {
    const root = document.querySelector("[data-stocks-root]");
    if (!root) return;
    root.innerHTML = `<section class="pair-grid" aria-label="主要指数と市場内部">${market(data?.marketInternals?.us)}${market(data?.marketInternals?.japan)}</section><section class="pair-grid" aria-label="大幅上昇・下落銘柄">${movers(data?.movers?.us)}${movers(data?.movers?.japan)}</section><section class="pair-grid" aria-label="セクター・業種">${snapshotSector(data?.sectors?.us)}${snapshotSector(data?.sectors?.japan)}</section><section class="pair-grid" aria-label="指数寄与度">${contributions(data?.contributions?.us)}${contributions(data?.contributions?.japan)}</section>${judgement(data?.judgement)}${analyses(data?.analysisCards)}<p class="note">${esc(data?.note)}</p>`;
    applyMarketDateLabels(data);
    applyAllCardMeta(data);
  }

  function entries() {
    return arr(historyIndex?.dates)
      .map(item => typeof item === "string" ? { date: item } : item)
      .filter(item => /^\d{4}-\d{2}-\d{2}$/.test(item.date || ""))
      .sort((a, b) => String(b.date).localeCompare(String(a.date)));
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
    const fallbackDate = marketDatesOf(latestStocksPayload).japan || marketDatesOf(latestStocksPayload).us || "";
    const selected = requestedDate || historyIndex?.latestDate || list[0]?.date || fallbackDate;
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
    root.parentNode.insertBefore(status, root);
    control.querySelector("[data-stock-prev]")?.addEventListener("click", () => go(older));
    control.querySelector("[data-stock-next]")?.addEventListener("click", () => go(newer));
    control.querySelector("[data-stock-date]")?.addEventListener("change", event => go(event.target.value));
  }

  async function loadHistory() {
    if (!requestedDate) return false;
    const root = document.querySelector("[data-stocks-root]");
    try {
      historyPayload = await loadJson(`${HISTORY_BASE_URL}${requestedDate}.json`);
      renderSnapshot(historyPayload);
      return true;
    } catch (error) {
      if (root) root.innerHTML = `<div class="stocks-history-error">${displayDate(requestedDate)}の保存データがありません。理由：${esc(error.message)}</div>`;
      return false;
    }
  }

  async function init() {
    injectStyles();
    const results = await Promise.allSettled([
      loadJson(STOCKS_URL),
      loadJson(NIKKEI_URL),
      loadJson(SECTOR_URL),
      loadJson(HISTORY_INDEX_URL)
    ]);
    if (results[0].status === "fulfilled") latestStocksPayload = results[0].value;
    if (results[1].status === "fulfilled") nikkeiPayload = results[1].value;
    if (results[2].status === "fulfilled") sectorPayload = results[2].value;
    if (results[3].status === "fulfilled") historyIndex = results[3].value;

    injectCalendar();
    if (requestedDate) {
      await loadHistory();
      applyMarketDateLabels(historyPayload);
      applyAllCardMeta(historyPayload);
      return;
    }

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
