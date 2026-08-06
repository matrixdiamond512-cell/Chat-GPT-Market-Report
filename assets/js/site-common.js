(function () {
  "use strict";

  var REFRESH_TEXT = "更新";
  var REFRESH_LABEL = "ページを更新";

  function createRefreshButton() {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "site-refresh-button";
    button.textContent = REFRESH_TEXT;
    button.setAttribute("aria-label", REFRESH_LABEL);
    return button;
  }

  function prepareRefreshButton(button) {
    if (!button || button.dataset.siteRefreshReady === "1") return;
    button.dataset.siteRefreshReady = "1";
    button.type = "button";
    button.classList.add("site-refresh-button");
    button.textContent = REFRESH_TEXT;
    button.setAttribute("aria-label", REFRESH_LABEL);
    button.addEventListener("click", function () {
      window.location.reload();
    });
  }

  function findHeaderInner(header) {
    return (
      header.querySelector(".header-inner") ||
      header.querySelector(".mt-top-inner") ||
      header.querySelector(".top-inner") ||
      header.querySelector(".head-inner") ||
      header.querySelector(".rb-top-inner") ||
      header.querySelector(".sd-head-row") ||
      header
    );
  }

  function ensureRefreshButton() {
    var buttons = Array.prototype.slice.call(
      document.querySelectorAll(".update-btn, .site-refresh-button")
    );

    if (buttons.length === 0) {
      var header = document.querySelector("header");
      if (header) {
        var inner = findHeaderInner(header);
        var actions = document.createElement("div");
        actions.className = "site-page-actions";
        actions.appendChild(createRefreshButton());
        inner.appendChild(actions);
        buttons = Array.prototype.slice.call(
          document.querySelectorAll(".update-btn, .site-refresh-button")
        );
      }
    }

    buttons.forEach(prepareRefreshButton);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ensureRefreshButton);
  } else {
    ensureRefreshButton();
  }
})();

(function () {
  "use strict";

  if (!document.getElementById("resultTable") || !document.getElementById("scenarioTable")) return;

  function text(value) {
    return String(value == null ? "" : value).replace(/\s+/g, " ").trim();
  }

  function nonEmptyArray(value) {
    return Array.isArray(value) && value.length > 0;
  }

  function isPlaceholder(value) {
    return /^(|—|-|未取得|確認中|未計測|データ次第|詳細待ち|結果待ち)$/.test(text(value));
  }

  function hasUsefulReaction(rows) {
    return nonEmptyArray(rows) && rows.some(function (row) {
      return Array.isArray(row) && row.length > 1 && !isPlaceholder(row[1]);
    });
  }

  function eventIsReleased(event) {
    return event.status === "released" || !isPlaceholder(event.actual) || !isPlaceholder(event.result && event.result.actual);
  }

  function eventIsPast(event) {
    if (!event.iso) return false;
    var timestamp = new Date(event.iso).getTime();
    return Number.isFinite(timestamp) && timestamp < Date.now();
  }

  function eventState(event) {
    if (eventIsReleased(event)) return "released";
    if (event.status === "result_pending" || event.status === "needs_result" || eventIsPast(event)) return "pending";
    return "scheduled";
  }

  function marketNames(event) {
    var names = [];
    var source = nonEmptyArray(event.focus) ? event.focus : text(event.affected).split("・");
    source.forEach(function (item) {
      var value = text(item);
      if (!value) return;
      if (/米2年/.test(value)) value = "米2年債";
      else if (/米10年/.test(value)) value = "米10年債";
      else if (/USD\/?JPY|ドル円/.test(value)) value = "USD/JPY";
      else if (/EUR\/?USD|ユーロ/.test(value)) value = "EUR/USD";
      else if (/日経225/.test(value)) value = "日経225先物";
      else if (/Nasdaq|ナスダック/.test(value)) value = "ナスダック先物";
      else if (/Dow|ダウ/.test(value)) value = "ダウ先物";
      else if (/金|Gold|ゴールド/.test(value)) value = "金";
      else if (/原油|WTI/.test(value)) value = "原油";
      if (names.indexOf(value) === -1) names.push(value);
    });

    ["米2年債", "米10年債", "USD/JPY", "日経225先物", "金"].forEach(function (name) {
      if (names.indexOf(name) === -1) names.push(name);
    });
    return names.slice(0, 8);
  }

  function defaultFocus(event) {
    return marketNames(event).slice(0, 5);
  }

  function defaultPriced(event) {
    var state = eventState(event);
    if (state === "released") {
      return [
        "実績値・予想値・前回値の差を確認",
        "米2年債、USD/JPY、株価指数先物の順に確認",
        "取得していない価格反応は表示しない"
      ];
    }
    if (state === "pending") {
      return [
        "発表時刻は経過済み。実績値を取得中",
        "取得元の更新と名称照合を再確認",
        "推測値は表示せず、取得不能理由を明記"
      ];
    }
    return [
      "市場予想と前回値を事前確認",
      "発表直後は米2年債、USD/JPY、株価指数先物を優先確認",
      "実績値は発表後に自動反映"
    ];
  }

  function defaultScenarioRows(event) {
    return marketNames(event).map(function (market) {
      return [market, "強い結果なら上方向を確認", "小動き", "弱い結果なら逆方向を確認"];
    });
  }

  function defaultOutlookRows(event) {
    return marketNames(event).map(function (market) {
      return [market, "発表直後の初動を確認", "金利・為替・株価との整合性を確認", "反応が継続する材料", "反応を打ち消す材料"];
    });
  }

  function fallbackReactions(event) {
    var state = eventState(event);
    if (state === "scheduled") {
      return [
        ["発表前", "市場反応はまだありません"],
        ["更新予定", "発表後に実績値と判定を更新します"]
      ];
    }
    if (state === "pending") {
      return [
        ["結果確認", text(event.resultExplanation) || "実績値を取得中です"],
        ["判定", "実績値が揃うまで保留します"]
      ];
    }
    return [
      ["実績値", "実績値は取得済みです"],
      ["判定", "予想値・前回値との差を確認します"]
    ];
  }

  function defaultWatch(event) {
    var items = [];
    marketNames(event).slice(0, 5).forEach(function (market) {
      items.push(market + "の方向と持続性");
    });
    return items.length ? items : ["予想・前回・実績の差", "米2年債とUSD/JPY", "株価指数先物"];
  }

  function enrichEvent(event) {
    var state = eventState(event);
    var result = event.result && typeof event.result === "object" ? event.result : {};

    event.focus = nonEmptyArray(event.focus) ? event.focus : defaultFocus(event);
    event.priced = nonEmptyArray(event.priced) ? event.priced : defaultPriced(event);
    event.scenarios = nonEmptyArray(event.scenarios) ? event.scenarios : defaultScenarioRows(event);
    event.outlook = nonEmptyArray(event.outlook) ? event.outlook : defaultOutlookRows(event);

    if (state === "scheduled") {
      result.actual = isPlaceholder(result.actual) ? "発表前" : result.actual;
      result.revised = isPlaceholder(result.revised) ? "発表後に確認" : result.revised;
      result.surprise = isPlaceholder(result.surprise) ? "発表前" : result.surprise;
      event.resultExplanation = text(event.resultExplanation) || "発表前です。実績値は発表後に更新します。";
    } else if (state === "pending") {
      result.actual = isPlaceholder(result.actual) ? "取得中" : result.actual;
      result.revised = isPlaceholder(result.revised) ? "確認中" : result.revised;
      result.surprise = isPlaceholder(result.surprise) ? "判定保留" : result.surprise;
      event.resultExplanation = text(event.resultExplanation) || "発表時刻は経過しています。実績値を取得中です。";
    } else {
      result.actual = isPlaceholder(result.actual) ? "数値発表なし" : result.actual;
      result.revised = isPlaceholder(result.revised) ? "改定なし" : result.revised;
      result.surprise = isPlaceholder(result.surprise) ? "比較保留" : result.surprise;
      event.resultExplanation = text(event.resultExplanation) || "実績値を確認済みです。";
    }

    result.consensus = isPlaceholder(result.consensus) ? (event.forecast || "予想なし") : result.consensus;
    result.previous = isPlaceholder(result.previous) ? (event.previousValue || event.previous || "前回値なし") : result.previous;
    event.result = result;

    if (!hasUsefulReaction(event.reactions)) event.reactions = fallbackReactions(event);

    var conclusion = event.conclusion && typeof event.conclusion === "object" ? event.conclusion : {};
    event.conclusion = {
      narrative: text(conclusion.narrative) || (state === "released" ? "結果確認済み" : state === "pending" ? "結果確認中" : "発表前"),
      reaction: text(conclusion.reaction) || (state === "released" ? "予想との差を確認" : state === "pending" ? "実績値を取得中" : "発表後に判定"),
      watch: nonEmptyArray(conclusion.watch) ? conclusion.watch : defaultWatch(event)
    };

    event.reason = text(event.reason) || text(event.resultExplanation) || (event.name + "の結果を確認");
    return event;
  }

  function installNormalizerGuard() {
    var original = typeof window.normalizeDedicatedEvents === "function"
      ? window.normalizeDedicatedEvents
      : (typeof normalizeDedicatedEvents === "function" ? normalizeDedicatedEvents : null);
    if (!original || original.__eventCompletenessWrapped) return false;

    var wrapped = function (payload) {
      var rows = original(payload);
      return Array.isArray(rows) ? rows.map(enrichEvent) : [];
    };
    wrapped.__eventCompletenessWrapped = true;

    window.normalizeDedicatedEvents = wrapped;
    try { normalizeDedicatedEvents = wrapped; } catch (error) { }
    return true;
  }

  function practicalMarketsPanel() {
    var section = document.createElement("section");
    section.className = "panel practical-markets-panel";
    section.innerHTML = [
      '<h3 class="panel-title"><span class="badge-num">4</span>確認すべき市場</h3>',
      '<div class="table-wrap">',
      '<table class="practical-markets-table">',
      '<thead><tr><th>イベント分類</th><th>主に確認する市場</th></tr></thead>',
      '<tbody>',
      '<tr><td>米雇用指標</td><td>米2年債・USD/JPY・米株先物</td></tr>',
      '<tr><td>CPI・PCE</td><td>米2年債・米10年債・ドル・金・ナスダック先物</td></tr>',
      '<tr><td>FOMC・FRB発言</td><td>米金利・ドル・米株先物・金</td></tr>',
      '<tr><td>日銀関連</td><td>USD/JPY・日本金利・日経225先物</td></tr>',
      '<tr><td>ECB関連</td><td>EUR/USD・欧州金利・欧州株</td></tr>',
      '<tr><td>原油在庫・OPEC</td><td>WTI・エネルギー株・インフレ期待</td></tr>',
      '<tr><td>国債入札</td><td>対象国の金利・為替・株価指数</td></tr>',
      '</tbody></table></div>'
    ].join("");
    return section;
  }

  function injectPracticalStyles() {
    if (document.getElementById("eventsPracticalStyles")) return;
    var style = document.createElement("style");
    style.id = "eventsPracticalStyles";
    style.textContent = [
      '.events-practical .grid-top{grid-template-columns:minmax(0,1.15fr) minmax(340px,.85fr);align-items:stretch}',
      '.events-practical .grid-mid{display:block}',
      '.events-practical .grid-mid>.panel{width:100%}',
      '.events-practical .grid-small{display:none!important}',
      '.events-practical .practical-markets-panel{margin-bottom:10px}',
      '.events-practical .practical-markets-table{min-width:680px}',
      '.events-practical .practical-markets-table th:first-child{width:25%}',
      '.events-practical .event-list-table th:nth-child(7),',
      '.events-practical .event-list-table td:nth-child(7),',
      '.events-practical .event-list-table th:nth-child(8),',
      '.events-practical .event-list-table td:nth-child(8){display:none}',
      '.events-practical .event-list-table{min-width:980px}',
      '.events-practical .scenario th:nth-child(2){color:#d0001d;background:#fff1f2}',
      '.events-practical .scenario th:nth-child(3){color:#0b55c8;background:#f4f8ff}',
      '.events-practical .scenario th:nth-child(4){color:#087045;background:#eef9f3}',
      '.events-practical #reactionTable{display:none}',
      '.events-practical .practical-note{margin:10px 0 0;padding:8px 10px;border-top:1px solid #d4dfef;color:#536680;font-size:12px;font-weight:800}',
      '.events-practical .events-head h3{display:flex;align-items:center;gap:9px}',
      '.events-practical .events-head h3:before{content:"5";display:inline-grid;place-items:center;min-width:26px;height:26px;border-radius:5px;background:#0a57ca;color:#fff;font-size:15px;font-weight:1000}',
      '@media(max-width:1180px){.events-practical .grid-top{grid-template-columns:1fr}}'
    ].join("");
    document.head.appendChild(style);
  }

  function rebuildPracticalLayout() {
    var page = document.querySelector("main.page");
    if (!page || page.dataset.practicalEventsReady === "1") return;

    var top = page.querySelector(".grid-top");
    var mid = page.querySelector(".grid-mid");
    var small = page.querySelector(".grid-small");
    var listSection = small && small.nextElementSibling;
    if (!top || !mid || !small || !listSection) return;

    var topPanels = top.querySelectorAll(":scope > .panel");
    var midPanels = mid.querySelectorAll(":scope > .panel");
    if (topPanels.length < 2 || midPanels.length < 2) return;

    var orderPanel = topPanels[1];
    var scenarioPanel = midPanels[0];
    var resultPanel = midPanels[1];

    orderPanel.remove();
    top.appendChild(resultPanel);

    var reactionTable = document.getElementById("reactionTable");
    if (reactionTable && reactionTable.parentElement) reactionTable.parentElement.remove();

    var marketsPanel = practicalMarketsPanel();
    page.insertBefore(marketsPanel, listSection);
    small.remove();

    var subtitle = page.querySelector(".page-head p");
    if (subtitle) subtitle.textContent = "これから発表される重要イベントと、発表後の予想値・実績値の差を確認します。";

    var eventHeading = listSection.querySelector(".events-head h3");
    if (eventHeading) eventHeading.textContent = "日付別重要イベント一覧";
    var eventHelp = listSection.querySelector(".events-head small");
    if (eventHelp) eventHelp.textContent = "行の「詳細」を押すと、上段のイベント情報が切り替わります。";

    var note = document.createElement("p");
    note.className = "practical-note";
    note.textContent = "空欄は表示せず、取得できない場合は理由を表示します。取得していない市場反応や推測値は表示しません。";
    listSection.appendChild(note);

    var scenarioTitle = scenarioPanel.querySelector(".panel-title");
    if (scenarioTitle) {
      var badge = scenarioTitle.querySelector(".badge-num");
      scenarioTitle.textContent = "";
      if (badge) scenarioTitle.appendChild(badge);
      scenarioTitle.appendChild(document.createTextNode("発表前シナリオ（市場の予想反応）"));
    }

    page.classList.add("events-practical");
    page.dataset.practicalEventsReady = "1";
    injectPracticalStyles();
  }

  function keepEventHeadingPractical() {
    var heading = document.querySelector(".events-head h3");
    if (heading && heading.textContent !== "日付別重要イベント一覧") {
      heading.textContent = "日付別重要イベント一覧";
    }
    var help = document.querySelector(".events-head small");
    if (help && !/詳細/.test(help.textContent)) {
      help.textContent = "行の「詳細」を押すと、上段のイベント情報が切り替わります。";
    }
  }

  installNormalizerGuard();
  rebuildPracticalLayout();
  keepEventHeadingPractical();

  var observer = new MutationObserver(function () {
    keepEventHeadingPractical();
  });
  observer.observe(document.body, { childList: true, subtree: true, characterData: true });
})();
