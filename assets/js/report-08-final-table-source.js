/*
 * Rebuild the 08:00 28-item / 5-column market table from the canonical
 * final report fullText, rather than from already-rendered DOM fragments.
 * This prevents row shifts when a direction such as "ドル安・円高" is
 * rendered as an h3 by the rich-text layer.
 */
(() => {
  "use strict";

  const ITEMS = [
    "NYダウ", "NASDAQ総合", "S&P500", "Russell 2000", "日経225現物",
    "CME日経225先物・円建て", "CME日経225先物・ドル建て", "日経225先物（大阪取引所）",
    "USD/JPY", "EUR/USD", "COMEX金先物", "WTI原油", "BTCUSD", "VIX", "日経VI",
    "Fear & Greed Index", "米10年債利回り", "日本10年国債利回り", "日経225予想PER",
    "日経225 PBR", "日経225予想EPS", "日経225 25日移動平均乖離率",
    "日経225 200日移動平均乖離率", "東証プライム売買代金", "東証プライム売買高",
    "東証プライム値上がり銘柄数", "東証プライム値下がり銘柄数", "東証プライム25日騰落レシオ"
  ];

  const NUMBER_PREFIX = /^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘]\s*/;
  const esc = (value = "") => String(value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");

  function currentReport() {
    try { return selectedReport || null; } catch (error) { return null; }
  }

  function normalizeLabel(value = "") {
    const label = String(value).replace(NUMBER_PREFIX, "").trim();
    if (/^(Dow|NYダウ|ダウ|NYダウ平均)$/i.test(label)) return "NYダウ";
    if (/^(Nasdaq|NASDAQ|Nasdaq総合|NASDAQ総合)$/i.test(label)) return "NASDAQ総合";
    if (/^S&P\s*500$/i.test(label)) return "S&P500";
    if (/^Russell\s*2000$/i.test(label)) return "Russell 2000";
    if (/^(日経225現物|日経225|日経平均|日経平均現物)$/.test(label)) return "日経225現物";
    if (/^CME.*日経225先物.*円建て/.test(label)) return "CME日経225先物・円建て";
    if (/^CME.*日経225先物.*ドル建て/.test(label)) return "CME日経225先物・ドル建て";
    if (/^(日経225先物・大阪取引所|日経225先物（大阪取引所）|日経225先物\(大阪取引所\)|日経225先物)$/.test(label)) return "日経225先物（大阪取引所）";
    if (/^(USD\/JPY|USDJPY|ドル円)$/i.test(label)) return "USD/JPY";
    if (/^(EUR\/USD|EURUSD|ユーロドル)$/i.test(label)) return "EUR/USD";
    if (/^(COMEX金先物|金|金先物|ゴールド)$/.test(label)) return "COMEX金先物";
    if (/^(WTI原油|WTI|原油)$/.test(label)) return "WTI原油";
    if (/^(BTCUSD|BTC\/USD|Bitcoin|ビットコイン)$/i.test(label)) return "BTCUSD";
    if (/^VIX(?:指数)?$/i.test(label)) return "VIX";
    if (label === "日経VI") return "日経VI";
    if (/^Fear\s*&\s*Greed(?:\s*Index)?$/i.test(label)) return "Fear & Greed Index";
    if (/^(米10年債利回り|米10年債|米国10年債利回り|米10年国債利回り)$/.test(label)) return "米10年債利回り";
    if (/^(日本10年国債利回り|日本10年債利回り|日本10年国債)$/.test(label)) return "日本10年国債利回り";
    if (/^(日経225予想PER|日経225PER|PER)$/.test(label)) return "日経225予想PER";
    if (/^(日経225\s*PBR|日経225PBR|PBR)$/.test(label)) return "日経225 PBR";
    if (/^(日経225予想EPS|日経225EPS|EPS)$/.test(label)) return "日経225予想EPS";
    if (/^日経225\s*25日(?:移動平均)?乖離率$/.test(label)) return "日経225 25日移動平均乖離率";
    if (/^日経225\s*200日(?:移動平均)?乖離率$/.test(label)) return "日経225 200日移動平均乖離率";
    if (label === "東証プライム売買代金") return label;
    if (label === "東証プライム売買高") return label;
    if (/^(東証プライム)?値上がり銘柄数$/.test(label)) return "東証プライム値上がり銘柄数";
    if (/^(東証プライム)?値下がり銘柄数$/.test(label)) return "東証プライム値下がり銘柄数";
    if (/^(東証プライム)?25日騰落レシオ$/.test(label)) return "東証プライム25日騰落レシオ";
    return label;
  }

  function rowsFromFullText(report) {
    if (!report || report.time !== "08:00") return null;
    const text = String(report.fullText || report.rawText || report.body || "").replace(/\r/g, "");
    if (!text) return null;
    const lines = text.split("\n").map((line) => line.trim()).filter(Boolean);
    const start = lines.findIndex((line) => /主要市場データ/.test(line));
    if (start < 0) return null;
    let end = lines.findIndex((line, index) => index > start && /^3[.．]\s*/.test(line));
    if (end < 0) end = lines.length;
    const block = lines.slice(start + 1, end);
    const found = new Map();

    for (let i = 0; i < block.length; i += 1) {
      if (!NUMBER_PREFIX.test(block[i])) continue;
      const label = normalizeLabel(block[i]);
      if (!ITEMS.includes(label) || i + 4 >= block.length) continue;
      found.set(label, {
        label,
        value: block[i + 1] || "取得不能",
        change: block[i + 2] || "—",
        rate: block[i + 3] || "—",
        direction: block[i + 4] || "—"
      });
      i += 4;
    }
    return ITEMS.map((label) => found.get(label) || {
      label,
      value: "取得不能（最終修正版本文に該当行なし）",
      change: "—",
      rate: "—",
      direction: "取得不能"
    });
  }

  function renderRows(rows) {
    return rows.map((item) => `<tr>
      <th scope="row">${esc(item.label)}</th>
      <td>${esc(item.value)}</td>
      <td>${esc(item.change)}</td>
      <td>${esc(item.rate)}</td>
      <td>${esc(item.direction)}</td>
    </tr>`).join("");
  }

  function apply() {
    const report = currentReport();
    const rows = rowsFromFullText(report);
    if (!rows || rows.length !== 28) return;
    document.querySelectorAll("#app .section").forEach((section) => {
      const heading = section.querySelector(":scope > h2");
      if (!heading || !/主要市場データ/.test(heading.textContent || "")) return;
      const table = section.querySelector("table.morning-28-market-table, table.market-table");
      if (!table) return;
      const thead = table.querySelector("thead");
      if (thead) thead.innerHTML = "<tr><th>項目</th><th>終値・値</th><th>前日比</th><th>騰落率</th><th>方向感</th></tr>";
      const tbody = table.querySelector("tbody");
      if (tbody) tbody.innerHTML = renderRows(rows);
      table.classList.add("morning-28-market-table", "market-table-five", "final-source-table");
      table.classList.remove("market-table-seven");
      section.dataset.finalMorningSource = "fullText";
    });
  }

  const app = document.getElementById("app");
  if (!app) return;
  new MutationObserver(apply).observe(app, { childList: true, subtree: true });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply, { once: true });
  else apply();
})();
