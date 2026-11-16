/*
 * WEB market report market-data renderer.
 * 08:00: fixed 28-item morning overview, always rendered as 5 columns.
 * 07:00 historical reports: keep the legacy morning profile.
 * 12:00 / 16:00 / 21:00: fixed 6-market intraday overview.
 * Missing rows are never hidden.
 */
(() => {
  "use strict";

  const MORNING_ITEMS = [
    "NYダウ",
    "NASDAQ総合",
    "S&P500",
    "Russell 2000",
    "日経225現物",
    "CME日経225先物・円建て",
    "CME日経225先物・ドル建て",
    "日経225先物（大阪取引所）",
    "USD/JPY",
    "EUR/USD",
    "COMEX金先物",
    "WTI原油",
    "BTCUSD",
    "VIX",
    "日経VI",
    "Fear & Greed Index",
    "米10年債利回り",
    "日本10年国債利回り",
    "日経225予想PER",
    "日経225 PBR",
    "日経225予想EPS",
    "日経225 25日移動平均乖離率",
    "日経225 200日移動平均乖離率",
    "東証プライム売買代金",
    "東証プライム売買高",
    "東証プライム値上がり銘柄数",
    "東証プライム値下がり銘柄数",
    "東証プライム25日騰落レシオ"
  ];

  const LEGACY_MORNING_ITEMS = [
    "NYダウ",
    "NASDAQ総合",
    "S&P500",
    "Russell 2000",
    "日経225現物",
    "CME日経225先物・円建て",
    "日経225先物（大阪取引所）",
    "USD/JPY",
    "EUR/USD",
    "COMEX金先物",
    "WTI原油",
    "BTCUSD",
    "VIX",
    "日経VI",
    "Fear & Greed Index",
    "米10年債利回り",
    "日本10年国債利回り",
    "東証プライム値上がり銘柄数",
    "東証プライム値下がり銘柄数",
    "東証プライム25日騰落レシオ",
    "日経225予想PER",
    "日経225予想EPS",
    "日経225 25日移動平均乖離率",
    "日経225 200日移動平均乖離率"
  ];

  const INTRADAY_ITEMS = [
    "COMEX金先物",
    "WTI原油",
    "日経225先物（大阪取引所）",
    "USD/JPY",
    "EUR/USD",
    "BTCUSD"
  ];

  const ALL_ITEMS = [...new Set([...MORNING_ITEMS, ...LEGACY_MORNING_ITEMS, ...INTRADAY_ITEMS])];

  const escHtml = (value = "") => String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  function currentReportTime() {
    try {
      return String(selectedReport?.time || "");
    } catch (error) {
      return "";
    }
  }

  function allowedItems() {
    const time = currentReportTime();
    if (time === "08:00") return MORNING_ITEMS;
    if (time === "07:00") return LEGACY_MORNING_ITEMS;
    return INTRADAY_ITEMS;
  }

  function isMorning08() {
    return currentReportTime() === "08:00";
  }

  function stripRowNumber(label) {
    return String(label || "")
      .trim()
      .replace(/^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚]\s*/, "")
      .replace(/^\d+[.)．、]\s*/, "")
      .trim();
  }

  function normalizeLabel(label) {
    const value = stripRowNumber(label).replace(/\s+/g, " ");

    if (/^(Dow|NYダウ|ダウ|NYダウ平均)$/i.test(value)) return "NYダウ";
    if (/^(Nasdaq|NASDAQ|Nasdaq総合|NASDAQ総合)$/i.test(value)) return "NASDAQ総合";
    if (/^S&P\s*500$/i.test(value)) return "S&P500";
    if (/^Russell\s*2000$/i.test(value)) return "Russell 2000";

    if (/^(日経225現物|日経225|日経平均|日経平均現物)$/.test(value)) return "日経225現物";
    if (/^CME.*日経225先物.*(円建て|円)$/i.test(value)) return "CME日経225先物・円建て";
    if (/^CME.*日経225先物.*(ドル建て|ドル)$/i.test(value)) return "CME日経225先物・ドル建て";
    if (/^CME.*日経225先物|^CME日経225/i.test(value)) return "CME日経225先物・円建て";
    if (/^(日経225先物|日経225先物（大阪取引所）|日経225先物\(大阪取引所\)|日経先物|日経225先物・大阪取引所)$/.test(value)) return "日経225先物（大阪取引所）";

    if (/^(USD\/JPY|USDJPY|ドル円)$/i.test(value)) return "USD/JPY";
    if (/^(EUR\/USD|EURUSD|ユーロドル)$/i.test(value)) return "EUR/USD";
    if (/^(COMEX金先物|金|金先物|金価格|金現物|ゴールド)$/i.test(value)) return "COMEX金先物";
    if (/^(WTI原油|原油|原油価格|WTI)$/i.test(value)) return "WTI原油";
    if (/^(BTCUSD|BTC\/USD|Bitcoin|ビットコイン)$/i.test(value)) return "BTCUSD";

    if (/^VIX(?:指数)?$/i.test(value)) return "VIX";
    if (/^日経VI$/.test(value)) return "日経VI";
    if (/^Fear\s*&\s*Greed(?:\s*Index)?$/i.test(value)) return "Fear & Greed Index";
    if (/^(米10年債利回り|米10年債|米国10年債利回り|米10年国債利回り)$/.test(value)) return "米10年債利回り";
    if (/^(日本10年国債利回り|日本10年債利回り|日本10年国債)$/.test(value)) return "日本10年国債利回り";

    if (/^(日経225予想PER|日経225 PER|日経225PER|PER)$/.test(value)) return "日経225予想PER";
    if (/^(日経225\s*PBR|日経225PBR|PBR)$/.test(value)) return "日経225 PBR";
    if (/^(日経225予想EPS|日経225 EPS|日経225EPS|EPS)$/.test(value)) return "日経225予想EPS";
    if (/^(日経225 )?25日(?:移動平均)?乖離率$/.test(value)) return "日経225 25日移動平均乖離率";
    if (/^(日経225 )?200日(?:移動平均)?乖離率$/.test(value)) return "日経225 200日移動平均乖離率";

    if (/^東証プライム売買代金$/.test(value)) return "東証プライム売買代金";
    if (/^東証プライム売買高$/.test(value)) return "東証プライム売買高";
    if (/^(東証プライム値上がり銘柄数|値上がり銘柄数（プライム）|プライム値上がり銘柄数)$/.test(value)) return "東証プライム値上がり銘柄数";
    if (/^(東証プライム値下がり銘柄数|値下がり銘柄数（プライム）|プライム値下がり銘柄数)$/.test(value)) return "東証プライム値下がり銘柄数";
    if (/^(東証プライム25日騰落レシオ|25日騰落レシオ|騰落レシオ.*)$/.test(value)) return "東証プライム25日騰落レシオ";

    return value;
  }

  function emptyRow(label, reason = "主要市場データ入力に該当行なし") {
    return {
      label,
      value: `取得不能（${reason}）`,
      change: "—",
      rate: "—",
      time: "—",
      marketType: "—",
      note: "—"
    };
  }

  function row(label, value, change, rate, time, marketType, note) {
    return {
      label: normalizeLabel(label),
      value: String(value || "—").trim() || "—",
      change: String(change || "—").trim() || "—",
      rate: String(rate || "—").trim() || "—",
      time: String(time || "—").trim() || "—",
      marketType: String(marketType || "—").trim() || "—",
      note: String(note || "—").trim() || "—"
    };
  }

  function splitChangeRate(value) {
    const source = String(value || "").trim();
    const match = source.match(/^(.+?)\s*\/\s*([+-]?\d+(?:\.\d+)?%)$/);
    if (!match) return { change: source || "—", rate: "—" };
    return { change: match[1].trim() || "—", rate: match[2].trim() || "—" };
  }

  function parsePipeLine(line) {
    const source = String(line || "").trim();
    if (!/[|｜]/.test(source)) return null;

    const cells = source.split(/[|｜]/).map((cell) => cell.trim()).filter((cell, index, list) => {
      if (cell) return true;
      return index > 0 && index < list.length - 1;
    });
    if (cells.length < 2) return null;

    const first = String(cells[0] || "").trim();
    if (/^(項目|市場|市場・指標|市場・資産|指標)$/.test(stripRowNumber(first))) return null;
    if (/^[-: ]+$/.test(first)) return null;

    const label = normalizeLabel(first);
    if (!ALL_ITEMS.includes(label)) return null;

    if (cells.length >= 7) {
      return row(label, cells[1], cells[2], cells[3], cells[4], cells[5], cells.slice(6).join(" / "));
    }

    if (cells.length >= 5) {
      return row(label, cells[1], cells[2], cells[3], "—", "—", cells[4]);
    }

    if (cells.length === 4) {
      const cr = splitChangeRate(cells[2]);
      return row(label, cells[1], cr.change, cr.rate, cells[3], "—", "—");
    }

    return row(label, cells[1], "—", "—", "—", "—", "—");
  }

  function parseStandardMarketLine(line) {
    const value = String(line || "").trim().replace(/^[-・]\s*/, "");
    const match = value.match(/^(.+?)[：:]\s*(.+?)、\s*前日比\s*([^、。]+)、\s*([+-]?\d+(?:\.\d+)?%)。?\s*(.*)$/);
    if (!match) return null;

    const label = normalizeLabel(match[1]);
    if (!ALL_ITEMS.includes(label)) return null;

    const tail = match[5].trim();
    const timeMatch = tail.match(/([0-9]{1,2}:[0-9]{2})(?:\s*JST)?/);
    return row(label, match[2], match[3], match[4], timeMatch ? timeMatch[1] : "—", "—", tail || "—");
  }

  function parseExistingTable(section) {
    const rows = [];
    section.querySelectorAll("table tbody tr").forEach((tr) => {
      const cells = [...tr.querySelectorAll("th,td")].map((cell) => (cell.textContent || "").trim());
      if (cells.length < 2) return;
      const label = normalizeLabel(cells[0]);
      if (!ALL_ITEMS.includes(label)) return;

      if (cells.length >= 7) {
        rows.push(row(label, cells[1], cells[2], cells[3], cells[4], cells[5], cells[6]));
        return;
      }
      if (cells.length >= 5) {
        rows.push(row(label, cells[1], cells[2], cells[3], "—", "—", cells[4]));
        return;
      }
      rows.push(row(label, cells[1], cells[2] || "—", cells[3] || "—", "—", "—", "—"));
    });
    return rows;
  }

  function parsePrimeBreadthLine(line) {
    const source = String(line || "").trim();
    const labelMatch = source.match(/^(?:騰落銘柄数（プライム）|東証プライム騰落銘柄数)[：:]?\s*(.*)$/);
    if (!labelMatch) return [];
    const body = labelMatch[1];
    const up = body.match(/値上がり\s*([0-9,]+)/);
    const down = body.match(/値下がり\s*([0-9,]+)/);
    const result = [];
    if (up) result.push(row("東証プライム値上がり銘柄数", up[1], "—", "—", "—", "東証プライム", "—"));
    if (down) result.push(row("東証プライム値下がり銘柄数", down[1], "—", "—", "—", "東証プライム", "—"));
    return result;
  }

  function sourceLines(section) {
    const lines = [];
    [...section.querySelectorAll(":scope > p, :scope > ul > li, :scope > ol > li, :scope > div:not(.market-table-wrap)")].forEach((node) => {
      String(node.textContent || "").split(/\n+/).forEach((part) => {
        const value = part.trim();
        if (value) lines.push(value);
      });
    });
    return lines;
  }

  function parseFlattenedFiveColumn(lines) {
    const rows = [];
    for (let i = 0; i < lines.length; i += 1) {
      const label = normalizeLabel(lines[i]);
      if (!MORNING_ITEMS.includes(label)) continue;
      if (i + 4 >= lines.length) continue;

      rows.push(row(
        label,
        lines[i + 1],
        lines[i + 2],
        lines[i + 3],
        "—",
        "—",
        lines[i + 4]
      ));
      i += 4;
    }
    return rows;
  }

  function collectRows(section) {
    const found = new Map();
    const add = (item) => {
      if (!item || !item.label) return;
      const label = normalizeLabel(item.label);
      if (!found.has(label)) found.set(label, { ...item, label });
    };

    parseExistingTable(section).forEach(add);

    const lines = sourceLines(section);
    if (isMorning08()) parseFlattenedFiveColumn(lines).forEach(add);

    lines.forEach((line) => {
      add(parsePipeLine(line));
      add(parseStandardMarketLine(line));
      parsePrimeBreadthLine(line).forEach(add);
    });

    return found;
  }

  function collectNotes(section) {
    return sourceLines(section).filter((line) => {
      if (parsePipeLine(line) || parseStandardMarketLine(line) || parsePrimeBreadthLine(line).length) return false;
      if (/^(項目|市場|市場・指標|市場・資産).*([|｜])/.test(line)) return false;
      if (/^[-:|｜ ]+$/.test(line)) return false;
      return /レポート作成時点|最終検証済み|スナップショット|同時刻値|リアルタイム値|取得時刻/.test(line);
    });
  }

  function buildMorningTable(rows) {
    const headers = ["項目", "終値・値", "前日比", "騰落率", "方向感"];
    return `<div class="market-table-wrap"><table class="market-table market-table-five time-profile-market-table morning-28-market-table">
      <thead><tr>${headers.map((cell) => `<th>${escHtml(cell)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((item) => `<tr>
        <th scope="row">${escHtml(item.label)}</th>
        <td>${escHtml(item.value)}</td>
        <td>${escHtml(item.change)}</td>
        <td>${escHtml(item.rate)}</td>
        <td>${escHtml(item.note)}</td>
      </tr>`).join("")}</tbody>
    </table></div>`;
  }

  function buildIntradayTable(rows) {
    const headers = ["市場", "最終検証済み値", "前日比", "騰落率", "対象時点", "市場区分", "備考・検証状態"];
    return `<div class="market-table-wrap"><table class="market-table market-table-seven time-profile-market-table">
      <thead><tr>${headers.map((cell) => `<th>${escHtml(cell)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((item) => `<tr>
        <th scope="row">${escHtml(item.label)}</th>
        <td>${escHtml(item.value)}</td>
        <td>${escHtml(item.change)}</td>
        <td>${escHtml(item.rate)}</td>
        <td>${escHtml(item.time)}</td>
        <td>${escHtml(item.marketType)}</td>
        <td>${escHtml(item.note)}</td>
      </tr>`).join("")}</tbody>
    </table></div>`;
  }

  function buildTable(rows) {
    return isMorning08() ? buildMorningTable(rows) : buildIntradayTable(rows);
  }

  function convertSection(section) {
    if (!section) return;
    const heading = section.querySelector(":scope > h2");
    if (!heading || !/主要市場データ/.test(heading.textContent || "")) return;

    const profileKey = `${currentReportTime()}-${section.textContent.length}`;
    if (section.dataset.marketTableProfile === profileKey && section.querySelector("table.time-profile-market-table")) return;

    const allowed = allowedItems();
    const found = collectRows(section);
    const notes = collectNotes(section);
    const output = allowed.map((label) => found.get(label) || emptyRow(label));

    [...section.children].forEach((node) => {
      if (node !== heading) node.remove();
    });

    if (notes.length) {
      const intro = document.createElement("p");
      intro.className = "market-data-intro";
      intro.textContent = notes.join(" ");
      section.appendChild(intro);
    }

    section.insertAdjacentHTML("beforeend", buildTable(output));
    section.dataset.marketTableProfile = `${currentReportTime()}-${section.textContent.length}`;
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