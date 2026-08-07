// USD/JPY需給分析 専用更新処理
// MarketReportMenu.gs から呼び出す。
// Apps Script側では重いデータ取得を行わず、GitHubに1回だけトリガーファイルを作成する。
// GitHub Actions側で既存JSONを集約し、CFTCとTraders Web FX無料ページの主要注文水準を更新する。

var USDJPY_SUPPLY_DEMAND_PAGE_UPDATE_VERSION = '1.1.0-key-levels';

function runUsdJpySupplyDemandPageUpdateNowV1() {
  var config = getMarketReportWebConfigForMenu_();
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) {
    SpreadsheetApp.getUi().alert(
      'USD/JPY需給分析の更新を起動できませんでした。\n\n理由: GITHUB_TOKEN が設定されていません。'
    );
    return { ok: false, queued: false, error: 'GITHUB_TOKEN is not configured' };
  }

  var branch = config.branch || 'main';
  var now = new Date();
  var requestedAt = Utilities.formatDate(
    now,
    'Asia/Tokyo',
    "yyyy-MM-dd'T'HH:mm:ssXXX"
  );
  var fileStamp = Utilities.formatDate(now, 'Asia/Tokyo', 'yyyyMMdd-HHmmss');
  var triggerPath =
    'data/usdjpy-supply-demand-trigger/request-' +
    fileStamp + '-' +
    now.getTime() +
    '.json';

  try {
    var result = createUsdJpySupplyDemandTriggerFileV1_(
      config,
      token,
      branch,
      triggerPath,
      requestedAt
    );

    PropertiesService.getScriptProperties().setProperty(
      'USDJPY_SUPPLY_DEMAND_LAST_MANUAL_REQUEST_AT',
      requestedAt
    );

    SpreadsheetApp.getUi().alert(
      'USD/JPY需給分析の更新処理を起動しました。\n\n' +
      '起動方式: GitHubトリガーファイルを1回作成\n' +
      'コード版: ' + USDJPY_SUPPLY_DEMAND_PAGE_UPDATE_VERSION + '\n' +
      '中核データ: market/latest.json / rates-bonds.json / usdjpy-volume.json / events.json\n' +
      '補助更新: CFTC円先物\n' +
      'Traders Web FX: 売り注文 / 買い注文 / ストップ / NYカット主要水準\n' +
      '更新対象: data/usdjpy-supply-demand.json\n\n' +
      'Apps Script側では重い取得処理を行いません。\n' +
      '反映後は「更新状態・注文水準を確認」で取得件数と基準日時を確認してください。'
    );

    return {
      ok: true,
      queued: true,
      triggerPath: triggerPath,
      commitSha: result.commitSha || null,
      requestedAt: requestedAt,
      version: USDJPY_SUPPLY_DEMAND_PAGE_UPDATE_VERSION
    };
  } catch (error) {
    SpreadsheetApp.getUi().alert(
      'USD/JPY需給分析の更新に失敗しました。\n\n' +
      'コード版: ' + USDJPY_SUPPLY_DEMAND_PAGE_UPDATE_VERSION + '\n' +
      '理由: ' + error.message
    );
    return {
      ok: false,
      queued: false,
      error: error.message,
      version: USDJPY_SUPPLY_DEMAND_PAGE_UPDATE_VERSION
    };
  }
}

function createUsdJpySupplyDemandTriggerFileV1_(config, token, branch, triggerPath, requestedAt) {
  var apiUrl =
    'https://api.github.com/repos/' +
    encodeURIComponent(config.owner) + '/' +
    encodeURIComponent(config.repo) +
    '/contents/' + encodeGitHubPathForUsdJpySupplyDemandV1_(triggerPath);

  var triggerData = {
    requestedAt: requestedAt,
    requestedBy: 'Google Sheets menu',
    page: 'usdjpy-supply-demand',
    mode: 'lightweight-integration-and-order-level-refresh',
    version: USDJPY_SUPPLY_DEMAND_PAGE_UPDATE_VERSION
  };

  var payload = {
    message: 'Trigger USDJPY supply-demand update ' + requestedAt,
    content: Utilities.base64Encode(
      Utilities.newBlob(JSON.stringify(triggerData, null, 2), 'application/json').getBytes()
    ),
    branch: branch
  };

  var response = UrlFetchApp.fetch(apiUrl, {
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
    var body = String(response.getContentText() || '').slice(0, 700);
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

function showUsdJpySupplyDemandPageUpdateStatusV1() {
  var config = getMarketReportWebConfigForMenu_();
  var url =
    'https://raw.githubusercontent.com/' +
    encodeURIComponent(config.owner) + '/' +
    encodeURIComponent(config.repo) + '/' +
    encodeURIComponent(config.branch || 'main') +
    '/data/usdjpy-supply-demand.json?ts=' + new Date().getTime();

  try {
    var response = UrlFetchApp.fetch(url, {
      method: 'get',
      muteHttpExceptions: true,
      headers: { 'Cache-Control': 'no-cache' }
    });
    var statusCode = response.getResponseCode();
    if (statusCode !== 200) {
      throw new Error('usdjpy-supply-demand.json の取得に失敗しました。HTTP ' + statusCode);
    }

    var data = JSON.parse(response.getContentText());
    var tw = data.tradersWebFx || {};
    var levels = tw.keyLevels || {};
    var cftc = data.cftc || {};
    var sourceStatus = data.sourceStatus || {};
    var requestedAt = PropertiesService.getScriptProperties().getProperty(
      'USDJPY_SUPPLY_DEMAND_LAST_MANUAL_REQUEST_AT'
    );

    var sellCount = Array.isArray(levels.sellOrders) ? levels.sellOrders.length : 0;
    var buyCount = Array.isArray(levels.buyOrders) ? levels.buyOrders.length : 0;
    var stopCount = Array.isArray(levels.stops) ? levels.stops.length : 0;
    var optionCount = Array.isArray(levels.nyCutOptions) ? levels.nyCutOptions.length : 0;
    var rowCount = Number(levels.extractedRowCount || 0);
    var freshnessText = getUsdJpySupplyDemandFreshnessLabelV1_(tw.freshness);

    SpreadsheetApp.getUi().alert(
      'USD/JPY需給分析 更新状態\n\n' +
      '最終集約更新: ' + (data.generatedAt || '取得不能') + '\n' +
      'Traders Web FX 基準日時: ' + (tw.sourceUpdatedAt || '取得不能') + '\n' +
      'Traders Web FX 最終取得確認: ' + (tw.checkedAt || '取得不能') + '\n' +
      'Traders Web FX 状態: ' + (sourceStatus.tradersWebFx || tw.status || '取得不能') + '\n' +
      '鮮度: ' + freshnessText + '\n' +
      '基準時点レート: ' + (levels.referenceSpot ? levels.referenceSpot + '円' : '取得不能') + '\n' +
      '抽出行数: ' + (rowCount || '取得不能') + '\n' +
      '売り注文: ' + sellCount + '件\n' +
      '買い注文: ' + buyCount + '件\n' +
      'ストップ: ' + stopCount + '件\n' +
      'NYカット: ' + optionCount + '件\n\n' +
      'CFTC基準日: ' + (cftc.asOf || '取得不能') + '\n' +
      'CFTC状態: ' + (sourceStatus.cftc || cftc.status || '取得不能') + '\n' +
      '中核JSON: ' + (sourceStatus.core || '取得不能') + '\n' +
      '手動更新要求: ' + (requestedAt || '記録なし')
    );

    return {
      ok: true,
      generatedAt: data.generatedAt || null,
      tradersWebFxAsOf: tw.sourceUpdatedAt || null,
      tradersWebFxCheckedAt: tw.checkedAt || null,
      tradersWebFxStatus: sourceStatus.tradersWebFx || tw.status || null,
      tradersWebFxFreshness: tw.freshness || null,
      referenceSpot: levels.referenceSpot || null,
      extractedRowCount: rowCount,
      sellOrderCount: sellCount,
      buyOrderCount: buyCount,
      stopCount: stopCount,
      nyCutOptionCount: optionCount,
      cftcAsOf: cftc.asOf || null,
      cftcStatus: sourceStatus.cftc || cftc.status || null,
      requestedAt: requestedAt || null
    };
  } catch (error) {
    SpreadsheetApp.getUi().alert(
      'USD/JPY需給分析の更新状態を取得できませんでした。\n\n理由: ' + error.message
    );
    return { ok: false, error: error.message };
  }
}

function getUsdJpySupplyDemandFreshnessLabelV1_(freshness) {
  if (freshness === 'today') return '当日データ';
  if (freshness === 'previous-session') return '前営業日データ';
  if (freshness === 'stale') return '古いデータ・要注意';
  return '判定不能';
}

function openUsdJpySupplyDemandWebPageV1() {
  showStandaloneMarketPage_(
    'USD/JPY需給分析',
    'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/usdjpy-supply-demand.html'
  );
}

function encodeGitHubPathForUsdJpySupplyDemandV1_(path) {
  return String(path || '')
    .split('/')
    .map(function(part) { return encodeURIComponent(part); })
    .join('/');
}
