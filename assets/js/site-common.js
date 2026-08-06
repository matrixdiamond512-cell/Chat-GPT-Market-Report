(function () {
  "use strict";

  var REFRESH_TEXT = "\u66f4\u65b0";
  var REFRESH_LABEL = "\u30da\u30fc\u30b8\u3092\u66f4\u65b0";

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

/*
 * Important-events page completeness guard.
 * Empty arrays from the calendar JSON used to suppress the fallback rows, and
 * partial conclusion objects could stop rendering before the bottom section.
 * This wrapper keeps every numbered section and every event-list row readable
 * without inventing market prices or reactions that were not acquired.
 */
(function () {
  "use strict";

  if (!document.getElementById("resultTable") || !document.getElementById("compareTable")) return;

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

  function hasUsefulComparison(rows) {
    return nonEmptyArray(rows) && rows.some(function (row) {
      return Array.isArray(row) && row.length > 2 && !isPlaceholder(row[2]);
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
        "米2年債、USD/JPY、株価指数先物の順に初動を確認",
        "価格反応データがない場合は取得不能理由を表示"
      ];
    }
    if (state === "pending") {
      return [
        "発表時刻は経過済み。実績値の取得を継続中",
        "取得元の更新と名称照合を再確認",
        "推測値は表示せず、取得不能理由を明記"
      ];
    }
    return [
      "市場予想と前回値を事前確認",
      "発表直後は米2年債、USD/JPY、株価指数先物を優先確認",
      "実績値と市場反応は発表後に自動反映"
    ];
  }

  function defaultScenarioRows(event) {
    return marketNames(event).map(function (market) {
      return [market, "上振れ・タカ派なら強い反応", "予想通りなら限定的", "下振れ・ハト派なら逆方向"];
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
        ["更新予定", "発表後の自動更新で初動・5分後・30分後・1時間後を確認します"]
      ];
    }
    if (state === "pending") {
      return [
        ["結果確認", text(event.resultExplanation) || "実績値の取得を継続しています"],
        ["価格反応", "実績値と価格スナップショットが揃うまで判定を保留します"]
      ];
    }
    return [
      ["実績値", "実績値は取得済みです"],
      ["価格反応", "価格スナップショット未取得のため、実際の反応は判定保留です"]
    ];
  }

  function fallbackComparison(event) {
    var state = eventState(event);
    return marketNames(event).map(function (market) {
      if (state === "scheduled") {
        return [market, "セクション2の事前シナリオ", "発表前", "発表後に判定"];
      }
      if (state === "pending") {
        return [market, "セクション2の事前シナリオ", "実績・価格反応を取得中", "判定保留"];
      }
      return [market, "セクション2の事前シナリオ", "価格反応データ未取得", "判定保留"];
    });
  }

  function defaultWatch(event) {
    var items = [];
    marketNames(event).slice(0, 5).forEach(function (market) {
      items.push(market + "の初動と持続性");
    });
    if (items.length < 3) {
      items.push("予想・前回・実績の差", "金利・為替・株式の反応整合性", "次の重要イベントへの影響");
    }
    return items.slice(0, 6);
  }

  function enrichEvent(event) {
    var state = eventState(event);
    var result = event.result && typeof event.result === "object" ? event.result : {};

    event.focus = nonEmptyArray(event.focus) ? event.focus : defaultFocus(event);
    event.priced = nonEmptyArray(event.priced) ? event.priced : defaultPriced(event);
    event.scenarios = nonEmptyArray(event.scenarios) ? event.scenarios : defaultScenarioRows(event);
    event.outlook = nonEmptyArray(event.outlook) ? event.outlook : defaultOutlookRows(event);

    if (state === "scheduled") {
      result.actual = isPlaceholder(result.actual) ? "発表前（発表後に自動反映）" : result.actual;
      result.revised = isPlaceholder(result.revised) ? "発表後に確認" : result.revised;
      result.surprise = isPlaceholder(result.surprise) ? "発表前" : result.surprise;
      event.resultExplanation = text(event.resultExplanation) || "発表前です。予想値と前回値を確認し、実績値と市場反応は発表後に自動更新します。";
    } else if (state === "pending") {
      result.actual = isPlaceholder(result.actual) ? "取得中" : result.actual;
      result.revised = isPlaceholder(result.revised) ? "確認中" : result.revised;
      result.surprise = isPlaceholder(result.surprise) ? "判定保留" : result.surprise;
      event.resultExplanation = text(event.resultExplanation) || "発表時刻は経過しています。実績値を取得中で、推測値は表示しません。";
    } else {
      result.actual = isPlaceholder(result.actual) ? "数値発表なし／取得結果を確認" : result.actual;
      result.revised = isPlaceholder(result.revised) ? "改定なし／確認中" : result.revised;
      result.surprise = isPlaceholder(result.surprise) ? "比較保留" : result.surprise;
      event.resultExplanation = text(event.resultExplanation) || "実績値を確認済みです。市場反応は価格データと照合して判定します。";
    }

    result.consensus = isPlaceholder(result.consensus) ? (event.forecast || "予想なし") : result.consensus;
    result.previous = isPlaceholder(result.previous) ? (event.previousValue || event.previous || "前回値なし") : result.previous;
    event.result = result;

    if (!hasUsefulReaction(event.reactions)) event.reactions = fallbackReactions(event);
    if (!hasUsefulComparison(event.comparison)) event.comparison = fallbackComparison(event);

    var conclusion = event.conclusion && typeof event.conclusion === "object" ? event.conclusion : {};
    event.conclusion = {
      narrative: text(conclusion.narrative) || (state === "released" ? "結果確認済み" : state === "pending" ? "結果確認中" : "発表前"),
      reaction: text(conclusion.reaction) || (state === "released" ? "価格反応は判定保留" : state === "pending" ? "実績値を取得中" : "発表後に判定"),
      watch: nonEmptyArray(conclusion.watch) ? conclusion.watch : defaultWatch(event)
    };

    event.reason = text(event.reason) || text(event.resultExplanation) || (event.name + "が金利・為替・株価へ与える影響を確認");
    return event;
  }

  function install() {
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
    try { normalizeDedicatedEvents = wrapped; } catch (error) { /* global binding may be read-only in some browsers */ }
    return true;
  }

  var installed = install();
  if (!installed) {
    window.setTimeout(install, 0);
  }

  if (installed && typeof window.loadDynamicEventPage === "function") {
    window.setTimeout(function () {
      window.loadDynamicEventPage();
    }, 0);
  }
})();
