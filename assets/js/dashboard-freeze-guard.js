(() => {
  "use strict";

  const nativeFetch = window.fetch.bind(window);
  const FETCH_TIMEOUT_MS = 3500;
  const WATCHDOG_DELAY_MS = 6500;
  const RECOVERY_TIMEOUT_MS = 3500;

  function isDashboardDataRequest(input) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    return /(?:^|\/)(?:data\/|reports\.json|economic-calendar\.json)/.test(url);
  }

  // Static JSON on GitHub Pages should return quickly. A stalled request must never
  // keep the whole dashboard in the initial "loading" state indefinitely.
  window.fetch = function guardedFetch(input, init = {}) {
    if (!isDashboardDataRequest(input) || init.signal) {
      return nativeFetch(input, init);
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    return nativeFetch(input, { ...init, signal: controller.signal })
      .finally(() => clearTimeout(timer));
  };

  function reportKey(report) {
    return `${report?.date || ""} ${report?.time || ""}`;
  }

  function normalizeReports(payload) {
    if (Array.isArray(payload)) return payload;
    if (!payload || typeof payload !== "object") return [];
    if (Array.isArray(payload.reports)) return payload.reports;
    if (payload.latestReport) return [payload.latestReport];
    if (payload.currentReport) return [payload.currentReport];
    return [];
  }

  async function fetchJson(path) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), RECOVERY_TIMEOUT_MS);
    try {
      const response = await nativeFetch(`${path}?recovery=${Date.now()}`, {
        cache: "no-store",
        signal: controller.signal
      });
      if (!response.ok) throw new Error(`${path} HTTP ${response.status}`);
      return await response.json();
    } finally {
      clearTimeout(timer);
    }
  }

  function statusIsStillLoading() {
    const node = document.getElementById("reportStatus");
    return Boolean(node && /読み込み中|確認中/.test(node.textContent || ""));
  }

  function setRecoveryFailure(message) {
    const status = document.getElementById("reportStatus");
    if (status) status.textContent = "読み込みを再試行してください";

    const existing = document.getElementById("dashboardRecoveryNotice");
    if (existing) return;

    const shell = document.querySelector(".page-shell");
    if (!shell) return;
    const notice = document.createElement("div");
    notice.id = "dashboardRecoveryNotice";
    notice.className = "empty-state";
    notice.innerHTML = `${message}<br><button type="button" id="dashboardRecoveryReload" style="margin-top:12px;padding:10px 16px;border-radius:8px;border:1px solid #8aa0bd;background:#fff;color:#0b2d5c;font-weight:700;">再読み込み</button>`;
    shell.prepend(notice);
    document.getElementById("dashboardRecoveryReload")?.addEventListener("click", () => location.reload());
  }

  function installReportIntoMainRenderer(payload, list) {
    try {
      if (typeof reports === "undefined" || typeof selectedReport === "undefined" || typeof render !== "function") {
        return false;
      }

      reports = list
        .filter((report) => report && /^\d{4}-\d{2}-\d{2}$/.test(report.date || ""))
        .slice()
        .sort((a, b) => reportKey(b).localeCompare(reportKey(a)));
      if (!reports.length) return false;

      selectedReport = reports[0];

      if (typeof dashboardMeta !== "undefined") {
        dashboardMeta = {
          generatedAt: payload?.generatedAt || "",
          dataAsOf: payload?.dataAsOf || "",
          status: payload?.status || "recovery",
          marketData: payload?.marketData || payload?.latestReport?.marketData || null,
          marketDataUpdatedAt: payload?.marketDataUpdatedAt || payload?.marketData?.generatedAt || ""
        };
      }

      render();
      const status = document.getElementById("reportStatus");
      if (status && /読み込み中|確認中/.test(status.textContent || "")) {
        status.textContent = `${selectedReport.title || reportKey(selectedReport)} を表示中`;
      }
      return true;
    } catch (error) {
      console.warn("dashboard emergency renderer failed", error);
      return false;
    }
  }

  function minimalRecoveryRender(report) {
    if (!report) return false;

    const status = document.getElementById("reportStatus");
    if (status) status.textContent = `${report.title || reportKey(report)} を表示中`;

    const dateInput = document.getElementById("dateInput");
    if (dateInput && report.date) dateInput.value = report.date;

    const timeTabs = document.getElementById("timeTabs");
    if (timeTabs && report.time) {
      timeTabs.innerHTML = `<button type="button" class="active" disabled>${report.time}</button>`;
    }

    const putList = (id, values, fallback) => {
      const node = document.getElementById(id);
      if (!node) return;
      const items = Array.isArray(values) ? values : values ? [values] : [];
      node.innerHTML = items.length
        ? items.slice(0, 5).map((item) => `<li>${String(item?.text || item || "")}</li>`).join("")
        : `<li>${fallback}</li>`;
    };

    putList("themeList", report.theme, "相場テーマを取得できませんでした");
    putList("changeList", report.changes, "前回からの変化を取得できませんでした");
    putList("newsList", report.news, "ニュースを取得できませんでした");
    putList("positionList", report.positioning, "需給・ポジションを取得できませんでした");

    const leading = document.getElementById("leadingMarket");
    if (leading) leading.textContent = report.leadingMarket || "取得不能";

    const environment = document.getElementById("temperatureMiniCards");
    if (environment && /読み込み中/.test(environment.textContent || "")) {
      environment.innerHTML = '<div class="temperature-mini-loading">主要レポートは復旧表示しました。市場温度データは次回読み込みで再取得します。</div>';
    }
    return true;
  }

  async function recoverDashboard() {
    if (!statusIsStillLoading()) return;

    let payload = null;
    let list = [];
    const errors = [];

    for (const path of ["data/dashboard.json", "reports.json"]) {
      try {
        const candidate = await fetchJson(path);
        const candidateList = normalizeReports(candidate);
        if (candidateList.length) {
          payload = candidate;
          list = candidateList;
          break;
        }
        errors.push(`${path}: レポートなし`);
      } catch (error) {
        errors.push(`${path}: ${error?.name === "AbortError" ? "タイムアウト" : error?.message || "取得失敗"}`);
      }
    }

    if (!list.length) {
      setRecoveryFailure(`ダッシュボードの読み込みが停止しました。${errors.join(" / ")}`);
      return;
    }

    list.sort((a, b) => reportKey(b).localeCompare(reportKey(a)));
    if (installReportIntoMainRenderer(payload, list)) return;
    minimalRecoveryRender(list[0]);
  }

  function startWatchdog() {
    setTimeout(recoverDashboard, WATCHDOG_DELAY_MS);
    setTimeout(() => {
      if (statusIsStillLoading()) recoverDashboard();
    }, 14000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startWatchdog, { once: true });
  } else {
    startWatchdog();
  }
})();
