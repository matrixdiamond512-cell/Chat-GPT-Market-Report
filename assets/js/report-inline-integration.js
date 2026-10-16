(() => {
  const frame = document.getElementById("reportDocumentFrame");
  const status = document.getElementById("reportInlineStatus");
  if (!frame || !status) return;

  let expectedReport = null;
  let requestedKey = "";

  function reportKey(report) {
    return `${report?.date || ""} ${report?.time || ""}`;
  }

  function fullText(report) {
    return String(report?.fullText || report?.rawText || report?.body || "").replace(/^\uFEFF/, "");
  }

  function identityMatches(expected, actual) {
    if (!expected || !actual || reportKey(expected) !== reportKey(actual)) return false;
    const expectedText = fullText(expected);
    const actualText = fullText(actual);
    if (!expectedText || expectedText !== actualText) return false;

    const fieldPairs = [
      ["report_id", "report_id"], ["reportId", "reportId"],
      ["revision", "revision"], ["bodyHash", "bodyHash"],
      ["snapshot_id", "snapshot_id"], ["snapshotId", "snapshotId"]
    ];
    return fieldPairs.every(([left, right]) => {
      const a = expected[left], b = actual[right];
      return a == null || a === "" || b == null || b === "" || String(a) === String(b);
    });
  }

  function requestReport(report) {
    if (!report?.date || !report?.time) {
      expectedReport = null;
      requestedKey = "";
      frame.hidden = true;
      status.textContent = "表示対象のレポートを確認できません";
      return;
    }
    expectedReport = report;
    const key = reportKey(report);
    if (key === requestedKey && frame.dataset.ready === "true") {
      const rendered = frame.contentWindow.MarketReportLastRendered;
      if (frame.dataset.verifiedKey === key && identityMatches(report, rendered) && !frame.hidden) {
        status.textContent = `${key}｜市場サマリーと同一本文・identityを確認`;
        return;
      }
      status.textContent = `${key} の本文を照合中`;
      frame.hidden = true;
      sendSelectedReport();
      return;
    }
    status.textContent = `${key} の本文を読み込み中`;
    frame.hidden = true;
    frame.dataset.verifiedKey = "";
    if (key === requestedKey) return;
    requestedKey = key;
    frame.dataset.ready = "false";
    const url = new URL("report.html", document.baseURI);
    url.searchParams.set("embedded", "1");
    url.searchParams.set("date", report.date);
    url.searchParams.set("time", report.time);
    frame.src = `${url.pathname}${url.search}`;
  }

  function sendSelectedReport() {
    if (!expectedReport || frame.dataset.ready !== "true") return;
    frame.contentWindow.postMessage({ type: "market-dashboard-selected-report", report: expectedReport }, location.origin);
  }

  window.addEventListener("market-dashboard-report-selected", event => requestReport(event.detail?.report));
  frame.addEventListener("load", () => {
    frame.dataset.ready = "true";
    sendSelectedReport();
  });
  window.addEventListener("message", event => {
    if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
    const message = event.data;
    if (!message || message.type !== "market-report-inline-rendered") return;

    if (Number.isFinite(message.height) && message.height > 0) {
      frame.style.height = `${Math.ceil(message.height)}px`;
    }
    if (message.status === "error" || message.status === "missing") {
      frame.hidden = false;
      status.textContent = message.status === "missing"
        ? `${reportKey(expectedReport)} の本文データがありません`
        : "本文を読み込めません。市場サマリーと本文の接続を確認してください";
      return;
    }
    if (message.status !== "ready") return;

    let rendered = null;
    try { rendered = frame.contentWindow.MarketReportLastRendered; } catch (_) { /* same-origin read is required below */ }
    if (message.date !== expectedReport?.date || message.time !== expectedReport?.time
        || !identityMatches(expectedReport, rendered)) {
      frame.dataset.verifiedKey = "";
      frame.hidden = true;
      status.textContent = "表示を停止しました：市場サマリーと本文の日時・本文・identityが一致しません";
      return;
    }
    frame.dataset.verifiedKey = reportKey(expectedReport);
    frame.hidden = false;
    status.textContent = `${reportKey(expectedReport)}｜市場サマリーと同一本文・identityを確認`;
  });

  if (window.MarketDashboardSelectedReport) requestReport(window.MarketDashboardSelectedReport);
})();

