var VMD_SYNC_CONFIG = {
  handler: 'syncVerifiedMarketDataIfChanged',
  intervalMinutes: 5,
  latestUrl: 'https://raw.githubusercontent.com/matrixdiamond512-cell/Chat-GPT-Market-Report/main/data/market/latest.json',
  inputSheetName: 'ChatGPT_Market_Input',
  historySheetName: 'Market_Data_Verified',
  rulesSheetName: 'ChatGPT_Market_Rules',
  lastSnapshotProperty: 'VMD_LAST_SYNCED_SNAPSHOT',
  lastResultProperty: 'VMD_LAST_SYNC_RESULT',
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

var VMD_SYNC_HEADERS = [
  'スナップショットID',
  '更新日時',
  '対象レポート時刻',
  '全体状態',
  '銘柄ID',
  'データ名',
  '利用判定',
  '現在値',
  '表示値',
  '単位',
  '前回値',
  '前回比',
  '前回比（%）',
  '前回比表示',
  '対象時点',
  '取得時刻',
  '検証状態',
  '鮮度',
  '前回確認値利用',
  '最終確認時刻',
  '取得元',
  '取得元URL',
  '市場区分',
  'セッション',
  '判定区分',
  '注記',
  'エラー'
];

/**
 * Run this once after saving the file. It installs one lightweight watcher
 * and immediately synchronizes the latest verified snapshot.
 */
function installVerifiedMarketDataAutoSync() {
  removeVerifiedMarketDataAutoSyncTriggers_();

  ScriptApp.newTrigger(VMD_SYNC_CONFIG.handler)
    .timeBased()
    .everyMinutes(VMD_SYNC_CONFIG.intervalMinutes)
    .create();

  var result = syncVerifiedMarketDataIfChanged(true);
  SpreadsheetApp.getUi().alert(
    '市場データの自動追随を設定しました。\n' +
    '5分ごとに更新時刻だけを確認し、GitHubのデータが変わった時だけシートを更新します。'
  );
  return result;
}

function uninstallVerifiedMarketDataAutoSync() {
  var deleted = removeVerifiedMarketDataAutoSyncTriggers_();
  SpreadsheetApp.getUi().alert('削除した自動追随トリガー: ' + deleted);
  return deleted;
}

function showVerifiedMarketDataAutoSyncStatus() {
  var active = ScriptApp.getProjectTriggers().filter(function(trigger) {
    return trigger.getHandlerFunction() === VMD_SYNC_CONFIG.handler;
  }).length;
  var properties = PropertiesService.getScriptProperties();
  var message =
    '自動追随トリガー: ' + active + '\n' +
    '最終スナップショット: ' +
      (properties.getProperty(VMD_SYNC_CONFIG.lastSnapshotProperty) || '未実行') + '\n\n' +
    '最終結果:\n' +
      (properties.getProperty(VMD_SYNC_CONFIG.lastResultProperty) || '実行履歴はありません。');
  SpreadsheetApp.getUi().alert(message);
  return message;
}

/**
 * Trigger entry point. A forced run can be requested by passing true when
 * executing from another function, but Apps Script triggers pass no value.
 */
function syncVerifiedMarketDataIfChanged(force) {
  var lock = LockService.getDocumentLock();
  if (lock && !lock.tryLock(5000)) {
    return saveVerifiedMarketDataSyncResult_({
      ok: true,
      skipped: true,
      reason: '別の更新処理が実行中のため、今回はスキップしました。'
    });
  }

  try {
    var payload = fetchVerifiedMarketDataSnapshot_();
    validateVerifiedMarketDataSnapshot_(payload);

    var snapshotKey = String(payload.generatedAt) + '|' + String(payload.reportSlot);
    var properties = PropertiesService.getScriptProperties();
    var previousKey = properties.getProperty(VMD_SYNC_CONFIG.lastSnapshotProperty);
    if (force !== true && previousKey === snapshotKey) {
      return saveVerifiedMarketDataSyncResult_({
        ok: true,
        skipped: true,
        reason: '同じスナップショットは反映済みです。',
        snapshot: snapshotKey
      });
    }

    var result = writeVerifiedMarketDataPayload_(payload);
    properties.setProperty(VMD_SYNC_CONFIG.lastSnapshotProperty, snapshotKey);
    result.ok = true;
    result.skipped = false;
    result.snapshot = snapshotKey;
    return saveVerifiedMarketDataSyncResult_(result);
  } catch (error) {
    saveVerifiedMarketDataSyncResult_({
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

/** Manual synchronization entry point. */
function syncVerifiedMarketDataToChatGptSheets() {
  return syncVerifiedMarketDataIfChanged(true);
}

function previewVerifiedMarketDataForChatGpt() {
  var payload = fetchVerifiedMarketDataSnapshot_();
  validateVerifiedMarketDataSnapshot_(payload);
  var rows = buildVerifiedMarketDataRows_(payload);
  var preview = {
    generatedAt: payload.generatedAt,
    reportSlot: payload.reportSlot,
    overallStatus: payload.overallStatus,
    markets: rows.map(function(row) {
      return {
        id: row[4],
        name: row[5],
        usePolicy: row[6],
        displayValue: row[8],
        unit: row[9],
        asOf: row[14],
        source: row[20]
      };
    })
  };
  var html = HtmlService.createHtmlOutput(
    '<pre style="white-space:pre-wrap;font-size:12px">' +
      escapeVerifiedMarketDataHtml_(JSON.stringify(preview, null, 2)) +
    '</pre>'
  ).setWidth(860).setHeight(680);
  SpreadsheetApp.getUi().showModalDialog(html, '検証済み市場データ');
  return preview;
}

function fetchVerifiedMarketDataSnapshot_() {
  var response = UrlFetchApp.fetch(
    VMD_SYNC_CONFIG.latestUrl + '?t=' + new Date().getTime(),
    {
      muteHttpExceptions: true,
      followRedirects: true,
      headers: { Accept: 'application/json' }
    }
  );
  var status = response.getResponseCode();
  if (status < 200 || status >= 300) {
    throw new Error('検証済み市場データを取得できませんでした。HTTP ' + status);
  }

  try {
    return JSON.parse(response.getContentText('UTF-8'));
  } catch (error) {
    throw new Error('検証済み市場データJSONを解析できませんでした。' + error.message);
  }
}

function validateVerifiedMarketDataSnapshot_(payload) {
  if (!payload || !payload.markets || typeof payload.markets !== 'object') {
    throw new Error('市場データJSONにmarketsがありません。');
  }
  if (!payload.generatedAt) {
    throw new Error('市場データJSONにgeneratedAtがありません。');
  }
  if (!payload.reportSlot || payload.reportSlot === 'manual') {
    throw new Error('市場データJSONの対象レポート時刻が定時枠ではありません。');
  }
  if (payload.overallStatus === 'blocked') {
    throw new Error('市場データがblockedのため、シートを上書きしません。');
  }

  var available = VMD_SYNC_CONFIG.marketOrder.filter(function(key) {
    return payload.markets[key] && typeof payload.markets[key] === 'object';
  });
  if (!available.length) {
    throw new Error('保存できる市場データがありません。');
  }
}

function writeVerifiedMarketDataPayload_(payload) {
  var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  var rows = buildVerifiedMarketDataRows_(payload);

  var inputSheet = ensureVerifiedMarketDataSheet_(
    spreadsheet,
    VMD_SYNC_CONFIG.inputSheetName,
    100
  );
  inputSheet.clearContents();
  inputSheet.getRange(1, 1, rows.length + 1, VMD_SYNC_HEADERS.length)
    .setValues([VMD_SYNC_HEADERS].concat(rows));
  formatVerifiedMarketDataSheet_(inputSheet, rows.length + 1, false);

  var historySheet = ensureVerifiedMarketDataSheet_(
    spreadsheet,
    VMD_SYNC_CONFIG.historySheetName,
    100000
  );
  migrateVerifiedMarketDataImportHistory_(historySheet);
  ensureVerifiedMarketDataHeader_(historySheet);

  var existingIds = {};
  var historyLastRow = historySheet.getLastRow();
  if (historyLastRow > 1) {
    historySheet.getRange(2, 1, historyLastRow - 1, 1)
      .getDisplayValues()
      .forEach(function(row) {
        if (row[0]) existingIds[String(row[0])] = true;
      });
  }
  var historyRows = rows.filter(function(row) {
    return !existingIds[String(row[0])];
  });
  if (historyRows.length) {
    historySheet
      .getRange(historySheet.getLastRow() + 1, 1, historyRows.length, VMD_SYNC_HEADERS.length)
      .setValues(historyRows);
  }
  formatVerifiedMarketDataSheet_(historySheet, historySheet.getLastRow(), true);

  var rulesSheet = ensureVerifiedMarketDataSheet_(
    spreadsheet,
    VMD_SYNC_CONFIG.rulesSheetName,
    50
  );
  var rules = buildVerifiedMarketDataRules_();
  rulesSheet.clearContents();
  rulesSheet.getRange(1, 1, rules.length, 2).setValues(rules);
  rulesSheet.setFrozenRows(1);
  rulesSheet.getRange(1, 1, 1, 2)
    .setFontWeight('bold')
    .setBackground('#e2ecff');
  rulesSheet.setColumnWidth(1, 90);
  rulesSheet.setColumnWidth(2, 720);
  rulesSheet.getRange(1, 1, rules.length, 2).setWrap(true);

  return {
    generatedAt: payload.generatedAt,
    reportSlot: payload.reportSlot,
    overallStatus: payload.overallStatus || 'unknown',
    inputRows: rows.length,
    historyRowsAdded: historyRows.length,
    sheets: [inputSheet.getName(), historySheet.getName(), rulesSheet.getName()]
  };
}

function buildVerifiedMarketDataRows_(payload) {
  var markets = payload.markets || {};
  var keys = VMD_SYNC_CONFIG.marketOrder.slice();
  Object.keys(markets).sort().forEach(function(key) {
    if (keys.indexOf(key) < 0) keys.push(key);
  });

  return keys.filter(function(key) {
    return markets[key] && typeof markets[key] === 'object';
  }).map(function(key) {
    var market = markets[key];
    return [
      String(payload.generatedAt) + '|' + key,
      payload.generatedAt,
      String(payload.reportSlot),
      payload.overallStatus || 'unknown',
      key,
      market.displayName || key,
      getVerifiedMarketDataUsePolicy_(market),
      getVerifiedMarketDataCell_(market.value),
      market.displayValue || '',
      market.unit || '',
      getVerifiedMarketDataCell_(market.previousClose),
      getVerifiedMarketDataCell_(market.change),
      getVerifiedMarketDataCell_(market.changePercent),
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

function getVerifiedMarketDataUsePolicy_(market) {
  if (market.verificationStatus === 'verified' && !market.fallbackUsed) {
    return '使用可';
  }
  if (market.verificationStatus === 'fallback' || market.fallbackUsed) {
    return '前回確認値（要注意）';
  }
  return '使用不可';
}

function getVerifiedMarketDataCell_(value) {
  if (value === null || typeof value === 'undefined') return '';
  if (typeof value === 'number' && !isFinite(value)) return '';
  return value;
}

function ensureVerifiedMarketDataSheet_(spreadsheet, name, minimumRows) {
  var sheet = spreadsheet.getSheetByName(name);
  if (!sheet) sheet = spreadsheet.insertSheet(name);
  if (sheet.getMaxRows() < minimumRows) {
    sheet.insertRowsAfter(sheet.getMaxRows(), minimumRows - sheet.getMaxRows());
  }
  if (sheet.getMaxColumns() < VMD_SYNC_HEADERS.length) {
    sheet.insertColumnsAfter(
      sheet.getMaxColumns(),
      VMD_SYNC_HEADERS.length - sheet.getMaxColumns()
    );
  }
  return sheet;
}

function migrateVerifiedMarketDataImportHistory_(sheet) {
  var formula = sheet.getRange(1, 1).getFormula();
  if (!formula || formula.toUpperCase().indexOf('IMPORTDATA(') < 0) return;

  var values = sheet.getDataRange().getValues();
  sheet.clearContents();
  if (values.length && values[0].length) {
    var width = Math.min(values[0].length, VMD_SYNC_HEADERS.length);
    var normalized = values.map(function(row) {
      return row.slice(0, width);
    });
    sheet.getRange(1, 1, normalized.length, width).setValues(normalized);
  }
}

function ensureVerifiedMarketDataHeader_(sheet) {
  if (sheet.getLastRow() === 0 || !sheet.getRange(1, 1).getDisplayValue()) {
    sheet.getRange(1, 1, 1, VMD_SYNC_HEADERS.length).setValues([VMD_SYNC_HEADERS]);
  }
}

function formatVerifiedMarketDataSheet_(sheet, rowCount, isHistory) {
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, VMD_SYNC_HEADERS.length)
    .setFontWeight('bold')
    .setBackground('#e2ecff')
    .setWrap(true);
  if (!isHistory) {
    sheet.autoResizeColumns(1, 21);
  }
  sheet.setColumnWidth(22, 260);
  sheet.setColumnWidth(26, 260);
  sheet.setColumnWidth(27, 260);
  if (rowCount > 1) {
    sheet.getRange(2, 3, rowCount - 1, 1).setNumberFormat('@');
  }
}

function buildVerifiedMarketDataRules_() {
  return [
    ['優先順位', 'ルール'],
    [1, 'マーケットレポートの価格はChatGPT_Market_Inputを正本として使用する。'],
    [2, '利用判定が「使用可」の値だけを最新の検証済み値として使用する。'],
    [3, '「前回確認値（要注意）」は前回値であることと最終確認時刻を本文に明記する。'],
    [4, '「使用不可」は推測で補わず、取得不能と理由を記載する。'],
    [5, '単位、市場区分、セッションが異なる商品を同じ名称で比較しない。'],
    [6, '異なる対象時点の数値を同じ基準時点の値として比較しない。'],
    [7, '価格変化だけからニュース、中央銀行会合、介入などの出来事を推測しない。']
  ];
}

function removeVerifiedMarketDataAutoSyncTriggers_() {
  var deleted = 0;
  ScriptApp.getProjectTriggers().forEach(function(trigger) {
    if (trigger.getHandlerFunction() === VMD_SYNC_CONFIG.handler) {
      ScriptApp.deleteTrigger(trigger);
      deleted += 1;
    }
  });
  return deleted;
}

function saveVerifiedMarketDataSyncResult_(result) {
  result.executedAt = Utilities.formatDate(
    new Date(),
    'Asia/Tokyo',
    'yyyy-MM-dd HH:mm:ss'
  );
  PropertiesService.getScriptProperties().setProperty(
    VMD_SYNC_CONFIG.lastResultProperty,
    JSON.stringify(result, null, 2)
  );
  console.log(JSON.stringify(result));
  return result;
}

function escapeVerifiedMarketDataHtml_(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
