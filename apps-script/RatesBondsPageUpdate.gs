// 金利・債券市場 専用更新処理
// MarketReportMenu.gs から呼び出す。
// GitHub Actions APIを直接呼ばず、1回のGitHubファイル作成だけでActionsを起動する。
// V2.2: Apps Scriptの実行時間超過を避けるため、事前GETを廃止して単一PUT化。

var RATES_BONDS_PAGE_UPDATE_VERSION = '2.2.0-single-put';

function runRatesBondsPageUpdateNowV2() {
  var config = getMarketReportWebConfigForMenu_();
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');

  if (!token) {
    SpreadsheetApp.getUi().alert(
      '金利・債券市場の更新を起動できませんでした。\n\n理由: GITHUB_TOKEN が設定されていません。'
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
    'data/rates-bonds-trigger/request-' +
    fileStamp + '-' +
    now.getTime() +
    '.json';

  try {
    var result = createRatesBondsTriggerFileV2_(
      config,
      token,
      branch,
      triggerPath,
      requestedAt
    );

    PropertiesService.getScriptProperties().setProperty(
      'RATES_BONDS_LAST_MANUAL_REQUEST_AT',
      requestedAt
    );

    SpreadsheetApp.getUi().alert(
      '金利・債券市場の更新処理を起動しました。\n' +
      '起動方式: GitHubトリガーファイルを1回作成\n' +
      'コード版: ' + RATES_BONDS_PAGE_UPDATE_VERSION + '\n' +
      '取得対象: FRED / 財務省 / Bundesbank / U.S. Treasury 等\n' +
      '更新対象: data/rates-bonds.json\n\n' +
      'Apps Script側ではデータ取得を行わず、GitHub Actionsへ処理を引き渡しています。\n' +
      '反映後は「更新状態を確認」で最終更新時刻を確認してください。'
    );

    return {
      ok: true,
      queued: true,
      branch: branch,
      triggerPath: triggerPath,
      requestedAt: requestedAt,
      commitSha: result.commitSha || null,
      version: RATES_BONDS_PAGE_UPDATE_VERSION
    };
  } catch (error) {
    SpreadsheetApp.getUi().alert(
      '金利・債券市場の更新に失敗しました。\n\n' +
      'コード版: ' + RATES_BONDS_PAGE_UPDATE_VERSION + '\n' +
      '理由: ' + error.message
    );
    return {
      ok: false,
      queued: false,
      error: error.message,
      version: RATES_BONDS_PAGE_UPDATE_VERSION
    };
  }
}

function createRatesBondsTriggerFileV2_(config, token, branch, triggerPath, requestedAt) {
  var baseUrl =
    'https://api.github.com/repos/' +
    encodeURIComponent(config.owner) + '/' +
    encodeURIComponent(config.repo) +
    '/contents/' + encodeGitHubPathForRatesBondsV2_(triggerPath);

  var triggerData = {
    requestedAt: requestedAt,
    requestedBy: 'Google Sheets menu',
    purpose: 'rates-bonds-manual-update',
    updaterVersion: RATES_BONDS_PAGE_UPDATE_VERSION
  };

  var payload = {
    message: 'Trigger rates and bonds update ' + requestedAt,
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

function encodeGitHubPathForRatesBondsV2_(path) {
  return String(path || '')
    .split('/')
    .map(function(part) { return encodeURIComponent(part); })
    .join('/');
}

function showRatesBondsPageUpdateStatusV2() {
  var config = getMarketReportWebConfigForMenu_();
  var branch = config.branch || 'main';
  var url =
    'https://raw.githubusercontent.com/' +
    encodeURIComponent(config.owner) + '/' +
    encodeURIComponent(config.repo) + '/' +
    encodeURIComponent(branch) +
    '/data/rates-bonds.json?ts=' + new Date().getTime();

  try {
    var response = UrlFetchApp.fetch(url, {
      method: 'get',
      muteHttpExceptions: true,
      headers: { 'Cache-Control': 'no-cache' }
    });

    var statusCode = response.getResponseCode();
    if (statusCode !== 200) {
      throw new Error('rates-bonds.json の取得に失敗しました。HTTP ' + statusCode);
    }

    var data = JSON.parse(response.getContentText());
    var meta = data.meta || {};
    var missing = Array.isArray(meta.missingData) ? meta.missingData : [];
    var rates = Array.isArray(data.rates) ? data.rates : [];
    var confirmedCount = rates.filter(function(item) {
      return item &&
        item.status === 'confirmed' &&
        item.value !== null &&
        item.value !== undefined;
    }).length;
    var requestedAt = PropertiesService.getScriptProperties()
      .getProperty('RATES_BONDS_LAST_MANUAL_REQUEST_AT');

    var updatedAt = meta.updatedAt || data.generatedAt || '取得不能';
    var asOfDate = meta.asOfDate || '取得不能';

    SpreadsheetApp.getUi().alert(
      '金利・債券市場 更新状態\n\n' +
      'コード版: ' + RATES_BONDS_PAGE_UPDATE_VERSION + '\n' +
      'ページ状態: ' + (meta.status || '取得不能') + '\n' +
      '基準日: ' + asOfDate + '\n' +
      '最終更新: ' + updatedAt + '\n' +
      '確認済み金利: ' + confirmedCount + '件\n' +
      '欠損: ' + (missing.length ? missing.join('、') : 'なし') + '\n' +
      '手動更新要求: ' + (requestedAt || '記録なし')
    );

    return {
      ok: true,
      status: meta.status || null,
      asOfDate: meta.asOfDate || null,
      updatedAt: meta.updatedAt || data.generatedAt || null,
      confirmedCount: confirmedCount,
      missingData: missing,
      requestedAt: requestedAt || null,
      version: RATES_BONDS_PAGE_UPDATE_VERSION
    };
  } catch (error) {
    SpreadsheetApp.getUi().alert(
      '金利・債券市場の更新状態を取得できませんでした。\n\n' +
      'コード版: ' + RATES_BONDS_PAGE_UPDATE_VERSION + '\n' +
      '理由: ' + error.message
    );
    return {
      ok: false,
      error: error.message,
      version: RATES_BONDS_PAGE_UPDATE_VERSION
    };
  }
}

function openRatesBondsWebPageV2() {
  var url = 'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/rates-bonds.html';
  var html = HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;padding:18px">' +
      '<p>金利・債券市場ページを開きます。</p>' +
      '<p><a href="' + url + '" target="_blank" rel="noopener">' + url + '</a></p>' +
      '<p>コード版: ' + RATES_BONDS_PAGE_UPDATE_VERSION + '</p>' +
    '</div>'
  ).setWidth(560).setHeight(200);

  SpreadsheetApp.getUi().showModalDialog(html, '金利・債券市場');
}
