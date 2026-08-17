/*
 * Final canonical market bridge for the six dashboard cards.
 *
 * Rule:
 *   verified data/market/latest.json > report text / structured fallback
 *
 * This script is intentionally loaded after every existing parseMetric wrapper so
 * USD/JPY, BTCUSD and the other four cards always use one consistent price/change
 * source when the canonical payload matches the displayed report date and slot.
 */
(() => {
  "use strict";

  if (typeof parseMetric !== "function") return;

  const baseParseMetric = parseMetric;
  let canonicalPayload = null;

  function finiteNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function reportMatchesPayload(report, payload) {
    if (!report || !payload) return false;
    const payloadDate = String(payload.generatedAt || payload.dataAsOf || "").slice(0, 10);
    return payloadDate === String(report.date || "")
      && String(payload.reportSlot || "") === String(report.time || "");
  }

  function marketKey(definition) {
    return definition?.dataKey || definition?.key || "";
  }

  function signed(value, digits) {
    if (value === null) return "";
    return value.toLocaleString("ja-JP", {
      signDisplay: "always",
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    });
  }

  function priceDigits(value) {
    const abs = Math.abs(value);
    if (abs < 10) return 5;
    if (abs < 1000) return 2;
    return 0;
  }

  function canonicalMetric(report, definition) {
    if (!reportMatchesPayload(report, canonicalPayload)) return null;

    const item = canonicalPayload?.markets?.[marketKey(definition)];
    if (!item || item.verificationStatus !== "verified") return null;

    const value = finiteNumber(item.value);
    if (value === null) return null;

    const previousClose = finiteNumber(item.previousClose);
    const storedChange = finiteNumber(item.change);
    const storedPercent = finiteNumber(item.changePercent);
    const change = previousClose !== null ? value - previousClose : storedChange;
    const percent = previousClose !== null && previousClose !== 0
      ? ((value / previousClose) - 1) * 100
      : storedPercent;

    const changeParts = [];
    if (change !== null) changeParts.push(signed(change, priceDigits(value)));
    if (percent !== null && Math.abs(percent) <= 100) changeParts.push(`${signed(percent, 2)}%`);

    const source = item.sourceName || item.sourceId || "検証済み市場データ";
    const displayValue = String(item.displayValue || "").trim()
      || value.toLocaleString("ja-JP", { maximumFractionDigits: 5 });

    let trend = "flat";
    const trendValue = change ?? percent;
    if (trendValue > 0) trend = "up";
    else if (trendValue < 0) trend = "down";

    return {
      value: displayValue,
      unit: item.unit || definition?.unit || "",
      change: changeParts.join(" / ") || String(item.changeText || "前日比：取得不能"),
      trend,
      raw: `canonical:${marketKey(definition)}`,
      sourceNote: `確認済み：${source}`,
      sourceClass: "verified"
    };
  }

  parseMetric = function(report, definition) {
    return canonicalMetric(report, definition) || baseParseMetric(report, definition);
  };

  async function loadCanonicalMarketData() {
    try {
      const response = await fetch(`data/market/latest.json?canonical=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      if (!payload || payload.overallStatus === "blocked" || !payload.markets) return;
      canonicalPayload = payload;
      try {
        if (typeof render === "function" && typeof selectedReport !== "undefined" && selectedReport) {
          render();
        }
      } catch (error) {
        console.warn("canonical market rerender failed", error);
      }
    } catch (error) {
      console.warn("canonical market data load failed", error);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadCanonicalMarketData, { once: true });
  } else {
    loadCanonicalMarketData();
  }
})();
