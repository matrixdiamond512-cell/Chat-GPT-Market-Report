/* 2026-08-17 report layout/table hotfix.
 * Keeps source text intact while making bracket headings independent sections
 * and turning inline intraday market data into a readable 5-column table.
 */
(() => {
  "use strict";

  const ACTIVE = new Set(["08:00", "12:00", "16:00", "21:00"]);
  const esc = (v = "") => String(v)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  const clean = (v = "") => String(v || "").replace(/\r/g, "").trim();

  function sourceOf(report) {
    return clean(report?.fullText || report?.rawText || report?.body || "");
  }

  function parse(source, fallbackTitle) {
    const lines = String(source || "").split("\n");
    let title = fallbackTitle || "マーケットレポート";
    const preface = [];
    const sections = [];
    let current = null;

    lines.forEach((raw, i) => {
      const line = raw.trim();
      if (i === 0 && /^マーケットレポート[｜|]/.test(line)) {
        title = line;
        return;
      }
      let heading = "";
      const bracket = line.match(/^【\s*(.+?)\s*】$/);
      const numbered = line.match(/^\s*\d{1,2}[．.]\s*(.+?)\s*$/);
      const markdown = line.match(/^#{1,3}\s+(.+?)\s*$/);
      if (bracket) heading = bracket[1].trim();
      else if (numbered) heading = numbered[1].trim();
      else if (markdown) heading = markdown[1].trim();

      if (heading && heading.length <= 50) {
        if (current) sections.push(current);
        current = { title: heading, lines: [] };
        return;
      }
      if (current) current.lines.push(raw);
      else preface.push(raw);
    });
    if (current) sections.push(current);
    return { title, preface, sections };
  }

  function isMarketSection(title) {
    return /主要市場データ|主要市場まとめ|主要価格|前営業日終値|終値一覧/.test(title || "");
  }

  function structuredRows(report) {
    const rows = [];
    const sourceRows = report?.marketDataTable?.rows;
    if (Array.isArray(sourceRows) && sourceRows.length) {
      sourceRows.forEach((r) => rows.push({
        label: clean(r?.label ?? r?.item ?? r?.name),
        value: clean(r?.value ?? r?.price) || "—",
        change: clean(r?.change) || "—",
        rate: clean(r?.rate ?? r?.changePercent) || "—",
        direction: clean(r?.direction ?? r?.status) || "—"
      }));
      return rows.filter((r) => r.label);
    }
    if (Array.isArray(report?.markets)) {
      report.markets.forEach((m) => rows.push({
        label: clean(m?.name),
        value: clean(m?.price) || "—",
        change: clean(m?.change) || "—",
        rate: clean(m?.rate ?? m?.changePercent) || "—",
        direction: clean(m?.direction) || "—"
      }));
    }
    return rows.filter((r) => r.label);
  }

  const EXTRA_PATTERNS = [
    ["米2年債", /米2年債(?:利回り)?[：:]?\s*([0-9.]+%)/],
    ["米10年債", /米10年債(?:利回り)?[：:]?\s*([0-9.]+%)/],
    ["日本10年国債", /日本10年国債(?:利回り)?[：:]?\s*([0-9.]+%)/],
    ["VIX", /VIX[：:]?\s*([0-9.]+)/],
    ["日経VI", /日経VI[：:]?\s*([0-9.]+)/],
    ["Fear & Greed", /(?<!Crypto\s)Fear\s*&\s*Greed[：:]?\s*([0-9]+(?:\s+[A-Za-z]+)?)/i],
    ["Crypto Fear & Greed", /Crypto\s+Fear\s*&\s*Greed[：:]?\s*([0-9]+(?:\s+[A-Za-z]+)?)/i]
  ];

  function supplementaryRows(lines, existing) {
    const text = (lines || []).map(clean).filter(Boolean).join(" ");
    const seen = new Set(existing.map((r) => r.label));
    const out = [];
    EXTRA_PATTERNS.forEach(([label, re]) => {
      if (seen.has(label)) return;
      const m = text.match(re);
      if (!m) return;
      out.push({ label, value: m[1], change: "—", rate: "—", direction: "—" });
    });
    return out;
  }

  function inlineRows(lines) {
    const text = (lines || []).map(clean).filter(Boolean).join(" ");
    if (!text) return [];
    const labels = ["金・COMEX先物", "COMEX金先物", "WTI原油", "日経225先物（大阪取引所）", "日経225先物", "USD/JPY", "EUR/USD", "BTCUSD"];
    const escaped = labels.map((x) => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const re = new RegExp(`(${escaped.join("|")})[：:]\\s*`, "g");
    const matches = [...text.matchAll(re)];
    return matches.map((m, i) => {
      const start = m.index + m[0].length;
      const end = i + 1 < matches.length ? matches[i + 1].index : text.length;
      const value = text.slice(start, end).trim().replace(/^[、,。\s]+|[、,。\s]+$/g, "");
      return { label: m[1], value: value || "—", change: "—", rate: "—", direction: "—" };
    }).filter((r) => r.value !== "—");
  }

  function marketTable(report, lines) {
    let rows = structuredRows(report);
    if (!rows.length) rows = inlineRows(lines);
    rows = rows.concat(supplementaryRows(lines, rows));
    if (!rows.length) return '<p class="sop-empty">主要市場データを表として構成できませんでした。</p>';
    return `<div class="market-table-wrap"><table class="market-table market-table-five sop-market-table">
      <thead><tr><th>銘柄</th><th>確定終値・現在値</th><th>前日比</th><th>騰落率</th><th>方向・状態</th></tr></thead>
      <tbody>${rows.map((r) => `<tr><th scope="row">${esc(r.label)}</th><td>${esc(r.value)}</td><td>${esc(r.change)}</td><td>${esc(r.rate)}</td><td>${esc(r.direction)}</td></tr>`).join("")}</tbody>
    </table></div>`;
  }

  function richText(lines) {
    const html = [];
    let paragraph = [];
    let list = [];
    const flushP = () => { if (paragraph.length) { html.push(`<p>${esc(paragraph.join(" "))}</p>`); paragraph = []; } };
    const flushL = () => { if (list.length) { html.push(`<ul>${list.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`); list = []; } };
    (lines || []).forEach((raw) => {
      const line = clean(raw);
      if (!line) { flushP(); flushL(); return; }
      const bullet = line.match(/^(?:[・●■▶]|[-*]\s+)(.+)$/);
      if (bullet) { flushP(); list.push(bullet[1].trim()); return; }
      flushL();
      paragraph.push(line);
      if (paragraph.join(" ").length > 240 || /[。！？]$/.test(line)) flushP();
    });
    flushP(); flushL();
    return html.join("");
  }

  function renderFixed(report) {
    if (!report || !ACTIVE.has(String(report.time || ""))) return false;
    const source = sourceOf(report);
    if (!source || !/【.+?】/.test(source)) return false;
    const app = document.getElementById("app");
    if (!app) return false;
    const parsed = parse(source, report.title || "マーケットレポート");
    if (parsed.sections.length < 3) return false;

    const sections = parsed.sections.map((s) => {
      const body = isMarketSection(s.title) ? marketTable(report, s.lines) : richText(s.lines);
      return `<section class="section sop-section" data-sop-title="${esc(s.title)}"><h2>${esc(s.title)}</h2>${body}</section>`;
    }).join("");

    const preface = parsed.preface.map(clean).filter((x) => x && !/^作成日時[：:]/.test(x) && !/^ファイル名[：:]/.test(x) && !/^データ基準[：:]/.test(x));
    app.className = "report sop-report-applied";
    app.innerHTML = `<header class="report-head"><h1 class="report-title">${esc(parsed.title)}</h1><div class="source-badge">Googleドキュメント原文連携</div></header><article class="report-body">${preface.length ? `<div class="document-preface">${preface.map((x) => `<p>${esc(x)}</p>`).join("")}</div>` : ""}${sections}</article>`;
    const status = document.getElementById("reportStatus");
    if (status) status.textContent = "本文全文を表示中｜Googleドキュメント原文連携｜SOP 5列表適用";
    return true;
  }

  try {
    if (typeof renderDocument === "function") {
      const previous = renderDocument;
      renderDocument = function(report) {
        if (!renderFixed(report)) previous(report);
      };
    }
  } catch (error) {
    console.warn("report layout hotfix failed", error);
  }
})();
