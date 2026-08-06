var STOCK_ANALYSIS_FRESHNESS_CONFIG = {
  timezone: 'Asia/Tokyo',
  maxDataAgeDays: 4,
  maxFutureDays: 1,
  triggerHours: [7, 12, 16, 21],
  triggerMinute: 40,
  handler: 'updateStockAnalysisPageSafelyScheduled',
  lastResultProperty: 'STOCK_ANALYSIS_SAFE_UPDATE_LAST_RESULT'
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
    var payload = stockAnalysisBuildPayloadFromSheet_();
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
      'Update stock analysis JSON from verified Google Sheets data'
    );
    return stockAnalysisSaveStandaloneResult_({
      ok: true,
      skipped: false,
      targetPath: targetPath,
      updatedAt: payload.updatedAt || '',
      dataAsOf: payload.dataAsOf || '',
      dataAgeDays: freshness.dataAgeDays,
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
  var payload = stockAnalysisBuildPayloadFromSheet_();
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
