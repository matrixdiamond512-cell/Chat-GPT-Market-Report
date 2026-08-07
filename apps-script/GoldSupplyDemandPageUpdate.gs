// ゴールド需給分析 専用更新処理
// MarketReportMenu.gs から呼び出す。
// GitHub Actions APIを直接dispatchせず、トリガーファイルを1回PUTして更新を起動する。

var GOLD_SUPPLY_DEMAND_PAGE_UPDATE_VERSION = '1.0.0-single-put';
var GOLD_SUPPLY_DEMAND_TRIGGER_HANDLER = 'refreshGoldDemandSheetAfterManualUpdateV1';

function runGoldSupplyDemandPageUpdateNowV1() {
  var config = getMarketReportWebConfigForMenu_();
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');

  if (!token) {
    SpreadsheetApp.getUi().alert(
      'ゴールド需給の更新を起動できませんでした。\n\n理由: GITHUB_TOKEN が設定されていません。'
    );
    return { ok: false, queued: false, error: 'GITHUB_TOKEN is not configured' };
  }

  var branch = config.branch || 'main';
  var now = new Date();
  var requestedAt = Utilities.formatDate(now, 'Asia/Tokyo', "yyyy-MM-dd'T'HH:mm:ssXXX");
  var fileStamp = Utilities.formatDate(now, 'Asia/Tokyo', 'yyyyMMdd-HHmmss');
  var triggerPath =
    'data/gold-supply-demand-trigger/request-' +
    fileStamp + '-' + now.getTime() + '.json';

  try {
    var result = createGoldSupplyDemandTriggerFileV1_(
      config, token, branch, triggerPath, requestedAt
    );

    var props = PropertiesService.getScriptProperties();
    props.setProperty('GOLD_SUPPLY_DEMAND_LAST_MANUAL_REQUEST_AT', requestedAt);
    props.setProperty('GOLD_SUPPLY_DEMAND_LAST_MANUAL_REQUEST_PATH', triggerPath);
    scheduleGoldDemandSheetRefreshV1_();

    SpreadsheetApp.getUi().alert(
      'ゴールド需給の更新処理を起動しました。\n' +
      '起動方式: GitHubトリガーファイルを1回作成\n' +
      'コード版: ' + GOLD_SUPPLY_DEMAND_PAGE_UPDATE_VERSION + '\n' +
      '更新対象: data/gold-supply-demand.json / 12列CSV / WEBページ\n\n' +
      'Gold_Demandシートは約3分後に自動再読込します。\n' +
      '必要なら「更新状態を確認」で最新状態とシート反映を確認してください。'
    );

    return {
      ok: true,
      queued: true,
      branch: branch,
      triggerPath: triggerPath,
      requestedAt: requestedAt,
      commitSha: result.commitSha || null,
      version: GOLD_SUPPLY_DEMAND_PAGE_UPDATE_VERSION
    };
  } catch (error) {
    SpreadsheetApp.getUi().alert(
      'ゴールド需給の更新に失敗しました。\n\n' +
      'コード版: ' + GOLD_SUPPLY_DEMAND_PAGE_UPDATE_VERSION + '\n' +
      '理由: ' + error.message
    );
    return {
      ok: false,
      queued: false,
      error: error.message,
      version: GOLD_SUPPLY_DEMAND_PAGE_UPDATE_VERSION
    };
  }
}

function createGoldSupplyDemandTriggerFileV1_(config, token, branch, triggerPath, requestedAt) {
  var baseUrl =
    'https://api.github.com/repos/' +
    encodeURIComponent(config.owner) + '/' +
    encodeURIComponent(config.repo) +
    '/contents/' + encodeGoldSupplyDemandGitHubPathV1_(triggerPath);

  var triggerData = {
    requestedAt: requestedAt,
    requestedBy: 'Google Sheets menu',
    purpose: 'gold-supply-demand-manual-update',
    updaterVersion: GOLD_SUPPLY_DEMAND_PAGE_UPDATE_VERSION
  };

  var payload = {
    message: 'Trigger gold supply-demand update ' + requestedAt,
    content: Utilities.base64Encode(
      JSON.stringify(triggerData, null, 2) + '\n',
      Utilities.Charset.UTF_8
    ),
    branch: branch
  };

  var response = UrlFetchApp.fetch(baseUrl, {
    method: 'put',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    },
    muteHttpExceptions: true
  });

  var status = response.getResponseCode();
  if (status !== 201) {
    var body = String(response.getContentText() || '').slice(0, 500);
    if (status === 403) {
      throw new Error(
        'GitHubファイル作成権限がありません。GITHUB_TOKEN に Contents の Read and write 権限が必要です。\n' +
        'HTTP 403\n' + body
      );
    }
    throw new Error(
      'GitHubトリガーファイルの作成に失敗しました。HTTP ' + status + '\n' + body
    );
  }

  var created = JSON.parse(response.getContentText());
  return {
    ok: true,
    commitSha: created.commit && created.commit.sha ? created.commit.sha : null,
    contentSha: created.content && created.content.sha ? created.content.sha : null
  };
}

function encodeGoldSupplyDemandGitHubPathV1_(path) {
  return String(path || '')
    .split('/')
    .map(function(part) { return encodeURIComponent(part); })
    .join('/');
}

function scheduleGoldDemandSheetRefreshV1_() {
  ScriptApp.getProjectTriggers()
    .filter(function(trigger) {
      return trigger.getHandlerFunction() === GOLD_SUPPLY_DEMAND_TRIGGER_HANDLER;
    })
    .forEach(function(trigger) { ScriptApp.deleteTrigger(trigger); });

  ScriptApp.newTrigger(GOLD_SUPPLY_DEMAND_TRIGGER_HANDLER)
    .timeBased()
    .after(180000)
    .create();
}

function refreshGoldDemandSheetAfterManualUpdateV1() {
  try {
    var result = refreshGoldDemandSheetImportV1_();
    PropertiesService.getScriptProperties().setProperty(
      'GOLD_SUPPLY_DEMAND_LAST_SHEET_REFRESH_AT',
      Utilities.formatDate(new Date(), 'Asia/Tokyo', "yyyy-MM-dd'T'HH:mm:ssXXX")
    );
    return result;
  } catch (error) {
    PropertiesService.getScriptProperties().setProperty(
      'GOLD_SUPPLY_DEMAND_LAST_SHEET_REFRESH_ERROR',
      String(error && error.message ? error.message : error)
    );
    throw error;
  }
}

function refreshGoldDemandSheetImportV1_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('Gold_Demand');
  if (!sheet) throw new Error('Gold_Demand シートが見つかりません。');

  var cacheKey = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyyMMddHHmmss');
  var csvUrl =
    'https://raw.githubusercontent.com/matrixdiamond512-cell/Chat-GPT-Market-Report/main/' +
    'data/gold-supply-demand-sheet.csv?v=' + cacheKey;
  var formula = '=IMPORTDATA("' + csvUrl + '")';

  sheet.getRange('A1').setFormula(formula);
  SpreadsheetApp.flush();
  return {
    ok: true,
    formula: formula,
    dataUpdatedAt: sheet.getRange('L2').getDisplayValue() || null
  };
}

function showGoldSupplyDemandPageUpdateStatusV1() {
  var config = getMarketReportWebConfigForMenu_();
  var branch = config.branch || 'main';
  var url =
    'https://raw.githubusercontent.com/' +
    encodeURIComponent(config.owner) + '/' +
    encodeURIComponent(config.repo) + '/' +
    encodeURIComponent(branch) +
    '/data/gold-supply-demand.json?ts=' + new Date().getTime();

  try {
    var response = UrlFetchApp.fetch(url, {
      method: 'get',
      muteHttpExceptions: true,
      headers: { 'Cache-Control': 'no-cache' }
    });
    var statusCode = response.getResponseCode();
    if (statusCode !== 200) {
      throw new Error('gold-supply-demand.json の取得に失敗しました。HTTP ' + statusCode);
    }

    var data = JSON.parse(response.getContentText());
    var dataStatus = data.dataStatus || {};
    var assessment = data.assessment || {};
    var comex = data.comex || {};
    var cftc = data.cftc || {};
    var etf = data.etf || {};
    var props = PropertiesService.getScriptProperties();

    var sheetResult = refreshGoldDemandSheetImportV1_();
    props.setProperty(
      'GOLD_SUPPLY_DEMAND_LAST_SHEET_REFRESH_AT',
      Utilities.formatDate(new Date(), 'Asia/Tokyo', "yyyy-MM-dd'T'HH:mm:ssXXX")
    );

    SpreadsheetApp.getUi().alert(
      'ゴールド需給分析 更新状態\n\n' +
      'コード版: ' + GOLD_SUPPLY_DEMAND_PAGE_UPDATE_VERSION + '\n' +
      'JSON最終更新: ' + (data.generatedAt || '取得不能') + '\n' +
      'データ状態: ' + (dataStatus.connected != null ? dataStatus.connected : '?') + '/' +
        (dataStatus.total != null ? dataStatus.total : '?') + '\n' +
      '短期需給: ' + (assessment.shortTerm || '取得不能') + '\n' +
      '構造的需給: ' + (assessment.structural || '取得不能') + '\n' +
      '総合スコア: ' + (assessment.score != null ? assessment.score + '/100' : '取得不能') + '\n' +
      'COMEX基準日: ' + (comex.asOfDate || '取得不能') + ' / ' + (comex.status || '取得不能') + '\n' +
      'CFTC基準日: ' + (cftc.asOfDate || '取得不能') + ' / ' + (cftc.status || '取得不能') + '\n' +
      'GLD: ' + ((etf.gld && etf.gld.asOfDate) || '取得不能') + '\n' +
      'IAU: ' + ((etf.iau && etf.iau.asOfDate) || '取得不能') + '\n' +
      '手動更新要求: ' + (props.getProperty('GOLD_SUPPLY_DEMAND_LAST_MANUAL_REQUEST_AT') || '記録なし') + '\n' +
      'Gold_Demand再読込: ' + (sheetResult.dataUpdatedAt || '再計算中')
    );

    return {
      ok: true,
      generatedAt: data.generatedAt || null,
      dataStatus: dataStatus,
      assessment: assessment,
      sheetUpdatedAt: sheetResult.dataUpdatedAt || null,
      version: GOLD_SUPPLY_DEMAND_PAGE_UPDATE_VERSION
    };
  } catch (error) {
    SpreadsheetApp.getUi().alert(
      'ゴールド需給の更新状態を取得できませんでした。\n\n' +
      'コード版: ' + GOLD_SUPPLY_DEMAND_PAGE_UPDATE_VERSION + '\n' +
      '理由: ' + error.message
    );
    return { ok: false, error: error.message, version: GOLD_SUPPLY_DEMAND_PAGE_UPDATE_VERSION };
  }
}

function openGoldSupplyDemandWebPageV1() {
  var url = 'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/gold-supply-demand.html';
  var html = HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;padding:18px">' +
      '<p>ゴールド需給分析ページを開きます。</p>' +
      '<p><a href="' + url + '" target="_blank" rel="noopener">' + url + '</a></p>' +
      '<p>コード版: ' + GOLD_SUPPLY_DEMAND_PAGE_UPDATE_VERSION + '</p>' +
    '</div>'
  ).setWidth(560).setHeight(200);
  SpreadsheetApp.getUi().showModalDialog(html, 'ゴールド需給分析');
}
