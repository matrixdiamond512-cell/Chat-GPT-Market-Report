var STOCK_ANALYSIS_JSON_CONFIG = {
  timezone: 'Asia/Tokyo',
  sheetName: 'Stock_Analysis_JSON',
  targetPath: 'data/stocks.json',
  rawJsonUrl: 'https://raw.githubusercontent.com/matrixdiamond512-cell/Chat-GPT-Market-Report/main/data/stocks.json',
  pagesUrl: 'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/stocks.html',
  handler: 'updateStockAnalysisPageFromSheet',
  triggerHours: [7, 12, 16, 21],
  triggerMinute: 30,
  lastResultProperty: 'STOCK_ANALYSIS_JSON_LAST_RESULT'
};

function setupStockAnalysisJsonSheet() {
  var sheet = stockAnalysisEnsureJsonSheet_();
  var summary = {
    ok: true,
    sheetName: STOCK_ANALYSIS_JSON_CONFIG.sheetName,
    targetPath: STOCK_ANALYSIS_JSON_CONFIG.targetPath,
    message: 'Stock_Analysis_JSONシートを作成または確認しました。B2以降のJSONをWEBへ反映します。'
  };
  stockAnalysisAlert_(
    '株式市場分析JSONシートを準備しました。\n' +
    'シート名: ' + summary.sheetName + '\n' +
    'WEB更新ファイル: ' + summary.targetPath + '\n\n' +
    '次に previewStockAnalysisJson を実行して確認できます。'
  );
  return summary;
}

function previewStockAnalysisJson() {
  var payload = stockAnalysisBuildPayloadFromSheet_();
  var json = JSON.stringify(payload, null, 2) + '\n';
  var html = HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;padding:12px">' +
      '<p><b>株式市場分析JSONプレビュー</b></p>' +
      '<pre style="white-space:pre-wrap;font-size:12px">' + stockAnalysisEscapeHtml_(json) + '</pre>' +
    '</div>'
  ).setWidth(920).setHeight(700);
  SpreadsheetApp.getUi().showModalDialog(html, '株式市場分析JSONプレビュー');
  return payload;
}

function syncStockAnalysisJsonToGitHub() {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var payload = stockAnalysisBuildPayloadFromSheet_();
    var json = JSON.stringify(payload, null, 2) + '\n';
    var current = stockAnalysisGetGitHubJsonFile_(STOCK_ANALYSIS_JSON_CONFIG.targetPath);
    var result = stockAnalysisPutGitHubJsonFile_(
      STOCK_ANALYSIS_JSON_CONFIG.targetPath,
      json,
      current.sha,
      'Update stock analysis JSON from Google Sheets'
    );
    var summary = stockAnalysisSaveResult_({
      ok: true,
      targetPath: STOCK_ANALYSIS_JSON_CONFIG.targetPath,
      updatedAt: payload.updatedAt || '',
      dataAsOf: payload.dataAsOf || '',
      commitSha: result.commit.sha,
      pagesUrl: STOCK_ANALYSIS_JSON_CONFIG.pagesUrl
    });
    stockAnalysisAlert_(
      '株式市場分析JSONをGitHubへ反映しました。\n' +
      '更新日時: ' + summary.updatedAt + '\n' +
      'コミット: ' + summary.commitSha + '\n' +
      'ページ: ' + summary.pagesUrl
    );
    return summary;
  } catch (error) {
    stockAnalysisSaveResult_({ ok: false, error: error.message });
    stockAnalysisAlert_('株式市場分析JSONを反映できませんでした。\n' + error.message);
    throw error;
  } finally {
    lock.releaseLock();
  }
}

function updateStockAnalysisPageFromSheet() {
  return syncStockAnalysisJsonToGitHub();
}

function installStockAnalysisPageScheduledTriggers() {
  uninstallStockAnalysisPageScheduledTriggers_(false);
  STOCK_ANALYSIS_JSON_CONFIG.triggerHours.forEach(function(hour) {
    ScriptApp.newTrigger(STOCK_ANALYSIS_JSON_CONFIG.handler)
      .timeBased()
      .atHour(hour)
      .nearMinute(STOCK_ANALYSIS_JSON_CONFIG.triggerMinute)
      .everyDays(1)
      .inTimezone(STOCK_ANALYSIS_JSON_CONFIG.timezone)
      .create();
  });
  stockAnalysisAlert_(
    '株式市場分析ページの定時更新を設定しました。\n' +
    '実行時刻: 07:30 / 12:30 / 16:30 / 21:30（日本時間）'
  );
  return showStockAnalysisPageScheduledStatus();
}

function uninstallStockAnalysisPageScheduledTriggers() {
  var deleted = uninstallStockAnalysisPageScheduledTriggers_(true);
  return { deleted: deleted };
}

function showStockAnalysisPageScheduledStatus() {
  var handler = STOCK_ANALYSIS_JSON_CONFIG.handler;
  var triggers = ScriptApp.getProjectTriggers().filter(function(trigger) {
    return trigger.getHandlerFunction() === handler;
  });
  var lastResult = PropertiesService.getScriptProperties()
    .getProperty(STOCK_ANALYSIS_JSON_CONFIG.lastResultProperty) || '未実行';
  var message =
    '株式市場分析ページ定時更新の状態\n' +
    'トリガー数: ' + triggers.length + '\n' +
    '想定: 4件（07:30 / 12:30 / 16:30 / 21:30）\n' +
    '実行関数: ' + handler + '\n\n' +
    '直近結果:\n' + lastResult;
  stockAnalysisAlert_(message);
  return {
    handler: handler,
    triggerCount: triggers.length,
    expectedCount: STOCK_ANALYSIS_JSON_CONFIG.triggerHours.length,
    lastResult: lastResult
  };
}

function stockAnalysisBuildPayloadFromSheet_() {
  var sheet = stockAnalysisEnsureJsonSheet_();
  var rawJson = stockAnalysisReadJsonFromSheet_(sheet);
  var payload;
  try {
    payload = JSON.parse(rawJson);
  } catch (error) {
    throw new Error('Stock_Analysis_JSONシートのJSON形式が正しくありません。' + error.message);
  }
  payload = stockAnalysisNormalizePayload_(payload);
  stockAnalysisValidatePayload_(payload);
  return payload;
}

function stockAnalysisEnsureJsonSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(STOCK_ANALYSIS_JSON_CONFIG.sheetName);
  if (!sheet) {
    sheet = ss.insertSheet(STOCK_ANALYSIS_JSON_CONFIG.sheetName);
    stockAnalysisInitializeJsonSheet_(sheet);
    return sheet;
  }
  if (sheet.getLastRow() === 0 || sheet.getLastColumn() === 0) {
    stockAnalysisInitializeJsonSheet_(sheet);
    return sheet;
  }
  var current = String(sheet.getRange(2, 2).getValue() || '').trim();
  if (!current) stockAnalysisInitializeJsonSheet_(sheet);
  return sheet;
}

function stockAnalysisInitializeJsonSheet_(sheet) {
  var seed = stockAnalysisFetchSeedJson_();
  sheet.clear();
  sheet.getRange(1, 1, 1, 3).setValues([['part', 'json', 'memo']]);
  sheet.getRange(2, 1, 1, 3).setValues([[
    1,
    seed,
    '株式市場分析ページ用JSONです。B2に入りきらない場合は、B2、B3、B4...へ分割して貼り付けても読み込みます。'
  ]]);
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, 3).setFontWeight('bold').setBackground('#eaf1fb');
  sheet.getRange(1, 1, Math.max(2, sheet.getLastRow()), 3).setWrap(true);
  sheet.setColumnWidth(1, 80);
  sheet.setColumnWidth(2, 720);
  sheet.setColumnWidth(3, 460);
}

function stockAnalysisReadJsonFromSheet_(sheet) {
  var values = sheet.getDataRange().getValues();
  if (values.length < 2) throw new Error('Stock_Analysis_JSONシートにJSON行がありません。');
  var headers = values[0].map(function(value) { return String(value || '').trim().toLowerCase(); });
  var jsonIndex = headers.indexOf('json');
  if (jsonIndex < 0) jsonIndex = 1;
  var parts = [];
  for (var i = 1; i < values.length; i += 1) {
    var value = String(values[i][jsonIndex] || '');
    if (value.trim()) parts.push(value);
  }
  var raw = parts.join('');
  if (!raw.trim()) throw new Error('Stock_Analysis_JSONシートのjson列が空です。');
  return raw.trim();
}

function stockAnalysisNormalizePayload_(payload) {
  var now = new Date();
  var generatedAt = stockAnalysisIsoJst_(now);
  payload.schemaVersion = payload.schemaVersion || '1.0.0';
  payload.pageId = 'stocks';
  payload.pageTitle = payload.pageTitle || '株式市場分析';
  payload.generatedAt = generatedAt;
  payload.publishedAt = generatedAt;
  payload.status = payload.status || 'ok';
  payload.sourceStatus = 'Google Sheetsから更新';
  payload.updatedAt = payload.updatedAt || stockAnalysisDisplayJst_(now);
  payload.dataAsOf = payload.dataAsOf || generatedAt;
  payload.sources = Array.isArray(payload.sources) ? payload.sources : [];
  payload.sources = stockAnalysisUpsertSource_(payload.sources, {
    id: 'STOCK_ANALYSIS_JSON',
    name: 'Googleスプレッドシート Stock_Analysis_JSON',
    status: 'ok',
    asOf: payload.updatedAt,
    note: '株式市場分析ページの表示データ。GASがdata/stocks.jsonへ反映します。'
  });
  return payload;
}

function stockAnalysisValidatePayload_(payload) {
  if (!payload || typeof payload !== 'object') throw new Error('株式市場分析JSONがオブジェクトではありません。');
  if (payload.pageId !== 'stocks') throw new Error('pageId は stocks にしてください。');
  stockAnalysisAssert_(payload.marketInternals && payload.marketInternals.us, 'marketInternals.us がありません。');
  stockAnalysisAssert_(payload.marketInternals && payload.marketInternals.japan, 'marketInternals.japan がありません。');
  stockAnalysisAssert_(payload.movers && payload.movers.us, 'movers.us がありません。');
  stockAnalysisAssert_(payload.movers && payload.movers.japan, 'movers.japan がありません。');
  stockAnalysisAssert_(payload.sectors && payload.sectors.us, 'sectors.us がありません。');
  stockAnalysisAssert_(payload.sectors && payload.sectors.japan, 'sectors.japan がありません。');
  stockAnalysisAssert_(payload.contributions && payload.contributions.us, 'contributions.us がありません。');
  stockAnalysisAssert_(payload.contributions && payload.contributions.japan, 'contributions.japan がありません。');
  stockAnalysisAssert_(payload.judgement, 'judgement がありません。');
}

function stockAnalysisUpsertSource_(sources, source) {
  var next = sources.filter(function(item) {
    return !item || item.id !== source.id;
  });
  next.push(source);
  return next;
}

function stockAnalysisFetchSeedJson_() {
  try {
    var response = UrlFetchApp.fetch(
      STOCK_ANALYSIS_JSON_CONFIG.rawJsonUrl + '?ts=' + new Date().getTime(),
      {
        method: 'get',
        muteHttpExceptions: true,
        headers: { Accept: 'application/json' }
      }
    );
    if (response.getResponseCode() === 200) {
      var text = response.getContentText('UTF-8');
      JSON.parse(text);
      return text.trim();
    }
  } catch (error) {
    Logger.log('株式市場分析JSONの初期データ取得に失敗: ' + error.message);
  }
  return JSON.stringify({
    schemaVersion: '1.0.0',
    pageId: 'stocks',
    pageTitle: '株式市場分析',
    updatedAt: stockAnalysisDisplayJst_(new Date()),
    status: 'ok',
    sourceStatus: '初期テンプレート',
    marketInternals: { us: stockAnalysisEmptyTable_('主要指数と市場内部（米国）', 'US'), japan: stockAnalysisEmptyTable_('主要指数と市場内部（日本）', 'JP') },
    movers: { us: stockAnalysisEmptyMovers_('米国市場の大幅上昇・下落銘柄', 'US'), japan: stockAnalysisEmptyMovers_('日本市場の大幅上昇・下落銘柄', 'JP') },
    sectors: { us: stockAnalysisEmptySectors_('米国市場のセクター・業種（上昇率TOP5）', 'US'), japan: stockAnalysisEmptySectors_('東京市場のセクター・業種（上昇率TOP5）', 'JP') },
    contributions: { us: stockAnalysisEmptyContributions_('米国市場（S&P500寄与度 上位・下位）', 'US'), japan: stockAnalysisEmptyContributions_('日本市場（日経225寄与度 上位・下位）', 'JP') },
    judgement: {
      conclusion: { title: '今日の結論', main: '取得不能', sub: 'Stock_Analysis_JSONを更新してください。' },
      reason: { title: 'なぜ買われたか／売られたか', items: [] },
      risk: { title: 'リスク', items: [] },
      watch: { title: '次の注目点', items: [] }
    },
    analysisCards: [],
    note: '初期テンプレートです。'
  }, null, 2);
}

function stockAnalysisEmptyTable_(title, flag) {
  return {
    title: title,
    flag: flag,
    columns: ['指標名', '終値', '前日比', '評価・概況'],
    rows: []
  };
}

function stockAnalysisEmptyMovers_(title, flag) {
  return { title: title, flag: flag, gainers: [], losers: [] };
}

function stockAnalysisEmptySectors_(title, flag) {
  return { title: title, flag: flag, rows: [] };
}

function stockAnalysisEmptyContributions_(title, flag) {
  return { title: title, flag: flag, top: [], bottom: [] };
}

function uninstallStockAnalysisPageScheduledTriggers_(showAlert) {
  var handler = STOCK_ANALYSIS_JSON_CONFIG.handler;
  var deleted = 0;
  ScriptApp.getProjectTriggers()
    .filter(function(trigger) { return trigger.getHandlerFunction() === handler; })
    .forEach(function(trigger) {
      ScriptApp.deleteTrigger(trigger);
      deleted += 1;
    });
  if (showAlert) stockAnalysisAlert_('株式市場分析ページ定時更新トリガーを削除しました。削除数: ' + deleted);
  return deleted;
}

function stockAnalysisGetGitHubJsonFile_(path) {
  var config = stockAnalysisGithubConfig_();
  var response = UrlFetchApp.fetch(
    stockAnalysisGithubContentsUrl_(config, path) + '?ref=' + encodeURIComponent(config.branch),
    {
      method: 'get',
      headers: stockAnalysisGithubHeaders_(config.token),
      muteHttpExceptions: true
    }
  );
  var code = response.getResponseCode();
  if (code === 404) return { data: null, sha: null };
  if (code !== 200) throw new Error('GitHubファイル取得失敗: HTTP ' + code + ' ' + response.getContentText());
  var payload = JSON.parse(response.getContentText());
  return {
    data: JSON.parse(Utilities.newBlob(Utilities.base64Decode(payload.content.replace(/\n/g, ''))).getDataAsString('UTF-8')),
    sha: payload.sha
  };
}

function stockAnalysisPutGitHubJsonFile_(path, content, sha, message) {
  var config = stockAnalysisGithubConfig_();
  var body = {
    message: message,
    content: Utilities.base64Encode(content, Utilities.Charset.UTF_8),
    branch: config.branch
  };
  if (sha) body.sha = sha;
  var response = UrlFetchApp.fetch(stockAnalysisGithubContentsUrl_(config, path), {
    method: 'put',
    contentType: 'application/json',
    headers: stockAnalysisGithubHeaders_(config.token),
    payload: JSON.stringify(body),
    muteHttpExceptions: true
  });
  var code = response.getResponseCode();
  if (code !== 200 && code !== 201) throw new Error('GitHub更新失敗: HTTP ' + code + ' ' + response.getContentText());
  return JSON.parse(response.getContentText());
}

function stockAnalysisGithubConfig_() {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('スクリプトプロパティ GITHUB_TOKEN が未設定です。');
  return {
    token: token,
    owner: props.getProperty('GITHUB_OWNER') || (typeof WEB_REPORT_CONFIG !== 'undefined' ? WEB_REPORT_CONFIG.owner : 'matrixdiamond512-cell'),
    repo: props.getProperty('GITHUB_REPO') || (typeof WEB_REPORT_CONFIG !== 'undefined' ? WEB_REPORT_CONFIG.repo : 'Chat-GPT-Market-Report'),
    branch: props.getProperty('GITHUB_BRANCH') || (typeof WEB_REPORT_CONFIG !== 'undefined' ? WEB_REPORT_CONFIG.branch : 'main')
  };
}

function stockAnalysisGithubContentsUrl_(config, path) {
  return 'https://api.github.com/repos/' + config.owner + '/' + config.repo + '/contents/' + path;
}

function stockAnalysisGithubHeaders_(token) {
  return {
    Authorization: 'Bearer ' + token,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };
}

function stockAnalysisSaveResult_(result) {
  var payload = Object.assign({
    executedAt: stockAnalysisDisplayJst_(new Date())
  }, result);
  PropertiesService.getScriptProperties().setProperty(
    STOCK_ANALYSIS_JSON_CONFIG.lastResultProperty,
    JSON.stringify(payload)
  );
  return payload;
}

function stockAnalysisIsoJst_(date) {
  return Utilities.formatDate(date, STOCK_ANALYSIS_JSON_CONFIG.timezone, "yyyy-MM-dd'T'HH:mm:ss'+09:00'");
}

function stockAnalysisDisplayJst_(date) {
  return Utilities.formatDate(date, STOCK_ANALYSIS_JSON_CONFIG.timezone, 'yyyy/MM/dd HH:mm');
}

function stockAnalysisAssert_(condition, message) {
  if (!condition) throw new Error(message);
}

function stockAnalysisAlert_(message) {
  try {
    SpreadsheetApp.getUi().alert(message);
  } catch (error) {
    Logger.log(message);
  }
}

function stockAnalysisEscapeHtml_(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
