/*
 * 21:00 market report manual-enforcement renderer.
 *
 * Purpose:
 * - Keep the Google Docs source intact while presenting the portal in the SOP order.
 * - Always render "主要市場データ" as a table.
 * - Keep internal QA wording such as "verified" out of the public UI.
 * - Preserve source content; low-priority acquisition notes are moved into a collapsed details block.
 * - From 2026-08-13 onward, hold a malformed 21:00 report instead of showing a broken layout.
 *
 * This is intentionally a presentation/QA layer. It does not invent or repair market data.
 */
(() => {
  "use strict";

  const ENFORCE_FROM = "2026-08-13";
  const REQUIRED_21_KEYS = [
    "marketData", "theme", "changes", "consistency", "leading", "news", "flow",
    "positioning", "events", "outlooks", "mainScenario", "alternativeScenario",
    "breakConditions", "handover"
  ];
  const REQUIRED_CORE_MARKETS = ["金", "WTI原油", "日経225先物（大阪取引所）", "USD/JPY", "EUR/USD", "BTCUSD"];

  const SECTION_SPECS = [
    { key: "dataCheck", title: "データ取得・確認情報", patterns: [/^データ確認$/, /^データ取得(?:・確認)?$/] },
    { key: "marketData", title: "主要市場データ", patterns: [/^主要市場データ(?:（.*）)?$/, /^主要価格$/, /^市場データ$/] },
    { key: "theme", title: "今日の相場テーマ", patterns: [/^今日の相場テーマ$/, /^今日のテーマ$/] },
    { key: "changes", title: "16:00からの変化", patterns: [/^16:00からの変化$/, /^16時からの変化$/, /^前回からの(?:主な)?変化$/] },
    { key: "consistency", title: "材料と値動きの整合性", patterns: [/^材料と値動きの整合性$/, /^材料.*整合性$/] },
    { key: "leading", title: "今日の主導市場", patterns: [/^今日の主導市場$/, /^主導市場$/] },
    { key: "news", title: "重要ニュース", patterns: [/^重要ニュース$/, /^重要材料$/] },
    { key: "rates", title: "金利・為替の連動", patterns: [/^金利$/, /^金利・為替(?:の連動)?$/, /^金利分析$/] },
    { key: "flow", title: "クロスアセット資金フロー", patterns: [/^クロスアセット(?:資金フロー)?$/, /^資金フロー$/] },
    { key: "positioning", title: "需給・ポジション", patterns: [/^需給・ポジション$/, /^需給(?:・ポジショニング)?$/, /^ポジションの偏り$/] },
    { key: "events", title: "今後の重要イベント", patterns: [/^今後の重要イベント$/, /^重要イベント$/, /^今後の予定$/] },
    { key: "outlooks", title: "6市場の個別見通し", patterns: [/^6市場の見通し$/, /^6市場の個別見通し$/, /^個別見通し$/] },
    { key: "mainScenario", title: "メインシナリオ", patterns: [/^メインシナリオ$/, /^基本シナリオ$/] },
    { key: "alternativeScenario", title: "代替シナリオ", patterns: [/^代替シナリオ$/, /^別シナリオ$/] },
    { key: "breakConditions", title: "シナリオが崩れる条件", patterns: [/^シナリオが崩れる条件$/, /^崩れる条件$/] },
    { key: "handover", title: "NY時間への引き継ぎ", patterns: [/^NY時間への引き継ぎ$/, /^次の時間帯への引き継ぎ$/, /^翌東京時間への引き継ぎ$/] },
    { key: "risk", title: "リスク管理", patterns: [/^リスク管理$/, /^主なリスク$/, /^リスク要因$/] },
    { key: "conclusion", title: "結論", patterns: [/^結論$/, /^まとめ$/] }
  ];

  const RENDER_ORDER = [
    "marketData", "theme", "changes", "consistency", "leading", "flow", "rates",
    "positioning", "news", "outlooks", "events", "handover", "mainScenario",
    "alternativeScenario", "breakConditions", "risk", "conclusion"
  ];

  const MARKET_LINE_RE = /^(金(?:・先物|・スポット|（[^）]+）)?|ゴールド|COMEX金先物|WTI原油|原油|日経225先物(?:（大阪取引所）)?|USD\/JPY|EUR\/USD|BTCUSD|米10年債利回り|日本10年国債利回り|VIX|日経VI|Fear\s*&\s*Greed(?:\s*Index)?)[：:]\s*(.*)$/i;
  const OUTLOOK_LINE_RE = /^(金|ゴールド|WTI原油|原油|日経225先物(?:（大阪取引所）)?|USD\/JPY|EUR\/USD|BTCUSD)[：:]\s*(.*)$/i;

  function escapeHtml(value = "") {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function publicText(value = "") {
    return String(value)
      .replace(/\bverified\b/gi, "確認済み")
      .replace(/\s+/g, " ")
      .trim();
  }

  function currentReport() {
    try {
      return selectedReport || null;
    } catch (error) {
      return null;
    }
  }

  function reportSource(report) {
    if (!report) return "";
    try {
      if (typeof fullTextOf === "function") return fullTextOf(report);
    } catch (error) {
      // Fall through to raw fields.
    }
    return String(report.fullText || report.rawText || report.body || "").replace(/\r/g, "").trim();
  }

  function normalizeHeading(line) {
    return String(line || "")
      .trim()
      .replace(/^【|】$/g, "")
      .replace(/^\s*(?:第?\d{1,2}|[一二三四五六七八九十]+)\s*[．.、:：)）]\s*/, "")
      .replace(/^[■◆◇●]\s*/, "")
      .trim();
  }

  function headingSpec(line) {
    const normalized = normalizeHeading(line);
    return SECTION_SPECS.find((spec) => spec.patterns.some((pattern) => pattern.test(normalized))) || null;
  }

  function parseSections(source) {
    const sections = new Map();
    const preface = [];
    let active = null;

    String(source || "").split("\n").forEach((rawLine) => {
      const line = rawLine.trim();
      const spec = headingSpec(line);
      if (spec) {
        active = spec.key;
        if (!sections.has(active)) sections.set(active, []);
        return;
      }
      if (active) sections.get(active).push(rawLine);
      else preface.push(rawLine);
    });

    return { sections, preface };
  }

  function meaningfulLines(lines) {
    return (lines || []).map((line) => publicText(line)).filter(Boolean);
  }

  function firstSentence(lines) {
    const joined = meaningfulLines(lines).join(" ");
    if (!joined) return "";
    const match = joined.match(/^.*?[。！？](?:\s|$)/);
    return publicText(match ? match[0] : joined);
  }

  function directionFrom(text) {
    const value = publicText(text);
    if (/上昇|反発|強含み|買い優勢|上値追い/.test(value)) return "↑ 上昇・強含み";
    if (/下落|低下|反落|弱含み|売り優勢|軟調/.test(value)) return "↓ 下落・弱含み";
    if (/横ばい|方向.*出にく|レンジ|もみ合/.test(value)) return "→ 横ばい・レンジ";
    return "—";
  }

  function normalizeMarketName(name) {
    const value = publicText(name);
    if (/^(金|ゴールド|COMEX金)/.test(value)) return "金";
    if (/^(WTI|原油)/.test(value)) return "WTI原油";
    if (/^日経225先物/.test(value)) return "日経225先物（大阪取引所）";
    return value;
  }

  function collectMarketRows(lines) {
    const rows = [];
    let current = null;

    (lines || []).forEach((rawLine) => {
      const line = publicText(rawLine);
      if (!line) return;
      const match = line.match(MARKET_LINE_RE);
      if (match) {
        if (current) rows.push(current);
        current = { name: normalizeMarketName(match[1]), body: match[2] || "" };
      } else if (current) {
        current.body = `${current.body} ${line}`.trim();
      }
    });
    if (current) rows.push(current);

    return rows.map((row) => {
      const body = publicText(row.body);
      const bracketIndex = body.search(/[（(]/);
      const price = publicText(bracketIndex >= 0 ? body.slice(0, bracketIndex) : body.split("。")[0]);
      let note = publicText(bracketIndex >= 0 ? body.slice(bracketIndex) : body.slice(price.length));
      note = note.replace(/^[（(]|[）)]$/g, "").trim() || "—";
      return {
        name: row.name,
        price: price || "—",
        direction: directionFrom(body),
        note
      };
    });
  }

  function splitReadableParts(line) {
    const text = publicText(line);
    if (!text) return [];
    if (text.length < 150) return [text];

    const pieces = text.match(/[^。！？]+[。！？]?/g) || [text];
    const chunks = [];
    let current = "";
    pieces.forEach((piece) => {
      const next = `${current}${piece}`.trim();
      if (current && next.length > 190) {
        chunks.push(current.trim());
        current = piece;
      } else {
        current = next;
      }
    });
    if (current.trim()) chunks.push(current.trim());
    return chunks;
  }

  function renderMarketTable(lines) {
    const rows = collectMarketRows(lines);
    if (!rows.length) return renderReadableText(lines);
    return `<div class="manual21-table-wrap"><table class="manual21-table">
      <thead><tr><th>市場</th><th>価格・水準</th><th>方向・状況</th><th>確認状況・補足</th></tr></thead>
      <tbody>${rows.map((row) => `<tr>
        <th scope="row">${escapeHtml(row.name)}</th>
        <td class="manual21-value">${escapeHtml(row.price)}</td>
        <td>${escapeHtml(row.direction)}</td>
        <td>${escapeHtml(row.note)}</td>
      </tr>`).join("")}</tbody>
    </table></div>`;
  }

  function renderReadableText(lines) {
    const clean = meaningfulLines(lines);
    if (!clean.length) return "";

    const pieces = [];
    clean.forEach((line) => {
      const bullet = line.match(/^(?:[・●■▶]|[-*]\s+)(.+)$/);
      if (bullet) {
        pieces.push(`<li>${escapeHtml(bullet[1])}</li>`);
        return;
      }
      splitReadableParts(line).forEach((part) => pieces.push(`<p>${escapeHtml(part)}</p>`));
    });

    return pieces.reduce((html, piece) => {
      if (piece.startsWith("<li>")) {
        if (html.endsWith("</ul>")) return html.slice(0, -5) + piece + "</ul>";
        return html + `<ul>${piece}</ul>`;
      }
      return html + piece;
    }, "");
  }

  function renderOutlooks(lines) {
    const cards = [];
    let current = null;
    meaningfulLines(lines).forEach((line) => {
      const match = line.match(OUTLOOK_LINE_RE);
      if (match) {
        if (current) cards.push(current);
        current = { name: normalizeMarketName(match[1]), body: match[2] || "" };
      } else if (current) {
        current.body = `${current.body} ${line}`.trim();
      }
    });
    if (current) cards.push(current);
    if (!cards.length) return renderReadableText(lines);

    return `<div class="manual21-outlook-grid">${cards.map((card) => `
      <article class="manual21-outlook-card">
        <h3>${escapeHtml(card.name)}</h3>
        ${splitReadableParts(card.body).map((part) => `<p>${escapeHtml(part)}</p>`).join("")}
      </article>`).join("")}</div>`;
  }

  function renderSection(key, lines) {
    const spec = SECTION_SPECS.find((item) => item.key === key);
    if (!spec || !meaningfulLines(lines).length) return "";
    let content = renderReadableText(lines);
    if (key === "marketData") content = renderMarketTable(lines);
    if (key === "outlooks") content = renderOutlooks(lines);

    const emphasis = ["theme", "changes", "consistency", "leading", "mainScenario", "alternativeScenario", "breakConditions", "risk", "conclusion"].includes(key)
      ? " manual21-section--emphasis"
      : "";

    return `<section class="section manual21-section${emphasis}" data-manual21-section="${escapeHtml(key)}">
      <h2>${escapeHtml(spec.title)}</h2>
      <div class="manual21-section-body">${content}</div>
    </section>`;
  }

  function renderSummary(parsed) {
    const cards = [
      ["相場テーマ", firstSentence(parsed.sections.get("theme"))],
      ["主導市場", firstSentence(parsed.sections.get("leading"))],
      ["最重要イベント", firstSentence(parsed.sections.get("events"))],
      ["NY時間の確認点", firstSentence(parsed.sections.get("handover"))]
    ].filter((item) => item[1]);

    if (!cards.length) return "";
    return `<section class="manual21-summary" aria-label="21時時点の要点">
      <h2>21時時点の要点</h2>
      <div class="manual21-summary-grid">${cards.map(([label, value]) => `
        <article class="manual21-summary-card"><h3>${escapeHtml(label)}</h3><p>${escapeHtml(value)}</p></article>`).join("")}</div>
    </section>`;
  }

  function renderDataCheck(lines) {
    if (!meaningfulLines(lines).length) return "";
    return `<details class="manual21-data-check">
      <summary>データ取得・確認情報</summary>
      <div>${renderReadableText(lines)}</div>
    </details>`;
  }

  function qaIssues(report, source, parsed) {
    if (String(report.date || "") < ENFORCE_FROM) return [];
    const issues = [];

    REQUIRED_21_KEYS.forEach((key) => {
      if (!meaningfulLines(parsed.sections.get(key)).length) {
        const spec = SECTION_SPECS.find((item) => item.key === key);
        issues.push(`${spec ? spec.title : key} がありません`);
      }
    });

    const marketRows = collectMarketRows(parsed.sections.get("marketData"));
    const marketNames = new Set(marketRows.map((row) => row.name));
    REQUIRED_CORE_MARKETS.forEach((name) => {
      if (!marketNames.has(name)) issues.push(`主要市場データに ${name} がありません`);
    });

    if (/\bverified\b/i.test(source)) issues.push("公開本文に内部確認用語 verified が残っています");
    if (/未確認/.test(source)) issues.push("公開本文に『未確認』が残っています");

    return issues;
  }

  function renderQaHold(issues) {
    return `<section class="manual21-qa-hold" role="status" aria-live="polite">
      <h2>21:00レポートは公開保留中です</h2>
      <p>マニュアルの公開前チェックを通過していないため、読みにくい・不完全な本文は表示していません。</p>
      <details>
        <summary>検出した項目</summary>
        <ul>${issues.map((issue) => `<li>${escapeHtml(issue)}</li>`).join("")}</ul>
      </details>
    </section>`;
  }

  function applyManualLayout() {
    const report = currentReport();
    if (!report || String(report.time || "") !== "21:00") return;

    const app = document.getElementById("app");
    const body = app && app.querySelector(".report-body");
    if (!app || !body) return;

    const key = `${report.date || ""} ${report.time || ""}`;
    if (app.dataset.manual21Key === key) return;

    const source = reportSource(report);
    if (!source) return;
    const parsed = parseSections(source);
    const issues = qaIssues(report, source, parsed);

    if (issues.length) {
      body.innerHTML = renderQaHold(issues);
      app.dataset.manual21Key = key;
      app.classList.add("manual21-applied", "manual21-qa-blocked");
      const status = document.getElementById("reportStatus");
      if (status) status.textContent = "21:00 SOP QA未通過｜公開保留";
      return;
    }

    if (!parsed.sections.has("marketData")) return;

    const known = new Set(RENDER_ORDER);
    let html = renderSummary(parsed);
    RENDER_ORDER.forEach((sectionKey) => {
      html += renderSection(sectionKey, parsed.sections.get(sectionKey));
    });

    parsed.sections.forEach((lines, sectionKey) => {
      if (known.has(sectionKey) || sectionKey === "dataCheck") return;
      html += renderSection(sectionKey, lines);
    });
    html += renderDataCheck(parsed.sections.get("dataCheck"));

    body.innerHTML = html;
    app.dataset.manual21Key = key;
    app.classList.add("manual21-applied");
    app.classList.remove("manual21-qa-blocked");

    const status = document.getElementById("reportStatus");
    if (status) status.textContent = "本文全文を表示中｜21:00 SOPレイアウト適用済み";
  }

  let scheduled = false;
  function scheduleApply() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      applyManualLayout();
    });
  }

  const observer = new MutationObserver(scheduleApply);
  const start = () => {
    const app = document.getElementById("app");
    if (app) observer.observe(app, { childList: true, subtree: true });
    scheduleApply();
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
