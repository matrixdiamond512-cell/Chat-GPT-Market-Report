const REPORT_TIMES = ["07:00", "12:00", "16:00", "21:00"];
let reports = [];
let selectedReport = null;

const $ = (id) => document.getElementById(id);

function esc(value = "") {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function asArray(value) {
  if (Array.isArray(value)) return value.filter(Boolean);
  if (value === null || value === undefined || value === "") return [];
  return [value];
}

function text(value = "") {
  return String(value).replace(/\s+/g, " ").trim();
}

function dateToJp(dateText) {
  if (!dateText) return "日付未設定";
  const date = new Date(`${dateText}T00:00:00+09:00`);
  if (Number.isNaN(date.getTime())) return dateText;
  const days = ["日", "月", "火", "水", "木", "金", "土"];
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}/${m}/${d}（${days[date.getDay()]}）`;
}

function reportKey(report) {
  return `${report?.date || ""} ${report?.time || ""}`;
}

function sortReports(list) {
  return list
    .filter((report) => report && /^\d{4}-\d{2}-\d{2}$/.test(report.date || ""))
    .sort((a, b) => reportKey(b).localeCompare(reportKey(a)));
}

function uniqueDates() {
  return [...new Set(reports.map((report) => report.date))].sort().reverse();
}

function reportsForDate(dateText) {
  return reports
    .filter((report) => report.date === dateText)
    .sort((a, b) => REPORT_TIMES.indexOf(a.time) - REPORT_TIMES.indexOf(b.time));
}

function resolveAvailableDate(dateText) {
  const dates = uniqueDates();
  if (!dates.length || dates.includes(dateText)) return dateText;
  const ascending = dates.slice().sort();
  return ascending.filter((date) => date <= dateText).at(-1) || ascending[0];
}

function selectReport(dateText, timeText) {
  const resolvedDate = resolveAvailableDate(dateText);
  const sameDate = reportsForDate(resolvedDate);
  selectedReport = sameDate.find((report) => report.time === timeText) || sameDate.at(-1) || reports[0];
  render();

  const url = new URL(location.href);
  url.searchParams.set("date", selectedReport.date || "");
  url.searchParams.set("time", selectedReport.time || "");
  history.replaceState(null, "", url);
}

function renderControls(report) {
  const dates = uniqueDates();
  const datePicker = $("datePicker");
  datePicker.value = report.date || "";
  datePicker.min = dates.at(-1) || "";
  datePicker.max = dates[0] || "";
  datePicker.onchange = () => selectReport(datePicker.value, report.time);
  $("dateLabel").textContent = dateToJp(report.date);

  const availableTimes = new Set(reportsForDate(report.date).map((item) => item.time));
  $("timeTabs").innerHTML = REPORT_TIMES.map((timeValue) => {
    const active = timeValue === report.time ? " is-active" : "";
    const disabled = availableTimes.has(timeValue) ? "" : " disabled";
    return `<button type="button" class="time-tab${active}" data-time="${esc(timeValue)}"${disabled}>${esc(timeValue)}</button>`;
  }).join("");

  $("timeTabs").querySelectorAll("button:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => selectReport(report.date, button.dataset.time));
  });

  const index = dates.indexOf(report.date);
  $("prevDate").disabled = index < 0 || index >= dates.length - 1;
  $("nextDate").disabled = index <= 0;
  $("prevDate").onclick = () => index >= 0 && index < dates.length - 1 && selectReport(dates[index + 1], report.time);
  $("nextDate").onclick = () => index > 0 && selectReport(dates[index - 1], report.time);
}

function fullTextOf(report) {
  return String(report?.fullText || report?.rawText || report?.body || "")
    .replace(/^\uFEFF/, "")
    .replace(/\r/g, "")
    .trim();
}

function structuredFallback(report) {
  const parts = [];
  const pushSection = (title, value) => {
    const items = asArray(value).map((item) => text(item)).filter(Boolean);
    if (!items.length) return;
    parts.push(title, "", ...items, "");
  };

  parts.push(report.title || `マーケットレポート｜${dateToJp(report.date)} ${report.time || ""}`, "");
  pushSection("今日の相場テーマ", report.theme);
  pushSection("前回からの主な変化", report.changes);
  pushSection("材料と値動きの整合性", report.consistency);
  pushSection("今日の主導市場", report.leadingMarket);
  pushSection("重要ニュース", report.news);
  pushSection("クロスアセット資金フロー", report.crossAssetFlow);
  pushSection("需給・ポジション", report.positioning);
  pushSection("メインシナリオ", report.mainScenario);
  pushSection("代替シナリオ", report.alternativeScenario);
  pushSection("崩れる条件", report.breakConditions || report.breakCondition);
  pushSection("重要イベント", report.events);
  pushSection("次の時間帯への引き継ぎ", report.handover);
  pushSection("リスク管理", report.riskManagement);
  return parts.join("\n").trim();
}

function parseDocument(rawText, fallbackTitle) {
  const lines = rawText.split("\n");
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
  const headingPattern = /^\s*(\d{1,2})[．.]\s*(.+?)\s*$/;

  for (; cursor < lines.length; cursor += 1) {
    const line = lines[cursor];
    const heading = line.match(headingPattern);
    if (heading) {
      if (current) sections.push(current);
      current = {
        number: heading[1],
        title: heading[2],
        lines: []
      };
      continue;
    }

    if (current) current.lines.push(line);
    else preface.push(line);
  }

  if (current) sections.push(current);

  if (!sections.length) {
    sections.push({ number: "", title: "本文", lines });
  }

  return { title: documentTitle, preface, sections };
}

const MARKET_LABEL_PATTERN = /^(Dow|NYダウ|ダウ|Nasdaq(?:総合)?|NASDAQ(?:総合)?|S&P\s*500|日経225現物|日経平均(?:現物)?|CME日経225先物|日経225先物(?:（[^）]+）)?|日経先物|USD\/JPY|USDJPY|ドル円|EUR\/USD|EURUSD|ユーロドル|金(?:（XAU\/USD）)?|金現物|ゴールド|WTI原油|原油(?:（WTI）)?|BTCUSD|BTC\/USD|Bitcoin|ビットコイン|VIX(?:指数)?|日経VI|米10年債(?:利回り)?|米国10年債(?:利回り)?|日本10年国債(?:利回り)?|Fear\s*&\s*Greed(?:\s*Index)?|Crypto\s+Fear\s*&\s*Greed|日経225予想EPS|日経225予想PER|日経225PER|日経225PBR|PER|PBR|EPS|25日移動平均乖離率|200日移動平均乖離率|値上がり銘柄数|値下がり銘柄数|騰落レシオ|東証プライム売買代金|東証プライム売買高)[：:]\s*(.+)$/i;

function parseMarketLine(line) {
  const compact = line.trim().replace(/^[-・]\s*/, "");
  const match = compact.match(MARKET_LABEL_PATTERN);
  if (!match) return null;

  const label = match[1].trim();
  const body = match[2].trim();
  const sentenceParts = body.split("。");
  const valueStatus = (sentenceParts.shift() || "").trim();
  const note = sentenceParts.join("。").trim();

  return { label, valueStatus, note };
}

function parseMarkdownTable(lines) {
  const nonEmpty = lines.map((line) => line.trim()).filter(Boolean);
  if (nonEmpty.length < 2) return null;
  const rows = nonEmpty.filter((line) => /^\|.*\|$/.test(line));
  if (rows.length < 2) return null;

  const splitRow = (line) => line
    .slice(1, -1)
    .split("|")
    .map((cell) => cell.trim());
  const header = splitRow(rows[0]);
  const dataRows = rows.slice(1).filter((row) => !/^\|(?:\s*:?-+:?\s*\|)+$/.test(row));
  if (!header.length || !dataRows.length) return null;

  return {
    header,
    rows: dataRows.map(splitRow)
  };
}

function renderMarkdownTable(table) {
  return `<div class="market-table-wrap"><table class="market-table">
    <thead><tr>${table.header.map((cell) => `<th>${esc(cell)}</th>`).join("")}</tr></thead>
    <tbody>${table.rows.map((row) => `<tr>${row.map((cell) => `<td>${esc(cell)}</td>`).join("")}</tr>`).join("")}</tbody>
  </table></div>`;
}

function isMarketDataSection(title) {
  return /主要市場データ|市場データ|前営業日終値|終値一覧|主要価格/.test(title || "");
}

function renderMarketDataSection(lines) {
  const markdownTable = parseMarkdownTable(lines);
  if (markdownTable) {
    const remainder = lines.filter((line) => !/^\s*\|.*\|\s*$/.test(line));
    return `${renderMarkdownTable(markdownTable)}${renderRichText(remainder)}`;
  }

  const rows = [];
  const remainder = [];
  for (const line of lines) {
    const parsed = parseMarketLine(line);
    if (parsed) rows.push(parsed);
    else remainder.push(line);
  }

  const table = rows.length ? `<div class="market-table-wrap"><table class="market-table">
    <thead><tr><th>市場・指標</th><th>価格・状態</th><th>補足・取得状況</th></tr></thead>
    <tbody>${rows.map((row) => `<tr>
      <th scope="row">${esc(row.label)}</th>
      <td>${esc(row.valueStatus || "—")}</td>
      <td>${esc(row.note || "—")}</td>
    </tr>`).join("")}</tbody>
  </table></div>` : "";

  return `${table}${renderRichText(remainder)}`;
}

function isSubheadingLine(line) {
  const value = line.trim();
  if (!value || value.length > 46) return false;
  if (/^[・→▶■●]/.test(value)) return false;
  if (/[。！？!?]$/.test(value)) return false;
  return /^(金|ゴールド|WTI原油|原油|日経225先物|USD\/JPY|EUR\/USD|BTCUSD|株式|債券|ドル|円|暗号資産|メインシナリオ|代替シナリオ|崩れる条件|確認ポイント|強気材料|弱気材料|リスク|結論|最終判断)/.test(value);
}

function renderRichText(lines) {
  const html = [];
  let paragraph = [];
  let list = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p>${esc(paragraph.join("\n"))}</p>`);
    paragraph = [];
  };

  const flushList = () => {
    if (!list.length) return;
    html.push(`<ul>${list.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`);
    list = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }

    const bullet = line.match(/^(?:[・●■▶]|[-*]\s+)(.+)$/);
    if (bullet) {
      flushParagraph();
      list.push(bullet[1].trim());
      continue;
    }

    if (/^→/.test(line)) {
      flushParagraph();
      list.push(line);
      continue;
    }

    if (isSubheadingLine(line)) {
      flushParagraph();
      flushList();
      html.push(`<h3>${esc(line)}</h3>`);
      continue;
    }

    flushList();
    paragraph.push(line);
  }

  flushParagraph();
  flushList();
  return html.join("");
}

function renderPreface(lines) {
  const visible = lines.map((line) => line.trim()).filter(Boolean);
  if (!visible.length) return "";
  return `<div class="document-preface">${visible.map((line) => `<p>${esc(line)}</p>`).join("")}</div>`;
}

function renderDocument(report) {
  const rawFullText = fullTextOf(report);
  const sourceText = rawFullText || structuredFallback(report);
  const fallbackTitle = report.title || `マーケットレポート｜${dateToJp(report.date)} ${report.time || ""}`;
  const documentData = parseDocument(sourceText, fallbackTitle);
  const sourceMode = rawFullText ? "Googleドキュメント原文連携" : "構造化データからの代替表示";

  $("lastUpdated").textContent = `表示中：${dateToJp(report.date)} ${report.time || ""}`;
  $("reportStatus").textContent = rawFullText
    ? `本文全文を表示中｜${sourceMode}`
    : `全文データなし｜${sourceMode}`;

  $("app").className = "report";
  $("app").innerHTML = `
    <header class="report-head">
      <h1 class="report-title">${esc(documentData.title)}</h1>
      <div class="source-badge">${esc(sourceMode)}</div>
    </header>
    <article class="report-body">
      ${renderPreface(documentData.preface)}
      ${documentData.sections.map((section) => `
        <section class="section">
          <h2>${section.number ? `${esc(section.number)}．` : ""}${esc(section.title)}</h2>
          ${isMarketDataSection(section.title)
            ? renderMarketDataSection(section.lines)
            : renderRichText(section.lines)}
        </section>
      `).join("")}
    </article>
  `;
}

function render() {
  if (!selectedReport) return;
  renderControls(selectedReport);
  renderDocument(selectedReport);
}

async function init() {
  try {
    const response = await fetch(`reports.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`reports.json HTTP ${response.status}`);
    const payload = await response.json();
    const list = Array.isArray(payload) ? payload : asArray(payload.reports);
    reports = sortReports(list);
    if (!reports.length) throw new Error("reports.jsonに表示できる本文データがありません");

    const params = new URLSearchParams(location.search);
    const date = params.get("date");
    const timeValue = params.get("time");
    selectedReport = reports.find((report) => report.date === date && report.time === timeValue) || reports[0];
    render();
  } catch (error) {
    $("lastUpdated").textContent = "読込エラー";
    $("reportStatus").textContent = "マーケットレポート本文を読み込めませんでした";
    $("app").className = "empty";
    $("app").innerHTML = `マーケットレポート本文を表示できません。理由：${esc(error.message)}`;
  }
}

init();
