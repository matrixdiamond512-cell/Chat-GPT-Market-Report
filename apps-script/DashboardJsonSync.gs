// Root-fix version: 2026-08-06 14:06 JST
var DASHBOARD_JSON_CONFIG = {
  targetPath: 'data/dashboard.json',
  reportsPath: 'reports.json',
  timezone: 'Asia/Tokyo',
  maxReports: 1,
  lastResultProperty: 'DASHBOARD_JSON_LAST_RESULT',
  priceSheetName: '終値一覧',
  priceSourceId: 'CLOSE_PRICE_SHEET',
  maxPriorCloseAgeDays: 4
};

function previewDashboardJson() {
  var reports = dashboardFetchReportsJson_();
  var json = buildDashboardJsonFromReports_(reports);
  var html = HtmlService.createHtmlOutput(
    '<pre style="white-space:pre-wrap;font-size:12px">' + dashboardEscapeHtml_(json) + '</pre>'
  ).setWidth(920).setHeight(700);
  SpreadsheetApp.getUi().showModalDialog(html, 'ダッシュボードJSONプレビュー');
  return JSON.parse(json);
}

function syncDashboardJsonToGitHub() {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var reports = dashboardFetchReportsJson_();
    var result = syncDashboardJsonToGitHubFromReports_(reports);
    var eventsLine = '';
    if (result.eventsStatus === 'ok') {
      eventsLine = '\n重要イベント: 反映済み';
    } else if (result.eventsStatus) {
      eventsLine = '\n重要イベント: ' + result.eventsStatus +
        (result.eventsError ? '\n理由: ' + result.eventsError : '');
    }
    dashboardAlert_(
      'ダッシュボードJSONをGitHubへ反映しました。\n' +
      '対象: ' + result.latestKey + '\n' +
      '件数: ' + result.reportCount + '\n' +
      'コミット: ' + result.commitSha + eventsLine
    );
    return result;
  } catch (error) {
    dashboardSaveResult_({ ok: false, error: error.message });
    dashboardAlert_('ダッシュボードJSONを反映できませんでした。\n' + error.message);
    throw error;
  } finally {
    lock.releaseLock();
  }
}

function syncDashboardJsonToGitHubFromReports_(reports) {
  var payload = dashboardBuildPayloadFromReports_(reports);
  var json = JSON.stringify(payload, null, 2) + '\n';
  var current = dashboardGetGitHubJsonFile_(DASHBOARD_JSON_CONFIG.targetPath);
  var result = dashboardPutGitHubJsonFile_(
    DASHBOARD_JSON_CONFIG.targetPath,
    json,
    current.sha,
    'Update dashboard JSON from market reports'
  );

  var eventsResult = null;
  if (typeof syncEventsJsonToGitHubFromReports_ === 'function') {
    try {
      eventsResult = syncEventsJsonToGitHubFromReports_(reports);
    } catch (eventError) {
      eventsResult = { ok: false, error: eventError.message };
      Logger.log('重要イベントJSONの自動反映に失敗: ' + eventError.message);
    }
  }

  return dashboardSaveResult_({
    ok: true,
    targetPath: DASHBOARD_JSON_CONFIG.targetPath,
    latestKey: payload.currentReportKey,
    reportCount: payload.reports.length,
    commitSha: result.commit.sha,
    eventsStatus: eventsResult ? (eventsResult.ok ? 'ok' : 'error') : 'not_installed',
    eventsTargetPath: eventsResult && eventsResult.targetPath ? eventsResult.targetPath : '',
    eventsCommitSha: eventsResult && eventsResult.commitSha ? eventsResult.commitSha : '',
    eventsError: eventsResult && eventsResult.error ? eventsResult.error : ''
  });
}

function buildDashboardJsonFromReports_(reports) {
  return JSON.stringify(dashboardBuildPayloadFromReports_(reports), null, 2) + '\n';
}

function dashboardBuildPayloadFromReports_(reports) {
  var sourceReports = dashboardNormalizeReports_(reports);
  if (!sourceReports.length) throw new Error('ダッシュボードに使えるマーケットレポートがありません。');

  // dashboard.json は最新レポートだけを保持する。
  // 過去レポート全文は reports.json をブラウザ側で結合して表示するため、
  // ここで120件分を複製・再加工しない。これによりGASの実行時間超過を防ぐ。
  var latestSource = sourceReports[0];
  var priceSource = dashboardFetchPriceSheetSource_(latestSource.date);
  var latest = dashboardPrepareReportForDashboard_(latestSource, priceSource, true);
  var generatedAt = dashboardIsoJst_(new Date());
  var latestKey = latest.date + ' ' + latest.time;
  return {
    schemaVersion: '1.1.0',
    pageId: 'dashboard',
    generatedAt: generatedAt,
    publishedAt: generatedAt,
    dataAsOf: latest.date + 'T' + latest.time + ':00+09:00',
    status: 'ok',
    isStale: dashboardIsStale_(latest.date),
    staleReason: dashboardIsStale_(latest.date) ? '最新レポートの日付が現在日から3日以上離れています。' : '',
    currentReportKey: latestKey,
    sources: dashboardBuildDashboardSources_(latestKey, priceSource),
    errors: dashboardBuildDashboardErrors_(priceSource),
    latestReport: latest,
    reports: [latest]
  };
}

function dashboardBuildDashboardSources_(latestKey, priceSource) {
  return [
    {
      id: 'MARKET_REPORTS_JSON',
      name: 'マーケットレポート本文の構造化JSON',
      path: DASHBOARD_JSON_CONFIG.reportsPath,
      asOf: latestKey,
      status: 'ok',
      note: 'Google Docsのマーケットレポート本文をGASで構造化したデータ。日中レポートの価格は本文を優先します。'
    },
    {
      id: DASHBOARD_JSON_CONFIG.priceSourceId,
      name: 'スプレッドシート価格データ',
      sheetName: DASHBOARD_JSON_CONFIG.priceSheetName,
      asOf: priceSource && priceSource.asOf ? priceSource.asOf : '',
      status: priceSource && priceSource.status ? priceSource.status : 'unavailable',
      note: '終値一覧は日付一致時、または07:00・土曜09:00の直近営業日終値としてのみ利用します。'
    }
  ];
}

function dashboardBuildDashboardErrors_(priceSource) {
  if (!priceSource || priceSource.status === 'ok' || priceSource.status === 'unavailable') return [];
  return ['終値一覧の価格データを反映できませんでした: ' +
    (priceSource.error || priceSource.status)];
}

function dashboardFetchReportsJson_() {
  var current = dashboardGetGitHubJsonFile_(DASHBOARD_JSON_CONFIG.reportsPath);
  return dashboardNormalizeReports_(current.data);
}

function dashboardNormalizeReports_(reports) {
  var list = [];
  if (Array.isArray(reports)) list = reports;
  else if (reports && Array.isArray(reports.reports)) list = reports.reports;
  else if (reports && reports.latestReport) list = [reports.latestReport];

  return list.filter(function(report) {
    return report &&
      /^\d{4}-\d{2}-\d{2}$/.test(String(report.date || '')) &&
      /^\d{2}:\d{2}$/.test(String(report.time || ''));
  }).sort(function(a, b) {
    return (b.date + ' ' + b.time).localeCompare(a.date + ' ' + a.time);
  });
}

function dashboardPrepareReportForDashboard_(report, priceSource, useLatestPriceFallback) {
  var prepared = dashboardClonePlainObject_(report);
  var metricLines = dashboardCollectMarketMetricLines_(report);
  var reparsedMarkets = [];

  if (typeof parseMarketsLenient_ === 'function' && prepared.fullText) {
    try {
      reparsedMarkets = parseMarketsLenient_(prepared.fullText);
    } catch (error) {
      reparsedMarkets = [];
    }
  }

  var markets = dashboardMarketsByName_(reparsedMarkets.length ? reparsedMarkets : prepared.markets);
  prepared.markets = dashboardMarketDefinitions_().map(function(definition) {
    var original = markets[definition.name] || { name: definition.name };
    var metricLine = dashboardFirst_(metricLines[definition.name]);
    var originalPrice = dashboardCleanPriceField_(original.price, definition, 180);
    var outlook = dashboardCleanOutlookField_(original.outlook, 240);

    return {
      name: definition.name,
      direction: dashboardCleanDirection_(original.direction),
      price: metricLine || originalPrice,
      change: dashboardCleanMarketField_(original.change, definition, 80, false),
      outlook: outlook,
      material: dashboardCleanMarketField_(original.material, definition, 180, true) || outlook || '本文参照',
      positioning: dashboardCleanMarketField_(original.positioning, definition, 220, true),
      levels: dashboardCleanMarketField_(original.levels, definition, 180, true),
      mainScenario: dashboardCleanMarketField_(original.mainScenario, definition, 240, true) || outlook,
      alternativeScenario: dashboardCleanMarketField_(original.alternativeScenario, definition, 240, true),
      breakCondition: dashboardCleanMarketField_(original.breakCondition, definition, 240, true),
      risk: dashboardCleanMarketField_(original.risk, definition, 180, true)
    };
  });

  dashboardApplyPriceSheetMetrics_(prepared, priceSource, !!useLatestPriceFallback);
  return prepared;
}

function dashboardFetchPriceSheetSource_(reportDate) {
  var source = {
    id: DASHBOARD_JSON_CONFIG.priceSourceId,
    sheetName: DASHBOARD_JSON_CONFIG.priceSheetName,
    status: 'unavailable',
    asOf: '',
    byDate: {},
    latest: null,
    error: ''
  };

  try {
    if (typeof SpreadsheetApp === 'undefined') return source;
    var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    if (!spreadsheet) {
      source.status = 'missing';
      source.error = 'アクティブなスプレッドシートを取得できません。';
      return source;
    }

    var sheet = spreadsheet.getSheetByName(DASHBOARD_JSON_CONFIG.priceSheetName);
    if (!sheet) {
      source.status = 'missing';
      source.error = 'シート「' + DASHBOARD_JSON_CONFIG.priceSheetName + '」が見つかりません。';
      return source;
    }

    var lastRow = sheet.getLastRow();
    var lastColumn = sheet.getLastColumn();
    if (lastRow < 2 || lastColumn < 1) {
      source.status = 'empty';
      source.error = '終値一覧にデータ行がありません。';
      return source;
    }

    // 全シートを一括取得せず、ヘッダー・日付列・必要な行だけ読む。
    var headers = sheet.getRange(1, 1, 1, lastColumn).getDisplayValues()[0] || [];
    var index = dashboardHeaderIndex_(headers);
    if (!Object.prototype.hasOwnProperty.call(index, '日付')) {
      source.status = 'error';
      source.error = '終値一覧に日付列が見つかりません。';
      return source;
    }

    var dateColumn = index['日付'] + 1;
    var dateValues = sheet.getRange(2, dateColumn, lastRow - 1, 1).getDisplayValues();
    var latestDate = '';
    var latestRowNumber = 0;
    var reportRowNumber = 0;

    // 同一日付が複数ある場合は、下側の行を優先する。
    for (var offset = dateValues.length - 1; offset >= 0; offset -= 1) {
      var date = dashboardNormalizeDateKey_(dateValues[offset][0]);
      if (!date) continue;
      var rowNumber = offset + 2;

      if (!reportRowNumber && date === reportDate) reportRowNumber = rowNumber;
      if (!latestDate || date > latestDate) {
        latestDate = date;
        latestRowNumber = rowNumber;
      }
    }

    if (!latestDate || !latestRowNumber) {
      source.status = 'empty';
      source.error = '終値一覧から有効な日付を取得できませんでした。';
      return source;
    }

    if (reportRowNumber) {
      var reportMetricRow = dashboardReadMetricRowAtSheetRow_(
        sheet,
        reportRowNumber,
        lastColumn,
        index,
        reportDate
      );
      if (Object.keys(reportMetricRow.markets).length) source.byDate[reportDate] = reportMetricRow;
    }

    if (latestDate === reportDate && source.byDate[reportDate]) {
      source.latest = source.byDate[reportDate];
    } else {
      var latestMetricRow = dashboardReadMetricRowAtSheetRow_(
        sheet,
        latestRowNumber,
        lastColumn,
        index,
        latestDate
      );
      if (Object.keys(latestMetricRow.markets).length) source.latest = latestMetricRow;
    }

    if (!source.latest && source.byDate[reportDate]) source.latest = source.byDate[reportDate];
    if (!source.latest) {
      source.status = 'empty';
      source.error = '終値一覧の最新日付行から市場価格データを作成できませんでした。';
      return source;
    }

    source.status = 'ok';
    source.asOf = source.latest.date;
    return source;
  } catch (error) {
    source.status = 'error';
    source.error = error.message;
    return source;
  }
}

function dashboardReadMetricRowAtSheetRow_(sheet, rowNumber, lastColumn, index, date) {
  var row = sheet.getRange(rowNumber, 1, 1, lastColumn).getDisplayValues()[0] || [];
  return dashboardBuildPriceMetricRow_(date, row, index);
}

function dashboardHeaderIndex_(headers) {
  var index = {};
  (headers || []).forEach(function(header, columnIndex) {
    var key = dashboardNormalizeInlineText_(header);
    if (key && !Object.prototype.hasOwnProperty.call(index, key)) index[key] = columnIndex;
  });
  return index;
}

function dashboardNormalizeDateKey_(value) {
  var text = String(value || '').trim();
  if (!text) return '';

  var match = text.match(/(\d{4})[\/.\-年](\d{1,2})[\/.\-月](\d{1,2})/);
  if (!match) return '';

  var year = Number(match[1]);
  var month = Number(match[2]);
  var day = Number(match[3]);
  if (year < 2000 || year > 2100 || month < 1 || month > 12 || day < 1 || day > 31) return '';

  var checked = new Date(Date.UTC(year, month - 1, day));
  if (checked.getUTCFullYear() !== year || checked.getUTCMonth() !== month - 1 || checked.getUTCDate() !== day) return '';

  return year + '-' + ('0' + month).slice(-2) + '-' + ('0' + day).slice(-2);
}

function dashboardBuildPriceMetricRow_(date, row, index) {
  var markets = {};

  dashboardAddPriceMetric_(markets, '金', '金（XAU/USD）',
    dashboardReadSheetValue_(row, index, 'ゴールド終値'),
    dashboardReadSheetValue_(row, index, 'ゴールド前日比'),
    dashboardReadSheetValue_(row, index, 'ゴールド騰落率'), 'ドル');

  dashboardAddPriceMetric_(markets, '原油', 'WTI原油',
    dashboardReadSheetValue_(row, index, 'WTI原油終値'),
    dashboardReadSheetValue_(row, index, 'WTI原油前日比'),
    dashboardReadSheetValue_(row, index, 'WTI原油騰落率'), 'ドル');

  dashboardAddPriceMetric_(markets, '日経225先物', '日経225先物（大阪取引所）',
    dashboardReadSheetValue_(row, index, '日経225先物大阪終値'),
    dashboardReadSheetValue_(row, index, '日経225先物大阪前日比'),
    dashboardReadSheetValue_(row, index, '日経225先物大阪騰落率'), '円');

  dashboardAddPriceMetric_(markets, 'USD/JPY', 'USD/JPY',
    dashboardChooseFirstSheetValue_(row, index, ['USDJPY終値（Investing.com）', 'USDJPY終値']),
    dashboardReadSheetValue_(row, index, 'USDJPY前日比'),
    dashboardReadSheetValue_(row, index, 'USDJPY騰落率'), '円');

  dashboardAddPriceMetric_(markets, 'EUR/USD', 'EUR/USD',
    dashboardReadSheetValue_(row, index, 'EURUSD終値'),
    dashboardReadSheetValue_(row, index, 'EURUSD前日比'),
    dashboardReadSheetValue_(row, index, 'EURUSD騰落率'), '');

  dashboardAddPriceMetric_(markets, 'BTCUSD', 'BTCUSD',
    dashboardReadSheetValue_(row, index, 'BTCUSD終値'),
    dashboardReadSheetValue_(row, index, 'BTCUSD前日比'),
    dashboardReadSheetValue_(row, index, 'BTCUSD騰落率'), 'ドル');

  return { date: date, markets: markets };
}

function dashboardAddPriceMetric_(markets, marketName, label, close, change, pct, unit) {
  close = dashboardCleanSheetValue_(close);
  if (!close) return;

  var changePair = dashboardFormatSignedPair_(change, pct, close);
  markets[marketName] = {
    price: label + '：' + close + unit + (changePair ? '（' + changePair + '）' : ''),
    change: changePair
  };
}

function dashboardReadSheetValue_(row, index, header) {
  if (!Object.prototype.hasOwnProperty.call(index, header)) return '';
  return dashboardCleanSheetValue_(row[index[header]]);
}

function dashboardChooseFirstSheetValue_(row, index, headers) {
  for (var i = 0; i < headers.length; i += 1) {
    var value = dashboardReadSheetValue_(row, index, headers[i]);
    if (value) return value;
  }
  return '';
}

function dashboardApplyPriceSheetMetrics_(prepared, priceSource, useLatestPriceFallback) {
  if (!priceSource || priceSource.status !== 'ok') return;

  var exactRow = priceSource.byDate[prepared.date];
  var priceRow = exactRow || null;
  var matchType = exactRow ? 'date' : '';

  if (!priceRow && useLatestPriceFallback && dashboardCanUsePriorCloseFallback_(prepared, priceSource.latest)) {
    priceRow = priceSource.latest;
    matchType = 'prior_close';
  }

  if (!priceRow || !priceRow.markets) return;

  var markets = dashboardMarketsByName_(prepared.markets);
  dashboardMarketDefinitions_().forEach(function(definition) {
    var market = markets[definition.name];
    var metric = priceRow.markets[definition.name];
    if (!market || !metric || !metric.price) return;

    market.price = metric.price;
    market.change = metric.change || market.change;
    market.priceSource = {
      id: DASHBOARD_JSON_CONFIG.priceSourceId,
      sheetName: priceSource.sheetName,
      asOf: priceRow.date,
      match: matchType
    };
  });

  prepared.marketDataAsOf = priceRow.date;
  prepared.marketDataSource = priceSource.sheetName;
}

function dashboardCanUsePriorCloseFallback_(prepared, priceRow) {
  if (!prepared || !priceRow || !priceRow.date) return false;
  var reportTime = String(prepared.time || '');
  if (reportTime !== '07:00' && reportTime !== '09:00') return false;

  var gapDays = dashboardDateDistanceDays_(prepared.date, priceRow.date);
  return gapDays >= 1 && gapDays <= DASHBOARD_JSON_CONFIG.maxPriorCloseAgeDays;
}

function dashboardDateDistanceDays_(laterDate, earlierDate) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(laterDate || ''))) return NaN;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(earlierDate || ''))) return NaN;

  var later = new Date(String(laterDate) + 'T00:00:00+09:00');
  var earlier = new Date(String(earlierDate) + 'T00:00:00+09:00');
  if (isNaN(later.getTime()) || isNaN(earlier.getTime())) return NaN;
  return Math.round((later.getTime() - earlier.getTime()) / 86400000);
}

function dashboardFormatSignedPair_(change, pct, close) {
  var values = [];
  var cleanChange = dashboardCleanSheetValue_(change);
  var cleanPct = dashboardNormalizePercentText_(pct, close, change);
  if (cleanChange) values.push(cleanChange);
  if (cleanPct) values.push(cleanPct);
  return values.join('、');
}

function dashboardNormalizePercentText_(value, close, change) {
  var providedText = dashboardCleanSheetValue_(value);
  var closeNumber = dashboardParseSheetNumber_(close);
  var changeNumber = dashboardParseSheetNumber_(change);
  var normalizedNumber = NaN;

  if (isFinite(closeNumber) && isFinite(changeNumber)) {
    var previousClose = closeNumber - changeNumber;
    if (previousClose !== 0) normalizedNumber = changeNumber / previousClose * 100;
  }

  if (!isFinite(normalizedNumber) && providedText) {
    normalizedNumber = dashboardParseSheetNumber_(providedText);
  }

  if (!isFinite(normalizedNumber) || Math.abs(normalizedNumber) > 1000) return '';
  return dashboardFormatPercentNumber_(normalizedNumber);
}

function dashboardParseSheetNumber_(value) {
  var source = dashboardNormalizeInlineText_(value);
  if (!source) return NaN;
  var negativeTriangle = /^▲/.test(source);
  var cleaned = source
    .replace(/[，,\s]/g, '')
    .replace(/[−–—]/g, '-')
    .replace(/[^0-9.+-]/g, '');

  if (!cleaned || cleaned === '+' || cleaned === '-' || cleaned === '.') return NaN;
  var number = Number(cleaned);
  if (!isFinite(number)) return NaN;
  return negativeTriangle ? -Math.abs(number) : number;
}

function dashboardFormatPercentNumber_(value) {
  var rounded = Math.round(value * 100) / 100;
  return (rounded > 0 ? '+' : '') + rounded.toFixed(2) + '％';
}

function dashboardCleanSheetValue_(value) {
  var textValue = dashboardNormalizeInlineText_(value);
  if (!textValue) return '';
  if (/^(?:-|--|―|N\/A|NA|null|undefined)$/i.test(textValue)) return '';
  if (/^#/.test(textValue)) return '';
  if (/休場|取得不能|該当なし/.test(textValue)) return '';
  return textValue;
}

function dashboardClonePlainObject_(value) {
  return JSON.parse(JSON.stringify(value || {}));
}

function dashboardMarketsByName_(markets) {
  var result = {};
  (Array.isArray(markets) ? markets : []).forEach(function(market) {
    if (market && market.name) result[String(market.name)] = market;
  });
  return result;
}

function dashboardMarketDefinitions_() {
  return [
    { name: '金', metricLabelRegex: '(?:金現物|金価格|金（XAU\\/USD）|ゴールド|金)', mentionRegex: /金[:：]|金現物|金価格|金は|金の|ゴールド|XAU\/USD/ },
    { name: '原油', metricLabelRegex: '(?:WTI原油|原油（WTI）|原油)', mentionRegex: /WTI|原油/ },
    { name: '日経225先物', metricLabelRegex: '(?:日経225先物[^：:\n]{0,24})', mentionRegex: /日経225|日本株|東京市場/ },
    { name: 'USD/JPY', metricLabelRegex: '(?:USD\\/JPY|ドル円)', mentionRegex: /USD\/JPY|ドル円|円相場|円ショート|ドル買い|円買い/ },
    { name: 'EUR/USD', metricLabelRegex: '(?:EUR\\/USD|ユーロドル)', mentionRegex: /EUR\/USD|ユーロドル|ユーロ/ },
    { name: 'BTCUSD', metricLabelRegex: '(?:BTCUSD|BTC\\/USD|BTC|ビットコイン)', mentionRegex: /BTCUSD|BTC\/USD|BTC|ビットコイン|暗号資産/ }
  ];
}

function dashboardCollectMarketMetricLines_(report) {
  var result = {};
  var definitions = dashboardMarketDefinitions_();
  definitions.forEach(function(definition) { result[definition.name] = []; });

  dashboardCollectTextCandidates_(report).forEach(function(candidate) {
    definitions.forEach(function(definition) {
      var line = dashboardMetricLineFromText_(candidate, definition);
      if (line && result[definition.name].indexOf(line) === -1) result[definition.name].push(line);
    });
  });
  return result;
}

function dashboardCollectTextCandidates_(report) {
  var values = [
    report.fullText,
    report.theme,
    report.leadingMarket,
    report.mainScenario,
    report.alternativeScenario,
    report.breakConditions
  ];

  [report.changes, report.consistency, report.positioning, report.news,
    report.crossAssetFlow, report.handover, report.events, report.riskManagement]
    .forEach(function(items) {
      (Array.isArray(items) ? items : []).forEach(function(item) {
        values.push(dashboardTextOf_(item));
      });
    });

  (Array.isArray(report.markets) ? report.markets : []).forEach(function(market) {
    ['direction', 'price', 'change', 'outlook', 'material', 'positioning', 'levels',
      'mainScenario', 'alternativeScenario', 'breakCondition', 'risk']
      .forEach(function(key) { values.push(market && market[key]); });
  });

  return values.map(dashboardNormalizeInlineText_).filter(Boolean);
}

function dashboardTextOf_(value) {
  if (typeof value === 'string') return value;
  if (!value) return '';
  return value.text || value.summary || value.title || '';
}

function dashboardMetricLineFromText_(value, definition) {
  var input = dashboardNormalizeInlineText_(value);
  if (!input) return '';

  var pattern = new RegExp(
    '(' + definition.metricLabelRegex + '\\s*[：:]\\s*[\\s\\S]*?)' +
    '(?=\\s*(?:' + dashboardAllMetricLabelRegex_() + ')\\s*[：:]|。|$)',
    'i'
  );
  var match = input.match(pattern);
  if (!match) return '';

  var line = dashboardTrimMetricLineTail_(dashboardNormalizeInlineText_(match[1]));
  if (!dashboardIsUsableMetricLine_(line, definition)) return '';
  return dashboardTrimText_(line, 180);
}

function dashboardTrimMetricLineTail_(line) {
  return dashboardNormalizeInlineText_(line).replace(
    /\s(?:日経VI|東証プライム|東証|騰落レシオ|日経225現物終値|米10年|日本10年|VIX|NYダウ|S&P500|Nasdaq|Russell)[^：:]{0,30}[：:][\s\S]*$/i,
    ''
  );
}

function dashboardAllMetricLabelRegex_() {
  return '(?:金現物|金価格|金（XAU\\/USD）|ゴールド|WTI原油|原油（WTI）|原油|日経225先物[^：:\\n]{0,24}|USD\\/JPY|ドル円|EUR\\/USD|ユーロドル|BTCUSD|BTC\\/USD|BTC|ビットコイン)';
}

function dashboardIsUsableMetricLine_(line, definition) {
  if (!line || dashboardStartsWithOtherMetricLabel_(line, definition)) return false;
  if (!definition.mentionRegex.test(line)) return false;
  var valuePart = line.replace(/^[^：:]+[：:]\s*/, '');
  if (!/[0-9]/.test(valuePart) && valuePart.indexOf('取得不能') === -1) return false;
  if (/VIX/.test(line) && definition.name !== 'BTCUSD') return false;
  return true;
}

function dashboardCleanDirection_(value) {
  var output = dashboardNormalizeInlineText_(value);
  if (!output || output.length > 40) return '中立・方向確認';
  if (/上昇|強|買い|流入|下落|弱|売り|流出|中立|横ばい|もみ合い|方向確認|警戒|上向き|下向き/.test(output)) return output;
  return '中立・方向確認';
}

function dashboardCleanPriceField_(value, definition, maxLength) {
  var output = dashboardNormalizeInlineText_(value);
  if (!output || output.length > maxLength) return '';
  if (/^(本文参照|個別記載なし|記載なし)$/.test(output)) return '';
  if (dashboardStartsWithOtherMetricLabel_(output, definition)) return '';
  return dashboardTrimText_(output, maxLength);
}

function dashboardCleanMarketField_(value, definition, maxLength, requireMention) {
  var output = dashboardNormalizeInlineText_(value);
  if (!output || output.length > maxLength) return '';
  if (output.indexOf('取得不能') !== -1) return '';
  if (/^(本文参照|個別記載なし|個別見通し参照|記載なし)$/.test(output)) return '';
  if (/^対象\s*[：:]/.test(output)) return '';
  if (/マーケットレポート｜|復旧日時|Google Docsファイル名|TSV|ヘッダーなし/.test(output)) return '';
  if (dashboardStartsWithOtherMetricLabel_(output, definition)) return '';
  if (requireMention && !definition.mentionRegex.test(output)) return '';
  if (/VIX/.test(output) && definition.name !== 'BTCUSD') return '';
  return dashboardTrimText_(output, maxLength);
}

function dashboardCleanOutlookField_(value, maxLength) {
  var output = dashboardNormalizeInlineText_(value);
  if (!output || output.length > maxLength) return '';
  if (/^(本文参照|個別記載なし|個別見通し参照|記載なし)$/.test(output)) return '';
  if (/^対象\s*[：:]/.test(output)) return '';
  if (/マーケットレポート｜|復旧日時|Google Docsファイル名|TSV|ヘッダーなし/.test(output)) return '';
  return dashboardTrimText_(output, maxLength);
}

function dashboardStartsWithOtherMetricLabel_(value, definition) {
  var output = dashboardNormalizeInlineText_(value);
  var definitions = dashboardMarketDefinitions_();
  for (var i = 0; i < definitions.length; i += 1) {
    var other = definitions[i];
    if (other.name === definition.name) continue;
    if (new RegExp('^\\s*' + other.metricLabelRegex + '\\s*[：:]', 'i').test(output)) return true;
  }
  return false;
}

function dashboardNormalizeInlineText_(value) {
  return String(value || '')
    .replace(/\r\n?/g, '\n')
    .replace(/\u00a0/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/^[・\s]+/, '')
    .trim();
}

function dashboardTrimText_(value, maxLength) {
  var output = dashboardNormalizeInlineText_(value);
  if (!output || output.length <= maxLength) return output;
  return output.slice(0, maxLength - 3) + '...';
}

function dashboardFirst_(values) {
  return values && values.length ? values[0] : '';
}

function dashboardIsStale_(dateText) {
  var todayText = Utilities.formatDate(new Date(), DASHBOARD_JSON_CONFIG.timezone, 'yyyy-MM-dd');
  var today = dashboardDateOnly_(todayText);
  var reportDate = dashboardDateOnly_(dateText);
  if (!today || !reportDate) return true;
  return (today.getTime() - reportDate.getTime()) / 86400000 >= 3;
}

function dashboardDateOnly_(dateText) {
  var match = String(dateText || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

function dashboardGetGitHubJsonFile_(path) {
  var config = dashboardGithubConfig_();
  var response = UrlFetchApp.fetch(
    dashboardGithubContentsUrl_(config, path) + '?ref=' + encodeURIComponent(config.branch),
    { method: 'get', headers: dashboardGithubHeaders_(config.token), muteHttpExceptions: true }
  );
  var code = response.getResponseCode();
  if (code === 404) return { data: [], sha: null };
  if (code !== 200) throw new Error('GitHubファイル取得失敗: HTTP ' + code + ' ' + response.getContentText());

  var payload = JSON.parse(response.getContentText());
  return {
    data: JSON.parse(Utilities.newBlob(Utilities.base64Decode(payload.content.replace(/\n/g, ''))).getDataAsString('UTF-8')),
    sha: payload.sha
  };
}

function dashboardPutGitHubJsonFile_(path, content, sha, message) {
  var config = dashboardGithubConfig_();
  var body = {
    message: message,
    content: Utilities.base64Encode(content, Utilities.Charset.UTF_8),
    branch: config.branch
  };
  if (sha) body.sha = sha;

  var response = UrlFetchApp.fetch(dashboardGithubContentsUrl_(config, path), {
    method: 'put',
    contentType: 'application/json',
    headers: dashboardGithubHeaders_(config.token),
    payload: JSON.stringify(body),
    muteHttpExceptions: true
  });
  var code = response.getResponseCode();
  if (code !== 200 && code !== 201) {
    throw new Error('GitHub更新失敗: HTTP ' + code + ' ' + response.getContentText());
  }
  return JSON.parse(response.getContentText());
}

function dashboardGithubConfig_() {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('スクリプトプロパティ GITHUB_TOKEN が未設定です。');
  return {
    token: token,
    owner: props.getProperty('GITHUB_OWNER') ||
      (typeof WEB_REPORT_CONFIG !== 'undefined' ? WEB_REPORT_CONFIG.owner : 'matrixdiamond512-cell'),
    repo: props.getProperty('GITHUB_REPO') ||
      (typeof WEB_REPORT_CONFIG !== 'undefined' ? WEB_REPORT_CONFIG.repo : 'Chat-GPT-Market-Report'),
    branch: props.getProperty('GITHUB_BRANCH') ||
      (typeof WEB_REPORT_CONFIG !== 'undefined' ? WEB_REPORT_CONFIG.branch : 'main')
  };
}

function dashboardGithubContentsUrl_(config, path) {
  return 'https://api.github.com/repos/' + config.owner + '/' + config.repo + '/contents/' + path;
}

function dashboardGithubHeaders_(token) {
  return {
    Authorization: 'Bearer ' + token,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };
}

function dashboardIsoJst_(date) {
  return Utilities.formatDate(date, DASHBOARD_JSON_CONFIG.timezone, "yyyy-MM-dd'T'HH:mm:ss'+09:00'");
}

function dashboardSaveResult_(result) {
  var payload = Object.assign({
    executedAt: Utilities.formatDate(new Date(), DASHBOARD_JSON_CONFIG.timezone, 'yyyy-MM-dd HH:mm:ss')
  }, result);
  PropertiesService.getScriptProperties().setProperty(
    DASHBOARD_JSON_CONFIG.lastResultProperty,
    JSON.stringify(payload)
  );
  return payload;
}

function dashboardEscapeHtml_(textValue) {
  return String(textValue)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function dashboardAlert_(message) {
  try {
    SpreadsheetApp.getUi().alert(message);
  } catch (error) {
    Logger.log(message);
  }
}
