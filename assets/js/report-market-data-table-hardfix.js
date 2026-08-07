/*
 * Hard guarantee for the WEB market report body:
 * every section titled "主要市場データ" is rendered as a table even when the
 * Google Docs source arrives as plain Japanese prose instead of a native table.
 */
(() => {
  "use strict";

  const escHtml = (value = "") => String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  function normalizeLabel(label) {
    const value = String(label || "").trim();
    if (/^金先物$/.test(value)) return "金先物";
    if (/^(WTI原油|原油|WTI)$/.test(value)) return "WTI原油";
    if (/^日経225先物/.test(value)) return "日経225先物（大阪取引所）";
    if (/^(USD\/JPY|USDJPY|ドル円)$/.test(value)) return "USD/JPY";
    if (/^(EUR\/USD|EURUSD|ユーロドル)$/.test(value)) return "EUR/USD";
    if (/^(BTCUSD|BTC\/USD)$/.test(value)) return "BTCUSD";
    return value;
  }

  function parseStandardMarketLine(line) {
    const value = String(line || "").trim();
    const match = value.match(/^(.+?)[：:]\s*(.+?)、\s*前日比\s*([^、。]+)、\s*([+-]?\d+(?:\.\d+)?%)。\s*(.*)$/);
    if (!match) return null;

    const label = normalizeLabel(match[1]);
    if (!/^(金先物|WTI原油|日経225先物（大阪取引所）|USD\/JPY|EUR\/USD|BTCUSD)$/.test(label)) return null;

    return [
      label,
      match[2].trim() || "—",
      match[3].trim() || "—",
      match[4].trim() || "—",
      match[5].trim() || "—"
    ];
  }

  function parseCompositeIndicators(line) {
    const value = String(line || "").trim();
    const rows = [];

    const vix = value.match(/VIXは前営業日ベース\s*([0-9]+(?:\.[0-9]+)?)/);
    if (vix) rows.push(["VIX", vix[1], "—", "—", "前営業日ベース"]);

    const nikkeiVi = value.match(/日経VIは(?:\s*([0-9]{1,2}:[0-9]{2})時点)?\s*([0-9]+(?:\.[0-9]+)?)/);
    if (nikkeiVi) rows.push(["日経VI", nikkeiVi[2], "—", "—", nikkeiVi[1] ? `${nikkeiVi[1]} JST` : "取得時点値"]);

    const us10y = value.match(/米(?:国)?10年国債利回りは\s*([0-9]+(?:\.[0-9]+)?%)(前後)?/);
    if (us10y) rows.push(["米10年国債利回り", us10y[1], "—", "—", us10y[2] ? "前後" : "取得時点値"]);

    const jp10y = value.match(/日本10年国債利回りは\s*([0-9]+(?:\.[0-9]+)?%)([^。]*)/);
    if (jp10y) rows.push(["日本10年国債利回り", jp10y[1], "—", "—", (jp10y[2] || "取得時点値").trim().replace(/^まで/, "") || "取得時点値"]);

    let trailing = "";
    if (rows.length) {
      const sentences = value.split("。").map((item) => item.trim()).filter(Boolean);
      if (sentences.length >= 3) trailing = sentences.slice(2).join("。") + "。";
    }

    return { rows, trailing };
  }

  function sourceLines(section) {
    const contentNodes = [...section.children].filter((node) => node.tagName !== "H2");
    const lines = [];
    for (const node of contentNodes) {
      const raw = node.textContent || "";
      raw.split(/\n+/).forEach((part) => {
        const value = part.trim();
        if (value) lines.push(value);
      });
    }
    return lines;
  }

  function buildTable(rows) {
    const headers = ["市場・指標", "値", "前日比", "騰落率", "取得時刻・注記"];
    return `<div class="market-table-wrap"><table class="market-table market-table-five intraday-market-table">
      <thead><tr>${headers.map((cell) => `<th>${escHtml(cell)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((row) => `<tr>
        <th scope="row">${escHtml(row[0] || "—")}</th>
        <td>${escHtml(row[1] || "—")}</td>
        <td>${escHtml(row[2] || "—")}</td>
        <td>${escHtml(row[3] || "—")}</td>
        <td>${escHtml(row[4] || "—")}</td>
      </tr>`).join("")}</tbody>
    </table></div>`;
  }

  function convertSection(section) {
    if (!section || section.dataset.marketTableHardfixed === "1") return;
    const heading = section.querySelector(":scope > h2");
    if (!heading || !/主要市場データ/.test(heading.textContent || "")) return;

    // Leave already-correct tables alone.
    if (section.querySelector("table.market-table")) {
      section.dataset.marketTableHardfixed = "1";
      return;
    }

    const lines = sourceLines(section);
    if (!lines.length) return;

    const rows = [];
    const notes = [];
    let intro = "";

    for (const line of lines) {
      const standard = parseStandardMarketLine(line);
      if (standard) {
        rows.push(standard);
        continue;
      }

      const composite = parseCompositeIndicators(line);
      if (composite.rows.length) {
        rows.push(...composite.rows);
        if (composite.trailing) notes.push(composite.trailing);
        continue;
      }

      if (!intro && /レポート作成時点|スナップショット|同時刻値|取得時刻/.test(line)) {
        intro = line;
      } else {
        notes.push(line);
      }
    }

    // Avoid touching unrelated prose if parsing failed.
    if (rows.length < 3) return;

    [...section.children].forEach((node) => {
      if (node !== heading) node.remove();
    });

    if (intro) {
      const p = document.createElement("p");
      p.className = "market-data-intro";
      p.textContent = intro;
      section.appendChild(p);
    }

    section.insertAdjacentHTML("beforeend", buildTable(rows));

    if (notes.length) {
      const note = document.createElement("p");
      note.className = "market-data-note";
      note.textContent = notes.join(" ");
      section.appendChild(note);
    }

    section.dataset.marketTableHardfixed = "1";
  }

  function applyAll() {
    document.querySelectorAll("#app .section").forEach(convertSection);
  }

  const app = document.getElementById("app");
  if (!app) return;

  const observer = new MutationObserver(() => applyAll());
  observer.observe(app, { childList: true, subtree: true });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyAll, { once: true });
  } else {
    applyAll();
  }
})();
