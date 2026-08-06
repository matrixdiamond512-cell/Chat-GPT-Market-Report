var STOCK_ANALYSIS_FRESHNESS_CONFIG = {
  timezone: 'Asia/Tokyo',
  maxDataAgeDays: 4,
  maxFutureDays: 1
};

/**
 * 共通スケジューラー専用の安全な株式市場分析更新。
 * データ基準日が古い場合はGitHubへ書き込まず、正常スキップとして返す。
 */
function updateStockAnalysisPageSafelyForMaster_() {
  if (
    typeof stockAnalysisBuildPayloadFromSheet_ !== 'function' ||
    typeof stockAnalysisGetGitHubJsonFile_ !== 'function' ||
    typeof stockAnalysisPutGitHubJsonFile_ !== 'function'
  ) {
    return {
      ok: true,
      skipped: true,
      reason: '株式市場分析の基礎関数が未導入のため更新をスキップしました。'
    };
  }

  try {
    var payload = stockAnalysisBuildPayloadFromSheet_();
    var freshness = stockAnalysisCheckFreshness_(payload);

    if (!freshness.ok) {
      var skipped = {
        ok: true,
        skipped: true,
        reason: freshness.reason,
        dataAsOf: freshness.dataAsOf || '',
        dataAgeDays: freshness.dataAgeDays,
        targetPath: typeof STOCK_ANALYSIS_JSON_CONFIG !== 'undefined'
          ? STOCK_ANALYSIS_JSON_CONFIG.targetPath
          : 'data/stocks.json'
      };
      if (typeof stockAnalysisSaveResult_ === 'function') stockAnalysisSaveResult_(skipped);
      console.log(JSON.stringify(skipped));
      return skipped;
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

    var summary = {
      ok: true,
      skipped: false,
      targetPath: targetPath,
      updatedAt: payload.updatedAt || '',
      dataAsOf: payload.dataAsOf || '',
      dataAgeDays: freshness.dataAgeDays,
      commitSha: result.commit.sha,
      pagesUrl: STOCK_ANALYSIS_JSON_CONFIG.pagesUrl
    };
    if (typeof stockAnalysisSaveResult_ === 'function') stockAnalysisSaveResult_(summary);
    return summary;
  } catch (error) {
    var failure = {
      ok: false,
      skipped: false,
      error: error.message,
      reason: '株式市場分析の安全更新に失敗しました。'
    };
    if (typeof stockAnalysisSaveResult_ === 'function') stockAnalysisSaveResult_(failure);
    return failure;
  }
}

function stockAnalysisCheckFreshness_(payload) {
  if (!payload || typeof payload !== 'object') {
    return { ok: false, reason: '株式市場分析JSONがありません。', dataAsOf: '', dataAgeDays: null };
  }

  var sourceStatus = String(payload.sourceStatus || '');
  var note = String(payload.note || '');
  if (/初期テンプレート/.test(sourceStatus) || /初期テンプレート/.test(note)) {
    return {
      ok: false,
      reason: '株式市場分析JSONが初期テンプレートのため、GitHub更新を停止しました。',
      dataAsOf: '',
      dataAgeDays: null
    };
  }

  var hasUsRows = !!(
    payload.marketInternals &&
    payload.marketInternals.us &&
    Array.isArray(payload.marketInternals.us.rows) &&
    payload.marketInternals.us.rows.length
  );
  var hasJapanRows = !!(
    payload.marketInternals &&
    payload.marketInternals.japan &&
    Array.isArray(payload.marketInternals.japan.rows) &&
    payload.marketInternals.japan.rows.length
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
    return {
      ok: false,
      reason: '株式市場分析のデータ基準日を判定できないため、GitHub更新を停止しました。',
      dataAsOf: '',
      dataAgeDays: null
    };
  }

  var today = Utilities.formatDate(
    new Date(),
    STOCK_ANALYSIS_FRESHNESS_CONFIG.timezone,
    'yyyy-MM-dd'
  );
  var dataAgeDays = stockAnalysisCalendarDayDiff_(dataAsOf, today);

  if (dataAgeDays < -STOCK_ANALYSIS_FRESHNESS_CONFIG.maxFutureDays) {
    return {
      ok: false,
      reason: '株式市場分析のデータ基準日が未来日です。基準日: ' + dataAsOf,
      dataAsOf: dataAsOf,
      dataAgeDays: dataAgeDays
    };
  }

  if (dataAgeDays > STOCK_ANALYSIS_FRESHNESS_CONFIG.maxDataAgeDays) {
    return {
      ok: false,
      reason:
        '株式市場分析のデータ基準日が古すぎるため、GitHub更新を停止しました。' +
        ' 基準日: ' + dataAsOf +
        ' / 経過日数: ' + dataAgeDays + '日',
      dataAsOf: dataAsOf,
      dataAgeDays: dataAgeDays
    };
  }

  return {
    ok: true,
    reason: '',
    dataAsOf: dataAsOf,
    dataAgeDays: dataAgeDays
  };
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
  if (
    checked.getUTCFullYear() !== year ||
    checked.getUTCMonth() !== month - 1 ||
    checked.getUTCDate() !== day
  ) return '';

  return year + '-' + ('0' + month).slice(-2) + '-' + ('0' + day).slice(-2);
}

function stockAnalysisCalendarDayDiff_(fromDate, toDate) {
  var from = stockAnalysisDateKeyToUtcMs_(fromDate);
  var to = stockAnalysisDateKeyToUtcMs_(toDate);
  return Math.round((to - from) / 86400000);
}

function stockAnalysisDateKeyToUtcMs_(dateKey) {
  var parts = String(dateKey).split('-').map(Number);
  return Date.UTC(parts[0], parts[1] - 1, parts[2]);
}

function showStockAnalysisFreshnessStatus() {
  var payload = stockAnalysisBuildPayloadFromSheet_();
  var result = stockAnalysisCheckFreshness_(payload);
  var message = result.ok
    ? '株式市場分析データは公開可能です。\n基準日: ' + result.dataAsOf + '\n経過日数: ' + result.dataAgeDays + '日'
    : '株式市場分析データは公開停止対象です。\n理由: ' + result.reason;
  try {
    SpreadsheetApp.getUi().alert(message);
  } catch (error) {
    Logger.log(message);
  }
  return result;
}
