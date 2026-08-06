var STOCK_ANALYSIS_FRESHNESS_CONFIG = {
  timezone: 'Asia/Tokyo',
  maxDataAgeDays: 4,
  maxFutureDays: 1,
  triggerHours: [7, 12, 16, 21],
  triggerMinute: 40,
  handler: 'updateStockAnalysisPageSafelyScheduled',
  lastResultProperty: 'STOCK_ANALYSIS_SAFE_UPDATE_LAST_RESULT'
};

var STOCK_BREADTH_ROOT_FIX_CONFIG = {
  headerScanRows: 12,
  maximumLookbackDays: 10,
  dateHeaders: ['日付', '年月日', '基準日', '取引日', '営業日', 'date'],
  advancerHeaders: ['東証プライム値上がり銘柄数', 'プライム値上がり銘柄数', '値上がり銘柄数', '値上がり'],
  declinerHeaders: ['東証プライム値下がり銘柄数', 'プライム値下がり銘柄数', '値下がり銘柄数', '値下がり'],
  ratioHeaders: ['騰落レシオ', '騰落レシオ（25日）', '25日騰落レシオ']
};

function updateStockAnalysisPageSafelyForMaster_() {
  if (
    typeof stockAnalysisBuildPayloadFromSheet_ !== 'function' ||
    typeof stockAnalysisGetGitHubJsonFile_ !== 'function' ||
    typeof stockAnalysisPutGitHubJsonFile_ !== 'function'
  ) {
    return stockAnalysisSaveStandaloneResult_({
      ok: true,
      skipped: true,
      reason: '株式市場分析の基礎関数が未導入のため更新をスキップしました。'
    });
  }
  try {
    var payload = stockAnalysisBuildFreshPayload_();
    var freshness = stockAnalysisCheckFreshness_(payload);
    if (!freshness.ok) {
      return stockAnalysisSaveStandaloneResult_({
        ok: true,
        skipped: true,
        reason: freshness.reason,
        dataAsOf: freshness.dataAsOf || '',
        dataAgeDays: freshness.dataAgeDays,
        targetPath: typeof STOCK_ANALYSIS_JSON_CONFIG !== 'undefined' ? STOCK_ANALYSIS_JSON_CONFIG.targetPath : 'data/stocks.json'
      });
    }
    var targetPath = STOCK_ANALYSIS_JSON_CONFIG.targetPath;
    var json = JSON.stringify(payload, null, 2) + '\n';
    var current = stockAnalysisGetGitHubJsonFile_(targetPath);
    var result = stockAnalysisPutGitHubJsonFile_(
      targetPath,
      json,
      current.sha,
      'Update stock analysis JSON from verified latest Google Sheets row'
    );
    return stockAnalysisSaveStandaloneResult_({
      ok: true,
      skipped: false,
      targetPath: targetPath,
      updatedAt: payload.updatedAt || '',
      dataAsOf: payload.dataAsOf || '',
      dataAgeDays: freshness.dataAgeDays,
      breadthSourceSheet: payload.breadthValidation ? payload.breadthValidation.sheetName : '',
      breadthSourceRow: payload.breadthValidation ? payload.breadthValidation.rowNumber : null,
      commitSha: result.commit.sha,
      pagesUrl: STOCK_ANALYSIS_JSON_CONFIG.pagesUrl
    });
  } catch (error) {
    return stockAnalysisSaveStandaloneResult_({
      ok: false,
      skipped: false,
      error: error.message,
      reason: '株式市場分析の安全更新に失敗しました。'
    });
  }
}

function stockAnalysisBuildFreshPayload_() {
  var payload = stockAnalysisBuildPayloadFromSheet_();
  var breadth = stockAnalysisFindLatestBreadthRow_();
  if (!breadth) return payload;

  stockAnalysisApplyLatestBreadth_(payload, breadth);
  return payload;
}

function stockAnalysisFindLatestBreadthRow_() {
  var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  var sheets = spreadsheet.getSheets();
  var todayKey = Utilities.formatDate(new Date(), STOCK_ANALYSIS_FRESHNESS_CONFIG.timezone, 'yyyy-MM-dd');
  var candidates = [];

  sheets.forEach(function(sheet) {
    var range = sheet.getDataRange();
    if (!range || range.getNumRows() < 2 || range.getNumColumns() < 3) return;

    var values = range.getValues();
    var displays = range.getDisplayValues();
    var maxHeaderRow = Math.min(STOCK_BREADTH_ROOT_FIX_CONFIG.headerScanRows, values.length);

    for (var headerIndex = 0; headerIndex < maxHeaderRow; headerIndex += 1) {
      var headers = displays[headerIndex].map(stockAnalysisNormalizeHeader_);
      var dateColumn = stockAnalysisFindHeaderColumn_(headers, STOCK_BREADTH_ROOT_FIX_CONFIG.dateHeaders);
      var advancerColumn = stockAnalysisFindHeaderColumn_(headers, STOCK_BREADTH_ROOT_FIX_CONFIG.advancerHeaders);
      var declinerColumn = stockAnalysisFindHeaderColumn_(headers, STOCK_BREADTH_ROOT_FIX_CONFIG.declinerHeaders);
      var ratioColumn = stockAnalysisFindHeaderColumn_(headers, STOCK_BREADTH_ROOT_FIX_CONFIG.ratioHeaders);

      if (dateColumn < 0 || advancerColumn < 0 || declinerColumn < 0) continue;

      for (var rowIndex = headerIndex + 1; rowIndex < values.length; rowIndex += 1) {
        var dateKey = stockAnalysisCellDateKey_(values[rowIndex][dateColumn], displays[rowIndex][dateColumn]);
        if (!dateKey || dateKey > todayKey) continue;

        var ageDays = stockAnalysisCalendarDayDiff_(dateKey, todayKey);
        if (ageDays < 0 || ageDays > STOCK_BREADTH_ROOT_FIX_CONFIG.maximumLookbackDays) continue;

        var advancers = stockAnalysisCellNumber_(values[rowIndex][advancerColumn], displays[rowIndex][advancerColumn]);
        var decliners = stockAnalysisCellNumber_(values[rowIndex][declinerColumn], displays[rowIndex][declinerColumn]);
        var ratio = ratioColumn >= 0
          ? stockAnalysisCellNumber_(values[rowIndex][ratioColumn], displays[rowIndex][ratioColumn])
          : null;

        if (!isFinite(advancers) || !isFinite(decliners)) continue;
        if (advancers < 0 || decliners < 0 || advancers + decliners <= 0) continue;
        if (ratio !== null && (!isFinite(ratio) || ratio < 0 || ratio > 1000)) ratio = null;

        candidates.push({
          dateKey: dateKey,
          ageDays: ageDays,
          advancers: Math.round(advancers),
          decliners: Math.round(decliners),
          ratio: ratio,
          sheetName: sheet.getName(),
          rowNumber: rowIndex + 1,
          headerRowNumber: headerIndex + 1
        });
      }
    }
  });

  candidates.sort(function(a, b) {
    if (a.dateKey !== b.dateKey) return b.dateKey.localeCompare(a.dateKey);
    if (a.sheetName === '終値一覧' && b.sheetName !== '終値一覧') return -1;
    if (b.sheetName === '終値一覧' && a.sheetName !== '終値一覧') return 1;
    return b.rowNumber - a.rowNumber;
  });

  return candidates.length ? candidates[0] : null;
}

function stockAnalysisApplyLatestBreadth_(payload, breadth) {
  if (!payload || typeof payload !== 'object') throw new Error('株式市場分析ペイロードが不正です。');
  if (!payload.marketInternals) payload.marketInternals = {};
  if (!payload.marketInternals.japan) payload.marketInternals.japan = {};
  if (!Array.isArray(payload.marketInternals.japan.rows)) payload.marketInternals.japan.rows = [];

  var rows = payload.marketInternals.japan.rows;
  var breadthIndex = -1;
  var ratioIndex = -1;

  rows.forEach(function(row, index) {
    var label = Array.isArray(row) ? String(row[0] || '') : '';
    if (/値上がり.*値下がり|上昇銘柄.*下落銘柄/.test(label)) breadthIndex = index;
    if (/騰落レシオ/.test(label)) ratioIndex = index;
  });

  var breadthRow = [
    '値上がり銘柄 / 値下がり銘柄',
    breadth.advancers.toLocaleString('ja-JP') + ' / ' + breadth.decliners.toLocaleString('ja-JP'),
    '-',
    breadth.advancers > breadth.decliners ? '値上がり優勢。' : breadth.advancers < breadth.decliners ? '値下がり優勢。' : '値上がり・値下がりが拮抗。'
  ];
  if (breadthIndex >= 0) rows[breadthIndex] = breadthRow;
  else rows.push(breadthRow);

  if (breadth.ratio !== null) {
    var ratioRow = ['騰落レシオ（25日）', stockAnalysisFormatRatio_(breadth.ratio), '-', '東証プライム市場内部の確認値。'];
    if (ratioIndex >= 0) rows[ratioIndex] = ratioRow;
    else rows.push(ratioRow);
  }

  var now = new Date();
  payload.updatedAt = Utilities.formatDate(now, STOCK_ANALYSIS_FRESHNESS_CONFIG.timezone, 'yyyy/MM/dd HH:mm');
  payload.generatedAt = Utilities.formatDate(now, STOCK_ANALYSIS_FRESHNESS_CONFIG.timezone, "yyyy-MM-dd'T'HH:mm:ssXXX");
  payload.publishedAt = payload.generatedAt;
  payload.dataAsOf = breadth.dateKey + 'T15:30:00+09:00';
  payload.sourceStatus = 'Google Sheetsの最新営業日行から検証更新';
  payload.breadthValidation = {
    status: 'verified',
    date: breadth.dateKey,
    sheetName: breadth.sheetName,
    rowNumber: breadth.rowNumber,
    headerRowNumber: breadth.headerRowNumber,
    advancers: breadth.advancers,
    decliners: breadth.decliners,
    advanceDeclineRatio: breadth.ratio,
    checkedAt: payload.generatedAt
  };
}

function stockAnalysisNormalizeHeader_(value) {
  return String(value || '')
    .replace(/[\s　]/g, '')
    .replace(/[（）()]/g, '')
    .replace(/％/g, '%')
    .toLowerCase();
}

function stockAnalysisFindHeaderColumn_(normalizedHeaders, candidates) {
  var normalizedCandidates = candidates.map(stockAnalysisNormalizeHeader_);
  for (var i = 0; i < normalizedCandidates.length; i += 1) {
    var exact = normalizedHeaders.indexOf(normalizedCandidates[i]);
    if (exact >= 0) return exact;
  }
  for (var column = 0; column < normalizedHeaders.length; column += 1) {
    for (var j = 0; j < normalizedCandidates.length; j += 1) {
      if (normalizedHeaders[column].indexOf(normalizedCandidates[j]) >= 0) return column;
    }
  }
  return -1;
}

function stockAnalysisCellDateKey_(rawValue, displayValue) {
  if (Object.prototype.toString.call(rawValue) === '[object Date]' && !isNaN(rawValue.getTime())) {
    return Utilities.formatDate(rawValue, STOCK_ANALYSIS_FRESHNESS_CONFIG.timezone, 'yyyy-MM-dd');
  }
  return stockAnalysisExtractDateKey_(displayValue || rawValue);
}

function stockAnalysisCellNumber_(rawValue, displayValue) {
  if (typeof rawValue === 'number' && isFinite(rawValue)) return rawValue;
  var text = String(displayValue || rawValue || '')
    .replace(/,/g, '')
    .replace(/%/g, '')
    .replace(/％/g, '')
    .trim();
  if (!text || !/^-?\d+(?:\.\d+)?$/.test(text)) return null;
  var number = Number(text);
  return isFinite(number) ? number : null;
}

function stockAnalysisFormatRatio_(value) {
  return Number(value).toLocaleString('ja-JP', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function updateStockAnalysisPageSafelyScheduled() {
  return updateStockAnalysisPageSafelyForMaster_();
}

function installStockAnalysisStandaloneTriggers() {
  var cleanup = deleteStockAnalysisStandaloneTriggers_(true);
  var created = [];
  STOCK_ANALYSIS_FRESHNESS_CONFIG.triggerHours.forEach(function(hour) {
    ScriptApp.newTrigger(STOCK_ANALYSIS_FRESHNESS_CONFIG.handler)
      .timeBased()
      .atHour(hour)
      .nearMinute(STOCK_ANALYSIS_FRESHNESS_CONFIG.triggerMinute)
      .everyDays(1)
      .inTimezone(STOCK_ANALYSIS_FRESHNESS_CONFIG.timezone)
      .create();
    created.push(('0' + hour).slice(-2) + ':' + ('0' + STOCK_ANALYSIS_FRESHNESS_CONFIG.triggerMinute).slice(-2));
  });
  SpreadsheetApp.getUi().alert(
    '株式市場分析の独立トリガーを設定しました。\n\n' +
    '実行時刻: ' + created.join(' / ') + '\n' +
    '実行関数: ' + STOCK_ANALYSIS_FRESHNESS_CONFIG.handler + '\n' +
    '削除した旧トリガー: ' + cleanup.deletedCount + '\n\n' +
    '本文・ダッシュボード、重要イベントとは連動しません。'
  );
  return showStockAnalysisStandaloneTriggerStatus();
}

function uninstallStockAnalysisStandaloneTriggers() {
  var cleanup = deleteStockAnalysisStandaloneTriggers_(true);
  SpreadsheetApp.getUi().alert(
    '株式市場分析の独立トリガーを削除しました。\n' +
    '削除数: ' + cleanup.deletedCount
  );
  return cleanup;
}

function showStockAnalysisStandaloneTriggerStatus() {
  var triggers = ScriptApp.getProjectTriggers();
  var safe = [];
  var unsafe = [];
  triggers.forEach(function(trigger) {
    var handler = trigger.getHandlerFunction();
    if (handler === STOCK_ANALYSIS_FRESHNESS_CONFIG.handler) safe.push(handler);
    if (handler === 'updateStockAnalysisPageFromSheet') unsafe.push(handler);
  });
  var lastResult = PropertiesService.getScriptProperties()
    .getProperty(STOCK_ANALYSIS_FRESHNESS_CONFIG.lastResultProperty) ||
    'まだ安全更新の実行履歴はありません。';
  SpreadsheetApp.getUi().alert(
    '株式市場分析の独立トリガー状態\n\n' +
    '安全トリガー: ' + safe.length + '/' + STOCK_ANALYSIS_FRESHNESS_CONFIG.triggerHours.length + '\n' +
    '旧・非安全トリガー: ' + unsafe.length + '\n' +
    (unsafe.length ? '旧トリガーを削除するため、定時更新を設定し直してください。\n\n' : '\n') +
    '直近結果:\n' + lastResult
  );
  return {
    handler: STOCK_ANALYSIS_FRESHNESS_CONFIG.handler,
    safeTriggerCount: safe.length,
    expectedCount: STOCK_ANALYSIS_FRESHNESS_CONFIG.triggerHours.length,
    unsafeTriggerCount: unsafe.length,
    lastResult: lastResult
  };
}

function deleteStockAnalysisStandaloneTriggers_(includeUnsafe) {
  var deleted = [];
  ScriptApp.getProjectTriggers().forEach(function(trigger) {
    var handler = trigger.getHandlerFunction();
    var isSafe = handler === STOCK_ANALYSIS_FRESHNESS_CONFIG.handler;
    var isUnsafe = includeUnsafe && handler === 'updateStockAnalysisPageFromSheet';
    if (isSafe || isUnsafe) {
      ScriptApp.deleteTrigger(trigger);
      deleted.push(handler);
    }
  });
  return { deletedCount: deleted.length, deletedHandlers: deleted };
}

function stockAnalysisCheckFreshness_(payload) {
  if (!payload || typeof payload !== 'object') {
    return { ok: false, reason: '株式市場分析JSONがありません。', dataAsOf: '', dataAgeDays: null };
  }
  var sourceStatus = String(payload.sourceStatus || '');
  var note = String(payload.note || '');
  if (/初期テンプレート/.test(sourceStatus) || /初期テンプレート/.test(note)) {
    return { ok: false, reason: '株式市場分析JSONが初期テンプレートのため、GitHub更新を停止しました。', dataAsOf: '', dataAgeDays: null };
  }
  var hasUsRows = !!(
    payload.marketInternals && payload.marketInternals.us &&
    Array.isArray(payload.marketInternals.us.rows) && payload.marketInternals.us.rows.length
  );
  var hasJapanRows = !!(
    payload.marketInternals && payload.marketInternals.japan &&
    Array.isArray(payload.marketInternals.japan.rows) && payload.marketInternals.japan.rows.length
  );
  if (!hasUsRows && !hasJapanRows) {
    return {
      ok: false,
      reason: '株式市場分析の主要指数データが空のため、GitHub更新を停止しました。',
      dataAsOf: stockAnalysisExtractDateKey_(payload.dataAsOf || payload.updatedAt),
      dataAgeDays: null
    };
  }
  var dataAsOf = stockAnalysisExtractDateKey_(payload.dataAsOf || payload.updatedAt);
  if (!dataAsOf) {
    return { ok: false, reason: '株式市場分析のデータ基準日を判定できないため、GitHub更新を停止しました。', dataAsOf: '', dataAgeDays: null };
  }
  var today = Utilities.formatDate(new Date(), STOCK_ANALYSIS_FRESHNESS_CONFIG.timezone, 'yyyy-MM-dd');
  var dataAgeDays = stockAnalysisCalendarDayDiff_(dataAsOf, today);
  if (dataAgeDays < -STOCK_ANALYSIS_FRESHNESS_CONFIG.maxFutureDays) {
    return { ok: false, reason: '株式市場分析のデータ基準日が未来日です。基準日: ' + dataAsOf, dataAsOf: dataAsOf, dataAgeDays: dataAgeDays };
  }
  if (dataAgeDays > STOCK_ANALYSIS_FRESHNESS_CONFIG.maxDataAgeDays) {
    return {
      ok: false,
      reason: '株式市場分析のデータ基準日が古すぎるため、GitHub更新を停止しました。 基準日: ' + dataAsOf + ' / 経過日数: ' + dataAgeDays + '日',
      dataAsOf: dataAsOf,
      dataAgeDays: dataAgeDays
    };
  }
  return { ok: true, reason: '', dataAsOf: dataAsOf, dataAgeDays: dataAgeDays };
}

function stockAnalysisExtractDateKey_(value) {
  var text = String(value || '').trim();
  var match = text.match(/(\d{4})[\/\.\-年](\d{1,2})[\/\.\-月](\d{1,2})/);
  if (!match) return '';
  var year = Number(match[1]);
  var month = Number(match[2]);
  var day = Number(match[3]);
  if (year < 2000 || year > 2100 || month < 1 || month > 12 || day < 1 || day > 31) return '';
  var checked = new Date(Date.UTC(year, month - 1, day));
  if (checked.getUTCFullYear() !== year || checked.getUTCMonth() !== month - 1 || checked.getUTCDate() !== day) return '';
  return year + '-' + ('0' + month).slice(-2) + '-' + ('0' + day).slice(-2);
}

function stockAnalysisCalendarDayDiff_(fromDate, toDate) {
  return Math.round((stockAnalysisDateKeyToUtcMs_(toDate) - stockAnalysisDateKeyToUtcMs_(fromDate)) / 86400000);
}

function stockAnalysisDateKeyToUtcMs_(dateKey) {
  var parts = String(dateKey).split('-').map(Number);
  return Date.UTC(parts[0], parts[1] - 1, parts[2]);
}

function showStockAnalysisFreshnessStatus() {
  if (typeof stockAnalysisBuildPayloadFromSheet_ !== 'function') {
    SpreadsheetApp.getUi().alert('株式市場分析の基礎関数が見つかりません。');
    return { ok: false, reason: 'stockAnalysisBuildPayloadFromSheet_ is not defined' };
  }
  var payload = stockAnalysisBuildFreshPayload_();
  var result = stockAnalysisCheckFreshness_(payload);
  var message = result.ok
    ? '株式市場分析データは公開可能です。\n基準日: ' + result.dataAsOf + '\n経過日数: ' + result.dataAgeDays + '日'
    : '株式市場分析データは公開停止対象です。\n理由: ' + result.reason;
  SpreadsheetApp.getUi().alert(message);
  return result;
}

function stockAnalysisSaveStandaloneResult_(result) {
  var payload = {};
  Object.keys(result || {}).forEach(function(key) { payload[key] = result[key]; });
  payload.executedAt = Utilities.formatDate(new Date(), STOCK_ANALYSIS_FRESHNESS_CONFIG.timezone, 'yyyy-MM-dd HH:mm:ss');
  PropertiesService.getScriptProperties().setProperty(
    STOCK_ANALYSIS_FRESHNESS_CONFIG.lastResultProperty,
    JSON.stringify(payload, null, 2)
  );
  if (typeof stockAnalysisSaveResult_ === 'function') stockAnalysisSaveResult_(payload);
  console.log(JSON.stringify(payload));
  return payload;
}
