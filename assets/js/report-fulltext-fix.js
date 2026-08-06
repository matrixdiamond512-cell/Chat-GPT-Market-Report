/* Market-data table parser hardening. Loaded after report-fulltext.js. */
parseMarketLine = function parseMarketLineSafely(line) {
  const compact = String(line || "").trim().replace(/^[-・]\s*/, "");
  const separatorIndex = compact.search(/[：:]/);
  if (separatorIndex <= 0 || separatorIndex > 60) return null;

  const label = compact.slice(0, separatorIndex).trim();
  const body = compact.slice(separatorIndex + 1).trim();
  if (!label || !body) return null;
  if (/^(作成時点|作成日時|対象|注記|注意|出典|補足|参考|理由)$/.test(label)) return null;
  if (/[。！？!?]/.test(label)) return null;

  const recognized = /^(?:Dow|NYダウ|ダウ|Nasdaq(?:総合)?|NASDAQ(?:総合)?|S&P\s*500|日経225(?:現物|先物.*)?|日経平均.*|CME日経225先物.*|日経先物.*|USD\/JPY|USDJPY|ドル円|EUR\/USD|EURUSD|ユーロドル|金.*|ゴールド|WTI原油|原油.*|BTCUSD|BTC\/USD|Bitcoin|ビットコイン|VIX.*|日経VI|米.*債.*|日本.*国債.*|Fear\s*&\s*Greed.*|Crypto\s+Fear\s*&\s*Greed.*|日経225.*(?:EPS|PER|PBR)|PER|PBR|EPS|25日.*乖離率|200日.*乖離率|値上がり銘柄数|値下がり銘柄数|騰落レシオ|東証プライム.*)$/i.test(label);

  if (!recognized && label.length > 30) return null;

  const firstStop = body.indexOf("。");
  const valueStatus = firstStop >= 0 ? body.slice(0, firstStop).trim() : body;
  const note = firstStop >= 0 ? body.slice(firstStop + 1).trim() : "";
  return { label, valueStatus, note };
};

(() => {
  "use strict";
  let attempts = 0;
  const timer = window.setInterval(() => {
    attempts += 1;
    const list = typeof reports !== "undefined" && Array.isArray(reports) ? reports : [];
    if (!list.length || typeof selectReport !== "function") {
      if (attempts >= 40) window.clearInterval(timer);
      return;
    }

    const latest = [...list]
      .filter((item) => item && item.date && item.time)
      .sort((a, b) => `${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`))[0];
    if (!latest) {
      window.clearInterval(timer);
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const requestedDate = params.get("date");
    const requestedTime = params.get("time");
    const current = typeof selectedReport !== "undefined" ? selectedReport : null;
    const staleCurrentDaySelection = requestedDate === latest.date
      && requestedTime
      && `${requestedDate} ${requestedTime}` < `${latest.date} ${latest.time}`;
    const defaultOpenedOnOlderReport = !requestedDate
      && current
      && `${current.date} ${current.time || ""}` < `${latest.date} ${latest.time}`;

    if (staleCurrentDaySelection || defaultOpenedOnOlderReport) {
      selectReport(latest.date, latest.time);
    }
    window.clearInterval(timer);
  }, 100);
})();
