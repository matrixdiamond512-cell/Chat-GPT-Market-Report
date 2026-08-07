// ゴールド需給分析 独立トップメニュー
// 既存の MarketReportMenu.gs を変更せず追加できる。

var GOLD_SUPPLY_DEMAND_MENU_VERSION = '1.0.0';
var GOLD_SUPPLY_DEMAND_MENU_HANDLER = 'createGoldSupplyDemandMenuV1_';

function installGoldSupplyDemandMenuV1() {
  var spreadsheet = SpreadsheetApp.getActive();

  ScriptApp.getProjectTriggers()
    .filter(function(trigger) {
      return trigger.getHandlerFunction() === GOLD_SUPPLY_DEMAND_MENU_HANDLER;
    })
    .forEach(function(trigger) { ScriptApp.deleteTrigger(trigger); });

  ScriptApp.newTrigger(GOLD_SUPPLY_DEMAND_MENU_HANDLER)
    .forSpreadsheet(spreadsheet)
    .onOpen()
    .create();

  createGoldSupplyDemandMenuV1_();
  SpreadsheetApp.getUi().alert(
    'ゴールド需給分析メニューを設定しました。\n' +
    'コード版: ' + GOLD_SUPPLY_DEMAND_MENU_VERSION + '\n\n' +
    '表示項目:\n' +
    '・ゴールド需給を今すぐ更新\n' +
    '・更新状態を確認\n' +
    '・ゴールド需給分析ページを開く\n\n' +
    '次回以降もスプレッドシートを開くと自動表示されます。'
  );
}

function createGoldSupplyDemandMenuV1_() {
  SpreadsheetApp.getUi()
    .createMenu('ゴールド需給分析')
    .addItem('ゴールド需給を今すぐ更新', 'runGoldSupplyDemandPageUpdateNowV1')
    .addItem('更新状態を確認', 'showGoldSupplyDemandPageUpdateStatusV1')
    .addSeparator()
    .addItem('ゴールド需給分析ページを開く', 'openGoldSupplyDemandWebPageV1')
    .addToUi();
}

function uninstallGoldSupplyDemandMenuV1() {
  var deleted = 0;
  ScriptApp.getProjectTriggers()
    .filter(function(trigger) {
      return trigger.getHandlerFunction() === GOLD_SUPPLY_DEMAND_MENU_HANDLER;
    })
    .forEach(function(trigger) {
      ScriptApp.deleteTrigger(trigger);
      deleted += 1;
    });

  SpreadsheetApp.getUi().alert(
    'ゴールド需給分析メニューの自動表示トリガーを削除しました。\n削除数: ' + deleted
  );
}
