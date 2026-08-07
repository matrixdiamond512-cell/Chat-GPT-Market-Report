/* Market report full-text hardening. Loaded after report-fulltext.js. */

/*
 * Google Docs report headings are written as:
 *   【1. 前営業日終値・主要市場データ】
 * The base parser historically recognized only "1. ...", so the complete
 * document was treated as one body block and the market-data table renderer
 * was never called. Recognize both bracketed and plain headings.
 */
parseDocument = function parseDocumentWithBracketHeadings(rawText, fallbackTitle) {
  const lines = String(rawText || "").replace(/\r/g, "").split("\n");
  let cursor = 0;
  while (cursor < lines.length && !lines[cursor].trim()) cursor += 1;

  let documentTitle = fallbackTitle;
  if (cursor < lines.length && /^マーケットレポート[｜|]/.test(lines[cursor].trim())) {
    documentTitle = lines[cursor].trim();
    cursor += 1;
  }

  const preface = [];
  const sections = [];
  let current = null;
  const plainHeadingPattern = /^\s*(\d{1,2})[．.]\s*(.+?)\s*$/;
  const bracketHeadingPattern = /^\s*【\s*(?:(\d{1,2})[．.]\s*)?(.+?)\s*】\s*$/;

  const startSection = (number, title) => {
    if (current) sections.push(current);
    current = {
      number: number || "",
      title: String(title || "").trim(),
      lines: []
    };
  };

  for (; cursor < lines.length; cursor += 1) {
    const line = lines[cursor];
    const trimmed = line.trim();
    const bracketHeading = trimmed.match(bracketHeadingPattern);
    const plainHeading = trimmed.match(plainHeadingPattern);

    if (bracketHeading) {
      startSection(bracketHeading[1], bracketHeading[2]);
      continue;
    }
    if (plainHeading) {
      startSection(plainHeading[1], plainHeading[2]);
      continue;
    }

    if (current) current.lines.push(line);
    else preface.push(line);
  }

  if (current) sections.push(current);
  if (!sections.length) sections.push({ number: "", title: "本文", lines });
  return { title: documentTitle, preface, sections };
};

function isRecognizedMarketLabel(label) {
  return /^(?:Dow|NYダウ|ダウ|Nasdaq(?:総合)?|NASDAQ(?:総合)?|S&P\s*500|Russell\s*2000|Russell2000|日経225(?:現物|先物.*)?|日経平均.*|CME日経225先物.*|日経先物.*|USD\/JPY|USDJPY|ドル円|EUR\/USD|EURUSD|ユーロドル|金.*|ゴールド|WTI原油|原油.*|BTCUSD|BTC\/USD|Bitcoin|ビットコイン|VIX.*|日経VI|米.*債.*|日本.*国債.*|Fear\s*&\s*Greed.*|日経225.*(?:EPS|PER|PBR)|PER|PBR|EPS|25日.*乖離率|200日.*乖離率|値上がり銘柄数|値下がり銘柄数|騰落レシオ|東証プライム.*)$/i.test(String(label || "").trim());
}

parseMarketLine = function parseMarketLineSafely(line) {
  const compact = String(line || "").trim().replace(/^[-・]\s*/, "");
  const separatorIndex = compact.search(/[：:]/);
  if (separatorIndex <= 0 || separatorIndex > 60) return null;

  const label = compact.slice(0, separatorIndex).trim();
  const body = compact.slice(separatorIndex + 1).trim();
  if (!label || !body) return null;
  if (/^(作成時点|作成日時|対象|注記|注意|出典|補足|参考|理由)$/.test(label)) return null;
  if (/[。！？!?]/.test(label)) return null;
  if (!isRecognizedMarketLabel(label) && label.length > 30) return null;

  const firstStop = body.indexOf("。");
  const valueStatus = firstStop >= 0 ? body.slice(0, firstStop).trim() : body;
  const note = firstStop >= 0 ? body.slice(firstStop + 1).trim() : "";
  return { label, valueStatus, note };
};

function splitMarketValue(valueStatus, note) {
  const source = String(valueStatus || "").trim();
  const result = {
    value: source || "—",
    change: "—",
    rate: "—",
    note: String(note || "").trim()
  };

  const bracket = source.match(/^(.+?)（(.+)）$/);
  if (!bracket) return result;

  result.value = bracket[1].trim() || "—";
  const details = bracket[2].split("、").map((item) => item.trim()).filter(Boolean);
  if (details.length >= 1) result.change = details[0].replace(/^前日比\s*/, "") || "—";
  if (details.length >= 2) result.rate = details.slice(1).join("、") || "—";
  return result;
}

/*
 * DocumentApp.getBody().getText() flattens a native Google Docs table into
 * one cell per line. Example:
 *   市場・指標 / 終値・値 / 前日比 / 騰落率・区分
 *   VIX / 15.15 / -0.66 / -4.17%
 * Rebuild the original four-column rows so the WEB page never shows orphaned
 * labels and numbers as unrelated paragraphs.
 */
function parseFlattenedDocsMarketTable(lines) {
  const indexed = lines
    .map((line, index) => ({ value: String(line || "").trim(), index }))
    .filter((item) => item.value);
  const expectedHeader = ["市場・指標", "終値・値", "前日比", "騰落率・区分"];

  let headerStart = -1;
  for (let i = 0; i <= indexed.length - expectedHeader.length; i += 1) {
    if (expectedHeader.every((header, offset) => indexed[i + offset].value === header)) {
      headerStart = i;
      break;
    }
  }
  if (headerStart < 0) return null;

  const consumedIndexes = new Set();
  for (let offset = 0; offset < expectedHeader.length; offset += 1) {
    consumedIndexes.add(indexed[headerStart + offset].index);
  }

  const rows = [];
  let cursor = headerStart + expectedHeader.length;
  while (cursor + 3 < indexed.length) {
    const label = indexed[cursor].value;
    if (!isRecognizedMarketLabel(label)) break;

    const rowItems = indexed.slice(cursor, cursor + 4);
    rows.push(rowItems.map((item) => item.value || "—"));
    rowItems.forEach((item) => consumedIndexes.add(item.index));
    cursor += 4;
  }

  if (!rows.length) return null;
  return {
    table: { header: expectedHeader, rows },
    remainder: lines.filter((line, index) => !consumedIndexes.has(index))
  };
}

renderMarketDataSection = function renderMarketDataSectionFourColumns(lines) {
  const markdownTable = parseMarkdownTable(lines);
  if (markdownTable) {
    const remainder = lines.filter((line) => !/^\s*\|.*\|\s*$/.test(line));
    return `${renderMarkdownTable(markdownTable)}${renderRichText(remainder)}`;
  }

  const flattenedTable = parseFlattenedDocsMarketTable(lines);
  if (flattenedTable) {
    return `${renderMarkdownTable(flattenedTable.table)}${renderRichText(flattenedTable.remainder)}`;
  }

  const rows = [];
  const remainder = [];
  for (const line of lines) {
    const parsed = parseMarketLine(line);
    if (!parsed) {
      remainder.push(line);
      continue;
    }
    rows.push({ ...parsed, ...splitMarketValue(parsed.valueStatus, parsed.note) });
  }

  const table = rows.length ? `<div class="market-table-wrap"><table class="market-table">
    <thead><tr>
      <th>市場・指標</th>
      <th>終値・値</th>
      <th>前日比</th>
      <th>騰落率・区分</th>
    </tr></thead>
    <tbody>${rows.map((row) => `<tr>
      <th scope="row">${esc(row.label)}</th>
      <td>${esc(row.value || "—")}</td>
      <td>${esc(row.change || "—")}</td>
      <td>${esc(row.rate || row.note || "—")}</td>
    </tr>`).join("")}</tbody>
  </table></div>` : "";

  return `${table}${renderRichText(remainder)}`;
};

(() => {
  "use strict";
  let attempts = 0;
  const timer = window.setInterval(() => {
    attempts += 1;
    const list = typeof reports !== "undefined" && Array.isArray(reports) ? reports : [];
    if (!list.length || typeof selectReport !== "function") {
      if (attempts >= 40) window.clearInterval(timer);
      return;
    }

    const latest = [...list]
      .filter((item) => item && item.date && item.time)
      .sort((a, b) => `${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`))[0];
    if (!latest) {
      window.clearInterval(timer);
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const requestedDate = params.get("date");
    const requestedTime = params.get("time");
    const current = typeof selectedReport !== "undefined" ? selectedReport : null;
    const staleCurrentDaySelection = requestedDate === latest.date
      && requestedTime
      && `${requestedDate} ${requestedTime}` < `${latest.date} ${latest.time}`;
    const defaultOpenedOnOlderReport = !requestedDate
      && current
      && `${current.date} ${current.time || ""}` < `${latest.date} ${latest.time}`;

    if (staleCurrentDaySelection || defaultOpenedOnOlderReport) {
      selectReport(latest.date, latest.time);
    } else if (current && typeof render === "function") {
      /* Re-render once so reports loaded before this patch also use the table parser. */
      render();
    }
    window.clearInterval(timer);
  }, 100);
})();
