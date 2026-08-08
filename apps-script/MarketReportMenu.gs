function installMarketReportWebMenu() {
  createMarketReportWebMenu_();
  SpreadsheetApp.getActive().toast(
    'WEB版マーケットレポートのメニューを更新しました。',
    'WEB版マーケットレポート',
    4
  );
}

function onOpen(e) {
  createMarketReportWebMenu_();
}

function createMarketReportWebMenu_() {
  var ui = SpreadsheetApp.getUi();

  var advancedMenu = ui.createMenu('詳細・保守')
    .addItem('Google Docsを指定して公開', 'publishMarketReportFromDocUrlPrompt')
    .addSeparator()
    .addItem('過去レポートを一括取り込み', 'startHistoricalMarketReportImport')
    .addItem('過去レポート取り込み状況', 'showHistoricalMarketReportImportStatus')
    .addItem('過去レポート取り込み停止', 'stopHistoricalMarketReportImport')
    .addSeparator()
    .addItem('ダッシュボードJSONをプレビュー', 'previewDashboardJson')
    .addItem('ダッシュボードJSONをGitHubへ反映', 'syncDashboardJsonToGitHub')
    .addSeparator()
    .addItem('JSONを貼り付けて公開', 'showWebReportSidebar')
    .addItem('GitHub設定を確認', 'showMarketReportWebConfigStatus');

  var stockSubMenu = ui.createMenu('株式市場分析')
    .addItem('株式市場分析を今すぐ更新', 'runStockAnalysisStandaloneNow')
    .addItem('データ鮮度を確認', 'showStockAnalysisFreshnessStatus')
    .addSeparator()
    .addItem('株式市場分析ページを開く', 'showStockAnalysisWebPage');

  var nikkeiSubMenu = ui.createMenu('日経225需給分析')
    .addItem('日経225需給分析を今すぐ更新', 'runNikkei225SupplyDemandNowV1')
    .addItem('更新状態を確認', 'showNikkei225SupplyDemandStatusV1')
    .addSeparator()
    .addItem('日経225需給分析ページを開く', 'openNikkei225SupplyDemandWebPageV1');

  var goldSubMenu = ui.createMenu('ゴールド需給分析')
    .addItem('ゴールド需給を今すぐ更新', 'runGoldSupplyDemandPageUpdateNowV1')
    .addItem('更新状態を確認', 'showGoldSupplyDemandPageUpdateStatusV1')
    .addSeparator()
    .addItem('ゴールド需給分析ページを開く', 'openGoldSupplyDemandWebPageV1');

  ui.createMenu('WEB版マーケットレポート')
    .addItem('最新Google Docsをプレビュー', 'previewLatestMarketReportFromDrive')
    .addItem('最新Google DocsをWEB公開', 'publishLatestMarketReportFromDrive')
    .addSeparator()
    .addItem('本文・ダッシュボードを今すぐ更新', 'runMarketReportMasterNow')
    .addItem('本文・ダッシュボード自動更新を設定・修復', 'installMarketReportMasterSchedulerTriggers')
    .addItem('本文・ダッシュボード自動更新の状態', 'showMarketReportMasterSchedulerStatus')
    .addSeparator()
    .addSubMenu(stockSubMenu)
    .addSubMenu(nikkeiSubMenu)
    .addSubMenu(goldSubMenu)
    .addSeparator()
    .addItem('WEB版を開く', 'showMarketReportWebPage')
    .addSubMenu(advancedMenu)
    .addToUi();

  ui.createMenu('東京市場ドル円出来高')
    .addItem('東京市場ドル円出来高を今すぐ更新', 'updateUsdJpyVolumePageFromSources')
    .addItem('更新状態を確認', 'showUsdJpyVolumeUnifiedStatus')
    .addSeparator()
    .addItem('定時更新を設定', 'installUsdJpyVolumePageScheduledTriggers')
    .addItem('定時更新の状態を確認', 'showUsdJpyVolumePageScheduledStatus')
    .addItem('定時更新を削除', 'uninstallUsdJpyVolumePageScheduledTriggers')
    .addSeparator()
    .addItem('出来高JSONをプレビュー', 'previewUsdJpyVolumeJsonFlexible')
    .addItem('日銀スポット出来高の取得内容を確認', 'previewUsdJpySpotVolumeImport')
    .addItem('USD/JPY日足価格の取得内容を確認', 'previewUsdJpyInvestingPriceImport')
    .addItem('出来高JSON設定を確認', 'showUsdJpyVolumeJsonSyncStatus')
    .addItem('東京市場ドル円出来高ページを開く', 'showUsdJpyVolumeWebPage')
    .addToUi();

  ui.createMenu('USD/JPY需給分析')
    .addItem('USD/JPY需給分析を今すぐ更新（注文水準含む）', 'runUsdJpySupplyDemandPageUpdateNowV1')
    .addItem('更新状態・注文水準を確認', 'showUsdJpySupplyDemandPageUpdateStatusV1')
    .addSeparator()
    .addItem('USD/JPY需給分析ページを開く', 'openUsdJpySupplyDemandWebPageV1')
    .addToUi();

  ui.createMenu('重要イベント')
    .addItem('重要イベントを今すぐ更新', 'runImportantEventsStandaloneNow')
    .addItem('重要イベントページを開く', 'showImportantEventsWebPage')
    .addToUi();

  ui.createMenu('金利・債券市場')
    .addItem('金利・債券市場を今すぐ更新', 'runRatesBondsPageUpdateNowV2')
    .addItem('更新状態を確認', 'showRatesBondsPageUpdateStatusV2')
    .addSeparator()
    .addItem('金利・債券市場ページを開く', 'openRatesBondsWebPageV2')
    .addToUi();

  ui.createMenu('株式市場分析')
    .addItem('株式市場分析を今すぐ更新', 'runStockAnalysisStandaloneNow')
    .addItem('データ鮮度を確認', 'showStockAnalysisFreshnessStatus')
    .addSeparator()
    .addItem('株式市場分析の定時更新を設定', 'installStockAnalysisStandaloneTriggers')
    .addItem('株式市場分析の定時更新状態', 'showStockAnalysisStandaloneTriggerStatus')
    .addItem('株式市場分析の定時更新を削除', 'uninstallStockAnalysisStandaloneTriggers')
    .addItem('株式市場分析ページを開く', 'showStockAnalysisWebPage')
    .addToUi();

  ui.createMenu('日経225需給分析')
    .addItem('日経225需給分析を今すぐ更新', 'runNikkei225SupplyDemandNowV1')
    .addItem('更新状態を確認', 'showNikkei225SupplyDemandStatusV1')
    .addSeparator()
    .addItem('日経225需給分析ページを開く', 'openNikkei225SupplyDemandWebPageV1')
    .addToUi();

  ui.createMenu('ゴールド需給分析')
    .addItem('ゴールド需給を今すぐ更新', 'runGoldSupplyDemandPageUpdateNowV1')
    .addItem('更新状態を確認', 'showGoldSupplyDemandPageUpdateStatusV1')
    .addSeparator()
    .addItem('ゴールド需給分析ページを開く', 'openGoldSupplyDemandWebPageV1')
    .addToUi();
}

function runImportantEventsStandaloneNow() {
  var config = getMarketReportWebConfigForMenu_();
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) {
    SpreadsheetApp.getActive().toast('GITHUB_TOKEN が設定されていません。', '重要イベント', 6);
    return { ok: false, queued: false, error: 'GITHUB_TOKEN is not configured' };
  }

  var workflow = 'update-economic-calendar.yml';
  var apiUrl = 'https://api.github.com/repos/' + encodeURIComponent(config.owner) + '/' +
    encodeURIComponent(config.repo) + '/actions/workflows/' + encodeURIComponent(workflow) + '/dispatches';

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
    if (statusCode !== 204) throw new Error('GitHub Actionsの起動に失敗しました。HTTP ' + statusCode);
    SpreadsheetApp.getActive().toast('重要イベントの更新処理を起動しました。', '重要イベント', 5);
    return { ok: true, queued: true, workflow: workflow };
  } catch (error) {
    SpreadsheetApp.getActive().toast('更新に失敗しました: ' + error.message, '重要イベント', 8);
    return { ok: false, queued: false, error: error.message };
  }
}

function runStockAnalysisStandaloneNow() {
  if (typeof updateStockAnalysisPageSafelyForMaster_ !== 'function') {
    SpreadsheetApp.getActive().toast('StockAnalysisFreshnessGuard.gs の更新関数が見つかりません。', '株式市場分析', 8);
    return { ok: false, skipped: true, reason: 'updateStockAnalysisPageSafelyForMaster_ is not defined' };
  }
  var result = updateStockAnalysisPageSafelyForMaster_();
  if (result && result.ok && !result.skipped) {
    SpreadsheetApp.getActive().toast('株式市場分析を更新しました。', '株式市場分析', 5);
  } else {
    SpreadsheetApp.getActive().toast('株式市場分析を更新できませんでした。', '株式市場分析', 6);
  }
  return result;
}

function runNikkei225SupplyDemandNowV1() {
  var config = getMarketReportWebConfigForMenu_();
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) {
    SpreadsheetApp.getActive().toast('GITHUB_TOKEN が設定されていません。', '日経225需給分析', 6);
    return { ok: false, error: 'GITHUB_TOKEN is not configured' };
  }

  var branch = config.branch || 'main';
  var path = '.github/nikkei225-supply-demand-trigger.txt';
  var apiUrl = 'https://api.github.com/repos/' + encodeURIComponent(config.owner) + '/' +
    encodeURIComponent(config.repo) + '/contents/' + path.split('/').map(encodeURIComponent).join('/');

  try {
    var getRes = UrlFetchApp.fetch(apiUrl + '?ref=' + encodeURIComponent(branch), {
      headers: {
        Authorization: 'Bearer ' + token,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
      },
      muteHttpExceptions: true
    });
    var currentSha = null;
    if (getRes.getResponseCode() === 200) {
      currentSha = JSON.parse(getRes.getContentText()).sha || null;
    }

    var now = Utilities.formatDate(new Date(), 'Asia/Tokyo', "yyyy-MM-dd'T'HH:mm:ssXXX");
    var payload = {
      message: 'Trigger Nikkei 225 supply-demand update ' + now,
      content: Utilities.base64Encode('requestedAt=' + now + '\n', Utilities.Charset.UTF_8),
      branch: branch
    };
    if (currentSha) payload.sha = currentSha;

    var putRes = UrlFetchApp.fetch(apiUrl, {
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
    var code = putRes.getResponseCode();
    if (code !== 200 && code !== 201) {
      throw new Error('GitHubトリガーファイル更新失敗 HTTP ' + code + ' ' + String(putRes.getContentText() || '').slice(0, 300));
    }
    SpreadsheetApp.getActive().toast('日経225需給分析の更新を起動しました。', '日経225需給分析', 5);
    return { ok: true, queued: true, requestedAt: now };
  } catch (error) {
    SpreadsheetApp.getActive().toast('更新に失敗しました: ' + error.message, '日経225需給分析', 8);
    return { ok: false, error: error.message };
  }
}

function showNikkei225SupplyDemandStatusV1() {
  var url = 'https://raw.githubusercontent.com/matrixdiamond512-cell/Chat-GPT-Market-Report/main/data/nikkei225-supply-demand.json?ts=' + Date.now();
  try {
    var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, headers: { 'Cache-Control': 'no-cache' } });
    if (res.getResponseCode() !== 200) throw new Error('HTTP ' + res.getResponseCode());
    var data = JSON.parse(res.getContentText());
    var status = data.sourceStatus || data.dataStatus || {};
    var text = '最終更新: ' + (data.generatedAt || data.updatedAt || '取得不能');
    if (status && status.connected != null && status.total != null) text += ' / ' + status.connected + '/' + status.total;
    SpreadsheetApp.getActive().toast(text, '日経225需給分析', 8);
    return { ok: true, generatedAt: data.generatedAt || data.updatedAt || null, status: status };
  } catch (error) {
    SpreadsheetApp.getActive().toast('状態取得に失敗しました: ' + error.message, '日経225需給分析', 8);
    return { ok: false, error: error.message };
  }
}

function openNikkei225SupplyDemandWebPageV1() {
  showStandaloneMarketPage_(
    '日経225需給分析',
    'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/nikkei225-supply-demand.html'
  );
}

function showUsdJpyVolumeWebPage() {
  showStandaloneMarketPage_('東京市場ドル円出来高', 'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/usdjpy-volume.html');
}

function showImportantEventsWebPage() {
  showStandaloneMarketPage_('重要イベント', 'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/events.html');
}

function showStockAnalysisWebPage() {
  showStandaloneMarketPage_('株式市場分析', 'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/stocks.html');
}

function showStandaloneMarketPage_(title, url) {
  var html = HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;padding:18px"><p>' + escapeMarketReportMenuHtml_(title) +
    'ページを開きます。</p><p><a href="' + escapeMarketReportMenuHtml_(url) +
    '" target="_blank" rel="noopener">' + escapeMarketReportMenuHtml_(url) + '</a></p></div>'
  ).setWidth(560).setHeight(180);
  SpreadsheetApp.getUi().showModalDialog(html, title);
}

function showMarketReportWebConfigStatus() {
  var config = getMarketReportWebConfigForMenu_();
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  SpreadsheetApp.getActive().toast(
    'リポジトリ: ' + config.owner + '/' + config.repo + ' / GitHubトークン: ' + (token ? '設定済み' : '未設定'),
    'GitHub設定', 8
  );
}

function showMarketReportWebPage() {
  var config = getMarketReportWebConfigForMenu_();
  showStandaloneMarketPage_('WEB版マーケットレポート', config.pagesUrl);
}

function uninstallMarketReportWebMenuTrigger() {
  var handler = 'createMarketReportWebMenu_';
  var deleted = 0;
  ScriptApp.getProjectTriggers()
    .filter(function(trigger) { return trigger.getHandlerFunction() === handler; })
    .forEach(function(trigger) { ScriptApp.deleteTrigger(trigger); deleted += 1; });
  SpreadsheetApp.getActive().toast('メニュー用トリガー削除数: ' + deleted, 'WEB版マーケットレポート', 5);
}

function getMarketReportWebConfigForMenu_() {
  if (typeof WEB_REPORT_CONFIG !== 'undefined') return WEB_REPORT_CONFIG;
  if (typeof MARKET_REPORT_WEB_CONFIG !== 'undefined') return MARKET_REPORT_WEB_CONFIG;
  return {
    owner: 'matrixdiamond512-cell',
    repo: 'Chat-GPT-Market-Report',
    branch: 'main',
    targetPath: 'reports.json',
    pagesUrl: 'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/'
  };
}

function escapeMarketReportMenuHtml_(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
