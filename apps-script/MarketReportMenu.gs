function installMarketReportWebMenu() {
  createMarketReportWebMenu_();
  SpreadsheetApp.getUi().alert(
    'WEB版マーケットレポートメニューを設定しました。\n' +
    '次回以降もスプレッドシートを開くと自動表示されます。'
  );
}

function onOpen(e) {
  createMarketReportWebMenu_();
}

function createMarketReportWebMenu_() {
  const ui = SpreadsheetApp.getUi();
  const advancedMenu = ui.createMenu('詳細・保守')
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
    .addItem('共通自動更新を設定・修復', 'installMarketReportMasterSchedulerTriggers')
    .addItem('共通自動更新の状態を確認', 'showMarketReportMasterSchedulerStatus')
    .addSeparator()
    .addItem('WEB版を開く', 'showMarketReportWebPage')
    .addSubMenu(advancedMenu)
    .addToUi();
}

function showMarketReportWebConfigStatus() {
  const config = getMarketReportWebConfigForMenu_();
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');

  SpreadsheetApp.getUi().alert(
    'リポジトリ: ' + config.owner + '/' + config.repo + '\n' +
    'ブランチ: ' + config.branch + '\n' +
    '更新ファイル: ' + config.targetPath + '\n' +
    'GitHubトークン: ' + (token ? '設定済み' : '未設定')
  );
}

function showMarketReportWebPage() {
  const config = getMarketReportWebConfigForMenu_();
  const html = HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;padding:18px">' +
      '<p>WEB版マーケットレポートを開きます。</p>' +
      '<p><a href="' + config.pagesUrl + '" target="_blank" rel="noopener">' +
        config.pagesUrl +
      '</a></p>' +
    '</div>'
  ).setWidth(520).setHeight(180);

  SpreadsheetApp.getUi().showModalDialog(html, 'WEB版マーケットレポート');
}

function uninstallMarketReportWebMenuTrigger() {
  const handler = 'createMarketReportWebMenu_';
  let deleted = 0;

  ScriptApp.getProjectTriggers()
    .filter(trigger => trigger.getHandlerFunction() === handler)
    .forEach(trigger => {
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
