(() => {
  "use strict";

  if (typeof stockBreadthFor !== "function") return;

  const originalStockBreadthFor = stockBreadthFor;

  function reportText(report) {
    if (!report || typeof report !== "object") return "";
    const parts = [
      report.fullText,
      report.theme,
      report.leadingMarket,
      report.mainScenario,
      report.alternativeScenario,
      report.breakConditions,
      ...(Array.isArray(report.changes) ? report.changes : []),
      ...(Array.isArray(report.news) ? report.news : []),
      ...(Array.isArray(report.positioning) ? report.positioning : [])
    ];
    return parts.filter(Boolean).join(" ").replace(/\s+/g, " ");
  }

  function parseJapanBreadth(report) {
    const text = reportText(report);
    if (!text || /東証プライム[^。\n]{0,50}取得不能/.test(text)) return null;

    const patterns = [
      /東証プライム(?:の)?(?:市場内部では[^。]*?)?値上がり銘柄数\s*([\d,]+)[、,\s]+値下がり銘柄数\s*([\d,]+)[、,\s]+騰落レシオ\s*([\d.]+)\s*%?/,
      /値上がり銘柄数\s*([\d,]+)[、,\s]+値下がり銘柄数\s*([\d,]+)[、,\s]+騰落レシオ\s*([\d.]+)\s*%?/
    ];

    let match = null;
    for (const pattern of patterns) {
      match = text.match(pattern);
      if (match) break;
    }
    if (!match) return null;

    const advancers = Number(match[1].replace(/,/g, ""));
    const decliners = Number(match[2].replace(/,/g, ""));
    const advanceDeclineRatio = Number(match[3]);
    if (![advancers, decliners, advanceDeclineRatio].every(Number.isFinite)) return null;
    if (advancers < 0 || decliners < 0 || advancers + decliners === 0) return null;

    return {
      status: "available",
      advancers,
      decliners,
      unchanged: null,
      total: advancers + decliners,
      ratio: decliners > 0 ? advancers / decliners : null,
      advanceDeclineRatio,
      asOf: String(report.date || ""),
      source: "最新マーケットレポート記載値"
    };
  }

  function latestJapanBreadth(report) {
    const candidates = [];
    if (report) candidates.push(report);

    if (typeof reports !== "undefined" && Array.isArray(reports)) {
      reports
        .filter((item) => item && item.date && (!report?.date || item.date <= report.date))
        .sort((a, b) => `${b.date} ${b.time || ""}`.localeCompare(`${a.date} ${a.time || ""}`))
        .forEach((item) => candidates.push(item));
    }

    const seen = new Set();
    for (const candidate of candidates) {
      const key = `${candidate?.date || ""} ${candidate?.time || ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const parsed = parseJapanBreadth(candidate);
      if (parsed) return parsed;
    }
    return null;
  }

  stockBreadthFor = function patchedStockBreadthFor(region, report) {
    const primary = originalStockBreadthFor(region, report);
    if (region !== "japan" || primary?.status === "available") return primary;

    const fallback = latestJapanBreadth(report);
    return fallback || primary;
  };
})();
