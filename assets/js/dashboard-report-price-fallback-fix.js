/*
 * Dashboard market-price / previous-day-change fallback fix.
 *
 * Priority:
 *   1. Canonical/verified dashboard market data
 *   2. Structured report marketDataTable row (change / rate)
 *   3. Structured reports[].markets price/change
 *
 * Important: if a usable price already exists but its displayed change says
 * "取得不能", do not stop there. The 08:00 report may already contain the
 * verified previous-day change in marketDataTable.rows[]. This patch merges it
 * into the 6-market card instead of showing a false unavailable state.
 */
(() => {
  "use strict";

  if (typeof parseMetric !== "function" || typeof reportMarket !== "function") return;

  const baseParseMetric = parseMetric;

  const TABLE_LABELS = {
    gold: ["COMEX金先物", "金", "金（XAU/USD）"],
    oil: ["WTI原油", "原油", "WTI"],
    nikkei: ["日経225先物（大阪取引所）", "日経225先物"],
    usdjpy: ["USD/JPY", "USDJPY"],
    eurusd: ["EUR/USD", "EURUSD"],
    btc: ["BTCUSD", "BTC/USD", "BTC"]
  };

  function normalizeLabel(value) {
    return String(value || "")
      .replace(/[　\s]/g, "")
      .replace(/[()（）]/g, "")
      .toUpperCase();
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
      sourceClass: "verified"
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
      sourceClass: metric.sourceClass || "verified"
    };
  }

  parseMetric = function(report, definition) {
    const primary = baseParseMetric(report, definition);

    // A valid price with a false "前日比：取得不能" is the main bug fixed here.
    if (!isUnavailableMetric(primary)) {
      return mergeTableChange(report, definition, primary);
    }

    // If the primary price is unavailable, keep the existing structured-price fallback,
    // then enrich its change/rate from marketDataTable when available.
    const reportFallback = metricFromStructuredReport(report, definition);
    return mergeTableChange(report, definition, reportFallback || primary);
  };
})();
