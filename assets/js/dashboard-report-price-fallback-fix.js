/*
 * Dashboard market-price fallback fix.
 *
 * If the dashboard's canonical/verified market-data layer cannot parse a price,
 * but reports.json already contains a numeric markets[].price for the selected
 * report, use that structured report price instead of showing "取得不能".
 *
 * This is intentionally a fallback only: successfully verified dashboard
 * market data keeps priority.
 */
(() => {
  "use strict";

  if (typeof parseMetric !== "function" || typeof reportMarket !== "function") return;

  const baseParseMetric = parseMetric;

  function isUnavailableMetric(metric) {
    if (!metric) return true;
    return /取得不能|未取得|未確認/.test(String(metric.value || ""));
  }

  function trendFromStructuredMarket(market) {
    const source = [market?.change, market?.direction, market?.price]
      .filter(Boolean)
      .join(" ")
      .replace(/[−－]/g, "-");

    if (typeof trendFromText === "function") return trendFromText(source);
    if (/\+|上昇|強気|買い|反発|流入/.test(source)) return "up";
    if (/-|下落|弱気|売り|反落|流出/.test(source)) return "down";
    return "flat";
  }

  function metricFromStructuredReport(report, definition) {
    const market = reportMarket(report, definition) || {};
    const price = String(market.price || "").trim();

    if (!price || /取得不能|未取得|未確認|確認できず/.test(price)) return null;
    if (!/\d[\d,]*(?:\.\d+)?/.test(price)) return null;

    const change = String(market.change || "").trim();
    return {
      value: price,
      unit: "",
      change: change || "前日比：取得不能",
      trend: trendFromStructuredMarket(market),
      raw: `${market.name || definition?.display || definition?.label || "市場"}：${price}`,
      sourceNote: "マーケットレポート構造化JSON",
      sourceClass: "verified"
    };
  }

  parseMetric = function(report, definition) {
    const primary = baseParseMetric(report, definition);
    if (!isUnavailableMetric(primary)) return primary;

    const reportFallback = metricFromStructuredReport(report, definition);
    return reportFallback || primary;
  };
})();
