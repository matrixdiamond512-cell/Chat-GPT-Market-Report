(() => {
  "use strict";

  const DATA_URL = "data/sector-performance.json";
  const NIKKEI_URL = "data/nikkei-metrics.json";
  const HISTORY_INDEX_URL = "data/history/stocks/index.json";
  const HISTORY_BASE_URL = "data/history/stocks/";
  const STYLE_ID = "stock-sector-decliners-style";
  const params = new URLSearchParams(window.location.search);
  const requestedDate = /^\d{4}-\d{2}-\d{2}$/.test(params.get("date") || "") ? params.get("date") : "";

  let payload = null;
  let nikkeiPayload = null;
  let historyIndex = null;
  let applying = false;

  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[char]));

  const arr = value => Array.isArray(value) ? value : [];
  const rows = value => Array.isArray(value) ? value.slice(0, 5) : [];
  const number = value => {
    const match = String(value ?? "").replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
    return match ? Number(match[0]) : 0;
  };
  const cls = value => {
    const text = String(value ?? "");
    if (/^\s*\+|上昇|買い|改善|強/.test(text)) return "up";
    if (/^\s*-|^\s*−|下落|売り|悪化|弱/.test(text)) return "down";
    return "muted";
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

  function toJpDate(date) {
    return String(date || "").replace(/-/g, "/");
  }

  function dateEntries() {
    return arr(historyIndex && historyIndex.dates)
      .map(item => typeof item === "string" ? { date: item } : item)
      .filter(item => /^\d{4}-\d{2}-\d{2}$/.test(item.date || ""))
      .sort((a, b) => String(b.date).localeCompare(String(a.date)));
  }

  function navigateDate(date) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date || "")) return;
    const next = new URL(window.location.href);
    next.searchParams.set("date", date);
    window.location.href = next.toString();
  }

  function injectCalendar() {
    const root = document.querySelector("[data-stocks-root]");
    if (!root || document.querySelector("[data-stocks-calendar]")) return;
    const entries = dateEntries();
    const selected = requestedDate || historyIndex?.latestDate || entries[0]?.date || "";
    const index = entries.findIndex(item => item.date === selected);
    const older = index >= 0 ? entries[index + 1]?.date : entries.find(item => item.date < selected)?.date;
    const newer = index > 0 ? entries[index - 1]?.date : entries.slice().reverse().find(item => item.date > selected)?.date;

    const control = document.createElement("section");
    control.className = "stocks-date-control";
    control.dataset.stocksCalendar = "1";
    control.setAttribute("aria-label", "株式市場分析の日付選択");
    control.innerHTML = `
      <button type="button" class="stocks-date-button" data-stock-prev aria-label="前の保存日" ${older ? "" : "disabled"}>‹</button>
      <input type="date" class="stocks-date-input" data-stock-date aria-label="表示日" value="${esc(selected)}">
      <button type="button" class="stocks-date-button" data-stock-next aria-label="次の保存日" ${newer ? "" : "disabled"}>›</button>
    `;
    root.parentNode.insertBefore(control, root);

    const status = document.createElement("div");
    status.className = "stocks-date-status";
    status.dataset.stocksDateStatus = "1";
    status.textContent = requestedDate
      ? `保存済み株式市場分析：${toJpDate(selected)}`
      : entries.length
        ? `最新表示。保存済み履歴はカレンダーから選択できます（最新保存日 ${toJpDate(selected)}）`
        : "履歴データを準備中です。";
    root.parentNode.insertBefore(status, root);

    control.querySelector("[data-stock-prev]")?.addEventListener("click", () => navigateDate(older));
    control.querySelector("[data-stock-next]")?.addEventListener("click", () => navigateDate(newer));
    control.querySelector("[data-stock-date]")?.addEventListener("change", event => navigateDate(event.target.value));
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

  function table(columns, tableRows, className) {
    return `<div class="table-wrap"><table class="${className || ""}">
      <thead><tr>${arr(columns).map(col => `<th>${esc(col)}</th>`).join("")}</tr></thead>
      <tbody>${arr(tableRows).map(row => `<tr>${arr(row).map((cell, index) => `<td class="${index === 1 || index === 2 ? `num ${cls(cell)}` : index === 3 ? "comment" : ""}">${esc(cell)}</td>`).join("")}</tr>`).join("")}</tbody>
    </table></div>`;
  }

  function panel(section, body) {
    const safe = section || {};
    const flag = safe.flag === "US" ? "🇺🇸" : safe.flag === "JP" ? "🇯🇵" : "";
    return `<article class="panel"><h2 class="panel-title"><span class="flag">${flag}</span>${esc(safe.title || "取得不能")}</h2>${body}</article>`;
  }

  function marketPanel(section) {
    return panel(section, table(section?.columns, section?.rows, "market-table"));
  }

  function rankRows(items, type) {
    return arr(items).map(item => `<tr>
      ${type === "mover" ? `<td class="num">${esc(item.rank)}</td>` : ""}
      <td>${esc(item.name)}${item.reason ? `<span class="reason">${esc(item.reason)}</span>` : ""}</td>
      ${type === "mover" ? `<td class="num">${esc(item.close)}</td><td class="num ${cls(item.change)}">${esc(item.change)}</td>` : `<td class="num ${cls(item.contribution)}">${esc(item.contribution)}</td>`}
    </tr>`).join("");
  }

  function moverTable(title, items, kind) {
    return `<div class="table-wrap"><h3 class="mini-title ${kind}">${esc(title)}</h3><table class="rank-table"><thead><tr><th>順位</th><th>銘柄名</th><th>終値</th><th>騰落率</th></tr></thead><tbody>${rankRows(items, "mover")}</tbody></table></div>`;
  }

  function moverPanel(section) {
    const safe = section || {};
    return panel(safe, `<div class="panel-body split">${moverTable("大幅上昇（上位5）", safe.gainers, "up")}${moverTable("大幅下落（下位5）", safe.losers, "down")}</div>`);
  }

  function historySectorPanel(section) {
    const safe = section || {};
    return panel(safe, `<div class="panel-body">${groupHtml(safe.gainers || safe.rows, "up", safe.sourceLabel)}${groupHtml(safe.losers, "down", safe.sourceLabel)}</div>`);
  }

  function contributionTable(title, items, kind) {
    return `<div class="table-wrap"><h3 class="mini-title ${kind}">${esc(title)}</h3><table class="rank-table"><thead><tr><th>銘柄名</th><th>寄与度</th></tr></thead><tbody>${rankRows(items, "contribution")}</tbody></table></div>`;
  }

  function contributionPanel(section) {
    const safe = section || {};
    return panel(safe, `<div class="panel-body split">${contributionTable("寄与度上位 5 銘柄", safe.top, "up")}${contributionTable("寄与度下位 5 銘柄", safe.bottom, "down")}</div>`);
  }

  function list(items) {
    return `<ul>${arr(items).map(item => `<li>${esc(item)}</li>`).join("")}</ul>`;
  }

  function infoCard(item, className, icon, body) {
    const safe = item || {};
    return `<article class="info-card ${className}"><h2><span class="icon">${esc(icon)}</span>${esc(safe.title || "取得不能")}</h2>${body}</article>`;
  }

  function judgementCards(judgement) {
    const j = judgement || {};
    const conclusion = j.conclusion || {};
    return `<section class="bottom-cards" aria-label="株式市場の判断">
      ${infoCard(conclusion, "conclusion", "✓", `<p class="conclusion-main">${esc(conclusion.main || "取得不能")}</p><p class="conclusion-sub">${esc(conclusion.sub || "")}</p>`)}
      ${infoCard(j.reason, "reason-card", "▮", list(j.reason?.items))}
      ${infoCard(j.risk, "risk", "!", list(j.risk?.items))}
      ${infoCard(j.watch, "watch", "◎", list(j.watch?.items))}
    </section>`;
  }

  function analysisCards(cards) {
    return `<section class="analysis-grid" aria-label="需給・シナリオ">${arr(cards).map(card => `<article class="analysis-card"><h2>${esc(card.title)}</h2>${card.items ? list(card.items) : `<p>${esc(card.body)}</p>`}</article>`).join("")}</section>`;
  }

  function renderHistory(data) {
    const root = document.querySelector("[data-stocks-root]");
    const updatedNode = document.querySelector("[data-updated]");
    if (!root) return;
    document.body.dataset.stocksHistory = requestedDate;
    document.title = `株式市場分析｜${toJpDate(requestedDate)}｜WEBマーケットレポート`;
    if (updatedNode) {
      updatedNode.textContent = `表示日：${toJpDate(requestedDate)} / 保存時更新：${data.updatedAt || data.historyGeneratedAt || "取得不能"} / データ状態：履歴保存済み`;
    }
    root.innerHTML = `
      <section class="pair-grid" aria-label="主要指数と市場内部">
        ${marketPanel(data.marketInternals?.us)}
        ${marketPanel(data.marketInternals?.japan)}
      </section>
      <section class="pair-grid" aria-label="大幅上昇・下落銘柄">
        ${moverPanel(data.movers?.us)}
        ${moverPanel(data.movers?.japan)}
      </section>
      <section class="pair-grid" aria-label="セクター・業種">
        ${historySectorPanel(data.sectors?.us)}
        ${historySectorPanel(data.sectors?.japan)}
      </section>
      <section class="pair-grid" aria-label="指数寄与度">
        ${contributionPanel(data.contributions?.us)}
        ${contributionPanel(data.contributions?.japan)}
      </section>
      ${judgementCards(data.judgement)}
      ${analysisCards(data.analysisCards)}
      <p class="note">${esc(data.note || `株式市場分析の保存履歴（${toJpDate(requestedDate)}）`)}</p>
    `;
  }

  async function loadHistoryIndex() {
    try {
      const response = await fetch(`${HISTORY_INDEX_URL}?ts=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`history index HTTP ${response.status}`);
      historyIndex = await response.json();
    } catch (error) {
      console.error("stock history index load failed", error);
      historyIndex = { latestDate: requestedDate || "", dates: requestedDate ? [{ date: requestedDate }] : [] };
    }
    injectCalendar();
  }

  async function loadHistoricalPage() {
    const root = document.querySelector("[data-stocks-root]");
    try {
      const response = await fetch(`${HISTORY_BASE_URL}${requestedDate}.json?ts=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`履歴データ HTTP ${response.status}`);
      const data = await response.json();
      renderHistory(data);
    } catch (error) {
      if (root) root.innerHTML = `<div class="stocks-history-error">${toJpDate(requestedDate)}の株式市場分析は保存されていません。カレンダーで保存済みの日付を選択してください。理由：${esc(error.message)}</div>`;
      const updatedNode = document.querySelector("[data-updated]");
      if (updatedNode) updatedNode.textContent = `表示日：${toJpDate(requestedDate)} / データ状態：履歴なし`;
    }
  }

  function applyLatestOverlays() {
    if (requestedDate || applying) return;
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

  async function loadLatestOverlays() {
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
    applyLatestOverlays();
  }

  async function init() {
    injectStyle();
    await loadHistoryIndex();
    if (requestedDate) await loadHistoricalPage();
    else await loadLatestOverlays();
  }

  if (!requestedDate) {
    new MutationObserver(applyLatestOverlays).observe(document.documentElement, { childList: true, subtree: true });
    setInterval(loadLatestOverlays, 15 * 60 * 1000);
  }
  window.addEventListener("DOMContentLoaded", init);
})();