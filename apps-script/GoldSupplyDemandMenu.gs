// ゴールド需給分析 独立トップメニュー
// メニュー表示は MarketReportMenu.gs の共通 onOpen から呼び出す。
// ゴールド専用のインストール型 onOpen トリガーは作成しない。

var GOLD_SUPPLY_DEMAND_MENU_VERSION = '1.1.1';
var GOLD_SUPPLY_DEMAND_MENU_HANDLER = 'createGoldSupplyDemandMenuV1_';

function installGoldSupplyDemandMenuV1() {
  // メニュー表示だけを即時実行する。
  // トリガーの作成・削除や blocking alert は行わないため、Apps Script エディタから実行してもすぐ終了する。
  createGoldSupplyDemandMenuV1_();

  var spreadsheet = SpreadsheetApp.getActive();
  if (spreadsheet) {
    spreadsheet.toast(
      'ゴールド需給分析メニューを表示しました。コード版: ' + GOLD_SUPPLY_DEMAND_MENU_VERSION,
      'ゴールド需給分析',
      5
    );
  }
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

// 旧版で作られたゴールド専用 onOpen トリガーを整理したい場合だけ、手動でこの関数を実行する。
function cleanupGoldSupplyDemandMenuLegacyTriggersV1() {
  var deleted = cleanupGoldSupplyDemandMenuLegacyTriggersV1_();
  var spreadsheet = SpreadsheetApp.getActive();
  if (spreadsheet) {
    spreadsheet.toast(
      '旧ゴールド専用トリガーを削除しました。削除数: ' + deleted,
      'ゴールド需給分析',
      5
    );
  }
  return deleted;
}

function uninstallGoldSupplyDemandMenuV1() {
  var deleted = cleanupGoldSupplyDemandMenuLegacyTriggersV1_();
  var spreadsheet = SpreadsheetApp.getActive();
  if (spreadsheet) {
    spreadsheet.toast(
      '旧ゴールド需給分析メニュー用トリガーを削除しました。削除数: ' + deleted,
      'ゴールド需給分析',
      5
    );
  }
}
