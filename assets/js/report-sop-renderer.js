/* Unified SOP renderer for 08:00 / 12:00 / 16:00 / 21:00 market reports. */
(() => {
  "use strict";

  const ACTIVE_SLOTS = new Set(["08:00", "12:00", "16:00", "21:00"]);
  const MORNING_REFERENCE_URL = "data/market/morning-reference.json";
  let morningReference = null;

  const escHtml = (value = "") => String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

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
    match = raw.match(/^\s*(?:第?\d{1,2}|[一二三四五六七八九十]+)\s*[．.]\s*(.+?)\s*$/);
    if (match) return normalizeHeading(match[1]);
    match = raw.match(/^#{1,3}\s+(.+?)\s*$/);
    if (match) return normalizeHeading(match[1]);
    return "";
  }

  function isSectionHeading(rawLine, heading) {
    if (!heading || heading.length > 60) return false;
    const raw = String(rawLine || "").trim();
    if (/^【.+】$/.test(raw)) return true;
    if (/^#{1,3}\s+/.test(raw)) return true;
    if (/^\s*(?:第?\d{1,2}|[一二三四五六七八九十]+)\s*[．.]\s*/.test(raw)) {
      return !/[。！？!?]$/.test(heading);
    }
    return false;
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
      if (isSectionHeading(line, heading)) {
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
    if (Array.isArray(rawRows) && rawRows.length) {
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

    if (Array.isArray(report?.markets) && report.markets.length) {
      const rows = report.markets.map((market) => {
        const cr = splitChangeRate(market?.change, market?.rate ?? market?.changePercent);
        return {
          label: publicText(market?.name ?? ""),
          value: publicText(market?.price ?? "—") || "—",
          change: publicText(cr.change) || "—",
          rate: publicText(cr.rate) || "—",
          direction: publicText(market?.direction ?? "—") || "—"
        };
      }).filter((row) => row.label);
      return applyMorningReference(report, rows);
    }

    return [];
  }

  const INLINE_MARKET_LABELS = [
    "金・COMEX先物",
    "COMEX金先物",
    "WTI原油",
    "日経225先物（大阪取引所）",
    "日経225先物",
    "USD/JPY",
    "EUR/USD",
    "BTCUSD"
  ];

  function regexEscape(value) {
    return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function inlineMarketRows(lines) {
    const text = (lines || []).map((line) => publicText(line)).filter(Boolean).join(" ");
    if (!text) return [];
    const re = new RegExp(`(${INLINE_MARKET_LABELS.map(regexEscape).join("|")})[：:]\\s*`, "g");
    const matches = [...text.matchAll(re)];
    return matches.map((match, index) => {
      const start = match.index + match[0].length;
      const end = index + 1 < matches.length ? matches[index + 1].index : text.length;
      const value = text.slice(start, end).trim().replace(/^[、,。\s]+|[、,。\s]+$/g, "");
      return {
        label: match[1],
        value: value || "—",
        change: "—",
        rate: "—",
        direction: "—"
      };
    }).filter((row) => row.value !== "—");
  }

  const SUPPLEMENTARY_PATTERNS = [
    ["米2年債", /米2年債(?:利回り)?[：:]?\s*([0-9.]+%)/],
    ["米10年債", /米10年債(?:利回り)?[：:]?\s*([0-9.]+%)/],
    ["日本10年国債", /日本10年国債(?:利回り)?[：:]?\s*([0-9.]+%)/],
    ["VIX", /VIX(?:指数)?[：:]?\s*([0-9.]+)/],
    ["日経VI", /日経VI[：:]?\s*([0-9.]+)/],
    ["Fear & Greed Index", /(?<!Crypto\s)Fear\s*&\s*Greed(?:\s*Index)?[：:]?\s*([0-9]+(?:\s+[A-Za-z]+)?)/i]
  ];

  function supplementaryMarketRows(lines, existingRows) {
    const text = (lines || []).map((line) => publicText(line)).filter(Boolean).join(" ");
    if (!text) return [];
    const existingLabels = new Set((existingRows || []).map((row) => row.label));
    const rows = [];
    SUPPLEMENTARY_PATTERNS.forEach(([label, pattern]) => {
      if (existingLabels.has(label)) return;
      const match = text.match(pattern);
      if (!match) return;
      rows.push({ label, value: match[1], change: "—", rate: "—", direction: "—" });
    });
    return rows;
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

  function dedupeRows(rows) {
    const seen = new Set();
    return (rows || []).filter((row) => {
      const key = String(row?.label || "").trim();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function renderMarketTable(report, lines) {
    let rows = structuredMarketRows(report);
    if (!rows.length) rows = inlineMarketRows(lines);
    if (!rows.length) rows = textMarketRows(lines);
    rows = dedupeRows(rows.concat(supplementaryMarketRows(lines, rows)));

    if (!rows.length) return '<p class="sop-empty">主要市場データを表として構成できませんでした。</p>';
    return `<div class="market-table-wrap"><table class="market-table market-table-five sop-market-table">
      <thead><tr><th>銘柄</th><th>現在値・確認値</th><th>前日比</th><th>騰落率</th><th>方向・状態</th></tr></thead>
      <tbody>${rows.map((row) => `<tr>
        <th scope="row">${escHtml(row.label)}</th>
        <td>${escHtml(row.value)}</td>
        <td>${escHtml(row.change)}</td>
        <td>${escHtml(row.rate)}</td>
        <td>${escHtml(row.direction)}</td>
      </tr>`).join("")}</tbody></table></div>`;
  }

  function renderText(lines) {
    const html = [];
    let list = [];
    let paragraph = [];
    const flushList = () => {
      if (!list.length) return;
      html.push(`<ul>${list.map((x) => `<li>${escHtml(x)}</li>`).join("")}</ul>`);
      list = [];
    };
    const flushParagraph = () => {
      if (!paragraph.length) return;
      html.push(`<p>${escHtml(paragraph.join(" "))}</p>`);
      paragraph = [];
    };
    (lines || []).forEach((raw) => {
      const line = publicText(raw);
      if (!line) {
        flushParagraph();
        flushList();
        return;
      }
      const bullet = line.match(/^(?:[・●■▶]|[-*]\s+)(.+)$/);
      if (bullet) {
        flushParagraph();
        list.push(bullet[1].trim());
        return;
      }
      if (/^\d+[.．]\s+/.test(line)) {
        flushParagraph();
        list.push(line);
        return;
      }
      flushList();
      paragraph.push(line);
      if (paragraph.join(" ").length > 220 || /[。！？]$/.test(line)) flushParagraph();
    });
    flushParagraph();
    flushList();
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
      list.push({
        title: "個別市場見通し",
        lines: report.markets.map((market) => `${market.name || ""}：${market.outlook || market.material || market.direction || ""}`).filter(Boolean)
      });
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
    return /主要市場データ|主要市場まとめ|主要価格|前営業日終値|終値一覧/.test(title || "");
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
    const sourceSections = parsed.sections.length >= 3 ? parsed.sections.slice() : structuredSections(report);
    const tableRows = structuredMarketRows(report);

    const sections = [];
    const hasMarket = sourceSections.some((section) => looksLikeMarketSection(section.title));
    if (!hasMarket && tableRows.length) {
      const themeIndex = sourceSections.findIndex((section) => /今日の相場テーマ/.test(section.title));
      const insertAt = themeIndex >= 0 ? themeIndex + 1 : 0;
      sourceSections.splice(insertAt, 0, { title: "主要市場データ", lines: [] });
    }

    sourceSections.forEach((section) => {
      const title = normalizeHeading(section.title);
      if (!title) return;
      const body = looksLikeMarketSection(title)
        ? renderMarketTable(report, section.lines)
        : renderText(section.lines);
      if (!body) return;
      sections.push(`<section class="section sop-section" data-sop-title="${escHtml(title)}"><h2>${escHtml(title)}</h2>${body}</section>`);
    });

    if (!sections.length) return false;
    const sourceMode = report?.sourceDocument?.url || source ? "Googleドキュメント原文連携" : "構造化レポート連携";
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
