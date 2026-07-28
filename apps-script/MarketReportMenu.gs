function installMarketReportWebMenu() {
  const spreadsheet = SpreadsheetApp.getActive();
  const handler = 'createMarketReportWebMenu_';

  ScriptApp.getProjectTriggers()
    .filter(trigger => trigger.getHandlerFunction() === handler)
    .forEach(trigger => ScriptApp.deleteTrigger(trigger));

  ScriptApp.newTrigger(handler)
    .forSpreadsheet(spreadsheet)
    .onOpen()
    .create();

  createMarketReportWebMenu_();
  SpreadsheetApp.getUi().alert(
    'WEB版レポートメニューを設定しました。\n' +
    '次回以降もスプレッドシートを開くと自動表示されます。'
  );
}

function createMarketReportWebMenu_() {
  SpreadsheetApp.getUi()
    .createMenu('WEB版マーケットレポート')
    .addItem('最新Google Docsをプレビュー', 'previewLatestMarketReportFromDrive')
    .addItem('最新Google DocsをWEB公開', 'publishLatestMarketReportFromDrive')
    .addSeparator()
    .addItem('Google Docsを指定して公開', 'publishMarketReportFromDocUrlPrompt')
    .addItem('JSONを貼り付けて公開', 'showWebReportSidebar')
    .addSeparator()
    .addItem('GitHub設定を確認', 'showMarketReportWebConfigStatus')
    .addItem('WEB版を開く', 'showMarketReportWebPage')
    .addToUi();
}

function showMarketReportWebConfigStatus() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  SpreadsheetApp.getUi().alert(
    'リポジトリ: ' + WEB_REPORT_CONFIG.owner + '/' + WEB_REPORT_CONFIG.repo + '\n' +
    'ブランチ: ' + WEB_REPORT_CONFIG.branch + '\n' +
    '更新ファイル: ' + WEB_REPORT_CONFIG.targetPath + '\n' +
    'GitHubトークン: ' + (token ? '設定済み' : '未設定')
  );
}

function showMarketReportWebPage() {
  const html = HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;padding:18px">' +
      '<p>WEB版マーケットレポートを開きます。</p>' +
      '<p><a href="' + WEB_REPORT_CONFIG.pagesUrl + '" target="_blank" rel="noopener">' +
        WEB_REPORT_CONFIG.pagesUrl +
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
