function installMarketReportWebMenu() {
  createMarketReportWebMenu_();
  SpreadsheetApp.getUi().alert(
    'WEB版マーケットレポートメニューを設定しました。\n' +
    '本文・ダッシュボード、重要イベント、株式市場分析は別メニューです。\n' +
    '次回以降もスプレッドシートを開くと自動表示されます。'
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
    .addItem('USD/JPY出来高JSONをプレビュー', 'previewUsdJpyVolumeJsonFlexible')
    .addItem('日銀スポット出来高の取得内容を確認', 'previewUsdJpySpotVolumeImport')
    .addItem('USD/JPY日足価格の取得内容を確認', 'previewUsdJpyInvestingPriceImport')
    .addItem('USD/JPY出来高JSON設定を確認', 'showUsdJpyVolumeJsonSyncStatus')
    .addSeparator()
    .addItem('JSONを貼り付けて公開', 'showWebReportSidebar')
    .addItem('GitHub設定を確認', 'showMarketReportWebConfigStatus');

  ui.createMenu('WEB版マーケットレポート')
    .addItem('最新Google Docsをプレビュー', 'previewLatestMarketReportFromDrive')
    .addItem('最新Google DocsをWEB公開', 'publishLatestMarketReportFromDrive')
    .addSeparator()
    .addItem('東京市場ドル円出来高を今すぐ更新', 'updateUsdJpyVolumePageFromSources')
    .addItem('東京市場ドル円出来高の状態を確認', 'showUsdJpyVolumeUnifiedStatus')
    .addSeparator()
    .addItem('本文・ダッシュボードを今すぐ更新', 'runMarketReportMasterNow')
    .addItem('本文・ダッシュボード自動更新を設定・修復', 'installMarketReportMasterSchedulerTriggers')
    .addItem('本文・ダッシュボード自動更新の状態', 'showMarketReportMasterSchedulerStatus')
    .addSeparator()
    .addItem('WEB版を開く', 'showMarketReportWebPage')
    .addSubMenu(advancedMenu)
    .addToUi();

  ui.createMenu('重要イベント')
    .addItem('重要イベントを今すぐ更新', 'runImportantEventsStandaloneNow')
    .addItem('重要イベントページを開く', 'showImportantEventsWebPage')
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
}

function runImportantEventsStandaloneNow() {
  if (typeof syncEventsJsonToGitHub !== 'function') {
    SpreadsheetApp.getUi().alert('重要イベントの更新関数 syncEventsJsonToGitHub が見つかりません。');
    return { ok: false, skipped: false, error: 'syncEventsJsonToGitHub is not defined' };
  }
  try {
    return syncEventsJsonToGitHub();
  } catch (error) {
    SpreadsheetApp.getUi().alert('重要イベントの更新に失敗しました。\n\n理由: ' + error.message);
    return { ok: false, skipped: false, error: error.message };
  }
}

function runStockAnalysisStandaloneNow() {
  if (typeof updateStockAnalysisPageSafelyForMaster_ !== 'function') {
    SpreadsheetApp.getUi().alert(
      '株式市場分析の安全更新関数が見つかりません。\n' +
      'StockAnalysisFreshnessGuard.gsを追加してください。'
    );
    return { ok: false, skipped: true, reason: 'updateStockAnalysisPageSafelyForMaster_ is not defined' };
  }
  var result = updateStockAnalysisPageSafelyForMaster_();
  if (result && result.ok && !result.skipped) {
    SpreadsheetApp.getUi().alert(
      '株式市場分析を更新しました。\n' +
      '基準日: ' + (result.dataAsOf || '取得不能') + '\n' +
      'コミット: ' + (result.commitSha || '取得不能')
    );
  } else if (result && result.skipped) {
    SpreadsheetApp.getUi().alert(
      '株式市場分析の更新を停止しました。\n\n理由: ' +
      (result.reason || 'データ鮮度の条件を満たしていません。')
    );
  } else {
    SpreadsheetApp.getUi().alert(
      '株式市場分析の更新に失敗しました。\n\n理由: ' +
      (result && (result.error || result.reason) ? (result.error || result.reason) : '不明なエラー')
    );
  }
  return result;
}

function showImportantEventsWebPage() {
  showStandaloneMarketPage_('重要イベント', 'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/events.html');
}

function showStockAnalysisWebPage() {
  showStandaloneMarketPage_('株式市場分析', 'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/stocks.html');
}

function showStandaloneMarketPage_(title, url) {
  var html = HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;padding:18px">' +
      '<p>' + escapeMarketReportMenuHtml_(title) + 'ページを開きます。</p>' +
      '<p><a href="' + escapeMarketReportMenuHtml_(url) + '" target="_blank" rel="noopener">' +
        escapeMarketReportMenuHtml_(url) +
      '</a></p>' +
    '</div>'
  ).setWidth(560).setHeight(180);
  SpreadsheetApp.getUi().showModalDialog(html, title);
}

function showMarketReportWebConfigStatus() {
  var config = getMarketReportWebConfigForMenu_();
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  SpreadsheetApp.getUi().alert(
    'リポジトリ: ' + config.owner + '/' + config.repo + '\n' +
    'ブランチ: ' + config.branch + '\n' +
    '更新ファイル: ' + config.targetPath + '\n' +
    'GitHubトークン: ' + (token ? '設定済み' : '未設定')
  );
}

function showMarketReportWebPage() {
  var config = getMarketReportWebConfigForMenu_();
  var html = HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;padding:18px">' +
      '<p>WEB版マーケットレポートを開きます。</p>' +
      '<p><a href="' + config.pagesUrl + '" target="_blank" rel="noopener">' + config.pagesUrl + '</a></p>' +
    '</div>'
  ).setWidth(520).setHeight(180);
  SpreadsheetApp.getUi().showModalDialog(html, 'WEB版マーケットレポート');
}

function uninstallMarketReportWebMenuTrigger() {
  var handler = 'createMarketReportWebMenu_';
  var deleted = 0;
  ScriptApp.getProjectTriggers()
    .filter(function(trigger) { return trigger.getHandlerFunction() === handler; })
    .forEach(function(trigger) {
      ScriptApp.deleteTrigger(trigger);
      deleted += 1;
    });
  SpreadsheetApp.getUi().alert('メニュー用トリガーを削除しました。削除数: ' + deleted);
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
