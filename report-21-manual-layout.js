/*
 * Market report manual-enforcement renderer / QA gate.
 *
 * 08:00: keep the dedicated 28-row morning renderer, but block publication in
 *         the portal when the source omits required SOP sections/data.
 * 12:00 / 16:00 / 21:00: render the report in the fixed SOP order and turn
 *         major-market data into the manual's five-column table.
 *
 * From 2026-08-13 onward, malformed reports are held instead of exposing a
 * broken or internally-oriented document. This layer never invents market data.
 */
(() => {
  "use strict";

  const ENFORCE_FROM = "2026-08-13";
  const SLOT_CONFIG = {
    "08:00": {
      render: false,
      summaryTitle: "8時時点の要点",
      changeTitle: "前回からの変化",
      handoverLabel: "東京時間の確認点"
    },
    "12:00": {
      render: true,
      summaryTitle: "12時時点の要点",
      changeTitle: "08:00からの変化",
      handoverLabel: "欧州時間の確認点"
    },
    "16:00": {
      render: true,
      summaryTitle: "16時時点の要点",
      changeTitle: "12:00からの変化",
      handoverLabel: "NY時間の確認点"
    },
    "21:00": {
      render: true,
      summaryTitle: "21時時点の要点",
      changeTitle: "16:00からの変化",
      handoverLabel: "NY時間・翌東京時間の確認点"
    }
  };

  const REQUIRED_SECTION_KEYS = [
    "marketData", "theme", "changes", "consistency", "leading", "news", "rates", "flow",
    "positioning", "events", "outlooks", "mainScenario", "alternativeScenario",
    "breakConditions", "handover", "risk", "conclusion"
  ];

  const REQUIRED_CORE_MARKETS = ["金", "WTI原油", "日経225先物（大阪取引所）", "USD/JPY", "EUR/USD", "BTCUSD"];
  const MORNING_REQUIRED_LABELS = [
    "NYダウ", "NASDAQ総合", "S&P500", "Russell 2000", "日経225現物",
    "CME日経225先物・円建て", "CME日経225先物・ドル建て", "日経225先物（大阪取引所）",
    "USD/JPY", "EUR/USD", "COMEX金先物", "WTI原油", "BTCUSD", "VIX", "日経VI",
    "Fear & Greed Index", "米10年債利回り", "日本10年国債利回り", "日経225予想PER",
    "日経225 PBR", "日経225予想EPS", "日経225 25日移動平均乖離率",
    "日経225 200日移動平均乖離率", "東証プライム売買代金", "東証プライム売買高",
    "東証プライム値上がり銘柄数", "東証プライム値下がり銘柄数", "東証プライム25日騰落レシオ"
  ];

  const SECTION_SPECS = [
    { key: "dataCheck", title: "データ取得・確認情報", patterns: [/^データ確認$/, /^データ取得(?:・確認)?$/, /^データ同期・検証状況$/] },
    { key: "marketData", title: "主要市場データ", patterns: [/^主要市場データ(?:（.*）)?$/, /^主要市場まとめ$/, /^主要価格$/, /^市場データ$/] },
    { key: "theme", title: "今日の相場テーマ", patterns: [/^今日の相場テーマ$/, /^今日のテーマ$/] },
    { key: "changes", title: "前回からの変化", patterns: [/^(?:07:00|08:00|12:00|16:00|21:00|07時|08時|12時|16時|21時|前回|前営業日|前日21:00|NY市場)からの(?:主な)?変化$/, /^前回からの市場解釈の変化$/] },
    { key: "consistency", title: "材料と値動きの整合性", patterns: [/^材料と値動きの整合性$/, /^材料.*整合性$/] },
    { key: "leading", title: "今日の主導市場", patterns: [/^今日の主導市場$/, /^主導市場$/] },
    { key: "news", title: "重要ニュース", patterns: [/^重要ニュース$/, /^重要材料$/] },
    { key: "rates", title: "金利", patterns: [/^金利$/, /^金利・為替(?:の連動)?$/, /^金利分析$/] },
    { key: "flow", title: "クロスアセット資金フロー", patterns: [/^クロスアセット(?:資金フロー)?$/, /^資金フロー$/] },
    { key: "positioning", title: "需給・ポジション", patterns: [/^需給・ポジション$/, /^需給(?:・ポジショニング)?$/, /^ポジションの偏り$/] },
    { key: "events", title: "重要イベント", patterns: [/^今後の重要イベント$/, /^重要イベント$/, /^今後の予定$/] },
    { key: "outlooks", title: "個別市場見通し", patterns: [/^6市場の見通し$/, /^6市場の個別見通し$/, /^個別市場見通し$/, /^個別見通し$/] },
    { key: "mainScenario", title: "メインシナリオ", patterns: [/^メインシナリオ$/, /^基本シナリオ$/] },
    { key: "alternativeScenario", title: "代替シナリオ", patterns: [/^代替シナリオ$/, /^別シナリオ$/] },
    { key: "breakConditions", title: "シナリオが崩れる条件", patterns: [/^シナリオが崩れる条件$/, /^崩れる条件$/] },
    { key: "handover", title: "次の時間帯への引き継ぎ", patterns: [/^東京時間への引き継ぎ$/, /^東京市場への引き継ぎ$/, /^欧州時間への引き継ぎ$/, /^欧州市場への引き継ぎ$/, /^NY時間への引き継ぎ$/, /^NY市場への引き継ぎ$/, /^次の時間帯への引き継ぎ$/, /^翌東京時間への引き継ぎ$/] },
    { key: "risk", title: "リスク管理", patterns: [/^リスク管理$/, /^主なリスク$/, /^リスク要因$/] },
    { key: "conclusion", title: "結論", patterns: [/^結論$/, /^まとめ$/, /^最終判断$/] }
  ];

  const RENDER_ORDER = [
    "marketData", "theme", "changes", "consistency", "leading", "news", "rates", "flow",
    "positioning", "outlooks", "events", "mainScenario", "alternativeScenario",
    "breakConditions", "handover", "risk", "conclusion"
  ];

  const MARKET_LINE_RE = /^(金(?:・先物|・スポット|（[^）]+）)?|ゴールド|COMEX金先物|WTI原油|原油|日経225先物(?:（大阪取引所）)?|USD\/JPY|USDJPY|ドル円|EUR\/USD|EURUSD|ユーロドル|BTCUSD|BTC\/USD|ビットコイン|米10年債利回り|日本10年国債利回り|VIX|日経VI|Fear\s*&\s*Greed(?:\s*Index)?)[：:]\s*(.*)$/i;
  const OUTLOOK_LINE_RE = /^(金|ゴールド|WTI原油|原油|日経225先物(?:（大阪取引所）)?|USD\/JPY|USDJPY|ドル円|EUR\/USD|EURUSD|ユーロドル|BTCUSD|BTC\/USD|ビットコイン)[：:]\s*(.*)$/i;

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
    try { return selectedReport || null; } catch (error) { return null; }
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
      .replace(/^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘]\s*/, "")
      .replace(/^\s*(?:第?\d{1,2}|[一二三四五六七八九十]+)\s*[．.、)）]\s*/, "")
      .replace(/^[■◆◇●▶]\s*/, "")
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
    if (/上昇|反発|強含み|買い優勢|上値追い|ドル高|利回り上昇/.test(value)) return "上昇・強含み";
    if (/下落|低下|反落|弱含み|売り優勢|軟調|ドル安|利回り低下/.test(value)) return "下落・弱含み";
    if (/横ばい|方向.*出にく|レンジ|もみ合|保ち合/.test(value)) return "横ばい・レンジ";
    return "—";
  }

  function normalizeMarketName(name) {
    const value = publicText(name);
    if (/^(金|ゴールド|COMEX金)/.test(value)) return "金";
    if (/^(WTI|原油)/.test(value)) return "WTI原油";
    if (/^日経225先物/.test(value)) return "日経225先物（大阪取引所）";
    if (/^(USD\/JPY|USDJPY|ドル円)$/i.test(value)) return "USD/JPY";
    if (/^(EUR\/USD|EURUSD|ユーロドル)$/i.test(value)) return "EUR/USD";
    if (/^(BTCUSD|BTC\/USD|ビットコイン)$/i.test(value)) return "BTCUSD";
    return value;
  }

  function parseBodyRow(name, body) {
    const clean = publicText(body);
    const paren = clean.match(/^([^（(]+?)\s*[（(]([^）)]*)[）)]\s*(.*)$/);
    let value = clean;
    let change = "—";
    let rate = "—";
    let state = directionFrom(clean);
    let note = "";

    if (paren) {
      value = publicText(paren[1]);
      const tokens = paren[2].split(/[、,]/).map((token) => publicText(token)).filter(Boolean);
      const rateToken = tokens.find((token) => /%/.test(token));
      const changeToken = tokens.find((token) => token !== rateToken && /^[+＋\-−]?\s*[\d,.]+/.test(token));
      const stateToken = tokens.find((token) => /上昇|下落|横ばい|強含み|弱含み|ドル高|ドル安|利回り/.test(token));
      if (changeToken) change = changeToken;
      if (rateToken) rate = rateToken;
      if (stateToken) state = stateToken;
      const used = new Set([changeToken, rateToken, stateToken].filter(Boolean));
      note = tokens.filter((token) => !used.has(token)).join("、");
      if (paren[3]) note = [note, publicText(paren[3])].filter(Boolean).join(" ");
    } else {
      const sentenceEnd = clean.indexOf("。");
      if (sentenceEnd > 0) {
        value = publicText(clean.slice(0, sentenceEnd));
        note = publicText(clean.slice(sentenceEnd + 1));
      }
    }

    return { name: normalizeMarketName(name), value: value || "—", change, rate, state, note };
  }

  function collectMarketRows(lines) {
    const clean = meaningfulLines(lines);
    const rows = [];
    const consumed = new Set();

    clean.forEach((line, index) => {
      if (!/^\|/.test(line)) return;
      const cells = line.split("|").map((cell) => publicText(cell)).filter(Boolean);
      if (cells.length < 5) return;
      const name = normalizeMarketName(cells[0]);
      if (!REQUIRED_CORE_MARKETS.includes(name) && !/米10年債|日本10年|VIX|日経VI|Fear/.test(name)) return;
      rows.push({ name, value: cells[1], change: cells[2], rate: cells[3], state: cells[4], note: cells.slice(5).join(" ") });
      consumed.add(index);
    });

    clean.forEach((line, index) => {
      if (consumed.has(index)) return;
      const match = line.match(MARKET_LINE_RE);
      if (!match) return;
      rows.push(parseBodyRow(match[1], match[2] || ""));
      consumed.add(index);
    });

    for (let i = 0; i < clean.length; i += 1) {
      if (consumed.has(i)) continue;
      const name = normalizeMarketName(clean[i]);
      if (!REQUIRED_CORE_MARKETS.includes(name)) continue;
      if (i + 4 >= clean.length) continue;
      rows.push({
        name,
        value: clean[i + 1] || "—",
        change: clean[i + 2] || "—",
        rate: clean[i + 3] || "—",
        state: clean[i + 4] || "—",
        note: ""
      });
      for (let j = i; j <= i + 4; j += 1) consumed.add(j);
      i += 4;
    }

    const deduped = new Map();
    rows.forEach((row) => deduped.set(row.name, row));
    return [...deduped.values()];
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
    const notes = rows.filter((row) => row.note).map((row) => `<li><strong>${escapeHtml(row.name)}</strong>：${escapeHtml(row.note)}</li>`).join("");
    return `<div class="manual21-table-wrap"><table class="manual21-table market-table-five">
      <thead><tr><th>銘柄</th><th>確定終値・現在値</th><th>前日比</th><th>騰落率</th><th>状態</th></tr></thead>
      <tbody>${rows.map((row) => `<tr>
        <th scope="row">${escapeHtml(row.name)}</th>
        <td class="manual21-value">${escapeHtml(row.value)}</td>
        <td>${escapeHtml(row.change)}</td>
        <td>${escapeHtml(row.rate)}</td>
        <td>${escapeHtml(row.state)}</td>
      </tr>`).join("")}</tbody>
    </table></div>${notes ? `<div class="manual21-market-notes"><p>補足</p><ul>${notes}</ul></div>` : ""}`;
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

  function sectionTitle(key, slot) {
    const spec = SECTION_SPECS.find((item) => item.key === key);
    if (key === "changes" && slot) return slot.changeTitle;
    return spec ? spec.title : key;
  }

  function renderSection(key, lines, slot) {
    if (!meaningfulLines(lines).length) return "";
    let content = renderReadableText(lines);
    if (key === "marketData") content = renderMarketTable(lines);
    if (key === "outlooks") content = renderOutlooks(lines);
    const emphasis = ["theme", "changes", "consistency", "leading", "mainScenario", "alternativeScenario", "breakConditions", "risk", "conclusion"].includes(key)
      ? " manual21-section--emphasis"
      : "";
    return `<section class="section manual21-section${emphasis}" data-manual21-section="${escapeHtml(key)}">
      <h2>${escapeHtml(sectionTitle(key, slot))}</h2>
      <div class="manual21-section-body">${content}</div>
    </section>`;
  }

  function renderSummary(parsed, slot) {
    const cards = [
      ["相場テーマ", firstSentence(parsed.sections.get("theme"))],
      ["主導市場", firstSentence(parsed.sections.get("leading"))],
      ["最重要イベント", firstSentence(parsed.sections.get("events"))],
      [slot.handoverLabel, firstSentence(parsed.sections.get("handover"))]
    ].filter((item) => item[1]);
    if (!cards.length) return "";
    return `<section class="manual21-summary" aria-label="${escapeHtml(slot.summaryTitle)}">
      <h2>${escapeHtml(slot.summaryTitle)}</h2>
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

  function normalizeMorningLabel(value = "") {
    const label = normalizeHeading(value);
    if (/^(Dow|NYダウ|ダウ|NYダウ平均)$/i.test(label)) return "NYダウ";
    if (/^(Nasdaq|NASDAQ|Nasdaq総合|NASDAQ総合)$/i.test(label)) return "NASDAQ総合";
    if (/^S&P\s*500$/i.test(label)) return "S&P500";
    if (/^Russell\s*2000$/i.test(label)) return "Russell 2000";
    if (/^(日経225現物|日経225|日経平均|日経平均現物)$/.test(label)) return "日経225現物";
    if (/^CME.*日経225先物.*円建て/.test(label)) return "CME日経225先物・円建て";
    if (/^CME.*日経225先物.*ドル建て/.test(label)) return "CME日経225先物・ドル建て";
    if (/^(日経225先物・大阪取引所|日経225先物（大阪取引所）|日経225先物\(大阪取引所\)|日経225先物)$/.test(label)) return "日経225先物（大阪取引所）";
    if (/^(USD\/JPY|USDJPY|ドル円)$/i.test(label)) return "USD/JPY";
    if (/^(EUR\/USD|EURUSD|ユーロドル)$/i.test(label)) return "EUR/USD";
    if (/^(COMEX金先物|金|金先物|ゴールド)$/.test(label)) return "COMEX金先物";
    if (/^(WTI原油|WTI|原油)$/.test(label)) return "WTI原油";
    if (/^(BTCUSD|BTC\/USD|Bitcoin|ビットコイン)$/i.test(label)) return "BTCUSD";
    if (/^VIX(?:指数)?$/i.test(label)) return "VIX";
    if (label === "日経VI") return "日経VI";
    if (/^Fear\s*&\s*Greed(?:\s*Index)?$/i.test(label)) return "Fear & Greed Index";
    if (/^(米10年債利回り|米10年債|米国10年債利回り|米10年国債利回り)$/.test(label)) return "米10年債利回り";
    if (/^(日本10年国債利回り|日本10年債利回り|日本10年国債)$/.test(label)) return "日本10年国債利回り";
    if (/^(日経225予想PER|日経225PER|PER)$/.test(label)) return "日経225予想PER";
    if (/^(日経225\s*PBR|日経225PBR|PBR)$/.test(label)) return "日経225 PBR";
    if (/^(日経225予想EPS|日経225EPS|EPS)$/.test(label)) return "日経225予想EPS";
    if (/^日経225\s*25日(?:移動平均)?乖離率$/.test(label)) return "日経225 25日移動平均乖離率";
    if (/^日経225\s*200日(?:移動平均)?乖離率$/.test(label)) return "日経225 200日移動平均乖離率";
    if (label === "東証プライム売買代金") return label;
    if (label === "東証プライム売買高") return label;
    if (/^(東証プライム)?値上がり銘柄数$/.test(label)) return "東証プライム値上がり銘柄数";
    if (/^(東証プライム)?値下がり銘柄数$/.test(label)) return "東証プライム値下がり銘柄数";
    if (/^(東証プライム)?25日騰落レシオ$/.test(label)) return "東証プライム25日騰落レシオ";
    return label;
  }

  function qaIssues(report, source, parsed, slot) {
    if (String(report.date || "") < ENFORCE_FROM) return [];
    const issues = [];

    REQUIRED_SECTION_KEYS.forEach((key) => {
      if (!meaningfulLines(parsed.sections.get(key)).length) {
        issues.push(`${sectionTitle(key, slot)} がありません`);
      }
    });

    if (String(report.time || "") === "08:00") {
      const found = new Set(String(source).split("\n").map((line) => normalizeMorningLabel(line)).filter((label) => MORNING_REQUIRED_LABELS.includes(label)));
      MORNING_REQUIRED_LABELS.forEach((label) => {
        if (!found.has(label)) issues.push(`主要市場データに ${label} がありません`);
      });
    } else {
      const marketRows = collectMarketRows(parsed.sections.get("marketData"));
      const byName = new Map(marketRows.map((row) => [row.name, row]));
      REQUIRED_CORE_MARKETS.forEach((name) => {
        const row = byName.get(name);
        if (!row) {
          issues.push(`主要市場データに ${name} がありません`);
          return;
        }
        if (!row.value || row.value === "—") issues.push(`${name} の確定終値・現在値がありません`);
        if (!row.change || row.change === "—") issues.push(`${name} の前日比がありません`);
        if (!row.rate || row.rate === "—") issues.push(`${name} の騰落率がありません`);
        if (!row.state || row.state === "—") issues.push(`${name} の状態がありません`);
      });
    }

    if (/\bverified\b/i.test(source)) issues.push("公開本文に内部確認用語 verified が残っています");
    if (/未確認/.test(source)) issues.push("公開本文に『未確認』が残っています");
    if (/JSONにありません|構造化JSON|内部構造/.test(source)) issues.push("公開本文に内部構造の診断文が残っています");

    return issues;
  }

  function renderQaHold(report, issues) {
    const time = String(report.time || "");
    return `<section class="manual21-qa-hold" role="status" aria-live="polite">
      <h2>${escapeHtml(time)}レポートは公開保留中です</h2>
      <p>マニュアルの公開前チェックを通過していないため、読みにくい・不完全な本文は表示していません。</p>
      <details>
        <summary>検出した項目</summary>
        <ul>${issues.map((issue) => `<li>${escapeHtml(issue)}</li>`).join("")}</ul>
      </details>
    </section>`;
  }

  function applyManualLayout() {
    const report = currentReport();
    if (!report) return;
    const time = String(report.time || "");
    const slot = SLOT_CONFIG[time];
    if (!slot) return;

    const app = document.getElementById("app");
    const body = app && app.querySelector(".report-body");
    if (!app || !body) return;

    const key = `${report.date || ""} ${time}`;
    if (app.dataset.manual21Key === key) return;

    const source = reportSource(report);
    if (!source) return;
    const parsed = parseSections(source);
    const issues = qaIssues(report, source, parsed, slot);

    if (issues.length) {
      body.innerHTML = renderQaHold(report, issues);
      app.dataset.manual21Key = key;
      app.classList.add("manual21-applied", "manual21-qa-blocked");
      const status = document.getElementById("reportStatus");
      if (status) status.textContent = `${time} SOP QA未通過｜公開保留`;
      return;
    }

    if (!slot.render) {
      app.dataset.manual21Key = key;
      app.classList.remove("manual21-qa-blocked");
      const status = document.getElementById("reportStatus");
      if (status) status.textContent = `${time} SOP QA通過｜朝レポート専用5列表を表示中`;
      return;
    }

    const known = new Set(RENDER_ORDER);
    let html = renderSummary(parsed, slot);
    RENDER_ORDER.forEach((sectionKey) => {
      html += renderSection(sectionKey, parsed.sections.get(sectionKey), slot);
    });
    parsed.sections.forEach((lines, sectionKey) => {
      if (known.has(sectionKey) || sectionKey === "dataCheck") return;
      html += renderSection(sectionKey, lines, slot);
    });
    html += renderDataCheck(parsed.sections.get("dataCheck"));

    body.innerHTML = html;
    app.dataset.manual21Key = key;
    app.classList.add("manual21-applied");
    app.classList.remove("manual21-qa-blocked");

    const status = document.getElementById("reportStatus");
    if (status) status.textContent = `本文全文を表示中｜${time} SOPレイアウト適用済み`;
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
