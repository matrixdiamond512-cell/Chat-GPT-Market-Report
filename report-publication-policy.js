/* Shared fail-closed eligibility for public report projections. */
(function attachMarketReportPublicationPolicy(root) {
  function isEligible(report) {
    if (!report || typeof report !== "object" || Array.isArray(report)) return false;
    const status = String(report.report_status || "").trim().toUpperCase();
    return !status || status === "PUBLISHED" || status === "DOC_READBACK_PASS";
  }

  function merge(historyReports, dashboardReports) {
    const mergedByKey = new Map();
    const isValidSlot = (report) => (
      report &&
      /^\d{4}-\d{2}-\d{2}$/.test(String(report.date || "")) &&
      typeof report.time === "string" &&
      report.time.length > 0
    );
    const reportKey = (report) => `${report.date} ${report.time}`;

    (Array.isArray(historyReports) ? historyReports : []).forEach((report) => {
      if (!isEligible(report) || !isValidSlot(report)) return;
      mergedByKey.set(reportKey(report), report);
    });
    (Array.isArray(dashboardReports) ? dashboardReports : []).forEach((report) => {
      if (!isEligible(report) || !isValidSlot(report)) return;
      const key = reportKey(report);
      const history = mergedByKey.get(key) || {};
      mergedByKey.set(key, {
        ...history,
        ...report,
        fullText: report.fullText || history.fullText || ""
      });
    });

    return [...mergedByKey.values()].sort((a, b) => (
      reportKey(b).localeCompare(reportKey(a))
    ));
  }

  const policy = Object.freeze({ isEligible, merge });
  root.MarketReportPublicationPolicy = policy;
  if (typeof module !== "undefined" && module.exports) module.exports = policy;
})(globalThis);
