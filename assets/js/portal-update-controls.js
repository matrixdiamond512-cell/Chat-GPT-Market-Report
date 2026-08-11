(function () {
  "use strict";

  var pageId = (location.pathname.split("/").pop() || "index.html").replace(/\.html$/, "");
  var workflows = {
    "index": "update-market-data.yml",
    "report": "build-reports.yml",
    "usdjpy-volume": "update-usdjpy-volume.yml",
    "events": "update-economic-calendar.yml",
    "rates-bonds": "update-rates-bonds.yml",
    "stocks": "update-stocks.yml",
    "usdjpy-supply-demand": "update-usdjpy-supply-demand.yml",
    "gold-supply-demand": "update-gold-supply-demand.yml",
    "nikkei225-supply-demand": "update-nikkei225-supply-demand.yml",
    "nikkei225-arbitrage": "update-nikkei225-arbitrage.yml"
  };
  var dataUrls = {
    "index": "data/dashboard.json",
    "report": "data/reports.json",
    "usdjpy-volume": "data/usdjpy-volume.json",
    "events": "data/events/latest.json",
    "rates-bonds": "data/rates-bonds.json",
    "stocks": "data/stocks.json",
    "usdjpy-supply-demand": "data/usdjpy-supply-demand.json",
    "gold-supply-demand": "data/gold-supply-demand.json",
    "nikkei225-supply-demand": "data/nikkei225-supply-demand.json",
    "nikkei225-arbitrage": "data/nikkei225-arbitrage.json"
  };
  var repoActions = "https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/workflows/";

  function addUpdateStyles() {
    if (document.getElementById("portalUpdateControlStyles")) return;
    var style = document.createElement("style");
    style.id = "portalUpdateControlStyles";
    style.textContent = ".site-update-actions{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.site-data-refresh-button{appearance:none;border:1px solid #c32c67;border-radius:8px;background:#fff0f6;color:#a51e54;padding:7px 11px;font:900 12px/1 sans-serif;cursor:pointer}.site-data-refresh-button:hover{background:#fbdde9}.site-data-refresh-button:disabled{border-color:#cbd4df;background:#f1f4f8;color:#7a8798;cursor:not-allowed}.site-update-request-status{flex-basis:100%;color:#64748b;font-size:10px;font-weight:800;line-height:1.4}.site-refresh-button{white-space:nowrap}@media(max-width:680px){.site-update-actions{width:100%}.site-update-request-status{width:100%}}";
    document.head.appendChild(style);
  }

  function prepareReloadButton(button) {
    if (!button || button.dataset.siteReloadReady === "1") return;
    button.dataset.siteReloadReady = "1";
    button.type = "button";
    button.classList.add("site-refresh-button");
    button.setAttribute("data-reload", "");
    button.removeAttribute("onclick");
    button.onclick = null;
    button.textContent = "再読込";
    button.setAttribute("aria-label", "表示中のページとJSONを再読込");
    button.addEventListener("click", function () {
      var url = new URL(window.location.href);
      url.searchParams.set("reload", Date.now());
      window.location.replace(url.toString());
    });
  }

  function statusHost(actions) {
    var node = actions.querySelector("[data-update-request-status]");
    if (node) return node;
    node = document.createElement("span");
    node.className = "site-update-request-status";
    node.setAttribute("data-update-request-status", "");
    node.setAttribute("role", "status");
    node.setAttribute("aria-live", "polite");
    actions.appendChild(node);
    return node;
  }

  async function readVersion() {
    var url = dataUrls[pageId];
    if (!url) return null;
    try {
      var response = await fetch(url + "?freshness=" + Date.now(), {cache:"no-store"});
      if (!response.ok) return null;
      var data = await response.json();
      var dates = [];
      function collect(value, depth) {
        if (!value || depth > 4) return;
        if (Array.isArray(value)) return value.slice(0, 5).forEach(function (item) { collect(item, depth + 1); });
        if (typeof value !== "object") return;
        Object.keys(value).forEach(function (key) {
          var item = value[key];
          if (/^(asOf|asOfDate|dataAsOf|dataDate|sourceDate|targetDate|publicationDate|latestTargetDate|latestPublicationDate)$/.test(key) && item) dates.push(key + ":" + item);
          else if (depth < 4 && item && typeof item === "object") collect(item, depth + 1);
        });
      }
      collect(data, 0);
      return dates.sort().join("|") || data.generatedAt || data.updatedAt || null;
    } catch (_) { return null; }
  }

  function addDataRefresh(actions) {
    if (actions.querySelector("[data-data-refresh]")) return;
    var workflow = workflows[pageId];
    var button = document.createElement("button");
    button.type = "button";
    button.className = "site-data-refresh-button";
    button.setAttribute("data-data-refresh", "");
    button.textContent = "データを更新";
    var status = statusHost(actions);
    if (!workflow) {
      button.disabled = true;
      button.title = "このページの統合更新Workflowは準備中です";
      status.textContent = "データ更新：専用Workflow準備中";
      return actions.insertBefore(button, status);
    }
    button.addEventListener("click", async function () {
      var before = await readVersion();
      try { sessionStorage.setItem("portalUpdate:" + pageId, JSON.stringify({before:before,requestedAt:new Date().toISOString()})); } catch (_) {}
      status.textContent = "GitHub Actionsで「Run workflow」を実行してください";
      window.open(repoActions + workflow, "_blank", "noopener");
    });
    actions.insertBefore(button, status);
  }

  async function showReturnStatus(actions) {
    var raw = null;
    try { raw = sessionStorage.getItem("portalUpdate:" + pageId); } catch (_) {}
    if (!raw) return;
    var request;
    try { request = JSON.parse(raw); } catch (_) { return; }
    var current = await readVersion();
    var status = statusHost(actions);
    if (current && request.before && current !== request.before) {
      status.textContent = "データ更新を確認しました：" + String(current).replace("T", " ").slice(0, 16);
      try { sessionStorage.removeItem("portalUpdate:" + pageId); } catch (_) {}
    } else {
      status.textContent = "更新要求後のデータ変更は未確認です";
    }
  }

  function ensureRefreshButtons() {
    addUpdateStyles();
    var buttons = Array.prototype.slice.call(document.querySelectorAll("[data-reload],.update-btn,.site-refresh-button,.refresh"));
    var actions = null;
    if (buttons.length) actions = buttons[0].closest(".site-page-actions,.top-meta,.gold-head-actions,.nikkei-head-actions,.usd-meta") || buttons[0].parentElement;
    if (!buttons.length) {
      var header = document.querySelector("header");
      var inner = header && (header.querySelector(".header-inner,.mt-top-inner,.top-inner,.head-inner,.rb-top-inner,.sd-head-row") || header);
      if (inner) {
        actions = document.createElement("div");
        actions.className = "site-page-actions";
        var button = document.createElement("button");
        button.className = "site-refresh-button";
        actions.appendChild(button);
        inner.appendChild(actions);
        buttons = [button];
      }
    }
    buttons.forEach(prepareReloadButton);
    if (actions) {
      actions.classList.add("site-update-actions");
      addDataRefresh(actions);
      void showReturnStatus(actions);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ensureRefreshButtons);
  else ensureRefreshButtons();
})();
