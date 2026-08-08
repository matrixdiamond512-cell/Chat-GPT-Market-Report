// ゴールド需給分析 独立トップメニュー
// メニュー表示は MarketReportMenu.gs の共通 onOpen から呼び出す。
// ゴールド専用のインストール型 onOpen トリガーは作成しない。

var GOLD_SUPPLY_DEMAND_MENU_VERSION = '1.1.0';
var GOLD_SUPPLY_DEMAND_MENU_HANDLER = 'createGoldSupplyDemandMenuV1_';

function installGoldSupplyDemandMenuV1() {
  // 旧版で作成されたゴールド専用トリガーがあれば削除する。
  var deleted = cleanupGoldSupplyDemandMenuLegacyTriggersV1_();

  // 現在の画面には即時表示する。次回以降は MarketReportMenu.gs の共通 onOpen が表示する。
  createGoldSupplyDemandMenuV1_();

  SpreadsheetApp.getUi().alert(
    'ゴールド需給分析メニューを設定しました。\n' +
    'コード版: ' + GOLD_SUPPLY_DEMAND_MENU_VERSION + '\n' +
    '旧ゴールド専用トリガー削除数: ' + deleted + '\n\n' +
    '表示項目:\n' +
    '・ゴールド需給を今すぐ更新\n' +
    '・更新状態を確認\n' +
    '・ゴールド需給分析ページを開く\n\n' +
    '新しいトリガーは作成していません。\n' +
    '次回以降は既存の共通 onOpen から自動表示されます。'
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

function cleanupGoldSupplyDemandMenuLegacyTriggersV1_() {
  var deleted = 0;
  ScriptApp.getProjectTriggers()
    .filter(function(trigger) {
      return trigger.getHandlerFunction() === GOLD_SUPPLY_DEMAND_MENU_HANDLER;
    })
    .forEach(function(trigger) {
      ScriptApp.deleteTrigger(trigger);
      deleted += 1;
    });
  return deleted;
}

function uninstallGoldSupplyDemandMenuV1() {
  var deleted = cleanupGoldSupplyDemandMenuLegacyTriggersV1_();
  SpreadsheetApp.getUi().alert(
    '旧ゴールド需給分析メニュー用トリガーを削除しました。\n削除数: ' + deleted + '\n\n' +
    '現在のメニュー表示は共通 onOpen 方式のため、この操作では共通 onOpen は削除しません。'
  );
}
