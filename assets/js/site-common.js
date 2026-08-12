(function () {
  "use strict";

  var pageId = (location.pathname.split("/").pop() || "index.html").replace(/\.html$/, "");
  var workflows = {
    "index": "update-market-data.yml",
    "report": "build-reports.yml",
    "usdjpy-volume": "update-usdjpy-volume.yml",
    "events": "update-economic-calendar.yml",
    "rates-bonds": "update-rates-bonds.yml",
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
      return data.generatedAt || data.updatedAt || data.asOfDate || data.dataAsOf || null;
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

(function () {
  "use strict";
  if (!document.getElementById("scenarioTable") || !document.getElementById("resultTable")) return;

  function clean(value) { return String(value == null ? "" : value).replace(/\s+/g, " ").trim(); }
  function list(value) { return Array.isArray(value) ? value.filter(Boolean) : []; }
  function blank(value) { return /^(|—|-|未取得|確認中|未計測|データ次第|詳細待ち|結果待ち)$/.test(clean(value)); }

  var scenarioFallback = [
    ["米2年債","上昇しやすい","小動き","低下しやすい"],
    ["米10年債","上昇しやすい","小動き","低下しやすい"],
    ["ダウ先物","金利上昇なら重い","小動き","金利低下なら支え"],
    ["ナスダック先物","高金利なら重い","小動き","金利低下なら支え"],
    ["日経225先物","米株安・円高なら重い","小動き","米株高・円安なら支え"],
    ["USD/JPY","ドル高で上昇しやすい","小動き","ドル安で下落しやすい"],
    ["EUR/USD","ドル高で下落しやすい","小動き","ドル安で上昇しやすい"],
    ["金","実質金利上昇なら重い","小動き","実質金利低下なら支え"],
    ["原油","景気上振れなら支え","小動き","景気減速なら重い"]
  ];

  function eventState(event) {
    if (event.status === "released" || !blank(event.actual)) return "released";
    if (event.status === "result_pending" || event.status === "needs_result") return "pending";
    if (event.iso && new Date(event.iso).getTime() < Date.now()) return "pending";
    return "scheduled";
  }

  function isCanonicalRawEvent(event) {
    if (!event || typeof event !== "object") return false;
    var sourceType = clean(event.sourceType);
    var sourceKey = clean(event.sourceKey);
    var title = clean(event.title || event.name || event.event);
    var narrativeTitle = /^(最重要イベント|重要イベントは|これから発表|本日の重要|注目点は)/.test(title);
    if (narrativeTitle || title.length > 120) return false;
    if (sourceType) return sourceType === "forex_factory_weekly" && Boolean(sourceKey);
    return Boolean(sourceKey && event.date && event.time);
  }

  function ensureEvent(event) {
    var state = eventState(event);
    event.focus = list(event.focus).length ? event.focus : list(event.affected && String(event.affected).split("・"));
    if (!event.focus.length) event.focus = ["米2年債","米10年債","USD/JPY","株価指数先物","金"];
    event.priced = list(event.priced).length ? event.priced : state === "scheduled"
      ? ["市場予想と前回値を確認","発表直後は米2年債とUSD/JPYを優先確認","実績値は発表後に更新"]
      : ["実績値・予想値・前回値の差を確認","取得していない市場反応は表示しない","取得不能時は理由を表示"];
    event.scenarios = list(event.scenarios).length ? event.scenarios : scenarioFallback;
    event.outlook = list(event.outlook).length ? event.outlook : [];
    event.reactions = list(event.reactions).length ? event.reactions : [[state === "scheduled" ? "発表前" : "結果確認", state === "scheduled" ? "市場反応はまだありません" : "予想値・前回値との差を確認します"]];

    event.result = event.result && typeof event.result === "object" ? event.result : {};
    event.result.actual = blank(event.result.actual) ? (state === "scheduled" ? "発表前" : state === "pending" ? "取得中" : "数値発表なし") : event.result.actual;
    event.result.consensus = blank(event.result.consensus) ? (event.forecast || "予想なし") : event.result.consensus;
    event.result.previous = blank(event.result.previous) ? (event.previousValue || event.previous || "前回値なし") : event.result.previous;
    event.result.revised = blank(event.result.revised) ? (state === "scheduled" ? "発表後に確認" : "改定なし") : event.result.revised;
    event.result.surprise = blank(event.result.surprise) ? (state === "scheduled" ? "発表前" : "判定保留") : event.result.surprise;
    event.resultExplanation = clean(event.resultExplanation) || (state === "scheduled" ? "発表前です。実績値は発表後に更新します。" : state === "pending" ? "発表時刻は経過しています。実績値を取得中です。" : "実績値を確認済みです。");

    var conclusion = event.conclusion && typeof event.conclusion === "object" ? event.conclusion : {};
    event.conclusion = {
      narrative: clean(conclusion.narrative) || (state === "scheduled" ? "発表前" : state === "pending" ? "結果確認中" : "結果確認済み"),
      reaction: clean(conclusion.reaction) || (state === "scheduled" ? "発表後に判定" : "予想との差を確認"),
      watch: list(conclusion.watch).length ? conclusion.watch : ["米2年債の方向","USD/JPYの方向","株価指数先物の反応"]
    };
    event.reason = clean(event.reason) || event.resultExplanation;
    return event;
  }

  function wrapNormalizer() {
    var original = window.normalizeDedicatedEvents;
    if (typeof original !== "function" || original.__practicalWrapped) return;
    var wrapped = function (payload) {
      var safePayload = payload;
      if (payload && Array.isArray(payload.events)) {
        safePayload = Object.assign({}, payload, { events: payload.events.filter(isCanonicalRawEvent) });
      }
      var events = original(safePayload);
      return Array.isArray(events) ? events.map(ensureEvent) : [];
    };
    wrapped.__practicalWrapped = true;
    window.normalizeDedicatedEvents = wrapped;
    try { normalizeDedicatedEvents = wrapped; } catch (error) { }
  }

  function syncHero(event) {
    if (!event) return;
    var state = eventState(event);
    var panel = document.querySelector(".grid-top>.panel:first-child");
    var heading = panel && panel.querySelector(".panel-title");
    if (heading) heading.innerHTML = '<span class="badge-num">1</span>' + (state === "scheduled" ? "次の重要イベント" : "選択中イベント");

    var name = document.getElementById("eventName");
    var time = document.getElementById("eventTime");
    var importance = document.getElementById("eventImportance");
    var consensus = document.getElementById("eventConsensus");
    var previous = document.getElementById("eventPrevious");
    if (name) name.textContent = event.name || "イベント名取得不能";
    if (time) time.textContent = event.time || "発表日時取得不能";
    if (importance) importance.textContent = event.importance || "—";
    if (consensus) consensus.textContent = event.consensus || event.forecast || "予想なし";
    if (previous) previous.textContent = event.previous || event.previousValue || "前回値なし";
  }

  function wrapRenderer() {
    var original = window.renderDynamicEvent;
    if (typeof original !== "function" || original.__integrityWrapped) return;
    var wrapped = function (event) {
      var result = original(event);
      syncHero(event);
      return result;
    };
    wrapped.__integrityWrapped = true;
    window.renderDynamicEvent = wrapped;
    try { renderDynamicEvent = wrapped; } catch (error) { }
  }

  function addStyles() {
    if (document.getElementById("eventsPracticalStyles")) return;
    var style = document.createElement("style");
    style.id = "eventsPracticalStyles";
    style.textContent = [
      '.events-practical .grid-top{grid-template-columns:minmax(0,1.15fr) minmax(340px,.85fr);align-items:stretch}',
      '.events-practical .grid-mid{display:block}.events-practical .grid-mid>.panel{width:100%}',
      '.events-practical .grid-small{display:none!important}',
      '.events-practical .practical-markets-panel{margin-bottom:10px}',
      '.events-practical .practical-markets-table{min-width:680px}',
      '.events-practical .practical-markets-table th:first-child{width:25%}',
      '.events-practical .event-list-table th:nth-child(8),.events-practical .event-list-table td:nth-child(8),.events-practical .event-list-table th:nth-child(9),.events-practical .event-list-table td:nth-child(9){display:none}',
      '.events-practical .event-list-table{min-width:1080px}',
      '.events-practical .event-country-heading{width:126px;min-width:126px}',
      '.events-practical .event-country-cell{width:126px;min-width:126px;font-weight:900}',
      '.events-practical .event-country-inner{display:flex;align-items:center;gap:7px;white-space:nowrap}',
      '.events-practical .event-country-flag{font-size:18px;line-height:1}',
      '.events-practical .event-country-name{color:#173968;font-weight:950}',
      '.events-practical .scenario th:nth-child(2){color:#d0001d;background:#fff1f2}',
      '.events-practical .scenario th:nth-child(3){color:#0b55c8;background:#f4f8ff}',
      '.events-practical .scenario th:nth-child(4){color:#087045;background:#eef9f3}',
      '.events-practical #reactionTable{display:none!important}',
      '.events-practical #reactionTableParent{display:none!important}',
      '.events-practical .practical-note{margin:10px 0 0;padding:8px 10px;border-top:1px solid #d4dfef;color:#536680;font-size:12px;font-weight:800}',
      '.events-practical .events-head h3{display:flex;align-items:center;gap:9px}',
      '.events-practical .events-head h3:before{content:"5";display:inline-grid;place-items:center;min-width:26px;height:26px;border-radius:5px;background:#0a57ca;color:#fff;font-size:15px;font-weight:1000}',
      '@media(max-width:1180px){.events-practical .grid-top{grid-template-columns:1fr}}'
    ].join("");
    document.head.appendChild(style);
  }

  function makeMarketsPanel() {
    var section = document.createElement("section");
    section.className = "panel practical-markets-panel";
    section.innerHTML = '<h3 class="panel-title"><span class="badge-num">4</span>確認すべき市場</h3><div class="table-wrap"><table class="practical-markets-table"><thead><tr><th>イベント分類</th><th>主に確認する市場</th></tr></thead><tbody><tr><td>米雇用指標</td><td>米2年債・USD/JPY・米株先物</td></tr><tr><td>CPI・PCE</td><td>米2年債・米10年債・ドル・金・ナスダック先物</td></tr><tr><td>FOMC・FRB発言</td><td>米金利・ドル・米株先物・金</td></tr><tr><td>日銀関連</td><td>USD/JPY・日本金利・日経225先物</td></tr><tr><td>ECB関連</td><td>EUR/USD・欧州金利・欧州株</td></tr><tr><td>原油在庫・OPEC</td><td>WTI・エネルギー株・インフレ期待</td></tr><tr><td>国債入札</td><td>対象国の金利・為替・株価指数</td></tr></tbody></table></div>';
    return section;
  }

  function countryFlag(country) {
    var key = clean(country);
    var flags = {
      "米国":"🇺🇸","日本":"🇯🇵","欧州":"🇪🇺","ユーロ圏":"🇪🇺","中国":"🇨🇳","英国":"🇬🇧",
      "カナダ":"🇨🇦","豪州":"🇦🇺","オーストラリア":"🇦🇺","ニュージーランド":"🇳🇿","スイス":"🇨🇭",
      "スペイン":"🇪🇸","フランス":"🇫🇷","ドイツ":"🇩🇪","イタリア":"🇮🇹","複数":"🌐"
    };
    return flags[key] || "🌐";
  }

  function currentDayEvents() {
    var source = [];
    var active = "all";
    try {
      if (typeof dynamicEventSource !== "undefined" && Array.isArray(dynamicEventSource)) source = dynamicEventSource.slice();
      if (typeof activeEventCountry !== "undefined") active = activeEventCountry || "all";
    } catch (error) { }

    if (active !== "all") {
      var primary = ["米国","日本","欧州","中国","英国"];
      source = active === "other"
        ? source.filter(function (event) { return primary.indexOf(event.country) === -1; })
        : source.filter(function (event) { return event.country === active; });
    }

    var picker = document.getElementById("eventDatePicker");
    var date = picker ? picker.value : "";
    source = source.filter(function (event) { return !date || event.date === date; });
    source.sort(function (a, b) {
      var aKey = String(a.date || "") + " " + String(a.clock || (a.iso ? a.iso.slice(11,16) : "99:99")) + " " + String(a.name || "");
      var bKey = String(b.date || "") + " " + String(b.clock || (b.iso ? b.iso.slice(11,16) : "99:99")) + " " + String(b.name || "");
      return aKey.localeCompare(bKey);
    });
    return source;
  }

  function addCountryColumn() {
    var table = document.querySelector(".event-list-table");
    if (!table) return;

    var headerRow = table.querySelector("thead tr");
    if (headerRow && !headerRow.querySelector(".event-country-heading")) {
      var heading = document.createElement("th");
      heading.className = "event-country-heading";
      heading.textContent = "国・地域";
      headerRow.insertBefore(heading, headerRow.children[1] || null);
    }

    var eventsForDay = currentDayEvents();
    table.querySelectorAll("tbody tr").forEach(function (row) {
      if (row.querySelector(".event-country-cell")) return;
      var button = row.querySelector("[data-dynamic-index]");
      var index = button ? Number(button.getAttribute("data-dynamic-index")) : -1;
      var event = Number.isInteger(index) && index >= 0 ? eventsForDay[index] : null;

      if (!event && row.children.length > 1) {
        var eventName = clean(row.children[1].textContent);
        event = eventsForDay.find(function (item) { return clean(item.name) === eventName; }) || null;
      }

      var country = clean(event && event.country) || "—";
      var cell = document.createElement("td");
      cell.className = "event-country-cell";
      var inner = document.createElement("span");
      inner.className = "event-country-inner";
      var flag = document.createElement("span");
      flag.className = "event-country-flag";
      flag.setAttribute("aria-hidden", "true");
      flag.textContent = country === "—" ? "" : countryFlag(country);
      var name = document.createElement("span");
      name.className = "event-country-name";
      name.textContent = country;
      inner.appendChild(flag);
      inner.appendChild(name);
      cell.appendChild(inner);
      row.insertBefore(cell, row.children[1] || null);
    });
  }

  function rebuild() {
    var page = document.querySelector("main.page");
    if (!page || page.dataset.practicalEventsReady === "1") return;
    var top = page.querySelector(".grid-top");
    var mid = page.querySelector(".grid-mid");
    var small = page.querySelector(".grid-small");
    var listSection = small && small.nextElementSibling;
    if (!top || !mid || !small || !listSection) return;

    var topPanels = top.querySelectorAll(":scope>.panel");
    var midPanels = mid.querySelectorAll(":scope>.panel");
    if (topPanels.length < 2 || midPanels.length < 2) return;

    topPanels[1].remove();
    top.appendChild(midPanels[1]);
    var reactionTable = document.getElementById("reactionTable");
    if (reactionTable && reactionTable.parentElement) reactionTable.parentElement.id = "reactionTableParent";
    if (!page.querySelector(".practical-markets-panel")) page.insertBefore(makeMarketsPanel(), listSection);

    /* Keep the legacy analysis nodes in the DOM. The original renderer writes to
       them even though this practical layout hides them. Removing the nodes made
       the dedicated calendar render throw, which incorrectly activated the old
       market-report fallback and mixed one event's title with another event's data. */
    small.setAttribute("aria-hidden", "true");

    var subtitle = page.querySelector(".page-head p");
    if (subtitle) subtitle.textContent = "これから発表される重要イベントと、発表後の予想値・実績値の差を確認します。";
    var heading = listSection.querySelector(".events-head h3");
    if (heading) heading.textContent = "日付別重要イベント一覧";
    var help = listSection.querySelector(".events-head small");
    if (help) help.textContent = "行の「詳細」を押すと、上段のイベント情報が切り替わります。";

    if (!listSection.querySelector(".practical-note")) {
      var note = document.createElement("p");
      note.className = "practical-note";
      note.textContent = "空欄は表示せず、取得できない場合は理由を表示します。取得していない市場反応や推測値は表示しません。";
      listSection.appendChild(note);
    }

    page.classList.add("events-practical");
    page.dataset.practicalEventsReady = "1";
    addStyles();
  }

  function enforceHeading() {
    var heading = document.querySelector(".events-head h3");
    if (heading && heading.textContent !== "日付別重要イベント一覧") heading.textContent = "日付別重要イベント一覧";
  }

  function keepPracticalPageComplete() {
    enforceHeading();
    addCountryColumn();
  }

  wrapNormalizer();
  wrapRenderer();
  rebuild();
  keepPracticalPageComplete();
  new MutationObserver(keepPracticalPageComplete).observe(document.body, {childList:true,subtree:true,characterData:true});
})();
