/* Version 7.01 renderer: preserve the existing stocks.html design system. */
(function () {
  var root = document.querySelector("[data-stocks-root]");
  var updated = document.querySelector("[data-updated]");
  if (!root || new URLSearchParams(location.search).has("date")) return;

  var esc = function (value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
    });
  };
  var arr = function (value) { return Array.isArray(value) ? value : []; };
  var dateText = function (value) { return String(value || "").slice(0, 10); };
  var jstDate = function () { return new Intl.DateTimeFormat("en-CA", {timeZone:"Asia/Tokyo", year:"numeric", month:"2-digit", day:"2-digit"}).format(new Date()); };
  var nyDate = function () { return new Intl.DateTimeFormat("en-CA", {timeZone:"America/New_York", year:"numeric", month:"2-digit", day:"2-digit"}).format(new Date()); };
  var flag = function (code) { return code === "US" ? "🇺🇸" : code === "JP" ? "🇯🇵" : ""; };
  var currentOf = function (payload) { return payload && typeof payload.current === "object" ? payload.current : (payload || {}); };
  var sourceText = function (source) {
    if (typeof source === "string") return source;
    return Object.values(source || {}).map(function (item) { return typeof item === "string" ? item : item && item.name; }).filter(Boolean).join(" / ") || "情報源取得不能";
  };
  var asOfText = function (value) {
    return value ? String(value).replace("T", " ").replace(/([+-]\d\d:\d\d|Z)$/, "").slice(0, 16) : "基準時刻取得不能";
  };
  var cls = function (value) {
    var text = String(value == null ? "" : value).trim();
    return text.indexOf("+") === 0 || text.indexOf("＋") === 0 || /上昇|買い|強/.test(text) ? "up"
      : text.indexOf("-") === 0 || text.indexOf("−") === 0 || /下落|売り|弱/.test(text) ? "down" : "muted";
  };

  function normalize(payload, expected, title, marketFlag) {
    var raw = Object.assign({}, currentOf(payload));
    var actual = dateText(raw.dataDate || raw.marketDate || raw.asOf);
    var hasRows = ["rows","gainers","losers","top","bottom","topGainers","topLosers"].some(function (key) { return arr(raw[key]).length > 0; });
    if (!raw.status) raw.status = actual && hasRows ? "ok" : "unavailable";
    if (!raw.freshness) raw.freshness = raw.status === "unavailable" ? "unavailable" : (expected && actual === expected ? "fresh" : "stale");
    if (expected && raw.status !== "unavailable" && actual && actual !== expected) raw.freshness = "stale";
    if (raw.status === "unavailable") raw.freshness = "unavailable";
    raw.dataDate = actual || null;
    raw.title = raw.title || title;
    raw.flag = raw.flag || marketFlag;
    return raw;
  }

  function meta(comp, session) {
    var base = session ? "session-meta" : "component-freshness";
    return "<div class=\"" + base + "\"><span>基準日 " + esc(comp.dataDate || "取得不能") + "</span><span>基準時刻 " + esc(asOfText(comp.asOf)) + "</span><span>更新日時 " + esc(comp.updatedAt || "更新日時取得不能") + "</span><span>情報源 " + esc(sourceText(comp.source)) + "</span><span>status " + esc(comp.status || "取得不能") + "</span><span>freshness " + esc(comp.freshness || "unavailable") + "</span></div>";
  }

  function warning(comp) {
    if (comp.freshness === "fresh") return "";
    if (comp.freshness === "stale") return "<div class=\"session-judgement\">前回データ／更新待ち：" + esc(comp.error || "当日の確定値へ更新されるまで最新値として扱いません。") + "</div>";
    return "<div class=\"panel-body\"><div class=\"empty\">取得不能<br><small>" + esc(comp.error || "当日の確定値を取得できませんでした。") + "</small></div></div>";
  }

  function panel(comp, body) {
    return "<article class=\"panel\"><h2 class=\"panel-title\"><span class=\"flag\">" + flag(comp.flag) + "</span>" + esc(String(comp.title || "取得不能").replace("（上昇率TOP5）", "")) + "</h2>" + meta(comp, false) + body + "</article>";
  }

  function dataTable(columns, rows, className) {
    if (!arr(rows).length) return "<div class=\"panel-body\"><div class=\"empty\">取得データなし</div></div>";
    return "<div class=\"table-wrap\"><table class=\"" + (className || "rank-table") + "\"><thead><tr>" +
      arr(columns).map(function (column) { return "<th>" + esc(column) + "</th>"; }).join("") +
      "</tr></thead><tbody>" +
      arr(rows).map(function (row) {
        return "<tr>" + arr(row).map(function (value, index) {
          return "<td class=\"" + (index > 0 ? "num " + cls(value) : "") + "\">" + esc(value) + "</td>";
        }).join("") + "</tr>";
      }).join("") + "</tbody></table></div>";
  }

  function market(comp) {
    if (comp.freshness === "unavailable" || !arr(comp.rows).length) return panel(comp, warning(comp));
    return panel(comp, warning(comp) + dataTable(["指標名","終値","前日比","評価・概況"], comp.rows, "market-table"));
  }

  function moverRows(items) {
    return arr(items).map(function (item, index) {
      return "<tr><td class=\"num\">" + esc(item.rank || index + 1) + "</td><td>" + esc(item.name || item.symbol || item.code || "銘柄名取得不能") +
        (item.reason ? "<span class=\"reason\">" + esc(item.reason) + "</span>" : "") +
        "</td><td class=\"num\">" + esc(item.close == null ? (item.price == null ? "取得不能" : item.price) : item.close) + "</td><td class=\"num " + cls(item.change || item.changePct) + "\">" + esc(item.change || item.changePct || "取得不能") + "</td></tr>";
    }).join("");
  }

  function moverTable(title, items, kind) {
    if (!arr(items).length) return "<div class=\"table-wrap\"><h3 class=\"mini-title " + kind + "\">" + title + "</h3><div class=\"empty\">取得データなし</div></div>";
    return "<div class=\"table-wrap\"><h3 class=\"mini-title " + kind + "\">" + title + "</h3><table class=\"rank-table\"><thead><tr><th>順位</th><th>銘柄名</th><th>終値</th><th>騰落率</th></tr></thead><tbody>" + moverRows(items) + "</tbody></table></div>";
  }

  function movers(comp) {
    if (comp.freshness === "unavailable") return panel(comp, warning(comp));
    return panel(comp, warning(comp) + "<div class=\"panel-body split\">" + moverTable("大幅上昇（上位5）", comp.gainers, "up") + moverTable("大幅下落（下位5）", comp.losers, "down") + "</div>");
  }

  function sectorGroup(items, title, kind, comp) {
    var rows = arr(items).slice(0, 5);
    if (!rows.length) return "<div class=\"sector-mover-group\"><h3 class=\"mini-title " + kind + "\">" + title + "</h3><div class=\"empty\">取得データなし</div></div>";
    var max = Math.max.apply(null, rows.map(function (item) { return Math.abs(parseFloat(String(item.change == null ? item.changePct : item.change).replace(/[+％%]/g, ""))) || 0; }).concat([0]));
    return "<div class=\"sector-mover-group\"><h3 class=\"mini-title " + kind + "\">" + title + "<span class=\"sector-source\">" + esc(comp.sourceLabel || "") + "</span></h3>" +
      rows.map(function (item, index) {
        var value = item.change == null ? (item.changePct == null ? "取得不能" : item.changePct) : item.change;
        var number = Math.abs(parseFloat(String(value).replace(/[+％%]/g, ""))) || 0;
        var width = max ? Math.max(8, Math.round(number / max * 100)) : 0;
        var barClass = kind === "down" ? "down-bar" : comp.flag === "JP" ? "jp" : "";
        return "<div class=\"sector-row\"><span class=\"rank\">" + (index + 1) + "</span><b>" + esc(item.name || "業種名取得不能") + "</b><span class=\"bar-track\"><span class=\"bar " + barClass + "\" style=\"width:" + width + "%\"></span></span><b class=\"num " + kind + "\">" + esc(value) + "</b><span class=\"sector-note\">" + esc(item.note || "前営業日終値比") + "</span></div>";
      }).join("") + "</div>";
  }

  function sectors(comp) {
    if (comp.freshness === "unavailable") return panel(comp, warning(comp));
    return panel(comp, warning(comp) + "<div class=\"panel-body\">" + sectorGroup(comp.gainers || comp.rows, "上昇率TOP5", "up", comp) + sectorGroup(comp.losers, "下落率TOP5", "down", comp) + "</div>");
  }

  function contributionTable(title, items, kind) {
    if (!arr(items).length) return "<div class=\"table-wrap\"><h3 class=\"mini-title " + kind + "\">" + title + "</h3><div class=\"empty\">取得データなし</div></div>";
    var rows = arr(items).map(function (item) { return "<tr><td>" + esc(item.name || item.symbol || item.code || "銘柄名取得不能") + "</td><td class=\"num " + cls(item.contribution) + "\">" + esc(item.contribution || "取得不能") + "</td></tr>"; }).join("");
    return "<div class=\"table-wrap\"><h3 class=\"mini-title " + kind + "\">" + title + "</h3><table class=\"rank-table\"><thead><tr><th>銘柄名</th><th>寄与度</th></tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function contributions(comp) {
    if (comp.freshness === "unavailable") return panel(comp, warning(comp));
    return panel(comp, warning(comp) + "<div class=\"panel-body split\">" + contributionTable("寄与度上位 5 銘柄", comp.top, "up") + contributionTable("寄与度下位 5 銘柄", comp.bottom, "down") + "</div>");
  }

  function list(items) {
    return "<ul>" + arr(items).map(function (item) { return "<li>" + esc(item) + "</li>"; }).join("") + "</ul>";
  }

  function judgement(data) {
    if (!data || typeof data !== "object") return "";
    var conclusion = data.conclusion || {};
    return "<section class=\"bottom-cards\"><article class=\"info-card conclusion\"><h2><span class=\"icon\">✓</span>" + esc(conclusion.title || "総合判断") + "</h2><p class=\"conclusion-main\">" + esc(conclusion.main || "取得不能") + "</p><p class=\"conclusion-sub\">" + esc(conclusion.sub || "") + "</p></article><article class=\"info-card reason-card\"><h2><span class=\"icon\">▮</span>" + esc(data.reason && data.reason.title || "理由") + "</h2>" + list(data.reason && data.reason.items) + "</article><article class=\"info-card risk\"><h2><span class=\"icon\">!</span>" + esc(data.risk && data.risk.title || "リスク") + "</h2>" + list(data.risk && data.risk.items) + "</article><article class=\"info-card watch\"><h2><span class=\"icon\">◎</span>" + esc(data.watch && data.watch.title || "注目") + "</h2>" + list(data.watch && data.watch.items) + "</article></section>";
  }

  function analyses(items) {
    if (!arr(items).length) return "";
    return "<section class=\"analysis-grid\">" + arr(items).map(function (item) {
      return "<article class=\"analysis-card\"><h2>" + esc(item.title) + "</h2>" + (item.items ? list(item.items) : "<p>" + esc(item.body || "") + "</p>") + "</article>";
    }).join("") + "</section>";
  }

  function sessionShell(title, comp, body) {
    var badge = comp.freshness === "fresh" ? "最新" : comp.freshness === "stale" ? "前回データ" : "取得不能";
    return "<article class=\"session-panel\"><div class=\"session-header\"><div class=\"session-title\"><span class=\"flag\">" + flag(comp.flag) + "</span>" + esc(title) + "</div><span class=\"session-badge\">" + badge + "</span></div>" + meta(comp, true) + body + "</article>";
  }

  function preopenTable(title, items, kind) {
    if (!arr(items).length) return "<div class=\"table-wrap\"><h3 class=\"mini-title " + kind + "\">" + title + "</h3><div class=\"empty\">取得データなし</div></div>";
    var rows = arr(items).map(function (item, index) {
      return "<tr><td class=\"num\">" + (index + 1) + "</td><td>" + esc(item.name || item.code || "銘柄名取得不能") + (item.reason ? "<span class=\"reason\">" + esc(item.reason) + "</span>" : "") + "</td><td class=\"num\">" + esc(item.indicativePrice == null ? "取得不能" : item.indicativePrice) + "</td><td class=\"num " + cls(item.change || item.changePct) + "\">" + esc(item.change || item.changePct || "取得不能") + "</td></tr>";
    }).join("");
    return "<div class=\"table-wrap\"><h3 class=\"mini-title " + kind + "\">" + title + "</h3><table class=\"rank-table\"><thead><tr><th>順位</th><th>銘柄名</th><th>気配値</th><th>騰落率</th></tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function preopen(comp) {
    if (comp.freshness === "unavailable") return sessionShell("東京市場 朝の寄り前分析", comp, warning(comp));
    var summary = comp.summary || {};
    var leadingSectors = arr(summary.leadingSectors).filter(Boolean);
    var sectorKpi = leadingSectors.length ? "<div class=\"kpi\"><span class=\"kpi-label\">主導業種</span><span class=\"kpi-value\">" + esc(leadingSectors.join("・")) + "</span></div>" : "";
    var kpis = "<div class=\"session-kpis\"><div class=\"kpi\"><span class=\"kpi-label\">全体</span><span class=\"kpi-value\">" + esc(summary.tone || "取得不能") + "</span></div><div class=\"kpi\"><span class=\"kpi-label\">広がり</span><span class=\"kpi-value\">" + esc(summary.breadth || "取得不能") + "</span></div>" + sectorKpi + "</div>";
    var insights = "<div class=\"session-insights\"><h3>分析コメント</h3><p class=\"comment\">" + esc(summary.comment || "取得できたランキングだけを集計しています。") + "</p></div>";
    var orders = arr(comp.buyOrderLeaders).length || arr(comp.sellOrderLeaders).length ? "<div class=\"panel-body split\">" + preopenTable("買い注文上位", comp.buyOrderLeaders, "up") + preopenTable("売り注文上位", comp.sellOrderLeaders, "down") + "</div>" : "";
    return sessionShell("東京市場 朝の寄り前分析", comp, (comp.freshness === "stale" ? warning(comp) : "") + kpis + insights + "<div class=\"panel-body split\">" + preopenTable("上昇気配TOP10", comp.gainers, "up") + preopenTable("下落気配TOP10", comp.decliners, "down") + "</div>" + orders);
  }

  function futuresTable(comp) {
    var rows = Object.values(comp.indexFutures || {}).filter(function (item) { return item && item.label; }).map(function (item) {
      return [item.label, item.change || "取得不能", item.asOf ? asOfText(item.asOf) : "取得不能"];
    });
    return dataTable(["指標","変化率","基準時刻"], rows, "rank-table");
  }

  function premarketSectorRows(comp) {
    var entries = Object.entries(comp.sectorBreadth || {});
    if (!entries.length) return "<div class=\"empty\">セクター強弱を取得できません。</div>";
    return entries.map(function (entry, index) {
      var name = entry[0], item = entry[1] || {};
      var average = item.averageChangePct == null ? "取得不能" : item.averageChangePct + "%";
      var direction = (item.up || 0) >= (item.down || 0) ? "up" : "down";
      var width = Math.min(100, Math.max(8, Math.abs(Number(item.averageChangePct || 0)) * 25));
      return "<div class=\"sector-row\"><span class=\"rank\">" + (index + 1) + "</span><b>" + esc(name) + "</b><span class=\"bar-track\"><span class=\"bar " + (direction === "down" ? "down-bar" : "") + "\" style=\"width:" + width + "%\"></span></span><b class=\"num " + direction + "\">" + esc((item.up || 0) + " / " + (item.down || 0)) + "</b><span class=\"sector-note\">平均 " + esc(average) + "｜監視銘柄ベース</span></div>";
    }).join("");
  }

  function premarket(comp) {
    if (comp.freshness === "unavailable") return sessionShell("米国市場 プレマーケット分析", comp, warning(comp));
    var breadth = comp.breadth || {};
    var kpis = "<div class=\"session-kpis\"><div class=\"kpi\"><span class=\"kpi-label\">監視銘柄</span><span class=\"kpi-value\">" + esc((comp.fetchedCount == null ? 0 : comp.fetchedCount) + " / " + (comp.universeSize == null ? 50 : comp.universeSize)) + "</span></div><div class=\"kpi\"><span class=\"kpi-label\">coverage</span><span class=\"kpi-value\">" + esc((comp.coverageRatio == null ? 0 : comp.coverageRatio) + "%") + "</span></div><div class=\"kpi\"><span class=\"kpi-label\">上昇 / 下落 / 横ばい</span><span class=\"kpi-value\">" + esc((breadth.up || 0) + " / " + (breadth.down || 0) + " / " + (breadth.flat || 0)) + "</span></div></div>";
    var comment = comp.analysis && comp.analysis.comment || "監視銘柄ベース。S&P500全体のBreadthとは別集計です。";
    var insights = "<div class=\"session-insights\"><h3>総合判定</h3><p class=\"comment\">" + esc(comment) + "</p></div>";
    return sessionShell("米国市場 プレマーケット分析", comp, (comp.freshness === "stale" ? warning(comp) : "") + kpis + insights + "<div class=\"panel-body split\">" + moverTable("上昇率TOP10", comp.topGainers, "up") + moverTable("下落率TOP10", comp.topLosers, "down") + "</div><div class=\"panel-body\">" + moverTable("出来高TOP10", comp.topVolume, "up") + futuresTable(comp) + "<div class=\"sector-mover-group\"><h3 class=\"mini-title\">セクター強弱（監視銘柄ベース）</h3>" + premarketSectorRows(comp) + "</div></div>");
  }

  function bridgeSection(japanPre, usPre, usInternal, pageStatus) {
    var jpText = japanPre.freshness === "fresh" ? japanPre.dataDate + " / " + (japanPre.summary && japanPre.summary.tone || "寄り前判定取得済み") : "東京寄り前データ取得不能";
    var usText = usPre.freshness === "fresh" ? usPre.dataDate + " / coverage " + (usPre.coverageRatio == null ? 0 : usPre.coverageRatio) + "%" : "米国プレマーケット取得不能";
    var closeText = usInternal.freshness === "fresh" ? usInternal.dataDate + " / 通常市場内部データ" : "米国通常市場内部データ取得不能";
    var conclusion = pageStatus === "ok" ? "東京寄り前・米国プレマーケット・通常市場内部が同時にfreshです。" : pageStatus === "degraded" ? "一部カードが更新待ちです。カード別の基準日とfreshnessを確認してください。" : "主要市場データが取得不能です。前回データを当日値として扱わないでください。";
    return "<section class=\"bridge\"><h2>日米市場の引き継ぎ分析</h2><div class=\"bridge-flow\"><div class=\"flow-step\"><b>東京市場</b><p>" + esc(jpText) + "</p></div><div class=\"flow-arrow\">→</div><div class=\"flow-step\"><b>米国プレマーケット</b><p>" + esc(usText) + "</p></div><div class=\"flow-arrow\">→</div><div class=\"flow-step\"><b>米国通常市場</b><p>" + esc(closeText) + "</p></div></div><p class=\"bridge-conclusion\">" + esc(conclusion) + "</p></section>";
  }

  function pageHead(pageStatus, freshCount, unavailableCount) {
    return "<section class=\"section-head\"><div><h2>時間軸で見る株式市場</h2></div><p>寄り付き → プレマーケット → 通常取引の流れを確認<br>ページ状態：" + esc(pageStatus) + " ／ 最新カード " + freshCount + "件 ／ 取得不能 " + unavailableCount + "件</p></section>";
  }

  function render(stocks, tokyo, uspre, moversJp, sectorPayload, breadthPayload, moversUs, contribUs, contribJp) {
    var dates = stocks.marketDates || {};
    var jpPre = normalize(tokyo, jstDate(), "東京市場 朝の寄り前分析", "JP");
    var usPre = normalize(uspre, nyDate(), "米国市場 プレマーケット分析", "US");
    var jpMovers = normalize(moversJp, dates.japan, "日本市場の大幅上昇・下落銘柄（東証プライム）", "JP");
    var usMovers = normalize(moversUs, dates.us, "米国市場の大幅上昇・下落銘柄（S&P500構成銘柄）", "US");
    var jpSectors = normalize(sectorPayload.markets && sectorPayload.markets.japan, dates.japan, "東京市場のセクター・業種", "JP");
    var usSectors = normalize(sectorPayload.markets && sectorPayload.markets.us, dates.us, "米国市場のセクター・業種", "US");
    var usBreadth = normalize(breadthPayload, dates.us, "米国市場内部 Breadth", "US");
    var usContrib = normalize(contribUs, dates.us, "米国市場（S&P500寄与度 推計・bp）", "US");
    var jpContribPayload = Object.keys(contribJp || {}).length ? contribJp : stocks.contributions && stocks.contributions.japan;
    var jpContrib = normalize(jpContribPayload, dates.japan, "日本市場（日経225寄与度 上位・下位）", "JP");
    var usInternal = normalize(stocks.marketInternals && stocks.marketInternals.us, dates.us, "米国市場の主要指数・市場内部", "US");
    var jpInternal = normalize(stocks.marketInternals && stocks.marketInternals.japan, dates.japan, "日本市場の主要指数・市場内部", "JP");
    var components = [jpPre, usPre, jpMovers, usMovers, jpSectors, usSectors, usBreadth, usContrib, jpContrib, usInternal, jpInternal];
    var freshCount = components.filter(function (item) { return item.freshness === "fresh"; }).length;
    var unavailableCount = components.filter(function (item) { return item.freshness === "unavailable"; }).length;
    var pageStatus = freshCount === 0 ? "unavailable" : (unavailableCount || components.some(function (item) { return item.freshness === "stale"; }) ? "degraded" : "ok");
    updated.textContent = "ページ状態：" + pageStatus + " / 各カードの鮮度を表示中";
    root.innerHTML = pageHead(pageStatus, freshCount, unavailableCount) +
      "<section class=\"session-grid\">" + preopen(jpPre) + premarket(usPre) + "</section>" +
      bridgeSection(jpPre, usPre, usInternal, pageStatus) +
      "<h2 class=\"subsection-label\">市場内部・値動き・需給</h2>" +
      "<section class=\"pair-grid\" aria-label=\"主要指数と市場内部\">" + market(usInternal) + market(jpInternal) + "</section>" +
      "<section class=\"pair-grid\" aria-label=\"大幅上昇・下落銘柄\">" + movers(usMovers) + movers(jpMovers) + "</section>" +
      "<section class=\"pair-grid\" aria-label=\"セクター・業種\">" + sectors(usSectors) + sectors(jpSectors) + "</section>" +
      "<section class=\"pair-grid\" aria-label=\"指数寄与度\">" + contributions(usContrib) + contributions(jpContrib) + "</section>" +
      judgement(stocks.judgement) + analyses(stocks.analysisCards) +
      "<p class=\"note\">" + esc(stocks.note || "データが存在しない項目は「取得不能」と表示します。") + "</p>";
  }

  var paths = [
    "data/stocks.json", "data/market/tokyo-preopen.json", "data/market/us-premarket.json",
    "data/market/japan-stock-movers.json", "data/market/sector-performance.json",
    "data/market/us-stock-breadth.json", "data/market/us-stock-movers.json",
    "data/market/sp500-contributions.json", "data/nikkei-contributions.json"
  ];
  var get = function (path) {
    return fetch(path + "?ts=" + Date.now(), {cache:"no-store"}).then(function (response) {
      return response.ok ? response.json() : null;
    }).catch(function () { return null; });
  };
  Promise.all(paths.map(get)).then(function (values) {
    if (!values[0]) throw new Error("data/stocks.jsonを取得できません");
    render(values[0], values[1] || {}, values[2] || {}, values[3] || {}, values[4] || {}, values[5] || {}, values[6] || {}, values[7] || {}, values[8] || {});
  }).catch(function (error) {
    updated.textContent = "ページ状態：unavailable";
    root.innerHTML = "<div class=\"empty\">株式市場分析を表示できません。理由：" + esc(error.message) + "</div>";
  });
})();

