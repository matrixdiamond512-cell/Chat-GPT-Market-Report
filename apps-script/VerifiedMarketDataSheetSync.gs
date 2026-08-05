var VERIFIED_MARKET_DATA_SHEET_CONFIG = {
  jsonUrl: 'https://raw.githubusercontent.com/matrixdiamond512-cell/Chat-GPT-Market-Report/main/data/market/latest.json',
  inputSheetName: 'ChatGPT_Market_Input',
  historySheetName: 'Market_Data_Verified',
  rulesSheetName: 'ChatGPT_Market_Rules',
  lastResultProperty: 'VERIFIED_MARKET_DATA_SHEET_LAST_RESULT',
  marketOrder: [
    'gold',
    'wti',
    'nikkei225_futures_ose',
    'usdjpy',
    'eurusd',
    'btcusd',
    'vix',
    'nikkei_vi',
    'fear_greed'
  ]
};

var VERIFIED_MARKET_DATA_HEADERS = [
  'スナップショットID', '更新日時', '対象レポート時刻', '全体状態',
  '銘柄ID', 'データ名', '利用判定', '現在値', '表示値', '単位',
  '前回値', '前回比', '前回比率(%)', '前回比表示', '対象時刻', '取得時刻',
  '検証状態', '鮮度', '前回確認値利用', '最終確認時刻', '取得元', '取得元URL',
  '市場区分', 'セッション', '判定区分', '注記', 'エラー'
];

function syncVerifiedMarketDataToChatGptSheets() {
  var lock = LockService.getDocumentLock();
  if (lock && !lock.tryLock(5000)) {
    return verifiedMarketDataSaveResult_({
      ok: true,
      skipped: true,
      reason: '別の更新処理が実行中のため、今回はスキップしました。'
    });
  }

  try {
    var payload = verifiedMarketDataFetchLatest_();
    var summary = verifiedMarketDataWritePayload_(payload);
    summary.ok = true;
    summary.skipped = false;
    return verifiedMarketDataSaveResult_(summary);
  } catch (error) {
    verifiedMarketDataSaveResult_({
      ok: false,
      skipped: false,
      error: error.message,
      stack: error.stack || ''
    });
    throw error;
  } finally {
    if (lock) lock.releaseLock();
  }
}

function previewVerifiedMarketDataForChatGpt() {
  var payload = verifiedMarketDataFetchLatest_();
  var rows = verifiedMarketDataRows_(payload);
  var preview = {
    generatedAt: payload.generatedAt,
    reportSlot: payload.reportSlot,
    overallStatus: payload.overallStatus,
    markets: rows.map(function(row) {
      return {
        id: row[4],
        name: row[5],
        usePolicy: row[6],
        value: row[8],
        unit: row[9],
        asOf: row[14],
        source: row[20]
      };
    })
  };
  var html = HtmlService.createHtmlOutput(
    '<pre style="white-space:pre-wrap;font-size:12px">' +
    verifiedMarketDataEscapeHtml_(JSON.stringify(preview, null, 2)) +
    '</pre>'
  ).setWidth(860).setHeight(680);
  SpreadsheetApp.getUi().showModalDialog(html, '検証済み市場データの確認');
  return preview;
}

function showVerifiedMarketDataSheetSyncStatus() {
  var last = PropertiesService.getScriptProperties()
    .getProperty(VERIFIED_MARKET_DATA_SHEET_CONFIG.lastResultProperty) || '実行履歴はありません。';
  SpreadsheetApp.getUi().alert(
    '最新入力シート: ' + VERIFIED_MARKET_DATA_SHEET_CONFIG.inputSheetName + '\n' +
    '履歴シート: ' + VERIFIED_MARKET_DATA_SHEET_CONFIG.historySheetName + '\n' +
    'ルールシート: ' + VERIFIED_MARKET_DATA_SHEET_CONFIG.rulesSheetName + '\n\n' +
    '最終結果:\n' + last
  );
  return last;
}

function verifiedMarketDataFetchLatest_() {
  var url = VERIFIED_MARKET_DATA_SHEET_CONFIG.jsonUrl + '?t=' + new Date().getTime();
  var response = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    followRedirects: true,
    headers: { Accept: 'application/json' }
  });
  var status = response.getResponseCode();
  if (status < 200 || status >= 300) {
    throw new Error('検証済み市場データを取得できませんでした。HTTP ' + status);
  }

  var payload;
  try {
    payload = JSON.parse(response.getContentText('UTF-8'));
  } catch (error) {
    throw new Error('検証済み市場データJSONを読み取れませんでした。' + error.message);
  }
  if (!payload || !payload.markets || typeof payload.markets !== 'object') {
    throw new Error('検証済み市場データに markets がありません。');
  }
  if (payload.overallStatus === 'blocked') {
    throw new Error('市場データが blocked のため、ChatGPT入力シートを上書きしません。');
  }
  return payload;
}

function verifiedMarketDataWritePayload_(payload) {
  var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  var rows = verifiedMarketDataRows_(payload);
  if (!rows.length) throw new Error('シートへ保存できる市場データがありません。');

  var inputSheet = verifiedMarketDataEnsureSheet_(spreadsheet, VERIFIED_MARKET_DATA_SHEET_CONFIG.inputSheetName);
  inputSheet.clearContents();
  inputSheet.getRange(1, 1, rows.length + 1, VERIFIED_MARKET_DATA_HEADERS.length)
    .setValues([VERIFIED_MARKET_DATA_HEADERS].concat(rows));
  verifiedMarketDataFormatSheet_(inputSheet, rows.length + 1, VERIFIED_MARKET_DATA_HEADERS.length);

  var historySheet = verifiedMarketDataEnsureSheet_(spreadsheet, VERIFIED_MARKET_DATA_SHEET_CONFIG.historySheetName);
  var historyLastRow = historySheet.getLastRow();
  if (historyLastRow === 0) {
    historySheet.getRange(1, 1, 1, VERIFIED_MARKET_DATA_HEADERS.length)
      .setValues([VERIFIED_MARKET_DATA_HEADERS]);
    historyLastRow = 1;
  }
  var existingIds = {};
  if (historyLastRow > 1) {
    historySheet.getRange(2, 1, historyLastRow - 1, 1).getDisplayValues().forEach(function(row) {
      if (row[0]) existingIds[row[0]] = true;
    });
  }
  var historyRows = rows.filter(function(row) { return !existingIds[String(row[0])]; });
  if (historyRows.length) {
    historySheet.getRange(historySheet.getLastRow() + 1, 1, historyRows.length, VERIFIED_MARKET_DATA_HEADERS.length)
      .setValues(historyRows);
  }
  verifiedMarketDataFormatSheet_(historySheet, historySheet.getLastRow(), VERIFIED_MARKET_DATA_HEADERS.length);

  var rulesSheet = verifiedMarketDataEnsureSheet_(spreadsheet, VERIFIED_MARKET_DATA_SHEET_CONFIG.rulesSheetName);
  var rules = verifiedMarketDataRules_();
  rulesSheet.clearContents();
  rulesSheet.getRange(1, 1, rules.length, 2).setValues(rules);
  verifiedMarketDataFormatSheet_(rulesSheet, rules.length, 2);

  return {
    generatedAt: payload.generatedAt || '',
    reportSlot: payload.reportSlot || '',
    overallStatus: payload.overallStatus || 'unknown',
    inputRows: rows.length,
    historyRowsAdded: historyRows.length,
    sheets: [inputSheet.getName(), historySheet.getName(), rulesSheet.getName()]
  };
}

function verifiedMarketDataRows_(payload) {
  var markets = payload.markets || {};
  var keys = VERIFIED_MARKET_DATA_SHEET_CONFIG.marketOrder.slice();
  Object.keys(markets).sort().forEach(function(key) {
    if (keys.indexOf(key) < 0) keys.push(key);
  });
  return keys.filter(function(key) {
    return markets[key] && typeof markets[key] === 'object';
  }).map(function(key) {
    var market = markets[key];
    return [
      String(payload.generatedAt || '') + '|' + key,
      payload.generatedAt || '',
      payload.reportSlot || '',
      payload.overallStatus || 'unknown',
      key,
      market.displayName || key,
      verifiedMarketDataUsePolicy_(market),
      verifiedMarketDataCell_(market.value),
      market.displayValue || '',
      market.unit || '',
      verifiedMarketDataCell_(market.previousClose),
      verifiedMarketDataCell_(market.change),
      verifiedMarketDataCell_(market.changePercent),
      market.changeText || '',
      market.asOf || '',
      market.fetchedAt || '',
      market.verificationStatus || '',
      market.freshnessStatus || '',
      !!market.fallbackUsed,
      market.lastVerifiedAt || '',
      market.sourceName || '',
      market.sourceUrl || '',
      market.marketType || '',
      market.session || '',
      market.classification || '',
      market.note || '',
      market.error || ''
    ];
  });
}

function verifiedMarketDataUsePolicy_(market) {
  if (market.verificationStatus === 'verified' && !market.fallbackUsed) return '使用可';
  if (market.verificationStatus === 'fallback' || market.fallbackUsed) return '前回確認値（要注記）';
  return '使用不可';
}

function verifiedMarketDataCell_(value) {
  if (value === null || typeof value === 'undefined') return '';
  if (typeof value === 'number' && !isFinite(value)) return '';
  return value;
}

function verifiedMarketDataRules_() {
  return [
    ['優先順位', 'ルール'],
    [1, 'マーケットレポートの価格は ChatGPT_Market_Input を正本として使用する。'],
    [2, '利用判定が「使用可」の値だけを確認済みの最新値として使用する。'],
    [3, '「前回確認値（要注記）」は、前回値であることと最終確認時刻を本文に明記する。'],
    [4, '「使用不可」は推測で補わず、取得不能と理由を記載する。'],
    [5, '単位、市場区分、セッションを変えず、異なる商品を同じ名称で表示しない。'],
    [6, '異なる対象時刻の数値を同じ基準時点の値として比較しない。'],
    [7, '価格変化だけからニュース、中央銀行会合、介入などの出来事を推測しない。']
  ];
}

function verifiedMarketDataEnsureSheet_(spreadsheet, name) {
  return spreadsheet.getSheetByName(name) || spreadsheet.insertSheet(name);
}

function verifiedMarketDataFormatSheet_(sheet, rowCount, columnCount) {
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, columnCount)
    .setFontWeight('bold')
    .setBackground('#e2ecff')
    .setWrap(true);
  if (sheet.getFilter()) sheet.getFilter().remove();
  if (rowCount > 1) sheet.getRange(1, 1, rowCount, columnCount).createFilter();
  sheet.autoResizeColumns(1, Math.min(columnCount, 21));
  if (columnCount >= 22) {
    sheet.setColumnWidth(22, 260);
    sheet.setColumnWidth(26, 260);
    sheet.setColumnWidth(27, 260);
  }
}

function verifiedMarketDataSaveResult_(result) {
  result.executedAt = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd HH:mm:ss');
  PropertiesService.getScriptProperties().setProperty(
    VERIFIED_MARKET_DATA_SHEET_CONFIG.lastResultProperty,
    JSON.stringify(result, null, 2)
  );
  console.log(JSON.stringify(result));
  return result;
}

function verifiedMarketDataEscapeHtml_(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
