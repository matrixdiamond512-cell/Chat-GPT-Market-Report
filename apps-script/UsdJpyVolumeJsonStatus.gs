function showUsdJpyVolumeJsonSyncStatus() {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('GITHUB_TOKEN');
  const priceRangeStart = props.getProperty(USDJPY_VOLUME_JSON_CONFIG.properties.priceRangeStart) || '未設定';
  const priceRangeEnd = props.getProperty(USDJPY_VOLUME_JSON_CONFIG.properties.priceRangeEnd) || '未設定';
  const priceRangeCount = props.getProperty(USDJPY_VOLUME_JSON_CONFIG.properties.priceRangeCount) || '未設定';
  const lastResult = props.getProperty(USDJPY_VOLUME_JSON_CONFIG.properties.lastResult) || '未実行';

  usdJpyVolumeAlert_(
    'USD/JPY出来高JSON同期設定\n' +
    'リポジトリ: ' + WEB_REPORT_CONFIG.owner + '/' + WEB_REPORT_CONFIG.repo + '\n' +
    'ブランチ: ' + WEB_REPORT_CONFIG.branch + '\n' +
    '対象シート: ' + USDJPY_VOLUME_JSON_CONFIG.sheetName + '\n' +
    '更新ファイル: ' + USDJPY_VOLUME_JSON_CONFIG.targetPath + '\n' +
    'GitHubトークン: ' + (token ? '設定済み' : '未設定') + '\n' +
    '価格範囲開始: ' + priceRangeStart + '\n' +
    '価格範囲終了: ' + priceRangeEnd + '\n' +
    '価格件数: ' + priceRangeCount + '\n' +
    '前回結果: ' + lastResult
  );
}
