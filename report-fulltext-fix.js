/* Market report full-text hardening. Loaded after report-fulltext.js. */

const REQUIRED_MARKET_DATA_LABELS = [
  "NYダウ",
  "NASDAQ総合",
  "S&P500",
  "Russell2000",
  "VIX",
  "Fear & Greed Index",
  "騰落銘柄数（NYSE）",
  "騰落銘柄数（NASDAQ）",
  "日経225",
  "日経225先物",
  "TOPIX",
  "グロース250",
  "日経VI",
  "騰落銘柄数（プライム）",
  "騰落銘柄数（スタンダード）",
  "騰落銘柄数（グロース）",
  "日経225 EPS",
  "日経225 PER",
  "日経225 PBR",
  "日経225 25日移動平均乖離率",
  "日経225 200日移動平均乖離率",
  "米10年債利回り",
  "日本10年国債利回り",
  "ドル円",
  "ユーロドル",
  "金価格",
  "原油価格",
  "BTCUSD"
];

const MARKET_TABLE_HEADER_5 = ["市場・指標", "終値", "前日比", "騰落率", "注記"];
const MARKET_TABLE_HEADER_PATTERNS = [
  ["市場・指標", "終値", "前日比", "騰落率", "注記"],
  ["市場・指標", "終値・値", "前日比", "騰落率", "注記"],
  ["市場・指標", "終値・値", "前日比", "騰落率・区分"],
  ["市場・指標", "終値", "前日比", "騰落率・区分"]
];

/* Google Docs headings may be bracketed: 【1. 前営業日終値・主要市場データ】 */
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
    current = { number: number || "", title: String(title || "").trim(), lines: [] };
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

function normalizeMarketLabel(label) {
  return String(label || "")
    .trim()
    .replace(/[　\s]/g, "")
    .replace(/[（）]/g, (char) => (char === "（" ? "(" : ")"))
    .replace(/指数$/i, "")
    .toLowerCase();
}

function canonicalMarketLabel(label) {
  const value = normalizeMarketLabel(label);
  if (/^(nyダウ|ダウ|dow|dowjones)$/.test(value)) return "NYダウ";
  if (/^(nasdaq総合|nasdaq|ナスダック総合)$/.test(value)) return "NASDAQ総合";
  if (/^s&p500$/.test(value)) return "S&P500";
  if (/^russell2000$/.test(value)) return "Russell2000";
  if (/^vix/.test(value)) return "VIX";
  if (/fear&greed/.test(value) && !/crypto/.test(value)) return "Fear & Greed Index";
  if (/nyse/.test(value) && /(騰落|値上がり|値下がり)/.test(value)) return "騰落銘柄数（NYSE）";
  if (/nasdaq/.test(value) && /(騰落|値上がり|値下がり)/.test(value)) return "騰落銘柄数（NASDAQ）";
  if (/^(日経225|日経平均|日経225現物|日経平均現物)$/.test(value)) return "日経225";
  if (/(日経225|日経).*(先物)/.test(value) || /^cme日経225先物/.test(value)) return "日経225先物";
  if (/^topix$/.test(value)) return "TOPIX";
  if (/^(グロース250|東証グロース250)$/.test(value)) return "グロース250";
  if (/^日経vi/.test(value)) return "日経VI";
  if (/(プライム)/.test(value) && /(騰落|値上がり|値下がり)/.test(value)) return "騰落銘柄数（プライム）";
  if (/(スタンダード)/.test(value) && /(騰落|値上がり|値下がり)/.test(value)) return "騰落銘柄数（スタンダード）";
  if (/(グロース)/.test(value) && /(騰落|値上がり|値下がり)/.test(value)) return "騰落銘柄数（グロース）";
  if (/日経225.*eps|^eps$/.test(value)) return "日経225 EPS";
  if (/日経225.*per|^per$/.test(value)) return "日経225 PER";
  if (/日経225.*pbr|^pbr$/.test(value)) return "日経225 PBR";
  if (/25日.*乖離率/.test(value)) return "日経225 25日移動平均乖離率";
  if (/200日.*乖離率/.test(value)) return "日経225 200日移動平均乖離率";
  if (/^(米|米国).*10年.*債.*利回り/.test(value)) return "米10年債利回り";
  if (/^日本.*10年.*国債.*利回り/.test(value)) return "日本10年国債利回り";
  if (/^(usd\/jpy|usdjpy|ドル円)$/.test(value)) return "ドル円";
  if (/^(eur\/usd|eurusd|ユーロドル)$/.test(value)) return "ユーロドル";
  if (/^(金価格|金現物|金|ゴールド|xau\/usd)/.test(value)) return "金価格";
  if (/^(原油価格|wti原油|原油|wti)/.test(value)) return "原油価格";
  if (/^(btcusd|btc\/usd|bitcoin|ビットコイン)$/.test(value)) return "BTCUSD";
  return String(label || "").trim();
}

function isRecognizedMarketLabel(label) {
  const canonical = canonicalMarketLabel(label);
  return REQUIRED_MARKET_DATA_LABELS.includes(canonical)
    || /^(値上がり銘柄数|値下がり銘柄数|騰落レシオ|東証プライム売買代金|東証プライム売買高)$/.test(String(label || "").trim());
}

parseMarketLine = function parseMarketLineSafely(line) {
  const compact = String(line || "").trim().replace(/^[-・]\s*/, "");
  const separatorIndex = compact.search(/[：:]/);
  if (separatorIndex <= 0 || separatorIndex > 80) return null;

  const label = compact.slice(0, separatorIndex).trim();
  const body = compact.slice(separatorIndex + 1).trim();
  if (!label || !body || !isRecognizedMarketLabel(label)) return null;

  const firstStop = body.indexOf("。");
  const valueStatus = firstStop >= 0 ? body.slice(0, firstStop).trim() : body;
  const note = firstStop >= 0 ? body.slice(firstStop + 1).trim() : "";
  return { label, valueStatus, note };
};

function splitMarketValue(valueStatus, note) {
  const source = String(valueStatus || "").trim();
  const result = { value: source || "—", change: "—", rate: "—", note: String(note || "").trim() || "—" };
  const bracket = source.match(/^(.+?)（(.+)）$/);
  if (!bracket) return result;

  result.value = bracket[1].trim() || "—";
  const details = bracket[2].split("、").map((item) => item.trim()).filter(Boolean);
  if (details.length >= 1) result.change = details[0].replace(/^前日比\s*/, "") || "—";
  if (details.length >= 2) {
    const second = details[1];
    if (/%|pt|bp/i.test(second)) result.rate = second;
    else result.note = second;
  }
  if (details.length >= 3) result.note = details.slice(2).join("、") || result.note;
  return result;
}

function sameHeaderValue(actual, expected) {
  return String(actual || "").trim() === expected;
}

function findFlattenedHeader(indexed) {
  for (let i = 0; i < indexed.length; i += 1) {
    for (const pattern of MARKET_TABLE_HEADER_PATTERNS) {
      if (i + pattern.length > indexed.length) continue;
      if (pattern.every((header, offset) => sameHeaderValue(indexed[i + offset].value, header))) {
        return { start: i, pattern };
      }
    }
  }
  return null;
}

function oldFourthCellToRateAndNote(value) {
  const textValue = String(value || "").trim() || "—";
  if (/[-+]?\d+(?:\.\d+)?%|[-+]?\d+(?:\.\d+)?(?:pt|bp)$/i.test(textValue)) {
    return { rate: textValue, note: "—" };
  }
  return { rate: "—", note: textValue };
}

function normalizeRowsToFive(header, rows) {
  if (header.length === 5) {
    return rows.map((row) => [row[0] || "—", row[1] || "—", row[2] || "—", row[3] || "—", row[4] || "—"]);
  }
  return rows.map((row) => {
    const converted = oldFourthCellToRateAndNote(row[3]);
    return [row[0] || "—", row[1] || "—", row[2] || "—", converted.rate, converted.note];
  });
}

/* Reconstruct native Google Docs tables flattened to one cell per line. */
function parseFlattenedDocsMarketTable(lines) {
  const indexed = lines
    .map((line, index) => ({ value: String(line || "").trim(), index }))
    .filter((item) => item.value);
  const match = findFlattenedHeader(indexed);
  if (!match) return null;

  const consumedIndexes = new Set();
  match.pattern.forEach((_, offset) => consumedIndexes.add(indexed[match.start + offset].index));

  const rawRows = [];
  const width = match.pattern.length;
  let cursor = match.start + width;
  while (cursor + width - 1 < indexed.length) {
    const label = indexed[cursor].value;
    if (!isRecognizedMarketLabel(label)) break;
    const rowItems = indexed.slice(cursor, cursor + width);
    rawRows.push(rowItems.map((item) => item.value || "—"));
    rowItems.forEach((item) => consumedIndexes.add(item.index));
    cursor += width;
  }

  if (!rawRows.length) return null;
  return {
    table: { header: MARKET_TABLE_HEADER_5, rows: normalizeRowsToFive(match.pattern, rawRows) },
    remainder: lines.filter((line, index) => !consumedIndexes.has(index))
  };
}

function normalizeMarkdownMarketTable(table) {
  if (!table || !Array.isArray(table.header) || !Array.isArray(table.rows)) return null;
  const header = table.header.map((cell) => String(cell || "").trim());
  const isFive = header.length === 5 && header[0] === "市場・指標";
  const isFour = header.length === 4 && header[0] === "市場・指標";
  if (!isFive && !isFour) return null;
  return { header: MARKET_TABLE_HEADER_5, rows: normalizeRowsToFive(header, table.rows) };
}

function marketDataValidationHtml(rows) {
  const present = new Set(rows.map((row) => canonicalMarketLabel(row[0])));
  const missing = REQUIRED_MARKET_DATA_LABELS.filter((label) => !present.has(label));
  if (!missing.length && rows.length >= REQUIRED_MARKET_DATA_LABELS.length) {
    return `<div class="market-data-validation is-ok">市場データ検証：28項目を確認</div>`;
  }
  return `<div class="market-data-validation is-error"><strong>市場データ不足：</strong>${esc(missing.join("、") || `規定28項目に対して${rows.length}行`)}</div>`;
}

function renderMarketTableFive(table) {
  const rows = table.rows || [];
  return `<div class="market-table-wrap"><table class="market-table market-table-five">
    <thead><tr>${MARKET_TABLE_HEADER_5.map((cell) => `<th>${esc(cell)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((row) => `<tr>
      <th scope="row">${esc(row[0] || "—")}</th>
      <td>${esc(row[1] || "—")}</td>
      <td>${esc(row[2] || "—")}</td>
      <td>${esc(row[3] || "—")}</td>
      <td>${esc(row[4] || "—")}</td>
    </tr>`).join("")}</tbody>
  </table></div>${marketDataValidationHtml(rows)}`;
}

renderMarketDataSection = function renderMarketDataSectionFiveColumns(lines) {
  const markdownTable = normalizeMarkdownMarketTable(parseMarkdownTable(lines));
  if (markdownTable) {
    const remainder = lines.filter((line) => !/^\s*\|.*\|\s*$/.test(line));
    return `${renderMarketTableFive(markdownTable)}${renderRichText(remainder)}`;
  }

  const flattenedTable = parseFlattenedDocsMarketTable(lines);
  if (flattenedTable) {
    return `${renderMarketTableFive(flattenedTable.table)}${renderRichText(flattenedTable.remainder)}`;
  }

  const parsedRows = [];
  const remainder = [];
  for (const line of lines) {
    const parsed = parseMarketLine(line);
    if (!parsed) {
      remainder.push(line);
      continue;
    }
    const split = splitMarketValue(parsed.valueStatus, parsed.note);
    parsedRows.push([parsed.label, split.value, split.change, split.rate, split.note]);
  }

  const tableHtml = parsedRows.length
    ? renderMarketTableFive({ header: MARKET_TABLE_HEADER_5, rows: parsedRows })
    : `<div class="market-data-validation is-error"><strong>市場データ表を認識できません。</strong> 規定の5列・28項目で作成してください。</div>`;
  return `${tableHtml}${renderRichText(remainder)}`;
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
      render();
    }
    window.clearInterval(timer);
  }, 100);
})();
