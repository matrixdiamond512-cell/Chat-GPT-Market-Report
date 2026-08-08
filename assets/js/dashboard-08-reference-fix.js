/*
 * Apply source-verified 08:00 morning reference values to dashboard cards.
 * This keeps the six-market summary aligned with the corrected report table,
 * while preserving the original 08:00 time axis.
 */
(() => {
  "use strict";

  if (typeof parseMetric !== "function") return;
  const baseParseMetric = parseMetric;
  let payload = null;

  const LABEL_BY_KEY = {
    nikkei: "日経225先物（大阪取引所）"
  };

  function asTrend(item) {
    const change = String(item?.change || "").replace(/[−－]/g, "-").trim();
    if (/^\+/.test(change)) return "up";
    if (/^-/.test(change)) return "down";
    if (/上昇|強気|高/.test(String(item?.direction || ""))) return "up";
    if (/下落|弱気|安/.test(String(item?.direction || ""))) return "down";
    return "flat";
  }

  function metricFromReference(report, definition) {
    if (!payload || !report || report.time !== "08:00") return null;
    if (payload.reportDate !== report.date || payload.reportSlot !== report.time) return null;
    const label = LABEL_BY_KEY[definition?.key];
    if (!label) return null;
    const item = payload.items?.[label];
    if (!item || !item.value || !/^verified/.test(String(item.status || ""))) return null;
    const change = [item.change, item.rate].filter(Boolean).join(" / ") || "前日比：取得不能";
    return {
      value: String(item.value),
      unit: "",
      change,
      trend: asTrend(item),
      raw: `${label}：${item.value}、${item.change || "—"}、${item.rate || "—"}、${item.direction || "—"}`,
      sourceNote: `確認済み：${item.sourceName || "08:00補完データ"}`,
      sourceClass: "verified"
    };
  }

  parseMetric = function(report, definition) {
    return metricFromReference(report, definition) || baseParseMetric(report, definition);
  };

  async function load() {
    try {
      const response = await fetch(`data/market/morning-reference.json?ts=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) return;
      payload = await response.json();
      try {
        if (typeof render === "function" && selectedReport) render();
      } catch (error) {
        console.warn("08:00 dashboard reference rerender failed", error);
      }
    } catch (error) {
      console.warn("08:00 dashboard reference load failed", error);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load, { once: true });
  else load();
})();
