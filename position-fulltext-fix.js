/* 2026-08-06 12:52 JST
 * Dashboard-wide consistency and full-text fix.
 * - Prefer same-day verified market data available by the report time.
 * - Reject stale spreadsheet prices whose source date does not match the report period.
 * - Fall back to the market-report body before using generated card values.
 * - Re-render analysis-heavy panels without character truncation.
 */
(function () {
  const originalMarketDataStatusText = marketDataStatusText;

  function parseDateTime(value, fallbackTime = "00:00") {
    const text = String(value || "").trim();
    if (!text) return null;

    const isoDateTime = text.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}:\d{2})(?::\d{2})?)?/);
    if (isoDateTime) {
      const timestamp = new Date(`${isoDateTime[1]}T${isoDateTime[2] || fallbackTime}:00+09:00`);
      return Number.isNaN(timestamp.getTime()) ? null : timestamp;
    }

    const slashDate = text.match(/^(\d{4})\/(\d{2})\/(\d{2})(?:\s+(\d{2}:\d{2}))?/);
    if (slashDate) {
      const timestamp = new Date(`${slashDate[1]}-${slashDate[2]}-${slashDate[3]}T${slashDate[4] || fallbackTime}:00+09:00`);
      return Number.isNaN(timestamp.getTime()) ? null : timestamp;
    }

    const timestamp = new Date(text);
    return Number.isNaN(timestamp.getTime()) ? null : timestamp;
  }

  function reportDateTime(report) {
    return parseDateTime(`${report?.date || ""}T${report?.time || "00:00"}`);
  }

  function marketItemDateTime(item, dataset) {
    return parseDateTime(
      item?.asOf
      || item?.lastVerifiedAt
      || item?.fetchedAt
      || dataset?.generatedAt
      || ""
    );
  }

  function isVerifiedMarketItemUsable(item, dataset, report) {
    if (!item || !report?.date) return false;
    if (item.verificationStatus === "unavailable") return false;
    if (finiteNumber(item.value) === null) return false;

    const datasetDate = String(dataset?.generatedAt || "").slice(0, 10);
    const itemTime = marketItemDateTime(item, dataset);
    const reportTime = reportDateTime(report);

    if (datasetDate && datasetDate !== report.date) return false;
    if (itemTime && itemTime.toISOString().slice(0, 10) !== report.date) return false;

    if (itemTime && reportTime) {
      const futureToleranceMs = 30 * 60 * 1000;
      if (itemTime.getTime() > reportTime.getTime() + futureToleranceMs) return false;
    }

    return true;
  }

  function candidateTime(item, dataset) {
    return marketItemDateTime(item, dataset)?.getTime() || 0;
  }

  marketDataFor = function marketDataForConsistentReport(report, definition) {
    const key = definition.dataKey || definition.key;
    const independentData = dashboardMeta?.marketData || null;
    const embeddedData = report?.marketData || null;

    const candidates = [
      { dataset: embeddedData, item: embeddedData?.markets?.[key] || null },
      { dataset: independentData, item: independentData?.markets?.[key] || null }
    ]
      .filter(({ dataset, item }) => isVerifiedMarketItemUsable(item, dataset, report))
      .sort((a, b) => candidateTime(b.item, b.dataset) - candidateTime(a.item, a.dataset));

    return candidates[0]?.item || null;
  };

  marketDataStatusText = function marketDataStatusTextWithTimestamp(item) {
    const base = originalMarketDataStatusText(item);
    const asOf = shortDateTime(item?.asOf || item?.lastVerifiedAt || item?.fetchedAt || "");
    return asOf ? `${base}｜基準 ${asOf}` : base;
  };

  function sourceDateIsUsable(report, market) {
    const sourceAsOf = market?.priceSource?.asOf;
    if (!sourceAsOf || !report?.date) return true;

    const sourceDate = parseDateTime(sourceAsOf);
    const targetDate = parseDateTime(report.date);
    if (!sourceDate || !targetDate) return false;

    const ageDays = Math.floor((targetDate.getTime() - sourceDate.getTime()) / 86400000);
    return ageDays >= 0 && ageDays <= 4;
  }

  function safeMarketPriceFields(report, market) {
    const usable = sourceDateIsUsable(report, market);
    return {
      price: usable ? market?.price : "",
      change: usable ? market?.change : ""
    };
  }

  sourceLines = function sourceLinesWithoutStalePrices(report) {
    return [
      ...asArray(report.changes).map(textOf),
      ...asArray(report.news).map(textOf),
      ...asArray(report.riskManagement).map(textOf),
      ...asArray(report.markets).flatMap((market) => {
        const safe = safeMarketPriceFields(report, market);
        return [
          safe.price,
          safe.change,
          market.material,
          market.levels,
          market.risk
        ];
      })
    ].filter(Boolean);
  };

  metricSourceValues = function metricSourceValuesBodyFirst(report, definition) {
    const market = reportMarket(report, definition) || {};
    const safe = safeMarketPriceFields(report, market);

    return [
      report.fullText,
      report.rawText,
      report.body,
      safe.price,
      safe.change,
      market.material,
      market.positioning,
      market.levels,
      market.risk,
      market.mainScenario,
      market.alternativeScenario,
      ...sourceLines(report),
      ...asArray(report.positioning).map(textOf),
      ...asArray(report.crossAssetFlow).map(textOf)
    ];
  };

  const originalExtractChangeText = extractChangeText;
  extractChangeText = function extractChangeTextWithSanityCheck(line, market) {
    const value = originalExtractChangeText(line, market);
    const isFx = /USD\/JPY|EUR\/USD|ドル円|ユーロドル/.test(`${line || ""} ${market?.name || ""}`);
    const percent = String(value || "").match(/([+\-]?\d[\d,.]*)\s*(?:％|%)/);

    if (isFx && percent) {
      const numeric = Number(percent[1].replace(/,/g, ""));
      if (Number.isFinite(numeric) && Math.abs(numeric) > 20) {
        return "騰落率の異常値を除外";
      }
    }

    if (!value && /ほぼ横ばい|横ばい/.test(String(line || ""))) return "ほぼ横ばい";
    return value;
  };

  function fullTextItems(values, limit) {
    return asArray(values)
      .map(textOf)
      .filter(Boolean)
      .map((item) => cleanText(item, Infinity))
      .slice(0, limit);
  }

  renderPositions = function renderPositionsFullText(report) {
    renderList(
      "positionList",
      fullTextItems(report.positioning, 3),
      "理由：需給・ポジション項目がJSONにありません"
    );

    const rows = ["株式", "原油", "ドル", "金", "BTC"];
    const headers = ["", "弱気", "中立", "強気"];
    const cell = (asset, side) => positionBias(report, asset) === side ? "•" : "";

    $("positionMatrix").innerHTML = [
      ...headers.map((header) => `<span>${esc(header)}</span>`),
      ...rows.flatMap((asset) => [
        `<span>${esc(asset)}</span>`,
        ...headers.slice(1).map((side) => `<span class="dot">${cell(asset, side)}</span>`)
      ])
    ].join("");
  };

  function renderFullTextPanels(report) {
    renderProseList(
      "themeList",
      proseItems([report.theme], 5, Infinity),
      "理由：相場テーマがJSONにありません"
    );

    renderProseList(
      "changeList",
      proseItems(report.changes, 4, Infinity),
      "理由：前回からの変化がJSONにありません"
    );

    renderProseBlock(
      "leadingMarket",
      report.leadingMarket,
      "取得不能。理由：主導市場コメントがJSONにありません",
      8,
      Infinity
    );

    renderPositions(report);

    const breakText = breakConditionsFromReport(report, Infinity);
    renderProseBlock(
      "breakConditions",
      breakText,
      "理由：崩れる条件を本文から取得できませんでした",
      8,
      Infinity
    );
    $("breakConditions").classList.toggle("missing", !breakText);

    renderList(
      "handoverList",
      fullTextItems(fallbackHandoverItems(report), 3),
      "理由：引き継ぎ項目がJSONにありません"
    );

    renderProseBlock(
      "conclusionText",
      conclusionFrom(report),
      "理由：結論に必要な項目がJSONにありません",
      8,
      Infinity
    );
  }

  const originalRender = render;
  render = function renderDashboardWithConsistentData() {
    originalRender();
    const report = selectedReport || reports[0];
    if (report) renderFullTextPanels(report);
  };
})();
