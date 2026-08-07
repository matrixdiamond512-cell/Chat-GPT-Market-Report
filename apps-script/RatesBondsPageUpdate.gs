// 金利・債券市場 専用更新処理
// MarketReportMenu.gs から呼び出す。
// GitHub Actions APIを直接呼ばず、トリガーファイルの更新でActionsを起動する。

function runRatesBondsStandaloneNow() {
  var config = getMarketReportWebConfigForMenu_();
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');

  if (!token) {
    SpreadsheetApp.getUi().alert(
      '金利・債券市場の更新を起動できませんでした。\n\n理由: GITHUB_TOKEN が設定されていません。'
    );
    return { ok: false, queued: false, error: 'GITHUB_TOKEN is not configured' };
  }

  var branch = config.branch || 'main';
  var triggerPath = 'data/rates-bonds-trigger.json';
  var requestedAt = Utilities.formatDate(
    new Date(),
    'Asia/Tokyo',
    "yyyy-MM-dd'T'HH:mm:ssXXX"
  );

  try {
    var result = updateRatesBondsTriggerFile_(config, token, branch, triggerPath, requestedAt);

    PropertiesService.getScriptProperties().setProperty(
      'RATES_BONDS_LAST_MANUAL_REQUEST_AT',
      requestedAt
    );

    SpreadsheetApp.getUi().alert(
      '金利・債券市場の更新処理を起動しました。\n' +
      '起動方式: GitHubトリガーファイル更新\n' +
      '取得対象: FRED / 財務省 / Bundesbank / U.S. Treasury 等\n' +
      '更新対象: data/rates-bonds.json\n\n' +
      '反映後は「更新状態を確認」で最終更新時刻を確認してください。'
    );

    return {
      ok: true,
      queued: true,
      branch: branch,
      triggerPath: triggerPath,
      requestedAt: requestedAt,
      commitSha: result.commitSha || null
    };
  } catch (error) {
    SpreadsheetApp.getUi().alert(
      '金利・債券市場の更新に失敗しました。\n\n理由: ' + error.message
    );
    return { ok: false, queued: false, error: error.message };
  }
}

function updateRatesBondsTriggerFile_(config, token, branch, triggerPath, requestedAt) {
  var baseUrl =
    'https://api.github.com/repos/' +
    encodeURIComponent(config.owner) + '/' +
    encodeURIComponent(config.repo) +
    '/contents/' + encodeGitHubPathForRatesBonds_(triggerPath);

  var headers = {
    Authorization: 'Bearer ' + token,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };

  var getResponse = UrlFetchApp.fetch(baseUrl + '?ref=' + encodeURIComponent(branch), {
    method: 'get',
    headers: headers,
    muteHttpExceptions: true
  });

  var getStatus = getResponse.getResponseCode();
  if (getStatus !== 200 && getStatus !== 404) {
    throw new Error(
      'GitHubトリガーファイルの確認に失敗しました。HTTP ' + getStatus + '\n' +
      String(getResponse.getContentText() || '').slice(0, 500)
    );
  }

  var currentSha = null;
  if (getStatus === 200) {
    var current = JSON.parse(getResponse.getContentText());
    currentSha = current.sha || null;
  }

  var triggerData = {
    requestedAt: requestedAt,
    requestedBy: 'Google Sheets menu',
    purpose: 'rates-bonds-manual-update'
  };

  var payload = {
    message: 'Trigger rates and bonds update ' + requestedAt,
    content: Utilities.base64Encode(
      JSON.stringify(triggerData, null, 2) + '\n',
      Utilities.Charset.UTF_8
    ),
    branch: branch
  };
  if (currentSha) payload.sha = currentSha;

  var putResponse = UrlFetchApp.fetch(baseUrl, {
    method: 'put',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    headers: headers,
    muteHttpExceptions: true
  });

  var putStatus = putResponse.getResponseCode();
  if (putStatus !== 200 && putStatus !== 201) {
    var body = String(putResponse.getContentText() || '').slice(0, 500);
    if (putStatus === 403) {
      throw new Error(
        'GitHubファイル更新権限がありません。GITHUB_TOKEN に Contents の Read and write 権限が必要です。\n' +
        'HTTP 403\n' + body
      );
    }
    throw new Error(
      'GitHubトリガーファイルの更新に失敗しました。HTTP ' + putStatus + '\n' + body
    );
  }

  var updated = JSON.parse(putResponse.getContentText());
  return {
    ok: true,
    commitSha: updated.commit && updated.commit.sha ? updated.commit.sha : null,
    contentSha: updated.content && updated.content.sha ? updated.content.sha : null
  };
}

function encodeGitHubPathForRatesBonds_(path) {
  return String(path || '')
    .split('/')
    .map(function(part) { return encodeURIComponent(part); })
    .join('/');
}

function showRatesBondsUpdateStatus() {
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
      requestedAt: requestedAt || null
    };
  } catch (error) {
    SpreadsheetApp.getUi().alert(
      '金利・債券市場の更新状態を取得できませんでした。\n\n理由: ' + error.message
    );
    return { ok: false, error: error.message };
  }
}

function showRatesBondsWebPage() {
  var url = 'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/rates-bonds.html';
  var html = HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;padding:18px">' +
      '<p>金利・債券市場ページを開きます。</p>' +
      '<p><a href="' + url + '" target="_blank" rel="noopener">' + url + '</a></p>' +
    '</div>'
  ).setWidth(560).setHeight(180);

  SpreadsheetApp.getUi().showModalDialog(html, '金利・債券市場');
}
