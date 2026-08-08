// ゴールド需給分析メニューのフォールバック表示
// トリガーは作成しない。実行すると即時にメニューを表示する。

function showGoldSupplyDemandMenuNowV2() {
  var ui = SpreadsheetApp.getUi();

  ui.createMenu('ゴールド需給分析')
    .addItem('ゴールド需給を今すぐ更新', 'runGoldSupplyDemandPageUpdateNowV1')
    .addItem('更新状態を確認', 'showGoldSupplyDemandPageUpdateStatusV1')
    .addSeparator()
    .addItem('ゴールド需給分析ページを開く', 'openGoldSupplyDemandWebPageV1')
    .addToUi();

  SpreadsheetApp.getActive().toast(
    'ゴールド需給分析メニューを表示しました。',
    'WEBマーケットレポート',
    5
  );
}

function createGoldSupplyDemandSubMenuV2_() {
  return SpreadsheetApp.getUi()
    .createMenu('ゴールド需給分析')
    .addItem('ゴールド需給を今すぐ更新', 'runGoldSupplyDemandPageUpdateNowV1')
    .addItem('更新状態を確認', 'showGoldSupplyDemandPageUpdateStatusV1')
    .addSeparator()
    .addItem('ゴールド需給分析ページを開く', 'openGoldSupplyDemandWebPageV1');
}
