/* Single-source market report renderer. 2026-08-17 18:30 JST */
const REPORT_TIMES = ["08:00", "12:00", "16:00", "21:00"];
let reports = [];
let selectedReport = null;

const $ = (id) => document.getElementById(id);
const esc = (v = "") => String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");
const arr = (v) => Array.isArray(v) ? v.filter(Boolean) : (v == null || v === "" ? [] : [v]);
const clean = (v = "") => String(v ?? "").replace(/\r/g, "").trim();
const compact = (v = "") => clean(v).replace(/\s+/g, " ");

function dateToJp(dateText) {
  if (!dateText) return "日付未設定";
  const date = new Date(`${dateText}T00:00:00+09:00`);
  if (Number.isNaN(date.getTime())) return dateText;
  const days = ["日","月","火","水","木","金","土"];
  return `${date.getFullYear()}/${String(date.getMonth()+1).padStart(2,"0")}/${String(date.getDate()).padStart(2,"0")}（${days[date.getDay()]}）`;
}
function reportKey(r) { return `${r?.date || ""} ${r?.time || ""}`; }
function sortReports(list) { return list.filter(r => r && /^\d{4}-\d{2}-\d{2}$/.test(r.date || "")).sort((a,b) => reportKey(b).localeCompare(reportKey(a))); }
function uniqueDates() { return [...new Set(reports.map(r => r.date))].sort().reverse(); }
function reportsForDate(d) { return reports.filter(r => r.date === d).sort((a,b) => REPORT_TIMES.indexOf(a.time) - REPORT_TIMES.indexOf(b.time)); }
function resolveAvailableDate(d) {
  const dates = uniqueDates();
  if (!dates.length || dates.includes(d)) return d;
  const asc = dates.slice().sort();
  return asc.filter(x => x <= d).at(-1) || asc[0];
}
function selectReport(dateText, timeText) {
  const d = resolveAvailableDate(dateText);
  const same = reportsForDate(d);
  selectedReport = same.find(r => r.time === timeText) || same.at(-1) || reports[0];
  render();
  const url = new URL(location.href);
  url.searchParams.set("date", selectedReport.date || "");
  url.searchParams.set("time", selectedReport.time || "");
  history.replaceState(null, "", url);
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
function headingInfo(line) {
  const raw = clean(line);
  let m = raw.match(/^【\s*(.+?)\s*】$/); if (m) return { number:"", title:m[1].trim() };
  m = raw.match(/^\s*(\d{1,2})[．.]\s*(.+?)\s*$/); if (m) return { number:m[1], title:m[2].trim() };
  m = raw.match(/^#{1,3}\s+(.+?)\s*$/); if (m) return { number:"", title:m[1].trim() };
  return null;
}
function structuredFallback(report) {
  const p = [report.title || `マーケットレポート｜${dateToJp(report.date)} ${report.time || ""}`, ""];
  const add = (title, value) => { const items = arr(value).map(compact).filter(Boolean); if (items.length) p.push(`【${title}】`, ...items, ""); };
  add("今日の相場テーマ", report.theme);
  if (marketRows(report).length) p.push("【主要市場データ】", "");
  add("前回からの変化", report.changes);
  add("材料と値動きの整合性", report.consistency);
  add("今日の主導市場", report.leadingMarket);
  add("重要ニュース", report.news);
  add("クロスアセット資金フロー", report.crossAssetFlow);
  add("需給・ポジション", report.positioning);
  add("メインシナリオ", report.mainScenario);
  add("代替シナリオ", report.alternativeScenario);
  add("シナリオが崩れる条件", report.breakConditions || report.breakCondition);
  add("重要イベント", report.events);
  add("次の時間帯への引き継ぎ", report.handover);
  add("リスク管理", report.riskManagement);
  return p.join("\n").trim();
}
function parseDocument(source, fallbackTitle) {
  const lines = String(source || "").split("\n");
  let cursor = 0, title = fallbackTitle;
  while (cursor < lines.length && !lines[cursor].trim()) cursor++;
  if (cursor < lines.length && /^マーケットレポート[｜|]/.test(lines[cursor].trim())) title = lines[cursor++].trim();
  const preface = [], sections = []; let current = null;
  for (; cursor < lines.length; cursor++) {
    const h = headingInfo(lines[cursor]);
    if (h && h.title.length <= 60) {
      if (current) sections.push(current);
      current = { number:h.number, title:h.title, lines:[] };
    } else if (current) current.lines.push(lines[cursor]); else preface.push(lines[cursor]);
  }
  if (current) sections.push(current);
  if (!sections.length) sections.push({number:"", title:"本文", lines});
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
const INLINE_LABELS = ["金・COMEX先物","COMEX金先物","WTI原油","日経225先物（大阪取引所）","日経225先物","USD/JPY","EUR/USD","BTCUSD"];
const rxEsc = v => String(v).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
function inlineRows(lines) {
  const source = lines.map(compact).filter(Boolean).join(" "); if (!source) return [];
  const re = new RegExp(`(${INLINE_LABELS.map(rxEsc).join("|")})[：:]\\s*`, "g");
  const ms = [...source.matchAll(re)];
  return ms.map((m,i) => { const start=m.index+m[0].length, end=i+1<ms.length?ms[i+1].index:source.length; return {label:m[1], value:source.slice(start,end).trim().replace(/^[、,。\s]+|[、,。\s]+$/g,""), change:"—", rate:"—", direction:"—"}; }).filter(r => r.value);
}
const EXTRA = [
  ["米2年債",/米2年債(?:利回り)?[：:]?\s*([0-9.]+%)/],
  ["米10年債",/米10年債(?:利回り)?[：:]?\s*([0-9.]+%)/],
  ["日本10年国債",/日本10年国債(?:利回り)?[：:]?\s*([0-9.]+%)/],
  ["VIX",/VIX(?:指数)?[：:]?\s*([0-9.]+)/], ["日経VI",/日経VI[：:]?\s*([0-9.]+)/],
  ["Fear & Greed Index",/(?<!Crypto\s)Fear\s*&\s*Greed(?:\s*Index)?[：:]?\s*([0-9]+(?:\s+[A-Za-z]+)?)/i]
];
function extras(lines, rows) {
  const source = lines.map(compact).filter(Boolean).join(" "), seen = new Set(rows.map(r => r.label)), out=[];
  EXTRA.forEach(([label,re]) => { if (!seen.has(label)) { const m=source.match(re); if (m) out.push({label,value:m[1],change:"—",rate:"—",direction:"—"}); } });
  return out;
}
function dedupe(rows) { const seen=new Set(); return rows.filter(r => r.label && !seen.has(r.label) && seen.add(r.label)); }
function isMarketSection(title) { return /主要市場データ|市場データ|前営業日終値|終値一覧|主要価格/.test(title || ""); }
function renderMarketTable(report, lines) {
  let rows = marketRows(report); if (!rows.length) rows = inlineRows(lines); rows = dedupe(rows.concat(extras(lines, rows)));
  if (!rows.length) return `<p>主要市場データを表として構成できませんでした。</p>`;
  return `<div class="market-table-wrap"><table class="market-table market-table-five"><thead><tr><th>市場・指標</th><th>現在値・確認値</th><th>前日比</th><th>騰落率</th><th>方向・状態</th></tr></thead><tbody>${rows.map(r => `<tr><th scope="row">${esc(r.label)}</th><td>${esc(r.value || "—")}</td><td>${esc(r.change || "—")}</td><td>${esc(r.rate || "—")}</td><td>${esc(r.direction || "—")}</td></tr>`).join("")}</tbody></table></div>`;
}

function isSubheading(line) {
  const v=clean(line); if (!v || v.length>46 || /^[・→▶■●]/.test(v) || /[。！？!?]$/.test(v)) return false;
  return /^(金|ゴールド|WTI原油|原油|日経225先物|USD\/JPY|EUR\/USD|BTCUSD|株式|債券|ドル|円|暗号資産|メインシナリオ|代替シナリオ|崩れる条件|確認ポイント|強気材料|弱気材料|リスク|結論|最終判断)/.test(v);
}
function renderRichText(lines) {
  const html=[]; let p=[], list=[];
  const fp=()=>{if(p.length){html.push(`<p>${esc(p.join("\n"))}</p>`);p=[];}};
  const fl=()=>{if(list.length){html.push(`<ul>${list.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`);list=[];}};
  lines.forEach(raw => { const line=clean(raw); if(!line){fp();fl();return;} const b=line.match(/^(?:[・●■▶]|[-*]\s+)(.+)$/); if(b){fp();list.push(b[1].trim());return;} if(/^→/.test(line)){fp();list.push(line);return;} if(isSubheading(line)){fp();fl();html.push(`<h3>${esc(line)}</h3>`);return;} fl();p.push(line); });
  fp();fl();return html.join("");
}
function renderPreface(lines) {
  const visible=lines.map(clean).filter(x => x && !/^作成日時[：:]/.test(x) && !/^ファイル名[：:]/.test(x) && !/^データ基準[：:]/.test(x));
  return visible.length ? `<div class="document-preface">${visible.map(x=>`<p>${esc(x)}</p>`).join("")}</div>` : "";
}
function renderDocument(report) {
  const raw=fullTextOf(report), source=raw || structuredFallback(report), fallback=report.title || `マーケットレポート｜${dateToJp(report.date)} ${report.time || ""}`;
  const doc=parseDocument(source,fallback), mode=raw?"Googleドキュメント原文連携":"構造化データからの代替表示";
  $("lastUpdated").textContent=`表示中：${dateToJp(report.date)} ${report.time || ""}`;
  $("reportStatus").textContent=`本文全文を表示中｜${mode}｜統合レンダラー v2`;
  $("app").className="report sop-report-applied";
  $("app").innerHTML=`<header class="report-head"><h1 class="report-title">${esc(doc.title)}</h1><div class="source-badge">${esc(mode)}</div></header><article class="report-body">${renderPreface(doc.preface)}${doc.sections.map(s=>`<section class="section sop-section" data-sop-title="${esc(s.title)}"><h2>${s.number?`${esc(s.number)}．`:""}${esc(s.title)}</h2>${isMarketSection(s.title)?renderMarketTable(report,s.lines):renderRichText(s.lines)}</section>`).join("")}</article>`;
}
function render(){ if(!selectedReport)return; renderControls(selectedReport); renderDocument(selectedReport); }

async function init(){
  try{
    const [ar,dr]=await Promise.allSettled([
      fetch(`reports.json?ts=${Date.now()}`,{cache:"no-store"}).then(async r=>{if(!r.ok)throw new Error(`reports.json HTTP ${r.status}`);return r.json();}),
      fetch(`data/dashboard.json?ts=${Date.now()}`,{cache:"no-store"}).then(async r=>{if(!r.ok)throw new Error(`data/dashboard.json HTTP ${r.status}`);return r.json();})
    ]);
    const archive=ar.status==="fulfilled"?ar.value:null, dashboard=dr.status==="fulfilled"?dr.value:null;
    const archiveReports=Array.isArray(archive)?archive:arr(archive?.reports);
    const dashboardReports=Array.isArray(dashboard?.reports)?dashboard.reports:arr(dashboard?.latestReport||dashboard?.currentReport);
    const map=new Map(); archiveReports.forEach(r=>map.set(reportKey(r),r));
    dashboardReports.forEach(r=>{const key=reportKey(r), prev=map.get(key)||{}; map.set(key,{...prev,...r,fullText:r.fullText||prev.fullText||""});});
    reports=sortReports([...map.values()]); if(!reports.length)throw new Error("reports.jsonに表示できる本文データがありません");
    const q=new URLSearchParams(location.search), date=q.get("date"), time=q.get("time");
    selectedReport=reports.find(r=>r.date===date&&r.time===time)||reports[0]; render();
  }catch(error){ $("lastUpdated").textContent="読込エラー"; $("reportStatus").textContent="マーケットレポート本文を読み込めませんでした"; $("app").className="empty"; $("app").innerHTML=`マーケットレポート本文を表示できません。理由：${esc(error.message)}`; }
}
window.MarketReportRendererVersion="20260817-1830-core-v2";
init();
