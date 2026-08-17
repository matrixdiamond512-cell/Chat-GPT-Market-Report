/*
 * Dashboard six-market data priority guard.
 *
 * Final priority:
 *   1. data/market/latest.json item when it is VERIFIED and matches report date/slot
 *   2. Existing dashboard renderer result
 *   3. Structured report marketDataTable row (change / rate)
 *   4. Structured reports[].markets price/change
 *
 * This prevents a report-text fallback price from replacing a newer verified
 * market quote and accidentally dropping previous-close change data.
 */
(() => {
  "use strict";

  if (typeof parseMetric !== "function" || typeof reportMarket !== "function") return;

  const baseParseMetric = parseMetric;
  let verifiedMarketPayload = null;

  const TABLE_LABELS = {
    gold: ["COMEX金先物", "金", "金（XAU/USD）"],
    oil: ["WTI原油", "原油", "WTI"],
    nikkei: ["日経225先物（大阪取引所）", "日経225先物"],
    usdjpy: ["USD/JPY", "USDJPY"],
    eurusd: ["EUR/USD", "EURUSD"],
    btc: ["BTCUSD", "BTC/USD", "BTC"]
  };

  const DATA_KEY_BY_DEFINITION = {
    gold: "gold",
    oil: "wti",
    nikkei: "nikkei225_futures_ose",
    usdjpy: "usdjpy",
    eurusd: "eurusd",
    btc: "btcusd"
  };

  function normalizeLabel(value) {
    return String(value || "")
      .replace(/[　\s]/g, "")
      .replace(/[()（）]/g, "")
      .toUpperCase();
  }

  function finiteNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function isUnavailableText(value) {
    const text = String(value || "").trim();
    return !text || /取得不能|未取得|未確認|確認できず|^[-—–]+$/.test(text);
  }

  function isUnavailableMetric(metric) {
    if (!metric) return true;
    return isUnavailableText(metric.value);
  }

  function isUnavailableChange(metric) {
    if (!metric) return true;
    return isUnavailableText(metric.change) || /前日比\s*[：:]?\s*取得不能/.test(String(metric.change || ""));
  }

  function reportMatchesVerifiedPayload(report) {
    if (!report || !verifiedMarketPayload) return false;
    const generatedDate = String(verifiedMarketPayload.generatedAt || "").slice(0, 10);
    return generatedDate === String(report.date || "")
      && String(verifiedMarketPayload.reportSlot || "") === String(report.time || "");
  }

  function verifiedItemFor(report, definition) {
    if (!reportMatchesVerifiedPayload(report)) return null;
    const dataKey = DATA_KEY_BY_DEFINITION[definition?.key];
    if (!dataKey) return null;
    const item = verifiedMarketPayload?.markets?.[dataKey];
    if (!item || item.verificationStatus !== "verified") return null;
    if (finiteNumber(item.value) === null) return null;
    return item;
  }

  function formatVerifiedChange(item) {
    const value = finiteNumber(item?.value);
    const previous = finiteNumber(item?.previousClose);
    let change = finiteNumber(item?.change);
    let rate = finiteNumber(item?.changePercent);

    if (value !== null && previous !== null) {
      change = value - previous;
      if (previous !== 0) rate = ((value / previous) - 1) * 100;
    }

    const absValue = value === null ? null : Math.abs(value);
    const digits = absValue !== null && absValue < 10 ? 5 : absValue !== null && absValue < 1000 ? 2 : 0;
    const parts = [];

    if (change !== null) {
      parts.push(change.toLocaleString("ja-JP", {
        signDisplay: "always",
        minimumFractionDigits: digits,
        maximumFractionDigits: digits
      }));
    }
    if (rate !== null && Math.abs(rate) <= 100) {
      parts.push(`${rate.toLocaleString("ja-JP", {
        signDisplay: "always",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })}%`);
    }
    return parts.join(" / ") || String(item?.changeText || "").trim() || "前日比：取得不能";
  }

  function trendFromVerifiedItem(item) {
    const change = finiteNumber(item?.change);
    const rate = finiteNumber(item?.changePercent);
    const value = change ?? rate;
    if (value > 0) return "up";
    if (value < 0) return "down";
    return "flat";
  }

  function metricFromVerifiedPayload(report, definition) {
    const item = verifiedItemFor(report, definition);
    if (!item) return null;
    const value = finiteNumber(item.value);
    return {
      value: item.displayValue || value.toLocaleString("ja-JP", { maximumFractionDigits: 5 }),
      unit: item.unit || definition?.unit || "",
      change: formatVerifiedChange(item),
      trend: trendFromVerifiedItem(item),
      raw: "verified-market-data",
      sourceNote: `確認済み：${item.sourceName || item.sourceId || "市場データ"}`,
      sourceClass: "verified"
    };
  }

  function tableRows(report) {
    const direct = report?.marketDataTable?.rows;
    if (Array.isArray(direct)) return direct;
    const nested = report?.marketData?.marketDataTable?.rows;
    if (Array.isArray(nested)) return nested;
    return [];
  }

  function rowLabel(row) {
    if (!row) return "";
    if (Array.isArray(row)) return row[0] || "";
    return row.label || row.name || row.item || row.market || "";
  }

  function rowField(row, objectKey, arrayIndex) {
    if (!row) return "";
    if (Array.isArray(row)) return row[arrayIndex] ?? "";
    return row[objectKey] ?? "";
  }

  function tableRowFor(report, definition) {
    const aliases = TABLE_LABELS[definition?.key] || [definition?.label, definition?.display].filter(Boolean);
    const normalizedAliases = aliases.map(normalizeLabel);
    return tableRows(report).find((row) => {
      const label = normalizeLabel(rowLabel(row));
      return normalizedAliases.some((alias) => label === alias || label.includes(alias) || alias.includes(label));
    }) || null;
  }

  function cleanSignedValue(value) {
    return String(value ?? "")
      .replace(/[−－]/g, "-")
      .replace(/％/g, "%")
      .trim();
  }

  function usableTableValue(value) {
    const text = cleanSignedValue(value);
    return text && !/取得不能|未取得|未確認|^[-—–]+$/.test(text);
  }

  function formatTableChange(row) {
    const change = cleanSignedValue(rowField(row, "change", 2));
    const rate = cleanSignedValue(rowField(row, "rate", 3));
    const parts = [];
    if (usableTableValue(change)) parts.push(change);
    if (usableTableValue(rate)) parts.push(rate);
    return parts.join(" / ");
  }

  function trendFromTableRow(row) {
    const change = cleanSignedValue(rowField(row, "change", 2));
    const rate = cleanSignedValue(rowField(row, "rate", 3));
    const source = `${change} ${rate}`;
    const numberMatch = source.match(/[+\-]?\d[\d,.]*/);
    if (numberMatch) {
      const value = Number(numberMatch[0].replace(/,/g, ""));
      if (Number.isFinite(value)) {
        if (value > 0) return "up";
        if (value < 0) return "down";
        return "flat";
      }
    }
    const direction = String(rowField(row, "direction", 4) || "");
    if (/上昇|強い|高/.test(direction)) return "up";
    if (/下落|弱い|安/.test(direction)) return "down";
    return "flat";
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
      sourceClass: "fallback"
    };
  }

  function mergeTableChange(report, definition, metric) {
    if (!metric || !isUnavailableChange(metric)) return metric;
    const row = tableRowFor(report, definition);
    if (!row) return metric;

    const changeText = formatTableChange(row);
    if (!changeText) return metric;

    return {
      ...metric,
      change: changeText,
      trend: trendFromTableRow(row),
      sourceNote: metric.sourceNote || "マーケットレポート前日終値表",
      sourceClass: metric.sourceClass || "fallback"
    };
  }

  parseMetric = function(report, definition) {
    // Hard priority: verified live/slot market data must beat report-text fallbacks.
    const verified = metricFromVerifiedPayload(report, definition);
    if (verified) return verified;

    const primary = baseParseMetric(report, definition);
    if (!isUnavailableMetric(primary)) {
      return mergeTableChange(report, definition, primary);
    }

    const reportFallback = metricFromStructuredReport(report, definition);
    return mergeTableChange(report, definition, reportFallback || primary);
  };

  async function loadVerifiedMarketPayload() {
    try {
      const response = await fetch(`data/market/latest.json?verifiedPriority=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) return;
      const payload = await response.json();
      if (!payload || typeof payload !== "object" || payload.overallStatus === "blocked") return;
      if (!payload.markets || typeof payload.markets !== "object") return;
      verifiedMarketPayload = payload;

      // Repaint after the verified payload arrives so an earlier report fallback cannot remain visible.
      try {
        if (typeof render === "function" && typeof selectedReport !== "undefined" && selectedReport) render();
      } catch (error) {
        console.warn("verified six-market rerender failed", error);
      }
    } catch (error) {
      console.warn("verified six-market payload load failed", error);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadVerifiedMarketPayload, { once: true });
  } else {
    loadVerifiedMarketPayload();
  }
})();
