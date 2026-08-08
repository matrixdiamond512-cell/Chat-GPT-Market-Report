/*
 * 08:00 dashboard six-market canonical-value bridge.
 * The morning dashboard must match the final 28-item market-data table embedded
 * in the report fullText. This deliberately takes precedence over stale/older
 * dashboard marketData snapshots for the six summary cards only.
 */
(() => {
  "use strict";

  if (typeof parseMetric !== "function") return;

  const baseParseMetric = parseMetric;
  const LABEL_BY_KEY = {
    gold: "COMEX金先物",
    oil: "WTI原油",
    nikkei: "日経225先物・大阪取引所",
    usdjpy: "USD/JPY",
    eurusd: "EUR/USD",
    btc: "BTCUSD"
  };

  function stripNumber(label = "") {
    return String(label)
      .replace(/^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘]\s*/, "")
      .trim();
  }

  function morningTableRows(report) {
    if (!report || report.time !== "08:00") return new Map();
    const text = String(report.fullText || report.rawText || report.body || "")
      .replace(/\r/g, "");
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

  function trendFromRow(row) {
    const direction = String(row?.direction || "");
    if (/取得不能|未確認/.test(row?.value || "")) return "missing";
    if (/上昇|高|強|買い|強気|ユーロ高/.test(direction)) return "up";
    if (/下落|安|弱|売り|円高|ドル安/.test(direction)) return "down";
    const change = String(row?.change || "").replace(/[−－]/g, "-");
    if (/^\+/.test(change)) return "up";
    if (/^-/.test(change)) return "down";
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

  parseMetric = function(report, definition) {
    return metricFromFinalTable(report, definition) || baseParseMetric(report, definition);
  };
})();
