/* Unified SOP renderer for 08:00 / 12:00 / 16:00 / 21:00 market reports. */
(() => {
  "use strict";

  const ACTIVE_SLOTS = new Set(["08:00", "12:00", "16:00", "21:00"]);
  const MORNING_REFERENCE_URL = "data/market/morning-reference.json";
  let morningReference = null;
  const escHtml = (value = "") => String(value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");

  function publicText(value = "") {
    return String(value || "")
      .replace(/\bverified\b/gi, "確認済み")
      .replace(/JSONにありません|構造化JSON|内部構造/g, "")
      .replace(/\r/g, "")
      .trim();
  }

  function currentReport() {
    try { return selectedReport || null; } catch (error) { return null; }
  }

  function reportSource(report) {
    try {
      if (typeof fullTextOf === "function") return publicText(fullTextOf(report));
    } catch (error) {}
    return publicText(report?.fullText || report?.rawText || report?.body || "");
  }

  function normalizeHeading(value = "") {
    return String(value)
      .trim()
      .replace(/^【|】$/g, "")
      .replace(/^\s*(?:第?\d{1,2}|[一二三四五六七八九十]+)\s*[．.、)）]\s*/, "")
      .replace(/^[■◆◇●▶]\s*/, "")
      .trim();
  }

  function headingFromLine(line) {
    const raw = String(line || "").trim();
    let match = raw.match(/^【\s*(.+?)\s*】$/);
    if (match) return normalizeHeading(match[1]);
    match = raw.match(/^\s*(?:第?\d{1,2}|[一二三四五六七八九十]+)\s*[．.、)）]\s*(.+?)\s*$/);
    if (match) return normalizeHeading(match[1]);
    match = raw.match(/^#{1,3}\s+(.+?)\s*$/);
    if (match) return normalizeHeading(match[1]);
    return "";
  }

  function isKnownHeading(title) {
    return /^(今日の相場テーマ|主要市場データ|主要市場まとめ|昨夜のNY市場|NY市場|前回からの(?:主な)?変化|\d{2}:00からの変化|材料と値動きの整合性|今日の主導市場|主導市場|重要ニュース(?:と市場への伝播)?|金利(?:・為替の連動)?|クロスアセット資金フロー|需給・ポジション|個別(?:市場)?見通し|6市場の(?:個別)?見通し|シナリオ|メインシナリオ|代替シナリオ|メインシナリオが崩れる条件|シナリオが崩れる条件|崩れる条件|本日の監視順|重要イベント|今後の重要イベント|東京時間への引き継ぎ|欧州時間への引き継ぎ|NY時間への引き継ぎ|翌東京時間への引き継ぎ|次の時間帯への引き継ぎ|リスク管理|08:00結論|12:00結論|16:00結論|21:00結論|結論|最終判断)$/i.test(normalizeHeading(title));
  }

  function parseSections(source, fallbackTitle) {
    const lines = String(source || "").split("\n");
    let title = fallbackTitle || "マーケットレポート";
    const preface = [];
    const sections = [];
    let current = null;

    lines.forEach((rawLine, index) => {
      const line = rawLine.trim();
      if (index === 0 && /^マーケットレポート[｜|]/.test(line)) {
        title = line;
        return;
      }
      const heading = headingFromLine(line);
      if (heading && isKnownHeading(heading)) {
        if (current) sections.push(current);
        current = { title: heading, lines: [] };
        return;
      }
      if (current) current.lines.push(rawLine);
      else preface.push(rawLine);
    });
    if (current) sections.push(current);
    return { title, preface, sections };
  }

  function splitChangeRate(change = "", rate = "") {
    const c = String(change || "").trim();
    const r = String(rate || "").trim();
    if (r && r !== "—") return { change: c || "—", rate: r };
    const match = c.match(/^(.*?)\s*[（(]\s*([+\-]?\d+(?:\.\d+)?%)\s*[）)]/);
    if (match) return { change: match[1].trim() || "—", rate: match[2] };
    return { change: c || "—", rate: r || "—" };
  }

  function applyMorningReference(report, rows) {
    if (!report || report.time !== "08:00" || !morningReference) return rows;
    if (morningReference.reportDate !== report.date || morningReference.reportSlot !== report.time) return rows;
    const items = morningReference.items || {};
    return rows.map((row) => {
      const ref = items[row.label];
      if (!ref || !String(ref.status || "").startsWith("verified") || ref.value == null || ref.value === "") return row;
      return {
        ...row,
        value: publicText(ref.value) || row.value,
        change: publicText(ref.change) || row.change,
        rate: publicText(ref.rate) || row.rate,
        direction: publicText(ref.direction) || row.direction
      };
    });
  }

  function structuredMarketRows(report) {
    const rawRows = report?.marketDataTable?.rows;
    if (!Array.isArray(rawRows)) return [];
    const rows = rawRows.map((row) => {
      const cr = splitChangeRate(row?.change, row?.rate ?? row?.changePercent);
      return {
        label: publicText(row?.label ?? row?.item ?? row?.name ?? ""),
        value: publicText(row?.value ?? row?.price ?? "—") || "—",
        change: publicText(cr.change) || "—",
        rate: publicText(cr.rate) || "—",
        direction: publicText(row?.direction ?? row?.status ?? "—") || "—"
      };
    }).filter((row) => row.label);
    return applyMorningReference(report, rows);
  }

  function textMarketRows(lines) {
    const result = [];
    const clean = (lines || []).map((line) => publicText(line)).filter(Boolean);
    clean.forEach((line) => {
      if (/^(市場|項目|銘柄)\s+/.test(line)) return;
      const cells = line.split(/\t+|\s{2,}/).map((cell) => cell.trim()).filter(Boolean);
      if (cells.length >= 4) {
        const cr = splitChangeRate(cells[2], "");
        result.push({ label: cells[0], value: cells[1], change: cr.change, rate: cr.rate, direction: cells.slice(3).join(" ") });
        return;
      }
      const m = line.match(/^([^：:]{1,36})[：:]\s*(.+)$/);
      if (m) result.push({ label: m[1].trim(), value: m[2].trim(), change: "—", rate: "—", direction: "—" });
    });
    return result;
  }

  function renderMarketTable(report, lines) {
    const structured = structuredMarketRows(report);
    const rows = structured.length ? structured : textMarketRows(lines);
    if (!rows.length) return '<p class="sop-empty">主要市場データを表として構成できませんでした。</p>';
    return `<div class="market-table-wrap"><table class="market-table market-table-five sop-market-table">
      <thead><tr><th>銘柄</th><th>確定終値・現在値</th><th>前日比</th><th>騰落率</th><th>状態</th></tr></thead>
      <tbody>${rows.map((row) => `<tr>
        <th scope="row">${escHtml(row.label)}</th><td>${escHtml(row.value)}</td><td>${escHtml(row.change)}</td><td>${escHtml(row.rate)}</td><td>${escHtml(row.direction)}</td>
      </tr>`).join("")}</tbody></table></div>`;
  }

  function renderText(lines) {
    const html = [];
    let list = [];
    let paragraph = [];
    const flushList = () => { if (list.length) { html.push(`<ul>${list.map((x) => `<li>${escHtml(x)}</li>`).join("")}</ul>`); list = []; } };
    const flushParagraph = () => { if (paragraph.length) { html.push(`<p>${escHtml(paragraph.join(" "))}</p>`); paragraph = []; } };
    (lines || []).forEach((raw) => {
      const line = publicText(raw);
      if (!line) { flushParagraph(); flushList(); return; }
      const bullet = line.match(/^(?:[・●■▶]|[-*]\s+)(.+)$/);
      if (bullet) { flushParagraph(); list.push(bullet[1].trim()); return; }
      if (/^\d+[.．]\s+/.test(line)) { flushParagraph(); list.push(line); return; }
      flushList();
      paragraph.push(line);
      if (paragraph.join(" ").length > 220 || /[。！？]$/.test(line)) flushParagraph();
    });
    flushParagraph(); flushList();
    return html.join("");
  }

  function structuredSections(report) {
    const list = [];
    const push = (title, value) => {
      const items = Array.isArray(value) ? value : (value == null || value === "" ? [] : [value]);
      const lines = items.map((item) => publicText(item)).filter(Boolean);
      if (lines.length) list.push({ title, lines });
    };
    push("今日の相場テーマ", report?.theme);
    push("前回からの変化", report?.changes);
    push("材料と値動きの整合性", report?.consistency);
    push("今日の主導市場", report?.leadingMarket);
    push("重要ニュース", report?.news);
    push("金利・為替の連動", report?.rates || report?.rateAnalysis);
    push("クロスアセット資金フロー", report?.crossAssetFlow);
    push("需給・ポジション", report?.positioning);
    if (Array.isArray(report?.markets) && report.markets.length) {
      list.push({ title: "個別市場見通し", lines: report.markets.map((m) => `${m.name || ""}：${m.outlook || m.material || m.direction || ""}`).filter(Boolean) });
    }
    push("重要イベント", report?.events);
    push("メインシナリオ", report?.mainScenario);
    push("代替シナリオ", report?.alternativeScenario);
    push("シナリオが崩れる条件", report?.breakConditions || report?.breakCondition);
    push("次の時間帯への引き継ぎ", report?.handover);
    push("リスク管理", report?.riskManagement);
    return list;
  }

  function looksLikeMarketSection(title) {
    return /主要市場データ|主要市場まとめ|主要価格|前営業日終値/.test(title || "");
  }

  function isInternalPreface(line) {
    const value = publicText(line);
    return !value || /^作成日時[：:]/.test(value) || /^ファイル名[：:]/.test(value) || /^データ基準[：:]/.test(value);
  }

  function renderSopReport(report) {
    if (!report || !ACTIVE_SLOTS.has(String(report.time || ""))) return false;
    const app = document.getElementById("app");
    if (!app) return false;

    const source = reportSource(report);
    const fallbackTitle = report.title || `マーケットレポート｜${report.date || ""} ${report.time || ""}`;
    const parsed = parseSections(source, fallbackTitle);
    const sourceSections = parsed.sections.length >= 3 ? parsed.sections : structuredSections(report);
    const tableRows = structuredMarketRows(report);

    const sections = [];
    const hasMarket = sourceSections.some((section) => looksLikeMarketSection(section.title));
    if (!hasMarket && tableRows.length) {
      const themeIndex = sourceSections.findIndex((s) => /今日の相場テーマ/.test(s.title));
      const insertAt = themeIndex >= 0 ? themeIndex + 1 : 0;
      sourceSections.splice(insertAt, 0, { title: "主要市場データ", lines: [] });
    }

    sourceSections.forEach((section) => {
      const title = normalizeHeading(section.title);
      if (!title) return;
      const body = looksLikeMarketSection(title) ? renderMarketTable(report, section.lines) : renderText(section.lines);
      if (!body) return;
      sections.push(`<section class="section sop-section" data-sop-title="${escHtml(title)}"><h2>${escHtml(title)}</h2>${body}</section>`);
    });

    if (!sections.length) return false;
    const sourceMode = report?.sourceDocument?.url ? "Googleドキュメント原文連携" : "構造化レポート連携";
    const preface = parsed.preface.map(publicText).filter((line) => !isInternalPreface(line));
    app.className = "report sop-report-applied";
    app.innerHTML = `<header class="report-head"><h1 class="report-title">${escHtml(parsed.title || fallbackTitle)}</h1><div class="source-badge">${escHtml(sourceMode)}</div></header>
      <article class="report-body">${preface.length ? `<div class="document-preface">${preface.map((line) => `<p>${escHtml(line)}</p>`).join("")}</div>` : ""}${sections.join("")}</article>`;

    const status = document.getElementById("reportStatus");
    if (status) status.textContent = `本文全文を表示中｜${sourceMode}｜SOP 5列表適用`;
    return true;
  }

  async function loadMorningReference() {
    try {
      const response = await fetch(`${MORNING_REFERENCE_URL}?ts=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) return;
      morningReference = await response.json();
      const report = currentReport();
      if (report?.time === "08:00") renderSopReport(report);
    } catch (error) {
      console.warn("morning reference load failed", error);
    }
  }

  try {
    if (typeof renderDocument === "function") {
      const legacyRenderDocument = renderDocument;
      renderDocument = function(report) {
        if (!renderSopReport(report)) legacyRenderDocument(report);
      };
    }
  } catch (error) {
    console.warn("SOP renderer override failed", error);
  }

  window.MarketReportSopRenderer = { render: renderSopReport, parseSections, structuredMarketRows };
  loadMorningReference();
})();
