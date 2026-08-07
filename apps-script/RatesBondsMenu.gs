function runRatesBondsStandaloneNow() {
  var config = getMarketReportWebConfigForMenu_();
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) {
    SpreadsheetApp.getUi().alert(
      '金利・債券市場の更新を起動できませんでした。\n\n理由: GITHUB_TOKEN が設定されていません。'
    );
    return { ok: false, queued: false, error: 'GITHUB_TOKEN is not configured' };
  }

  var workflow = 'update-rates-bonds.yml';
  var apiUrl =
    'https://api.github.com/repos/' +
    encodeURIComponent(config.owner) + '/' +
    encodeURIComponent(config.repo) +
    '/actions/workflows/' + encodeURIComponent(workflow) + '/dispatches';

  try {
    var response = UrlFetchApp.fetch(apiUrl, {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify({ ref: config.branch || 'main' }),
      headers: {
        Authorization: 'Bearer ' + token,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
      },
      muteHttpExceptions: true
    });
    var statusCode = response.getResponseCode();
    if (statusCode !== 204) {
      throw new Error(
        'GitHub Actionsの起動に失敗しました。HTTP ' + statusCode + '\n' +
        String(response.getContentText() || '').slice(0, 500)
      );
    }

    PropertiesService.getScriptProperties().setProperty(
      'RATES_BONDS_LAST_MANUAL_REQUEST_AT',
      Utilities.formatDate(new Date(), 'Asia/Tokyo', "yyyy-MM-dd'T'HH:mm:ssXXX")
    );

    SpreadsheetApp.getUi().alert(
      '金利・債券市場の更新処理を起動しました。\n' +
      'FRED・財務省・Bundesbank・U.S. Treasury等からデータを取得し、\n' +
      'data/rates-bonds.json を更新します。\n\n' +
      '「更新状態を確認」で反映時刻を確認できます。'
    );
    return {
      ok: true,
      queued: true,
      workflow: workflow,
      branch: config.branch || 'main',
      statusCode: statusCode
    };
  } catch (error) {
    SpreadsheetApp.getUi().alert('金利・債券市場の更新に失敗しました。\n\n理由: ' + error.message);
    return { ok: false, queued: false, error: error.message };
  }
}

function showRatesBondsUpdateStatus() {
  var config = getMarketReportWebConfigForMenu_();
  var url =
    'https://raw.githubusercontent.com/' +
    encodeURIComponent(config.owner) + '/' +
    encodeURIComponent(config.repo) + '/' +
    encodeURIComponent(config.branch || 'main') +
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
      return item && item.status === 'confirmed' && item.value !== null && item.value !== undefined;
    }).length;
    var requestedAt = PropertiesService.getScriptProperties().getProperty('RATES_BONDS_LAST_MANUAL_REQUEST_AT');

    SpreadsheetApp.getUi().alert(
      '金利・債券市場 更新状態\n\n' +
      'ページ状態: ' + (meta.status || '取得不能') + '\n' +
      '基準日: ' + (meta.asOfDate || '取得不能') + '\n' +
      '最終更新: ' + (meta.updatedAt || data.generatedAt || '取得不能') + '\n' +
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
    SpreadsheetApp.getUi().alert('金利・債券市場の更新状態を取得できませんでした。\n\n理由: ' + error.message);
    return { ok: false, error: error.message };
  }
}

function showRatesBondsWebPage() {
  showStandaloneMarketPage_(
    '金利・債券市場',
    'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/rates-bonds.html'
  );
}
