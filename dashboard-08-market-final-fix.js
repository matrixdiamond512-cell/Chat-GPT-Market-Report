/*
 * 08:00 dashboard six-market canonical bridge.
 * The dashboard must match the final 28-item market table and the final six-market
 * outlook section embedded in report fullText. These report-final values take
 * precedence over stale/older dashboard snapshots for 08:00 cards.
 */
(() => {
  "use strict";

  if (typeof parseMetric !== "function" || typeof reportMarket !== "function") return;

  const baseParseMetric = parseMetric;
  const baseReportMarket = reportMarket;

  const LABEL_BY_KEY = {
    gold: "COMEX金先物",
    oil: "WTI原油",
    nikkei: "日経225先物・大阪取引所",
    usdjpy: "USD/JPY",
    eurusd: "EUR/USD",
    btc: "BTCUSD"
  };

  const OUTLOOK_LABEL_BY_KEY = {
    gold: "金",
    oil: "WTI原油",
    nikkei: "日経225先物（大阪取引所）",
    usdjpy: "USD/JPY",
    eurusd: "EUR/USD",
    btc: "BTCUSD"
  };

  function reportText(report) {
    return String(report?.fullText || report?.rawText || report?.body || "").replace(/\r/g, "");
  }

  function stripNumber(label = "") {
    return String(label)
      .replace(/^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘]\s*/, "")
      .trim();
  }

  function morningTableRows(report) {
    if (!report || report.time !== "08:00") return new Map();
    const text = reportText(report);
    if (!text) return new Map();

    const lines = text.split("\n").map((line) => line.trim());
    const start = lines.findIndex((line) => /主要市場データ/.test(line));
    if (start < 0) return new Map();

    let end = lines.findIndex((line, index) => index > start && /^3[.．]\s*/.test(line));
    if (end < 0) end = lines.length;

    const block = lines.slice(start + 1, end).filter(Boolean);
    const rows = new Map();
    const numbered = /^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘]\s*/;

    for (let i = 0; i < block.length; i += 1) {
      if (!numbered.test(block[i])) continue;
      const label = stripNumber(block[i]);
      const value = block[i + 1] || "取得不能";
      const change = block[i + 2] || "—";
      const rate = block[i + 3] || "—";
      const direction = block[i + 4] || "取得不能";
      rows.set(label, { label, value, change, rate, direction });
      i += 4;
    }
    return rows;
  }

  function sixMarketOutlooks(report) {
    const found = new Map();
    if (!report || report.time !== "08:00") return found;
    const lines = reportText(report).split("\n").map((line) => line.trim()).filter(Boolean);
    const start = lines.findIndex((line) => /(?:個別6市場の見通し|6市場の見通し)/.test(line));
    if (start < 0) return found;

    const labels = new Set(Object.values(OUTLOOK_LABEL_BY_KEY));
    let current = null;
    for (let i = start + 1; i < lines.length; i += 1) {
      const line = lines[i];
      if (/^\d{1,2}[.．]\s*/.test(line) && found.size) break;
      if (labels.has(line)) {
        current = { name: line, direction: "", material: "", levels: "", breakCondition: "", risk: "", outlook: "" };
        found.set(line, current);
        continue;
      }
      if (!current) continue;
      let m = line.match(/^方向[：:]\s*(.+)$/);
      if (m) { current.direction = m[1].trim(); continue; }
      m = line.match(/^材料[：:]\s*(.+)$/);
      if (m) { current.material = m[1].trim(); continue; }
      m = line.match(/^注目(?:点)?[：:]\s*(.+)$/);
      if (m) { current.levels = m[1].trim(); continue; }
      m = line.match(/^崩れる条件[：:]\s*(.+)$/);
      if (m) { current.breakCondition = m[1].trim(); current.risk = m[1].trim(); continue; }
    }

    found.forEach((item) => {
      item.outlook = [item.direction, item.material, item.levels].filter(Boolean).join("。") + "。";
    });
    return found;
  }

  function trendFromRow(row) {
    if (/取得不能|未確認/.test(row?.value || "")) return "missing";
    const change = String(row?.change || "").replace(/[−－]/g, "-").trim();
    const rate = String(row?.rate || "").replace(/[−－]/g, "-").trim();
    if (/^\+/.test(change) || (!/^[-+]/.test(change) && /^\+/.test(rate))) return "up";
    if (/^-/.test(change) || (!/^[-+]/.test(change) && /^-/.test(rate))) return "down";
    const direction = String(row?.direction || "");
    if (/ドル安・円高|下落|弱気|売り優勢/.test(direction)) return "down";
    if (/ユーロ高|上昇|大幅高|小幅高|強気|買い/.test(direction)) return "up";
    return "flat";
  }

  function metricFromFinalTable(report, definition) {
    if (!report || report.time !== "08:00") return null;
    const target = LABEL_BY_KEY[definition?.key];
    if (!target) return null;
    const row = morningTableRows(report).get(target);
    if (!row) return null;

    const unavailable = /取得不能|未確認/.test(row.value);
    const rate = row.rate && row.rate !== "—" ? row.rate : "";
    const change = [row.change && row.change !== "—" ? row.change : "", rate]
      .filter(Boolean)
      .join(" / ") || "前日比：取得不能";

    return {
      value: unavailable ? "取得不能" : row.value,
      unit: "",
      change: unavailable ? row.value : change,
      trend: trendFromRow(row),
      raw: `${row.label}：${row.value}、${row.change}、${row.rate}、${row.direction}`,
      sourceNote: "08:00最終修正版・主要市場データ28項目",
      sourceClass: unavailable ? "missing" : "verified"
    };
  }

  reportMarket = function(report, definition) {
    const original = baseReportMarket(report, definition) || {};
    if (!report || report.time !== "08:00") return original;
    const target = OUTLOOK_LABEL_BY_KEY[definition?.key];
    const finalOutlook = target ? sixMarketOutlooks(report).get(target) : null;
    if (!finalOutlook) return original;
    return {
      ...original,
      ...finalOutlook,
      name: original.name || finalOutlook.name
    };
  };

  parseMetric = function(report, definition) {
    return metricFromFinalTable(report, definition) || baseParseMetric(report, definition);
  };
})();
