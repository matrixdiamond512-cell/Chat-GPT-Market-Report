/* Market report single-source renderer v3. 2026-08-17 18:45 JST */
const REPORT_TIMES = ["08:00", "12:00", "16:00", "21:00"];
let reports = [];
let selectedReport = null;

const $ = (id) => document.getElementById(id);
const esc = (v = "") => String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");
const clean = (v = "") => String(v ?? "").replace(/\r/g, "").trim();
const compact = (v = "") => clean(v).replace(/\s+/g, " ");

function dateToJp(dateText) {
  const m = String(dateText || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return dateText || "日付未設定";
  const y = Number(m[1]), mo = Number(m[2]), d = Number(m[3]);
  const days = ["日","月","火","水","木","金","土"];
  const dow = new Date(Date.UTC(y, mo - 1, d)).getUTCDay();
  return `${m[1]}/${m[2]}/${m[3]}（${days[dow]}）`;
}
function reportKey(r) { return `${r?.date || ""} ${r?.time || ""}`; }
function isPublicReport(r) {
  return window.MarketReportPublicationPolicy.isEligible(r);
}
function isArchivedRecovery(r) {
  // Historical recovery records are readable, but are never formal publication.
  return !!r && r.archiveStatus === "HISTORICAL_ARCHIVE"
    && r.verifiedAtSlot === false
    && /^\d{4}-\d{2}-\d{2}$/.test(String(r.date || ""))
    && REPORT_TIMES.includes(r.time)
    && typeof r.fullText === "string" && r.fullText.startsWith(String(r.title || ""))
    && String(r.archiveNotice || "").length > 10;
}
function sortReports(list) {
  return list.filter(r => r && (isPublicReport(r) || isArchivedRecovery(r))
      && /^\d{4}-\d{2}-\d{2}$/.test(r.date || ""))
    .sort((a,b) => reportKey(b).localeCompare(reportKey(a)));
}
function uniqueDates() { return [...new Set(reports.map(r => r.date))].sort().reverse(); }
function reportsForDate(d) { return reports.filter(r => r.date === d).sort((a,b) => REPORT_TIMES.indexOf(a.time) - REPORT_TIMES.indexOf(b.time)); }
function resolveAvailableDate(d) {
  const dates = uniqueDates();
  if (!dates.length || dates.includes(d)) return d;
  const asc = dates.slice().sort();
  return asc.filter(x => x <= d).at(-1) || asc[0];
}
function syncSelectedReportUrl(report) {
  if (!report?.date || !report?.time) return;
  const url = new URL(location.href);
  url.searchParams.set("date", report.date);
  url.searchParams.set("time", report.time);
  history.replaceState(null, "", url);
}
function selectReport(dateText, timeText) {
  const d = dateText;
  const same = reportsForDate(d);
  selectedReport = same.find(r => r.time === timeText);
  if (!selectedReport) { renderMissingReport(dateText, timeText); return; }
  render();
  syncSelectedReportUrl(selectedReport);
}
function renderControls(report) {
  const dates = uniqueDates();
  const picker = $("datePicker");
  picker.value = report.date || "";
  picker.min = dates.at(-1) || "";
  picker.max = dates[0] || "";
  picker.onchange = () => selectReport(picker.value, report.time);
  $("dateLabel").textContent = dateToJp(report.date);
  const available = new Set(reportsForDate(report.date).map(r => r.time));
  $("timeTabs").innerHTML = REPORT_TIMES.map(t => `<button type="button" class="time-tab${t === report.time ? " is-active" : ""}" data-time="${esc(t)}"${available.has(t) ? "" : " disabled"}>${esc(t)}</button>`).join("");
  $("timeTabs").querySelectorAll("button:not(:disabled)").forEach(b => b.addEventListener("click", () => selectReport(report.date, b.dataset.time)));
  const i = dates.indexOf(report.date);
  $("prevDate").disabled = i < 0 || i >= dates.length - 1;
  $("nextDate").disabled = i <= 0;
  $("prevDate").onclick = () => i >= 0 && i < dates.length - 1 && selectReport(dates[i+1], report.time);
  $("nextDate").onclick = () => i > 0 && selectReport(dates[i-1], report.time);
}

function fullTextOf(report) { return clean(report?.fullText || report?.rawText || report?.body || "").replace(/^\uFEFF/, ""); }
function renderMissingReport(date, time) {
  selectedReport = null;
  renderControls({date, time});
  $("lastUpdated").textContent = `対象：${dateToJp(date)} ${time || ""}`;
  $("reportStatus").textContent = "対象データなし";
  $("app").className = "empty";
  $("app").textContent = "対象データなし：この日時のレポート本文は登録されていません。";
  window.MarketReportLastRendered = null;
}
function renderInfographic(report) {
  if (typeof isArchivedRecovery === "function" && isArchivedRecovery(report)) return "";
  const image = report.infographic;
  if (!image || report.infographic_status !== "READY") return "";
  if (image.artifact_type !== "FORMAL_INFOGRAPHIC" || image.debug_preview === true) return "";
  const key = `${report.date}_${report.time.replace(":", "-")}`;
  const reportId = `${key}`;
  const reportSnapshot = report.snapshot_id || report.snapshotId || "";
  const hex = /^[0-9a-f]{64}$/i;
  if (image.slotKey !== key || image.report_id !== reportId ||
      Number(image.revision) !== Number(report.revision) ||
      !reportSnapshot || image.snapshot_id !== reportSnapshot ||
      !report.bodyHash || image.body_hash !== report.bodyHash ||
      !image.manifest_id || !hex.test(image.manifest_hash || "") ||
      !hex.test(image.sha256 || "") ||
      image.numeric_validation !== "PASS" || image.renderer_status !== "PASS" ||
      !new RegExp(`^images/reports/${key}\\.png$`).test(image.src || "")) return "";
  return `<figure class="report-infographic" data-report-key="${esc(key)}" hidden><img data-infographic-src="${esc(image.src)}" data-infographic-sha256="${esc(image.sha256)}" alt="${esc(report.title)} 図解" style="display:none;width:100%;height:auto" loading="eager"><figcaption>${esc(report.title)} 図解</figcaption></figure>`;
}
async function verifyAndLoadInfographicHash_(container) {
  const figure = container.querySelector("figure.report-infographic");
  const image = figure && figure.querySelector("img[data-infographic-src]");
  if (!image || !window.crypto || !window.crypto.subtle) return;
  const src = image.dataset.infographicSrc;
  if (!/^images\/reports\/\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.png$/.test(src)) return;
  try {
    const response = await fetch(src, { cache: "no-store", credentials: "same-origin" });
    if (!response.ok) return;
    const bytes = await response.arrayBuffer();
    const digest = await window.crypto.subtle.digest("SHA-256", bytes);
    const actual = Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("");
    if (actual !== image.dataset.infographicSha256.toLowerCase()) return;
    image.src = URL.createObjectURL(new Blob([bytes], { type: "image/png" }));
    image.style.display = "block";
    figure.hidden = false;
  } catch (_) {
    // Image verification is fail-closed for the infographic lane only.
  }
}
function headingInfo(line) {
  const raw = clean(line);
  let m = raw.match(/^【\s*(.+?)\s*】$/); if (m) return {number:"", title:m[1].trim()};
  m = raw.match(/^\s*(\d{1,2})[．.]\s*(.+?)\s*$/); if (m) return {number:m[1], title:m[2].trim()};
  m = raw.match(/^#{1,3}\s+(.+?)\s*$/); if (m) return {number:"", title:m[1].trim()};

  // Google Docs由来の本文では、主要セクション見出しがMarkdownや【】なしの
  // プレーンテキストになることがある。既知のSOP見出しだけを認識する。
  const plainHeadings = [
    "総合判断",
    "今日の相場テーマ",
    "前回からの変化",
    "08:00からの変化",
    "12:00からの変化",
    "16:00からの変化",
    "東京市場の確定結果",
    "主要市場データ",
    "主要市場まとめ",
    "材料と値動きの整合性",
    "今日の主導市場",
    "主導市場",
    "重要ニュース",
    "金利",
    "原油",
    "金",
    "為替",
    "BTCUSD",
    "クロスアセット資金フロー",
    "需給・ポジション",
    "重要イベント",
    "今後の重要イベント",
    "個別市場見通し",
    "主要6市場の短期見通し",
    "シナリオ分析",
    "メインシナリオ",
    "代替シナリオ",
    "シナリオが崩れる条件",
    "リスク管理",
    "東京時間への引き継ぎ",
    "欧州時間への引き継ぎ",
    "NY時間への引き継ぎ",
    "翌東京時間への引き継ぎ",
    "次の時間帯への引き継ぎ",
    "結論",
    "クロスチェック結果"
  ];
  if (plainHeadings.includes(raw)) return {number:"", title:raw};
  return null;
}
function splitCanonicalTitleFromSource_(source, fallbackTitle) {
  const text = String(source || "").replace(/\r\n?/g, "\n");
  const title = String(fallbackTitle || "");
  if (!title || !text.startsWith(title)) return {title, bodySource:text};
  if (text === title) return {title, bodySource:""};
  if (text.startsWith(title + "\n")) return {title, bodySource:text.slice(title.length + 1)};
  return {title, bodySource:text.slice(title.length)};
}
function parseDocument(source, fallbackTitle) {
  const split = splitCanonicalTitleFromSource_(source, fallbackTitle);
  const lines = split.bodySource.split("\n");
  let cursor = 0, title = split.title || fallbackTitle;
  const preface = [], sections = []; let current = null;
  for (; cursor < lines.length; cursor++) {
    const h = headingInfo(lines[cursor]);
    if (h && h.title.length <= 60) {
      if (current) sections.push(current);
      current = {number:h.number, title:h.title, lines:[]};
    } else if (current) current.lines.push(lines[cursor]); else preface.push(lines[cursor]);
  }
  if (current) sections.push(current);
  return {title, preface, sections};
}

function splitChangeRate(change = "", rate = "") {
  const c = clean(change), r = clean(rate);
  if (r && r !== "—") return {change:c || "—", rate:r};
  const m = c.match(/^(.*?)\s*[（(]\s*([+\-]?\d+(?:\.\d+)?%)\s*[）)]/);
  return m ? {change:m[1].trim() || "—", rate:m[2]} : {change:c || "—", rate:r || "—"};
}
function marketRows(report) {
  const raw = report?.marketDataTable?.rows;
  if (Array.isArray(raw) && raw.length) return raw.map(r => {
    const cr = splitChangeRate(r?.change, r?.rate ?? r?.changePercent);
    return {label:compact(r?.label ?? r?.item ?? r?.name), value:compact(r?.value ?? r?.price) || "—", change:cr.change, rate:cr.rate, direction:compact(r?.direction ?? r?.status) || "—"};
  }).filter(r => r.label);
  if (Array.isArray(report?.markets) && report.markets.length) return report.markets.map(m => {
    const cr = splitChangeRate(m?.change, m?.rate ?? m?.changePercent);
    return {label:compact(m?.name), value:compact(m?.price) || "—", change:cr.change, rate:cr.rate, direction:compact(m?.direction) || "—"};
  }).filter(r => r.label);
  return [];
}
function legacyMarketRowsFromFullText(report) {
  const source = fullTextOf(report);
  const specs = [
    ["金", /(?:現物金|金(?:\s*\(XAU\/USD\))?)[^\n]*?(?:約|[:：]\s*)?([0-9][0-9,]*(?:\.[0-9]+)?\s*(?:ドル|USD\/oz)?)/],
    ["WTI原油", /WTI[^\n]*?(?:約|[:：]\s*)?([0-9][0-9,]*(?:\.[0-9]+)?\s*ドル)/],
    ["日経225先物", /(?:大阪[^\n]*?先物|日経225先物)[^\n]*?(?:約|[:：]\s*)?([0-9][0-9,]*\s*円)/],
    ["USD/JPY", /USD\/JPY[^\n]*?(?:約|[:：]\s*)?([0-9]+(?:\.[0-9]+)?\s*円?)/],
    ["EUR/USD", /EUR\/USD[^\n]*?(?:約|[:：]\s*)?([0-9]+(?:\.[0-9]+)?)/],
    ["BTCUSD", /(?:BTCUSD|Bitcoin)[^\n]*?(?:約|[:：]\s*)?([0-9][0-9,]*(?:\.[0-9]+)?\s*(?:ドル|USD)?)/]
  ];
  return specs.map(([label,re]) => {
    const m = source.match(re);
    return m ? {label, value:compact(m[1]) || "—", change:"—", rate:"—", direction:"—"} : null;
  }).filter(Boolean);
}
const EXTRA = [
  ["米2年債",/米2年債(?:利回り)?[：:]?\s*([0-9.]+%)/],
  ["米10年債",/米10年債(?:利回り)?[：:]?\s*([0-9.]+%)/],
  ["日本10年国債",/日本10年国債(?:利回り)?[：:]?\s*([0-9.]+%)/],
  ["VIX",/VIX(?:指数)?[：:]?\s*([0-9.]+)/],
  ["日経VI",/日経VI[：:]?\s*([0-9.]+)/],
  ["Fear & Greed Index",/(?<!Crypto\s)Fear\s*&\s*Greed(?:\s*Index)?[：:]?\s*([0-9]+(?:\s+[A-Za-z]+)?)/i]
];
function extraRows(lines, rows) {
  const source = lines.map(compact).filter(Boolean).join(" ");
  const seen = new Set(rows.map(r => r.label)), out = [];
  EXTRA.forEach(([label,re]) => { if (!seen.has(label)) { const m = source.match(re); if (m) out.push({label,value:m[1],change:"—",rate:"—",direction:"—"}); } });
  return out;
}
function dedupe(rows) { const seen = new Set(); return rows.filter(r => r.label && !seen.has(r.label) && seen.add(r.label)); }
function isMarketSection(title) { return /主要市場データ|市場データ|前営業日終値|終値一覧|主要価格/.test(title || ""); }
const CURRENT_MARKET_HEADERS = ["市場・指標", "現在値・確認値", "前日比", "騰落率", "方向・状態"];
const PREVIOUS_CLOSE_HEADERS = ["項目", "終値・値", "前日比", "騰落率", "方向感"];
function previousCloseDataDate(report) {
  const value = report?.marketDataTable?.dataDate || report?.dataProvenance?.closeSheet?.dataDate || "";
  return compact(value).split("-").join("/");
}
function isPreviousCloseTable(report, sectionTitle = "") {
  if (report?.time !== "08:00") return false;
  return report?.marketDataTable?.semantics === "previous_close"
    || Boolean(report?.marketDataTable?.dataDate)
    || Boolean(report?.dataProvenance?.closeSheet?.dataDate)
    || /前営業日終値/.test(sectionTitle || "");
}
function previousCloseHeaders(report) {
  const columns = Array.isArray(report?.marketDataTable?.columns) ? report.marketDataTable.columns.map(compact) : [];
  const valid = columns.length === PREVIOUS_CLOSE_HEADERS.length
    && columns[0] === "項目"
    && columns[2] === "前日比"
    && columns[3] === "騰落率"
    && columns[4] === "方向感"
    && !columns.includes("現在値・確認値")
    && !columns.includes("市場・指標")
    && !columns.includes("方向・状態");
  return valid ? columns : PREVIOUS_CLOSE_HEADERS;
}
function marketSectionTitle(report, title) {
  const base = compact(title) || "主要市場データ";
  if (!isPreviousCloseTable(report, base)) return base;
  const dataDate = previousCloseDataDate(report);
  return dataDate ? `主要市場データ（前営業日終値：${dataDate}）` : "主要市場データ（前営業日終値）";
}
function marketRowsFromSectionLines(lines) {
  const rows = [];
  for (const raw of lines || []) {
    const line = clean(raw);
    if (!line || /^【.*】$/.test(line) || /^(項目|市場・指標)[｜|]/.test(line)) continue;
    // Morning report prose uses "label value / change / rate", not a Markdown table.
    const m = line.match(/^(.+?)\s+([+−-]?(?:約\s*)?[\d,]+(?:\.\d+)?\s*(?:円|ドル|%|％|倍|銘柄|ポイント|pt|bp)?)(?:\s*\/\s*([^\/\n（]+))?(?:\s*\/\s*([^\/\n（]+))?(.*)$/);
    if (!m || m[1].length > 58 || !/[0-9]/.test(m[2])) continue;
    const label = m[1].trim();
    if (/^(?:作成基準|注|出典)/.test(label)) continue;
    const remainder = [m[3], m[4], m[5]].filter(Boolean).join(" ").trim();
    const percent = remainder.match(/[+−-]?\d+(?:\.\d+)?\s*[%％]/);
    rows.push({label, value:m[2].trim(), change:(m[3] || "").trim() || "—", rate:percent ? percent[0] : "—", direction:"—"});
  }
  return rows;
}
function renderMarketTable(report, lines, sectionTitle = "") {
  const previousClose = isPreviousCloseTable(report, sectionTitle);
  const hasStructuredRows = Array.isArray(report?.marketDataTable?.rows) && report.marketDataTable.rows.length > 0;
  let rows = marketRows(report);
  if (!rows.length) rows = marketRowsFromSectionLines(lines || []);
  if (!rows.length) rows = legacyMarketRowsFromFullText(report);
  // A structured 08:00 table is the canonical 28-row contract. Do not append
  // guesses extracted from prose, which can reintroduce current-value rows.
  if (!(previousClose && hasStructuredRows)) rows = dedupe(rows.concat(extraRows(lines || [], rows)));
  if (!rows.length) return `<p class="sop-empty">主要市場データを表として構成できませんでした。</p>`;
  const headers = previousClose ? previousCloseHeaders(report) : CURRENT_MARKET_HEADERS;
  return `<div class="market-table-wrap"><table class="market-table market-table-five" data-market-table-mode="${previousClose ? "previous-close" : "current-value"}"><thead><tr>${headers.map(header => `<th>${esc(header)}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr><th scope="row">${esc(r.label)}</th><td>${esc(r.value || "—")}</td><td>${esc(r.change || "—")}</td><td>${esc(r.rate || "—")}</td><td>${esc(r.direction || "—")}</td></tr>`).join("")}</tbody></table></div>`;
}

function ensureMarketSection(report, parsed) {
  const sections = parsed.sections.slice();
  if (sections.some(s => isMarketSection(s.title))) return sections;
  if (!marketRows(report).length && !legacyMarketRowsFromFullText(report).length) return sections;
  let insertAt = sections.findIndex(s => /今日の相場テーマ/.test(s.title));
  if (insertAt < 0) insertAt = sections.findIndex(s => /結論/.test(s.title));
  insertAt = insertAt >= 0 ? insertAt + 1 : 0;
  sections.splice(insertAt, 0, {number:"", title:"主要市場データ", lines:[]});
  return sections;
}
function isSubheading(line) {
  const v = clean(line);
  if (!v || v.length > 46 || /^[・→▶■●]/.test(v) || /[。！？!?]$/.test(v)) return false;
  return /^(金|ゴールド|WTI原油|原油|日経225先物|USD\/JPY|EUR\/USD|BTCUSD|株式|債券|ドル|円|暗号資産|メインシナリオ|代替シナリオ|崩れる条件|確認ポイント|強気材料|弱気材料|リスク|結論|最終判断)/.test(v);
}
function renderRichText(lines) {
  const html = []; let p = [], list = [];
  const fp = () => { if (p.length) { html.push(`<p>${esc(p.join("\n"))}</p>`); p = []; } };
  const fl = () => { if (list.length) { html.push(`<ul>${list.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`); list = []; } };
  (lines || []).forEach(raw => {
    const line = clean(raw);
    if (!line) { fp(); fl(); return; }
    const b = line.match(/^(?:[・●■▶]|[-*]\s+)(.+)$/);
    if (b) { fp(); list.push(b[1].trim()); return; }
    if (/^→/.test(line)) { fp(); list.push(line); return; }
    if (isSubheading(line)) { fp(); fl(); html.push(`<h3>${esc(line)}</h3>`); return; }
    fl(); p.push(line);
  });
  fp(); fl(); return html.join("");
}
function renderPreface(lines) {
  const visible = (lines || []).map(clean).filter(x => x && !/^作成日時[：:]/.test(x) && !/^ファイル名[：:]/.test(x) && !/^データ基準[：:]/.test(x));
  return visible.length ? `<div class="document-preface">${visible.map(x=>`<p>${esc(x)}</p>`).join("")}</div>` : "";
}
const supplementalChronology20261016 = {"08:00":[["10/15 21:30","米9月PPI・小売売上高等が発表","インフレ警戒が残る一方、消費指標の評価が分かれる","米国","高","NY市場の反応"],["10/15 22:30","NY株式市場開場。AI資金調達・採算懸念","半導体・ハイテクに売り圧力","米国","高","主要指数の推移"],["10/16 00:05","Dow 52,146.08、Nasdaq 26,614.79を観測","Dow上昇・Nasdaq下落、業種格差","米国","高","米金利・AI株"],["10/16 04:12","Dow 52,183.86、Nasdaq 26,701.01を観測","Nasdaqがプラス圏回復","米国","中","NY終値"],["10/16 05:00頃","NY主要指数が反発して引ける","SOXは弱さを残す","米国","高","大阪先物夜間"],["10/16 06:00","大阪先物夜間引け65,520円","前日清算値比+720円","日本","高","東京寄り付き"]],"12:00":[["09:00","東京寄り付き、日経平均64,925.29円","前日比+499.34円で反発","日本","高","半導体株"],["09:30～10:30","半導体中心に買い戻し、10:16頃65,688円","急落後の反発が拡大","日本","高","買いの広がり"],["11:30","日経平均65,550.68円で前場終了","前日比+1,124.73円","日本","高","後場開始"],["12:00","大阪先物約65,600円","東京現物の反発を引き継ぐ","日本","中","65,000円維持"]],"16:00":[["09:00～11:30","日経平均が64,925.29円で寄り付き、65,550.68円で前引け","急落後の買い戻し拡大","日本","高","後場反応"],["12:30","後場寄り付き65,421.10円","前引け比約130円安、利益確定が交錯","日本","高","売り圧力"],["14:42","日経平均65,612.47円まで再上昇","午後も買い戻しが続く場面","日本","中","大引け"],["15:30","日経平均65,324.29円で大引け","前引け比226.39円下落、前日比+898.34円","日本","高","夜間先物"],["15:45","大阪先物清算値65,520円","前日比+720円","日本","高","NY市場"]],"21:00":[["12:00～13:00頃","東京後場の買い戻しと利益確定が交錯","時間帯概況。個別時刻の価格取得なし","日本","中","引け値"],["14:00～15:30","日経平均65,324.29円で大引け","前引け65,550.68円より伸び悩む","日本","高","欧州市場"],["16:00～18:00頃","欧州でAI信用懸念と金利低下を評価","時間帯概況。定量的な反応は未取得","欧州","中","NY市場"],["18:00～21:00頃","米株開場前、AI関連株と米金利に注目","21:00同時点の市場反応は未取得","米国・欧州","中","米鉱工業生産"],["22:15（予定）","米鉱工業生産・設備稼働率発表予定","21時時点では未発表","米国","高","指標結果"],["22:30（予定）","米株式市場開場予定","21時時点では未開始","米国","高","AI関連株"]]};
function renderSupplementalChronology(report) {
  if (!isArchivedRecovery(report)) return "";
  const legacyRows = report.date === "2026-10-16" ? supplementalChronology20261016[report.time] || [] : [];
  const storedRows = Array.isArray(report.archiveTimelineRows)
    ? report.archiveTimelineRows.filter(row => row && row.text && row.time).slice(0, 20)
        .map(row => [row.time, row.text, row.reaction || "", row.region || "対象市場", row.importance || "中", row.next || "確認待ち"])
    : [];
  const rows = storedRows.length ? storedRows : legacyRows;
  if (!rows.length) return "";
  const headers = ["日時（日本時間）","イベント","市場反応","国・地域","重要度","次のイベントまで"];
  return '<section class="section sop-section" data-sop-title="当日の市場時系列（実際に起きた出来事と市場反応）"><h2>当日の市場時系列（実際に起きた出来事と市場反応）</h2><p>保存本文に基づく補充・再構成データ。概況・予定は区別して表示。</p><div style="overflow-x:auto"><table class="market-table"><thead><tr>' + headers.map(h=>'<th>'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(cell=>'<td>'+esc(cell)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div></section>';
}
function renderDocument(report) {
  const source = fullTextOf(report);
  const fallback = report.title || `マーケットレポート｜${dateToJp(report.date)} ${report.time || ""}`;
  const parsed = parseDocument(source, fallback);
  const sections = ensureMarketSection(report, parsed);
  $("lastUpdated").textContent = `表示中：${dateToJp(report.date)} ${report.time || ""}`;
  $("reportStatus").textContent = `本文全文を表示中｜reports.json正本｜統合レンダラー v3`;
  $("app").className = "report sop-report-applied";
  const app = $("app");
  app.innerHTML = `<header class="report-head"><h1 class="report-title">${esc(parsed.title || fallback)}</h1><div class="source-badge">reports.json正本</div></header>${renderInfographic(report)}<article class="report-body">${renderSupplementalChronology(report)}${renderPreface(parsed.preface)}${sections.map(s => { const market = isMarketSection(s.title); const title = market ? marketSectionTitle(report, s.title) : s.title; return `<section class="section sop-section" data-sop-title="${esc(title)}"><h2>${s.number ? `${esc(s.number)}．` : ""}${esc(title)}</h2>${market ? renderMarketTable(report, s.lines, s.title) : renderRichText(s.lines)}</section>`; }).join("")}</article>`;
  if (isArchivedRecovery(report)) {
    $("reportStatus").textContent = "過去の記録を表示中｜保存本文・事後修復版（正式発行とは区別）";
    app.classList.add("report-archive-recovery");
    const sourceBadge = app.querySelector(".source-badge");
    if (sourceBadge) sourceBadge.textContent = "過去の保存記録・修復版";
    const notice = document.createElement("div");
    notice.className = "archive-provenance";
    notice.setAttribute("role", "note");
    const strong = document.createElement("strong");
    strong.textContent = "記録復元版（正式な発行原本とは区別・公開承認とは別）";
    notice.appendChild(strong);
    for (const line of [
      report.archiveNotice,
      "原本状態：" + report.originalReportStatus + "／復元区分：" + report.archiveType,
      "後日確認したデータは発行時点の情報として扱いません。"
    ]) {
      const p = document.createElement("p");
      p.textContent = line;
      notice.appendChild(p);
    }
    const head = app.querySelector(".report-head");
    if (head) head.insertAdjacentElement("afterend", notice);
  }
  void verifyAndLoadInfographicHash_(app);
}
function render() { if (!selectedReport) return; renderControls(selectedReport); renderDocument(selectedReport); window.MarketReportLastRendered = selectedReport; window.dispatchEvent(new CustomEvent("market-report-rendered", { detail: { report: selectedReport } })); }

async function init() {
  try {
    const response = await fetch(`reports.json?ts=${Date.now()}`, {cache:"no-store"});
    if (!response.ok) throw new Error(`reports.json HTTP ${response.status}`);
    const payload = await response.json();
    const formallyPublished = sortReports(Array.isArray(payload) ? payload : (Array.isArray(payload?.reports) ? payload.reports : [])).filter(isPublicReport);
    let recovered = [];
    try {
      const archiveResponse = await fetch("data/report-recovery-2026-10.json?ts=" + Date.now(), {cache:"no-store"});
      if (!archiveResponse.ok) throw new Error("archive HTTP " + archiveResponse.status);
      const archivePayload = await archiveResponse.json();
      if (archivePayload?.kind !== "HISTORICAL_ARCHIVE_NOT_OFFICIAL_PUBLICATION"
          || !Array.isArray(archivePayload.reports)) throw new Error("archive schema mismatch");
      recovered = archivePayload.reports.filter(isArchivedRecovery);
      if (recovered.length !== archivePayload.reports.length) throw new Error("archive entries invalid");
    } catch (error) {
      console.warn("[market report recovery] archive read unavailable", error.message);
    }
    // Read-back owner-folder docs are display-only history, not canonical publication.
    // This provides all four 2026-10-19 slots through the normal date/time controls.
    let driveArchive = [];
    try {
      const path = "data/dashboard-drive-archive-2026-10-19.json";
      const response = await fetch(path + "?ts=" + Date.now(), {cache:"no-store"});
      if (!response.ok) throw new Error(path + " HTTP " + response.status);
      const data = await response.json();
      if (data?.kind !== "HISTORICAL_ARCHIVE_NOT_OFFICIAL_PUBLICATION" ||
          data?.sourceFolderId !== "1qDOwDACdzWsGYcMaEobciDP3dFOdJ4Vz" ||
          !Array.isArray(data.reports)) throw new Error("Drive archive schema invalid");
      driveArchive = data.reports.filter(r => isArchivedRecovery(r) &&
        r.originalReportStatus === "DRIVE_DOC_READBACK_NOT_SLOT_VERIFIED" &&
        r.archiveType === "DRIVE_SAVED_DOCUMENT" && r.sourceDocument?.id &&
        typeof r.driveRevisionId === "string" && r.driveRevisionId &&
        r.driveTextLength === r.fullText.length &&
        Array.isArray(r.missingAtSlotEvidence) && r.missingAtSlotEvidence.length);
    } catch (error) {
      console.warn("[market report Drive readback] unavailable", error.message);
    }
    const bySlot = new Map(recovered.map(r => [reportKey(r), r]));
    driveArchive.forEach(r => {
      if (!bySlot.has(reportKey(r))) bySlot.set(reportKey(r), r);
    });
    formallyPublished.forEach(r => bySlot.set(reportKey(r), r)); // formal takes precedence
    reports = sortReports([...bySlot.values()]);
    window.MarketReportArchiveInfo = {count: recovered.length, publishedCount: formallyPublished.length};
    if (!reports.length) throw new Error("reports.jsonに表示できる本文データがありません");
    const params = new URLSearchParams(location.search);
    const date = params.get("date"), time = params.get("time");
    selectedReport = reports.find(r => r.date === date && r.time === time) || ((!date && !time) ? reports[0] : null);
    if (!selectedReport) { renderMissingReport(date || "", time || ""); return; }
    render();
    // The enrichment script needs the resolved default slot as well as explicit selections.
    // Keep the canonical slot in the URL so the bare report.html route gets full details.
    syncSelectedReportUrl(selectedReport);
  } catch (error) {
    $("lastUpdated").textContent = "読込エラー";
    $("reportStatus").textContent = "マーケットレポート本文を読み込めませんでした";
    $("app").className = "empty";
    $("app").innerHTML = `マーケットレポート本文を表示できません。理由：${esc(error.message)}`;
  }
}
window.MarketReportRendererVersion = "20260925-exact-slot-infographic";
init();

