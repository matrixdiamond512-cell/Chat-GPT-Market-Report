var USDJPY_VOLUME_PAGE_AUTO_CONFIG = {
  timezone: 'Asia/Tokyo',
  handler: 'updateUsdJpyVolumePageFromSources',
  triggerHours: [7, 12, 16, 21],
  triggerMinute: 30,
  lockWaitMs: 30000,
  maxBojPublications: 40,
  maxBojOcrPerRun: 1,
  priceMonthsBack: 2,
  priceSheetName: 'USDJPY_Price',
  volumeSheetName: 'USDJPY_Volume',
  closeSheetNames: ['終値一覧', '前日終値一覧'],
  bojSourceUrl: 'https://www.boj.or.jp/statistics/market/forex/fxdaily/fxlist/index.htm',
  bojPdfBaseUrl: 'https://www.boj.or.jp/statistics/market/forex/fxdaily/fxlist/',
  investingUrl: 'https://jp.investing.com/currencies/usd-jpy-historical-data',
  yahooChartUrl: 'https://query1.finance.yahoo.com/v8/finance/chart/JPY=X',
  lastResultProperty: 'USDJPY_VOLUME_PAGE_AUTO_LAST_RESULT'
};

function updateUsdJpyVolumePageFromSources() {
  var lock = LockService.getDocumentLock();
  if (lock && !lock.tryLock(5000)) {
    var skipped = {
      ok: true,
      skipped: true,
      executedAt: usdJpyVolumeAutoIsoJst_(new Date()),
      reason: '共通自動更新または別の手動更新が実行中です。数分後にもう一度実行してください。'
    };
    usdJpyVolumeAutoSaveResult_(skipped);
    usdJpyVolumeAutoAlert_(
      '現在、別のWEB版更新処理が実行中です。\n' +
      '処理が終わってから「東京市場ドル円出来高を今すぐ更新」をもう一度実行してください。'
    );
    return skipped;
  }

  try {
    return usdJpyVolumeRunUnifiedUpdate_({ mode: 'manual', showAlert: true });
  } finally {
    if (lock) lock.releaseLock();
  }
}

/** 共通スケジューラーがDocumentLockを取得した状態で呼ぶ入口。 */
function runUsdJpyVolumeUpdateForMaster_() {
  return usdJpyVolumeRunUnifiedUpdate_({ mode: 'master', showAlert: false });
}

function usdJpyVolumeRunUnifiedUpdate_(options) {
  var settings = options || {};
  var startedAt = new Date().getTime();
  var result = {
    ok: false,
    skipped: false,
    mode: settings.mode || 'manual',
    lightMode: true,
    executedAt: usdJpyVolumeAutoIsoJst_(new Date()),
    warnings: []
  };

  try {
    result.boj = usdJpyVolumeAutoImportLatestBojSpotVolumeLight_(false);

    try {
      result.price = usdJpyVolumeAutoImportTargetPriceLight_(result.boj.latestTargetDate);
      result.sheetSync = usdJpyVolumeAutoSyncTargetPriceLight_(result.boj.latestTargetDate);
    } catch (priceError) {
      result.price = { ok: false, error: priceError.message };
      result.sheetSync = { ok: false, error: priceError.message };
      result.warnings.push('USD/JPY価格: ' + priceError.message);
    }

    result.volumeDerived = usdJpyVolumeAutoRefreshLatestVolumeDerivedColumnsLight_();

    if (typeof syncUsdJpyVolumeJsonToGitHubFlexibleUnlocked_ !== 'function') {
      throw new Error('UsdJpyVolumeJsonFlexibleSync.gsを最新版に差し替えてください。');
    }

    if (new Date().getTime() - startedAt >= 240000) {
      result.github = usdJpyVolumeAutoScheduleJsonPublishLight_(result.boj.latestPublicationDate);
    } else {
      result.github = syncUsdJpyVolumeJsonToGitHubFlexibleUnlocked_({
        showAlert: false,
        expectedPublicationDate: result.boj.latestPublicationDate
      });
    }

    result.ok = true;
    result.completedAt = usdJpyVolumeAutoIsoJst_(new Date());
    result.elapsedSeconds = Math.round((new Date().getTime() - startedAt) / 1000);
    usdJpyVolumeAutoSaveResult_(result);

    if (settings.showAlert !== false) {
      var githubText = result.github && result.github.deferred
        ? '1分後に自動反映予定'
        : (result.github.commitSha || '');
      usdJpyVolumeAutoAlert_(
        '東京市場ドル円スポット出来高を軽量更新しました。\n\n' +
        '出来高対象日: ' + (result.boj.latestTargetDate || '') + '\n' +
        '日銀公表日: ' + (result.boj.latestPublicationDate || '') + '\n' +
        'PDF処理数: ' + (result.boj.processedPdfCount || 0) + '\n' +
        '価格更新: ' + (result.price && result.price.skipped ? '保存済み' : '更新') + '\n' +
        'GitHub: ' + githubText + '\n' +
        '処理時間: ' + result.elapsedSeconds + '秒' +
        (result.warnings.length ? '\n\n注意:\n' + result.warnings.join('\n') : '')
      );
    }
    return result;
  } catch (error) {
    result.ok = false;
    result.error = error.message;
    result.completedAt = usdJpyVolumeAutoIsoJst_(new Date());
    result.elapsedSeconds = Math.round((new Date().getTime() - startedAt) / 1000);
    usdJpyVolumeAutoSaveResult_(result);
    if (settings.showAlert !== false) {
      usdJpyVolumeAutoAlert_('東京市場ドル円スポット出来高の軽量更新に失敗しました。\n\n理由: ' + error.message);
    }
    throw error;
  }
}

function usdJpyVolumeAutoImportLatestBojSpotVolumeLight_(previewOnly) {
  var config = USDJPY_VOLUME_PAGE_AUTO_CONFIG;
  var sheet = usdJpyVolumeAutoEnsureSheet_(config.volumeSheetName, [
    '対象日', '公表日', '元PDF', '元PDF URL', 'USD/JPYスポット出来高',
    '出来高前営業日比', '出来高前営業日比率', '20営業日平均',
    '20日平均との差', '20日平均比', 'USD/JPY終値', 'USD/JPY始値',
    'USD/JPY高値', 'USD/JPY安値', 'USD/JPY変化率'
  ]);
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]
    .map(function(value) { return String(value || '').trim(); });
  usdJpyVolumeAutoRejectSwapHeaders_(headers);
  var index = usdJpyVolumeAutoResolveVolumeIndexes_(headers, sheet);
  var publications = usdJpyVolumeAutoFetchBojPublications_();
  var latestIndex = publications.length - 1;
  var latest = publications[latestIndex];
  var targetDate = usdJpyVolumeAutoTargetDateForPublication_(publications, latestIndex);
  var rowNumber = usdJpyVolumeAutoFindRowByDateLight_(sheet, index.targetDate, targetDate);
  var lastColumn = sheet.getLastColumn();
  var row = rowNumber ? sheet.getRange(rowNumber, 1, 1, lastColumn).getValues()[0] : null;

  if (row && usdJpyVolumeAutoSavedBojRowIsCurrent_(row, index, latest)) {
    return {
      ok: true, lightMode: true, processedPdfCount: 0,
      addCount: 0, updateCount: 0, unchangedCount: 1,
      latestPublicationDate: latest.date, latestTargetDate: targetDate,
      skippedReason: '最新公表日のスポット出来高は保存済みです。'
    };
  }

  var text = usdJpyVolumeAutoFetchPdfText_(latest.url, latest.pdfName);
  var spotVolume = usdJpyVolumeAutoParseBojSpotVolume_(text);
  var next = row ? row.slice() : new Array(lastColumn).fill('');
  next[index.targetDate] = targetDate;
  next[index.publicationDate] = latest.date;
  next[index.sourcePdfName] = latest.pdfName;
  next[index.sourcePdfUrl] = latest.url;
  next[index.spotVolume] = spotVolume;

  if (!previewOnly) {
    var writeRow = rowNumber || sheet.getLastRow() + 1;
    sheet.getRange(writeRow, 1, 1, lastColumn).setValues([next]);
    if (!rowNumber) usdJpyVolumeAutoSortSheetByDate_(sheet, index.targetDate + 1);
  }

  return {
    ok: true, lightMode: true, processedPdfCount: 1,
    addCount: rowNumber ? 0 : 1, updateCount: rowNumber ? 1 : 0,
    unchangedCount: 0, latestPublicationDate: latest.date,
    latestTargetDate: targetDate, spotVolume: spotVolume
  };
}

function usdJpyVolumeAutoFindRowByDateLight_(sheet, zeroBasedDateColumn, targetDate) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2 || zeroBasedDateColumn < 0) return 0;
  var values = sheet.getRange(2, zeroBasedDateColumn + 1, lastRow - 1, 1).getValues();
  for (var i = values.length - 1; i >= 0; i -= 1) {
    if (usdJpyVolumeAutoDateKey_(values[i][0]) === targetDate) return i + 2;
  }
  return 0;
}

function usdJpyVolumeAutoImportTargetPriceLight_(targetDate) {
  var sheet = usdJpyVolumeAutoEnsureSheet_(USDJPY_VOLUME_PAGE_AUTO_CONFIG.priceSheetName, [
    '日付', 'USD/JPY終値', 'USD/JPY始値', 'USD/JPY高値', 'USD/JPY安値',
    'USD/JPY変化率', '取得元', '取得日時'
  ]);
  var values = sheet.getDataRange().getValues();
  var headers = values[0].map(function(value) { return String(value || '').trim(); });
  var index = usdJpyVolumeAutoHeaderIndex_(headers);
  var rowNumber = 0;
  var saved = null;
  for (var i = 1; i < values.length; i += 1) {
    if (usdJpyVolumeAutoDateKey_(values[i][index['日付']]) !== targetDate) continue;
    rowNumber = i + 1;
    saved = values[i];
    break;
  }
  if (saved && [
    index['USD/JPY終値'], index['USD/JPY始値'], index['USD/JPY高値'], index['USD/JPY安値']
  ].every(function(column) { return usdJpyVolumeAutoNumber_(saved[column]) !== null; })) {
    return { ok: true, lightMode: true, skipped: true, latestDate: targetDate, sourceName: String(saved[index['取得元']] || '保存済み') };
  }

  var originalMonths = USDJPY_VOLUME_PAGE_AUTO_CONFIG.priceMonthsBack;
  USDJPY_VOLUME_PAGE_AUTO_CONFIG.priceMonthsBack = 2;
  var fetched;
  try {
    fetched = usdJpyVolumeAutoFetchPriceRows_();
  } finally {
    USDJPY_VOLUME_PAGE_AUTO_CONFIG.priceMonthsBack = originalMonths;
  }
  var target = fetched.rows.filter(function(item) { return item.date === targetDate; })[0];
  if (!target) throw new Error('出来高対象日 ' + targetDate + ' のUSD/JPY日足OHLCを取得できませんでした。');

  var fetchedAt = usdJpyVolumeAutoIsoJst_(new Date());
  var next = saved ? saved.slice() : new Array(headers.length).fill('');
  next[index['日付']] = target.date;
  next[index['USD/JPY終値']] = target.close;
  next[index['USD/JPY始値']] = target.open;
  next[index['USD/JPY高値']] = target.high;
  next[index['USD/JPY安値']] = target.low;
  next[index['USD/JPY変化率']] = target.priceChangePct;
  next[index['取得元']] = fetched.sourceName;
  next[index['取得日時']] = fetchedAt;
  sheet.getRange(rowNumber || sheet.getLastRow() + 1, 1, 1, headers.length).setValues([next]);
  if (!rowNumber) usdJpyVolumeAutoSortSheetByDate_(sheet, index['日付'] + 1);
  return { ok: true, lightMode: true, skipped: false, latestDate: targetDate, sourceName: fetched.sourceName };
}

function usdJpyVolumeAutoSyncTargetPriceLight_(targetDate) {
  var priceSheet = usdJpyVolumeAutoEnsureSheet_(USDJPY_VOLUME_PAGE_AUTO_CONFIG.priceSheetName, [
    '日付', 'USD/JPY終値', 'USD/JPY始値', 'USD/JPY高値', 'USD/JPY安値',
    'USD/JPY変化率', '取得元', '取得日時'
  ]);
  var priceRows = usdJpyVolumeAutoReadPriceSheet_(priceSheet);
  var price = priceRows.byDate[targetDate];
  if (!price) throw new Error('USDJPY_Priceに対象日の価格がありません: ' + targetDate);

  var volumeUpdated = usdJpyVolumeAutoSyncOnePriceToVolumeLight_(price);
  var closeUpdated = usdJpyVolumeAutoSyncOnePriceToCloseSheetsLight_(price, priceRows.byDate);
  return { ok: true, lightMode: true, latestDate: targetDate, volumeUpdated: volumeUpdated, closeSheetUpdated: closeUpdated };
}

function usdJpyVolumeAutoSyncOnePriceToVolumeLight_(price) {
  var sheet = usdJpyVolumeAutoEnsureSheet_(USDJPY_VOLUME_PAGE_AUTO_CONFIG.volumeSheetName, [
    '対象日', '公表日', '元PDF', '元PDF URL', 'USD/JPYスポット出来高',
    'USD/JPY終値', 'USD/JPY始値', 'USD/JPY高値', 'USD/JPY安値', 'USD/JPY変化率'
  ]);
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]
    .map(function(value) { return String(value || '').trim(); });
  var index = usdJpyVolumeAutoResolveVolumeIndexes_(headers, sheet);
  var rowNumber = usdJpyVolumeAutoFindRowByDateLight_(sheet, index.targetDate, price.date);
  if (!rowNumber) return 0;
  var row = sheet.getRange(rowNumber, 1, 1, sheet.getLastColumn()).getValues()[0];
  var before = JSON.stringify(row);
  row[index.close] = price.close;
  row[index.open] = price.open;
  row[index.high] = price.high;
  row[index.low] = price.low;
  row[index.priceChangePct] = price.priceChangePct;
  if (JSON.stringify(row) === before) return 0;
  sheet.getRange(rowNumber, 1, 1, row.length).setValues([row]);
  return 1;
}

function usdJpyVolumeAutoSyncOnePriceToCloseSheetsLight_(price, byDate) {
  var dates = Object.keys(byDate).sort();
  var position = dates.indexOf(price.date);
  var previous = position > 0 ? byDate[dates[position - 1]] : null;
  var change = previous && previous.close ? usdJpyVolumeAutoRound_(price.close - previous.close, 4) : '';
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheets = USDJPY_VOLUME_PAGE_AUTO_CONFIG.closeSheetNames
    .map(function(name) { return ss.getSheetByName(name); }).filter(Boolean);
  var updated = 0;
  sheets.forEach(function(sheet) {
    var headers = usdJpyVolumeAutoEnsureColumns_(sheet, [
      '日付', 'USDJPY終値（Investing.com）', 'USDJPY前日比', 'USDJPY騰落率',
      'USDJPY始値（Investing.com）', 'USDJPY高値（Investing.com）',
      'USDJPY安値（Investing.com）', 'USDJPY価格取得元', 'USDJPY価格取得日時'
    ]);
    var index = usdJpyVolumeAutoHeaderIndex_(headers);
    var rowNumber = usdJpyVolumeAutoFindRowByDateLight_(sheet, index['日付'], price.date);
    var row = rowNumber
      ? sheet.getRange(rowNumber, 1, 1, sheet.getLastColumn()).getValues()[0]
      : new Array(sheet.getLastColumn()).fill('');
    var before = JSON.stringify(row);
    row[index['日付']] = price.date;
    row[index['USDJPY終値（Investing.com）']] = price.close;
    row[index['USDJPY前日比']] = change;
    row[index['USDJPY騰落率']] = price.priceChangePct;
    row[index['USDJPY始値（Investing.com）']] = price.open;
    row[index['USDJPY高値（Investing.com）']] = price.high;
    row[index['USDJPY安値（Investing.com）']] = price.low;
    row[index['USDJPY価格取得元']] = price.sourceName || '';
    row[index['USDJPY価格取得日時']] = price.fetchedAt || '';
    if (JSON.stringify(row) === before) return;
    sheet.getRange(rowNumber || sheet.getLastRow() + 1, 1, 1, row.length).setValues([row]);
    if (!rowNumber) usdJpyVolumeAutoSortSheetByDate_(sheet, index['日付'] + 1);
    updated += 1;
  });
  return updated;
}

function usdJpyVolumeAutoRefreshLatestVolumeDerivedColumnsLight_() {
  var sheet = usdJpyVolumeAutoEnsureSheet_(USDJPY_VOLUME_PAGE_AUTO_CONFIG.volumeSheetName, [
    '対象日', '公表日', '元PDF', '元PDF URL', 'USD/JPYスポット出来高',
    '出来高前営業日比', '出来高前営業日比率', '20営業日平均',
    '20日平均との差', '20日平均比'
  ]);
  var values = sheet.getDataRange().getValues();
  if (values.length < 2) return { ok: true, lightMode: true, rowCount: 0, updatedCells: 0 };
  var headers = values[0].map(function(value) { return String(value || '').trim(); });
  var index = usdJpyVolumeAutoResolveVolumeIndexes_(headers, sheet);
  values = sheet.getDataRange().getValues();
  var records = [];
  for (var i = 1; i < values.length; i += 1) {
    var date = usdJpyVolumeAutoDateKey_(values[i][index.targetDate]);
    var volume = usdJpyVolumeAutoNumber_(values[i][index.spotVolume]);
    if (date && volume !== null) records.push({ rowNumber: i + 1, targetDate: date, spotVolume: volume });
  }
  records.sort(function(a, b) { return a.targetDate.localeCompare(b.targetDate); });
  if (!records.length) return { ok: true, lightMode: true, rowCount: 0, updatedCells: 0 };
  var n = records.length - 1;
  var latest = records[n];
  var previous = n > 0 ? records[n - 1] : null;
  var change = previous ? usdJpyVolumeAutoRound_(latest.spotVolume - previous.spotVolume, 0) : '';
  var changePct = previous && previous.spotVolume ? usdJpyVolumeAutoRound_(change / previous.spotVolume * 100, 2) : '';
  var avg20 = '';
  var vs20 = '';
  var vs20Pct = '';
  if (n >= 19) {
    var window = records.slice(n - 19, n + 1);
    avg20 = usdJpyVolumeAutoRound_(window.reduce(function(sum, item) { return sum + item.spotVolume; }, 0) / 20, 0);
    vs20 = usdJpyVolumeAutoRound_(latest.spotVolume - avg20, 0);
    vs20Pct = avg20 ? usdJpyVolumeAutoRound_(vs20 / avg20 * 100, 2) : '';
  }
  var row = values[latest.rowNumber - 1].slice();
  var updates = [[index.volumeChange, change], [index.volumeChangePct, changePct], [index.avg20, avg20], [index.vs20, vs20], [index.vs20Pct, vs20Pct]];
  var changed = 0;
  updates.forEach(function(pair) {
    if (pair[0] >= 0 && String(row[pair[0]]) !== String(pair[1])) { row[pair[0]] = pair[1]; changed += 1; }
  });
  if (changed) sheet.getRange(latest.rowNumber, 1, 1, row.length).setValues([row]);
  return { ok: true, lightMode: true, rowCount: records.length, updatedCells: changed, latestDate: latest.targetDate };
}

function usdJpyVolumeAutoScheduleJsonPublishLight_(expectedPublicationDate) {
  var props = PropertiesService.getScriptProperties();
  props.setProperty('USDJPY_VOLUME_LIGHT_PENDING_PUBLICATION', expectedPublicationDate || '');
  usdJpyVolumeAutoDeleteJsonContinuationTriggersLight_();
  ScriptApp.newTrigger('continueUsdJpyVolumeJsonPublishLight').timeBased().after(60000).create();
  return { ok: true, deferred: true, expectedPublicationDate: expectedPublicationDate || '' };
}

function continueUsdJpyVolumeJsonPublishLight() {
  var lock = LockService.getDocumentLock();
  if (lock && !lock.tryLock(30000)) throw new Error('別の更新処理が実行中です。');
  try {
    var props = PropertiesService.getScriptProperties();
    var expected = props.getProperty('USDJPY_VOLUME_LIGHT_PENDING_PUBLICATION') || '';
    var result = syncUsdJpyVolumeJsonToGitHubFlexibleUnlocked_({ showAlert: false, expectedPublicationDate: expected });
    props.deleteProperty('USDJPY_VOLUME_LIGHT_PENDING_PUBLICATION');
    return result;
  } finally {
    usdJpyVolumeAutoDeleteJsonContinuationTriggersLight_();
    if (lock) lock.releaseLock();
  }
}

function usdJpyVolumeAutoDeleteJsonContinuationTriggersLight_() {
  ScriptApp.getProjectTriggers()
    .filter(function(trigger) { return trigger.getHandlerFunction() === 'continueUsdJpyVolumeJsonPublishLight'; })
    .forEach(function(trigger) { ScriptApp.deleteTrigger(trigger); });
}

function usdJpyVolumeAutoSaveResult_(result) {
  PropertiesService.getScriptProperties().setProperty(
    USDJPY_VOLUME_PAGE_AUTO_CONFIG.lastResultProperty,
    JSON.stringify(result)
  );
  return result;
}

function showUsdJpyVolumeUnifiedStatus() {
  var status = {
    checkedAt: usdJpyVolumeAutoIsoJst_(new Date()),
    official: { ok: false },
    sheet: { ok: false },
    publicJson: { ok: false },
    triggers: { master: 0, oldIndividual: 0 },
    lastResult: null
  };

  try {
    var publications = usdJpyVolumeAutoFetchBojPublications_();
    var officialIndex = publications.length - 1;
    var officialLatest = publications[officialIndex];
    status.official = {
      ok: true,
      publicationDate: officialLatest.date,
      targetDate: usdJpyVolumeAutoTargetDateForPublication_(publications, officialIndex)
    };
  } catch (officialError) {
    status.official.error = officialError.message;
  }

  try {
    var sheetPayload = buildUsdJpyVolumePayloadFlexible_();
    status.sheet = {
      ok: true,
      publicationDate: sheetPayload.components.bojSpotVolume.latestPublicationDate,
      targetDate: sheetPayload.components.bojSpotVolume.latestTargetDate,
      records: sheetPayload.data.records.length
    };
  } catch (sheetError) {
    status.sheet.error = sheetError.message;
  }

  try {
    var publicUrl = 'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/data/usdjpy-volume.json?t=' +
      new Date().getTime();
    var publicResponse = UrlFetchApp.fetch(publicUrl, { muteHttpExceptions: true, headers: { Accept: 'application/json' } });
    if (publicResponse.getResponseCode() !== 200) {
      throw new Error('HTTP ' + publicResponse.getResponseCode());
    }
    var publicPayload = JSON.parse(publicResponse.getContentText('UTF-8'));
    status.publicJson = {
      ok: true,
      publicationDate: publicPayload.components.bojSpotVolume.latestPublicationDate,
      targetDate: publicPayload.components.bojSpotVolume.latestTargetDate,
      generatedAt: publicPayload.generatedAt || ''
    };
  } catch (publicError) {
    status.publicJson.error = publicError.message;
  }

  var masterNames = typeof marketReportMasterHandlerNames_ === 'function'
    ? marketReportMasterHandlerNames_()
    : [];
  ScriptApp.getProjectTriggers().forEach(function(trigger) {
    var handler = trigger.getHandlerFunction();
    if (masterNames.indexOf(handler) >= 0) status.triggers.master += 1;
    if (handler === USDJPY_VOLUME_PAGE_AUTO_CONFIG.handler) status.triggers.oldIndividual += 1;
  });

  var lastResultText = PropertiesService.getScriptProperties()
    .getProperty(USDJPY_VOLUME_PAGE_AUTO_CONFIG.lastResultProperty);
  if (lastResultText) {
    try {
      status.lastResult = JSON.parse(lastResultText);
    } catch (ignore) {
      status.lastResult = { error: lastResultText };
    }
  }

  var current = status.official.ok && status.sheet.ok && status.publicJson.ok &&
    status.official.publicationDate === status.sheet.publicationDate &&
    status.sheet.publicationDate === status.publicJson.publicationDate;
  status.ok = current;

  var lastSummary = status.lastResult
    ? ((status.lastResult.ok ? '成功' : '失敗') + ' / ' + (status.lastResult.completedAt || status.lastResult.executedAt || '時刻不明'))
    : '実行履歴なし';
  var message =
    '東京市場ドル円スポット出来高 更新状態\n\n' +
    '総合判定: ' + (current ? '最新です' : '更新が必要です') + '\n\n' +
    '日銀最新公表日: ' + (status.official.publicationDate || '取得失敗') + '\n' +
    'シート最新公表日: ' + (status.sheet.publicationDate || '取得失敗') + '\n' +
    'WEB最新公表日: ' + (status.publicJson.publicationDate || '取得失敗') + '\n\n' +
    '共通トリガー: ' + status.triggers.master + '/8\n' +
    '古い個別トリガー: ' + status.triggers.oldIndividual + '\n' +
    '前回更新: ' + lastSummary;

  if (!current) {
    message += '\n\n「東京市場ドル円出来高を今すぐ更新」を実行してください。';
  }
  if (status.official.error) message += '\n日銀確認エラー: ' + status.official.error;
  if (status.sheet.error) message += '\nシート確認エラー: ' + status.sheet.error;
  if (status.publicJson.error) message += '\nWEB確認エラー: ' + status.publicJson.error;

  usdJpyVolumeAutoAlert_(message);
  return status;
}

function installUsdJpyVolumePageScheduledTriggers() {
  uninstallUsdJpyVolumePageScheduledTriggers_(false);
  USDJPY_VOLUME_PAGE_AUTO_CONFIG.triggerHours.forEach(function(hour) {
    ScriptApp.newTrigger(USDJPY_VOLUME_PAGE_AUTO_CONFIG.handler)
      .timeBased()
      .atHour(hour)
      .nearMinute(USDJPY_VOLUME_PAGE_AUTO_CONFIG.triggerMinute)
      .everyDays(1)
      .inTimezone(USDJPY_VOLUME_PAGE_AUTO_CONFIG.timezone)
      .create();
  });
  usdJpyVolumeAutoAlert_(
    'USD/JPYページ定時更新を設定しました。\n' +
    '実行時刻: 07:30 / 12:30 / 16:30 / 21:30（日本時間）'
  );
  return showUsdJpyVolumePageScheduledStatus();
}

function uninstallUsdJpyVolumePageScheduledTriggers() {
  var deleted = uninstallUsdJpyVolumePageScheduledTriggers_(true);
  return { deleted: deleted };
}

function showUsdJpyVolumePageScheduledStatus() {
  var handler = USDJPY_VOLUME_PAGE_AUTO_CONFIG.handler;
  var triggers = ScriptApp.getProjectTriggers().filter(function(trigger) {
    return trigger.getHandlerFunction() === handler;
  });
  var lastResult = PropertiesService.getScriptProperties()
    .getProperty(USDJPY_VOLUME_PAGE_AUTO_CONFIG.lastResultProperty) || '未実行';
  var message =
    'USD/JPYページ定時更新の状態\n' +
    'トリガー数: ' + triggers.length + '\n' +
    '想定: 4件（07:30 / 12:30 / 16:30 / 21:30）\n' +
    '実行関数: ' + handler + '\n\n' +
    '直近結果:\n' + lastResult;
  usdJpyVolumeAutoAlert_(message);
  return {
    handler: handler,
    triggerCount: triggers.length,
    expectedCount: USDJPY_VOLUME_PAGE_AUTO_CONFIG.triggerHours.length,
    lastResult: lastResult
  };
}

function previewUsdJpyInvestingPriceImport() {
  var summary = usdJpyVolumeAutoImportPrice_(true);
  var html = HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;padding:16px">' +
      '<h3>USD/JPY価格 取込プレビュー</h3>' +
      '<p>取得元: ' + usdJpyVolumeAutoEscapeHtml_(summary.sourceName) + '</p>' +
      '<p>取得件数: ' + summary.fetchedCount + ' / 追加予定: ' + summary.addCount +
      ' / 更新予定: ' + summary.updateCount + '</p>' +
      '<p>取得範囲: ' + summary.startDate + ' - ' + summary.endDate + '</p>' +
      '<pre style="white-space:pre-wrap;font-size:12px">' +
        usdJpyVolumeAutoEscapeHtml_(JSON.stringify(summary.sampleRows, null, 2)) +
      '</pre>' +
      '<p style="color:#9b1c1c">' + usdJpyVolumeAutoEscapeHtml_(summary.warning || '') + '</p>' +
    '</div>'
  ).setWidth(860).setHeight(680);
  SpreadsheetApp.getUi().showModalDialog(html, 'USD/JPY価格プレビュー');
  return summary;
}

function importUsdJpyInvestingPrice() {
  var summary = usdJpyVolumeAutoImportPrice_(false);
  usdJpyVolumeAutoAlert_(
    'USD/JPY価格を取り込みました。\n' +
    '取得元: ' + summary.sourceName + '\n' +
    '取得件数: ' + summary.fetchedCount + '\n' +
    '追加: ' + summary.addCount + '\n' +
    '更新: ' + summary.updateCount + '\n' +
    '最新日: ' + (summary.latestDate || '') +
    (summary.warning ? '\n注意: ' + summary.warning : '')
  );
  return summary;
}

function syncUsdJpyInvestingPriceToReportSheets() {
  var summary = usdJpyVolumeAutoSyncPriceToReportSheets_();
  var derivedSummary = usdJpyVolumeAutoRefreshVolumeDerivedColumns_();
  usdJpyVolumeAutoAlert_(
    'USD/JPY価格を出来高シートと終値一覧へ同期しました。\n' +
    '出来高シート更新: ' + summary.volumeUpdated + '\n' +
    '終値一覧更新: ' + summary.closeSheetUpdated + '\n' +
    '計算列保存: ' + derivedSummary.updatedCells + '\n' +
    '最新日: ' + (summary.latestDate || '')
  );
  summary.volumeDerived = derivedSummary;
  return summary;
}

function usdJpyVolumeAutoImportBojPdfSpotVolume_(previewOnly) {
  var config = USDJPY_VOLUME_PAGE_AUTO_CONFIG;
  var sheet = usdJpyVolumeAutoEnsureSheet_(config.volumeSheetName, [
    '対象日',
    '公表日',
    '元PDF',
    '元PDF URL',
    'USD/JPYスポット出来高',
    '出来高前営業日比',
    '出来高前営業日比率',
    '20営業日平均',
    '20日平均との差',
    '20日平均比',
    'USD/JPY終値',
    'USD/JPY始値',
    'USD/JPY高値',
    'USD/JPY安値',
    'USD/JPY変化率'
  ]);
  var values = sheet.getDataRange().getValues();
  var headers = values[0].map(function(value) { return String(value || '').trim(); });
  usdJpyVolumeAutoRejectSwapHeaders_(headers);
  var index = usdJpyVolumeAutoResolveVolumeIndexes_(headers, sheet);
  values = sheet.getDataRange().getValues();
  var existing = usdJpyVolumeAutoBuildRowMap_(values, index.targetDate);
  var publications = usdJpyVolumeAutoFetchBojPublications_()
    .slice(-config.maxBojPublications);
  var rowsToAdd = [];
  var rowsToUpdate = [];
  var unchangedRows = [];
  var pendingRows = [];
  var processedPdfCount = 0;

  publications.forEach(function(publication, publicationIndex) {
    var targetDate = usdJpyVolumeAutoTargetDateForPublication_(publications, publicationIndex);
    var current = existing[targetDate];
    if (current && usdJpyVolumeAutoSavedBojRowIsCurrent_(current.row, index, publication)) {
      unchangedRows.push({
        targetDate: targetDate,
        publicationDate: publication.date,
        sourcePdfName: publication.pdfName,
        sourcePdfUrl: publication.url,
        spotVolume: usdJpyVolumeAutoNumber_(current.row[index.spotVolume])
      });
      return;
    }
    pendingRows.push({
      publication: publication,
      targetDate: targetDate,
      current: current
    });
  });

  pendingRows.sort(function(a, b) {
    return b.publication.date.localeCompare(a.publication.date);
  });

  var rowsDeferred = pendingRows.slice(config.maxBojOcrPerRun || pendingRows.length);
  pendingRows.slice(0, config.maxBojOcrPerRun || pendingRows.length).forEach(function(item) {
    var publication = item.publication;
    var current = item.current;
    var text = usdJpyVolumeAutoFetchPdfText_(publication.url, publication.pdfName);
    var spotVolume = usdJpyVolumeAutoParseBojSpotVolume_(text);
    processedPdfCount += 1;
    var next = {
      targetDate: item.targetDate,
      publicationDate: publication.date,
      sourcePdfName: publication.pdfName,
      sourcePdfUrl: publication.url,
      spotVolume: spotVolume
    };
    if (!current) {
      rowsToAdd.push(next);
    } else if (usdJpyVolumeAutoVolumeNeedsUpdate_(current.row, index, next)) {
      rowsToUpdate.push(Object.assign({ rowNumber: current.rowNumber }, next));
    }
  });

  if (!previewOnly) {
    usdJpyVolumeAutoWriteVolumeRows_(sheet, index, rowsToAdd, rowsToUpdate);
    usdJpyVolumeAutoSortSheetByDate_(sheet, index.targetDate + 1);
  }

  var latest = publications.length ? publications[publications.length - 1] : null;
  return {
    ok: true,
    previewOnly: previewOnly,
    source: '日本銀行 外国為替市況PDF',
    fetchedCount: publications.length,
    fetchedPublications: publications.length,
    processedPdfCount: processedPdfCount,
    deferredCount: rowsDeferred.length,
    addCount: rowsToAdd.length,
    updateCount: rowsToUpdate.length,
    unchangedCount: unchangedRows.length,
    latestPublicationDate: latest ? latest.date : '',
    latestTargetDate: latest ?
      usdJpyVolumeAutoTargetDateForPublication_(publications, publications.length - 1) : '',
    rowsToAdd: rowsToAdd,
    rowsToUpdate: rowsToUpdate,
    missingPriceDates: []
  };
}

/**
 * 「前営業日」は単純な月曜から金曜ではなく、日銀が前回公表した市場日を使う。
 * これにより祝日や大型連休でも対象日と公表日がずれない。
 */
function usdJpyVolumeAutoTargetDateForPublication_(publications, index) {
  if (index > 0 && publications[index - 1] && publications[index - 1].date) {
    return publications[index - 1].date;
  }
  return usdJpyVolumeAutoPreviousWeekday_(publications[index].date);
}

function usdJpyVolumeAutoImportPrice_(previewOnly) {
  var fetchResult = usdJpyVolumeAutoFetchPriceRows_();
  var rows = fetchResult.rows;
  var sheet = usdJpyVolumeAutoEnsureSheet_(USDJPY_VOLUME_PAGE_AUTO_CONFIG.priceSheetName, [
    '日付',
    'USD/JPY終値',
    'USD/JPY始値',
    'USD/JPY高値',
    'USD/JPY安値',
    'USD/JPY変化率',
    '取得元',
    '取得日時'
  ]);
  var current = usdJpyVolumeAutoReadPriceSheet_(sheet);
  var addCount = 0;
  var updateCount = 0;
  var fetchedAt = usdJpyVolumeAutoIsoJst_(new Date());
  rows.forEach(function(row) {
    var before = current.byDate[row.date];
    var next = {
      date: row.date,
      close: row.close,
      open: row.open,
      high: row.high,
      low: row.low,
      priceChangePct: row.priceChangePct,
      sourceName: fetchResult.sourceName,
      fetchedAt: fetchedAt
    };
    if (!before) {
      addCount += 1;
    } else if (usdJpyVolumeAutoPriceChanged_(before, next)) {
      updateCount += 1;
    }
    current.byDate[row.date] = next;
  });

  if (!previewOnly) {
    usdJpyVolumeAutoWritePriceSheet_(sheet, current.byDate);
  }

  return {
    ok: true,
    previewOnly: previewOnly,
    sourceName: fetchResult.sourceName,
    warning: fetchResult.warning || '',
    startDate: rows.length ? rows[0].date : '',
    endDate: rows.length ? rows[rows.length - 1].date : '',
    latestDate: rows.length ? rows[rows.length - 1].date : '',
    fetchedCount: rows.length,
    addCount: addCount,
    updateCount: updateCount,
    sampleRows: rows.slice(-12).reverse()
  };
}

function usdJpyVolumeAutoSyncPriceToReportSheets_() {
  var priceSheet = usdJpyVolumeAutoEnsureSheet_(USDJPY_VOLUME_PAGE_AUTO_CONFIG.priceSheetName, [
    '日付',
    'USD/JPY終値',
    'USD/JPY始値',
    'USD/JPY高値',
    'USD/JPY安値',
    'USD/JPY変化率',
    '取得元',
    '取得日時'
  ]);
  var priceRows = usdJpyVolumeAutoReadPriceSheet_(priceSheet);
  var priceList = Object.keys(priceRows.byDate).sort().map(function(date) {
    return priceRows.byDate[date];
  });
  if (!priceList.length) throw new Error('USDJPY_Priceシートに価格データがありません。先に価格を取り込んでください。');

  var volumeUpdated = usdJpyVolumeAutoSyncPriceToVolumeSheet_(priceRows.byDate);
  var closeSheetUpdated = usdJpyVolumeAutoSyncPriceToCloseSheets_(priceList);
  return {
    ok: true,
    latestDate: priceList[priceList.length - 1].date,
    volumeUpdated: volumeUpdated,
    closeSheetUpdated: closeSheetUpdated
  };
}

function usdJpyVolumeAutoRefreshVolumeDerivedColumns_() {
  var sheet = usdJpyVolumeAutoEnsureSheet_(USDJPY_VOLUME_PAGE_AUTO_CONFIG.volumeSheetName, [
    '対象日',
    '公表日',
    '元PDF',
    '元PDF URL',
    'USD/JPYスポット出来高',
    '出来高前営業日比',
    '出来高前営業日比率',
    '20営業日平均',
    '20日平均との差',
    '20日平均比',
    'USD/JPY終値',
    'USD/JPY始値',
    'USD/JPY高値',
    'USD/JPY安値',
    'USD/JPY変化率'
  ]);
  var values = sheet.getDataRange().getValues();
  if (values.length < 2) {
    return {
      ok: true,
      rowCount: 0,
      updatedCells: 0,
      oldestDate: '',
      latestDate: ''
    };
  }

  var headers = values[0].map(function(value) { return String(value || '').trim(); });
  var index = usdJpyVolumeAutoResolveVolumeIndexes_(headers, sheet);
  values = sheet.getDataRange().getValues();
  var records = [];
  for (var i = 1; i < values.length; i += 1) {
    var targetDate = usdJpyVolumeAutoDateKey_(values[i][index.targetDate]);
    var spotVolume = usdJpyVolumeAutoNumber_(values[i][index.spotVolume]);
    if (!targetDate || spotVolume === null) continue;
    records.push({
      rowNumber: i + 1,
      targetDate: targetDate,
      spotVolume: spotVolume
    });
  }
  records.sort(function(a, b) { return a.targetDate.localeCompare(b.targetDate); });

  var updatedCells = 0;
  records.forEach(function(record, indexInList) {
    var previous = indexInList > 0 ? records[indexInList - 1] : null;
    var volumeChange = previous ? usdJpyVolumeAutoRound_(record.spotVolume - previous.spotVolume, 0) : '';
    var volumeChangePct = previous && previous.spotVolume ?
      usdJpyVolumeAutoRound_(volumeChange / previous.spotVolume * 100, 2) :
      '';
    var avg20 = '';
    var vs20 = '';
    var vs20Pct = '';
    if (indexInList >= 19) {
      var window = records.slice(indexInList - 19, indexInList + 1);
      avg20 = usdJpyVolumeAutoRound_(
        window.reduce(function(sum, item) { return sum + item.spotVolume; }, 0) / window.length,
        0
      );
      vs20 = usdJpyVolumeAutoRound_(record.spotVolume - avg20, 0);
      vs20Pct = avg20 ? usdJpyVolumeAutoRound_(vs20 / avg20 * 100, 2) : '';
    }

    updatedCells += usdJpyVolumeAutoSetCellIfChanged_(sheet, record.rowNumber, index.volumeChange, volumeChange);
    updatedCells += usdJpyVolumeAutoSetCellIfChanged_(sheet, record.rowNumber, index.volumeChangePct, volumeChangePct);
    updatedCells += usdJpyVolumeAutoSetCellIfChanged_(sheet, record.rowNumber, index.avg20, avg20);
    updatedCells += usdJpyVolumeAutoSetCellIfChanged_(sheet, record.rowNumber, index.vs20, vs20);
    updatedCells += usdJpyVolumeAutoSetCellIfChanged_(sheet, record.rowNumber, index.vs20Pct, vs20Pct);
  });

  usdJpyVolumeAutoSortSheetByDate_(sheet, index.targetDate + 1);
  return {
    ok: true,
    rowCount: records.length,
    updatedCells: updatedCells,
    oldestDate: records.length ? records[0].targetDate : '',
    latestDate: records.length ? records[records.length - 1].targetDate : '',
    note: 'USDJPY_Volumeシートに、WEB表と同じ出来高前営業日比・20営業日平均・平均との差を保存しました。履歴行は削除しません。'
  };
}

function usdJpyVolumeAutoFetchPriceRows_() {
  var errors = [];
  try {
    var investingRows = usdJpyVolumeAutoFetchInvestingRows_();
    return {
      sourceName: 'Investing.com USD/JPY日足OHLC',
      rows: investingRows,
      warning: ''
    };
  } catch (error) {
    errors.push('Investing.com: ' + error.message);
  }

  try {
    var yahooRows = usdJpyVolumeAutoFetchYahooRows_();
    return {
      sourceName: 'Yahoo Finance USD/JPY日足OHLC（Investing.com取得失敗時の予備）',
      rows: yahooRows,
      warning: errors.join(' / ')
    };
  } catch (error) {
    errors.push('Yahoo Finance: ' + error.message);
  }

  throw new Error('USD/JPY価格を取得できませんでした。' + errors.join(' / '));
}

function usdJpyVolumeAutoFetchInvestingRows_() {
  var response = UrlFetchApp.fetch(USDJPY_VOLUME_PAGE_AUTO_CONFIG.investingUrl, {
    method: 'get',
    muteHttpExceptions: true,
    followRedirects: true,
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'ja-JP,ja;q=0.9,en;q=0.8',
      'Cache-Control': 'no-cache'
    }
  });
  var code = response.getResponseCode();
  if (code !== 200) throw new Error('HTTP ' + code);
  var html = response.getContentText('UTF-8');
  var rows = usdJpyVolumeAutoParseInvestingRows_(html);
  if (!rows.length) throw new Error('価格表を抽出できませんでした。');
  return rows;
}

function usdJpyVolumeAutoParseInvestingRows_(html) {
  var rows = [];
  var seen = {};
  var trRegex = /<tr[\s\S]*?<\/tr>/gi;
  var match;
  while ((match = trRegex.exec(html)) !== null) {
    usdJpyVolumeAutoPushInvestingRow_(rows, seen, match[0]);
  }
  usdJpyVolumeAutoPushInvestingRowsFromText_(rows, seen, html);
  return rows.sort(function(a, b) { return a.date.localeCompare(b.date); });
}

function usdJpyVolumeAutoPushInvestingRowsFromText_(rows, seen, html) {
  var text = usdJpyVolumeAutoHtmlToText_(html);
  var regex = /(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日\s+([+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s+([+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s+([+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s+([+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)%/g;
  var match;
  while ((match = regex.exec(text)) !== null) {
    usdJpyVolumeAutoAddPriceRow_(rows, seen, {
      date: match[1] + '-' + ('0' + match[2]).slice(-2) + '-' + ('0' + match[3]).slice(-2),
      close: usdJpyVolumeAutoNumber_(match[4]),
      open: usdJpyVolumeAutoNumber_(match[5]),
      high: usdJpyVolumeAutoNumber_(match[6]),
      low: usdJpyVolumeAutoNumber_(match[7]),
      priceChangePct: usdJpyVolumeAutoNumber_(match[8])
    });
  }
}

function usdJpyVolumeAutoPushInvestingRow_(rows, seen, htmlRow) {
  var text = usdJpyVolumeAutoHtmlToText_(htmlRow);
  var dateMatch = text.match(/(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日/);
  if (!dateMatch) return;
  var date = dateMatch[1] + '-' + ('0' + dateMatch[2]).slice(-2) + '-' + ('0' + dateMatch[3]).slice(-2);
  var rest = text.slice(dateMatch.index + dateMatch[0].length);
  var nums = rest.match(/[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?/g) || [];
  if (nums.length < 5) return;
  usdJpyVolumeAutoAddPriceRow_(rows, seen, {
    date: date,
    close: usdJpyVolumeAutoNumber_(nums[0]),
    open: usdJpyVolumeAutoNumber_(nums[1]),
    high: usdJpyVolumeAutoNumber_(nums[2]),
    low: usdJpyVolumeAutoNumber_(nums[3]),
    priceChangePct: usdJpyVolumeAutoNumber_(nums[4])
  });
}

function usdJpyVolumeAutoFetchYahooRows_() {
  var now = new Date();
  var start = new Date(now.getFullYear(), now.getMonth() - USDJPY_VOLUME_PAGE_AUTO_CONFIG.priceMonthsBack, 1);
  var url = USDJPY_VOLUME_PAGE_AUTO_CONFIG.yahooChartUrl +
    '?period1=' + Math.floor(start.getTime() / 1000) +
    '&period2=' + Math.floor((now.getTime() + 86400000) / 1000) +
    '&interval=1d&events=history';
  var response = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: { 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json' }
  });
  var code = response.getResponseCode();
  if (code !== 200) throw new Error('HTTP ' + code);
  var payload = JSON.parse(response.getContentText('UTF-8'));
  var result = payload.chart && payload.chart.result && payload.chart.result[0];
  if (!result || !result.timestamp || !result.indicators || !result.indicators.quote) {
    throw new Error('チャートデータがありません。');
  }
  var timestamps = result.timestamp;
  var quote = result.indicators.quote[0];
  var rows = [];
  for (var i = 0; i < timestamps.length; i += 1) {
    var close = usdJpyVolumeAutoFinite_(quote.close && quote.close[i]);
    var open = usdJpyVolumeAutoFinite_(quote.open && quote.open[i]);
    var high = usdJpyVolumeAutoFinite_(quote.high && quote.high[i]);
    var low = usdJpyVolumeAutoFinite_(quote.low && quote.low[i]);
    if (close === null || open === null || high === null || low === null) continue;
    rows.push({
      date: Utilities.formatDate(new Date(timestamps[i] * 1000), USDJPY_VOLUME_PAGE_AUTO_CONFIG.timezone, 'yyyy-MM-dd'),
      close: usdJpyVolumeAutoRound_(close, 2),
      open: usdJpyVolumeAutoRound_(open, 2),
      high: usdJpyVolumeAutoRound_(high, 2),
      low: usdJpyVolumeAutoRound_(low, 2),
      priceChangePct: null
    });
  }
  rows.sort(function(a, b) { return a.date.localeCompare(b.date); });
  for (var j = 0; j < rows.length; j += 1) {
    if (rows[j].priceChangePct !== null) continue;
    var previous = j > 0 ? rows[j - 1] : null;
    rows[j].priceChangePct = previous && previous.close ?
      usdJpyVolumeAutoRound_((rows[j].close - previous.close) / previous.close * 100, 2) :
      null;
  }
  if (!rows.length) throw new Error('有効な価格行がありません。');
  return rows;
}

function usdJpyVolumeAutoAddPriceRow_(rows, seen, row) {
  if (!row.date || seen[row.date]) return;
  if ([row.close, row.open, row.high, row.low].some(function(value) { return value === null; })) return;
  seen[row.date] = true;
  rows.push({
    date: row.date,
    close: usdJpyVolumeAutoRound_(row.close, 2),
    open: usdJpyVolumeAutoRound_(row.open, 2),
    high: usdJpyVolumeAutoRound_(row.high, 2),
    low: usdJpyVolumeAutoRound_(row.low, 2),
    priceChangePct: row.priceChangePct === null ? null : usdJpyVolumeAutoRound_(row.priceChangePct, 2)
  });
}

function usdJpyVolumeAutoFetchBojPublications_() {
  var response = UrlFetchApp.fetch(USDJPY_VOLUME_PAGE_AUTO_CONFIG.bojSourceUrl, {
    method: 'get',
    muteHttpExceptions: true,
    headers: { Accept: 'text/html,application/xhtml+xml' }
  });
  if (response.getResponseCode() !== 200) {
    throw new Error('日銀外国為替市況一覧を取得できませんでした。HTTP ' + response.getResponseCode());
  }
  var html = response.getContentText('UTF-8');
  var results = [];
  var seen = {};
  var regex = /href=["']([^"']*fx(\d{6})\.pdf)["']/gi;
  var match;
  while ((match = regex.exec(html)) !== null) {
    var pdfName = 'fx' + match[2] + '.pdf';
    var date = '20' + match[2].slice(0, 2) + '-' + match[2].slice(2, 4) + '-' + match[2].slice(4, 6);
    if (seen[date]) continue;
    seen[date] = true;
    results.push({
      date: date,
      pdfName: pdfName,
      url: usdJpyVolumeAutoAbsoluteUrl_(match[1])
    });
  }
  if (!results.length) throw new Error('日銀外国為替市況一覧からPDFリンクを取得できませんでした。');
  return results.sort(function(a, b) { return a.date.localeCompare(b.date); });
}

function usdJpyVolumeAutoFetchPdfText_(url, pdfName) {
  var response = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: { Accept: 'application/pdf' }
  });
  if (response.getResponseCode() !== 200) {
    throw new Error('日銀PDFを取得できませんでした。HTTP ' + response.getResponseCode() + ' ' + url);
  }
  if (typeof Drive === 'undefined' || !Drive.Files || !Drive.Files.copy) {
    throw new Error('Drive APIが有効ではないため、PDFを文字に変換できません。Apps Scriptのサービスで Drive API を追加してください。');
  }

  var tempName = 'usd_jpy_boj_spot_' + pdfName + '_' + new Date().getTime();
  var pdfFile = null;
  var docId = '';
  try {
    pdfFile = DriveApp.createFile(response.getBlob().setName(tempName + '.pdf'));
    var resource = {
      title: tempName,
      mimeType: MimeType.GOOGLE_DOCS
    };
    var converted = Drive.Files.copy(resource, pdfFile.getId(), {
      ocr: true,
      ocrLanguage: 'ja'
    });
    docId = converted.id;
    return DocumentApp.openById(docId).getBody().getText();
  } finally {
    if (pdfFile) pdfFile.setTrashed(true);
    if (docId) DriveApp.getFileById(docId).setTrashed(true);
  }
}

function usdJpyVolumeAutoParseBojSpotVolume_(text) {
  var normalized = String(text || '').replace(/\r/g, '\n');
  var sectionMatch = normalized.match(/前営業日出来高[\s\S]{0,1200}/);
  if (!sectionMatch) sectionMatch = normalized.match(/Turnover of previous business day[\s\S]{0,1200}/i);
  if (!sectionMatch) {
    throw new Error('PDF本文から「前営業日出来高」を見つけられませんでした。');
  }
  var numbers = (sectionMatch[0].match(/\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?/g) || [])
    .map(usdJpyVolumeAutoNumber_)
    .filter(function(value) { return value !== null && value > 0; });
  if (numbers.length < 1) {
    throw new Error('PDF本文からUSD/JPYスポット出来高を抽出できませんでした。先頭部分: ' + normalized.slice(0, 800));
  }
  return Math.round(numbers[0]);
}

function usdJpyVolumeAutoWriteVolumeRows_(sheet, index, rowsToAdd, rowsToUpdate) {
  rowsToUpdate.forEach(function(item) {
    usdJpyVolumeAutoSetCell_(sheet, item.rowNumber, index.publicationDate, item.publicationDate);
    usdJpyVolumeAutoSetCell_(sheet, item.rowNumber, index.sourcePdfName, item.sourcePdfName);
    usdJpyVolumeAutoSetCell_(sheet, item.rowNumber, index.sourcePdfUrl, item.sourcePdfUrl);
    usdJpyVolumeAutoSetCell_(sheet, item.rowNumber, index.spotVolume, item.spotVolume);
  });
  if (!rowsToAdd.length) return;
  var values = rowsToAdd.map(function(item) {
    var row = new Array(sheet.getLastColumn()).fill('');
    row[index.targetDate] = item.targetDate;
    row[index.publicationDate] = item.publicationDate;
    row[index.sourcePdfName] = item.sourcePdfName;
    row[index.sourcePdfUrl] = item.sourcePdfUrl;
    row[index.spotVolume] = item.spotVolume;
    return row;
  });
  sheet.getRange(sheet.getLastRow() + 1, 1, values.length, values[0].length).setValues(values);
}

function usdJpyVolumeAutoSyncPriceToVolumeSheet_(priceByDate) {
  var sheet = usdJpyVolumeAutoEnsureSheet_(USDJPY_VOLUME_PAGE_AUTO_CONFIG.volumeSheetName, [
    '対象日',
    '公表日',
    '元PDF',
    '元PDF URL',
    'USD/JPYスポット出来高',
    'USD/JPY終値',
    'USD/JPY始値',
    'USD/JPY高値',
    'USD/JPY安値',
    'USD/JPY変化率'
  ]);
  var values = sheet.getDataRange().getValues();
  var headers = values[0].map(function(value) { return String(value || '').trim(); });
  var index = usdJpyVolumeAutoResolveVolumeIndexes_(headers, sheet);
  values = sheet.getDataRange().getValues();
  var updated = 0;
  for (var i = 1; i < values.length; i += 1) {
    var date = usdJpyVolumeAutoDateKey_(values[i][index.targetDate]);
    var price = priceByDate[date];
    if (!price) continue;
    var rowNumber = i + 1;
    updated += usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, index.close, price.close);
    updated += usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, index.open, price.open);
    updated += usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, index.high, price.high);
    updated += usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, index.low, price.low);
    updated += usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, index.priceChangePct, price.priceChangePct);
  }
  usdJpyVolumeAutoSortSheetByDate_(sheet, index.targetDate + 1);
  return updated;
}

function usdJpyVolumeAutoSyncPriceToCloseSheets_(priceList) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var targetSheets = USDJPY_VOLUME_PAGE_AUTO_CONFIG.closeSheetNames
    .map(function(name) { return ss.getSheetByName(name); })
    .filter(Boolean);
  if (!targetSheets.length) {
    targetSheets = [usdJpyVolumeAutoEnsureSheet_(USDJPY_VOLUME_PAGE_AUTO_CONFIG.closeSheetNames[0], ['日付'])];
  }
  var updated = 0;
  targetSheets.forEach(function(sheet) {
    updated += usdJpyVolumeAutoSyncPriceToCloseSheet_(sheet, priceList);
  });
  return updated;
}

function usdJpyVolumeAutoSyncPriceToCloseSheet_(sheet, priceList) {
  var headers = usdJpyVolumeAutoEnsureColumns_(sheet, [
    '日付',
    'USDJPY終値（Investing.com）',
    'USDJPY前日比',
    'USDJPY騰落率',
    'USDJPY始値（Investing.com）',
    'USDJPY高値（Investing.com）',
    'USDJPY安値（Investing.com）',
    'USDJPY価格取得元',
    'USDJPY価格取得日時'
  ]);
  var index = usdJpyVolumeAutoHeaderIndex_(headers);
  var values = sheet.getDataRange().getValues();
  var rowMap = usdJpyVolumeAutoBuildRowMap_(values, index['日付']);
  var updated = 0;
  priceList.forEach(function(price, i) {
    var previous = i > 0 ? priceList[i - 1] : null;
    var change = previous && previous.close ? usdJpyVolumeAutoRound_(price.close - previous.close, 2) : '';
    var existing = rowMap[price.date];
    var rowNumber = existing ? existing.rowNumber : sheet.getLastRow() + 1;
    if (!existing) {
      usdJpyVolumeAutoSetCell_(sheet, rowNumber, index['日付'], price.date);
      rowMap[price.date] = { rowNumber: rowNumber };
      updated += 1;
    }
    updated += usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, index['USDJPY終値（Investing.com）'], price.close);
    updated += usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, index['USDJPY前日比'], change);
    updated += usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, index['USDJPY騰落率'], price.priceChangePct);
    updated += usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, index['USDJPY始値（Investing.com）'], price.open);
    updated += usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, index['USDJPY高値（Investing.com）'], price.high);
    updated += usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, index['USDJPY安値（Investing.com）'], price.low);
    updated += usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, index['USDJPY価格取得元'], price.sourceName || '');
    updated += usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, index['USDJPY価格取得日時'], price.fetchedAt || '');
  });
  usdJpyVolumeAutoSortSheetByDate_(sheet, index['日付'] + 1);
  return updated;
}

function usdJpyVolumeAutoReadPriceSheet_(sheet) {
  var values = sheet.getDataRange().getValues();
  var headers = values[0].map(function(value) { return String(value || '').trim(); });
  var index = usdJpyVolumeAutoHeaderIndex_(headers);
  var byDate = {};
  for (var i = 1; i < values.length; i += 1) {
    var row = values[i];
    var date = usdJpyVolumeAutoDateKey_(row[index['日付']]);
    if (!date) continue;
    byDate[date] = {
      date: date,
      close: usdJpyVolumeAutoNumber_(row[index['USD/JPY終値']]),
      open: usdJpyVolumeAutoNumber_(row[index['USD/JPY始値']]),
      high: usdJpyVolumeAutoNumber_(row[index['USD/JPY高値']]),
      low: usdJpyVolumeAutoNumber_(row[index['USD/JPY安値']]),
      priceChangePct: usdJpyVolumeAutoNumber_(row[index['USD/JPY変化率']]),
      sourceName: String(row[index['取得元']] || ''),
      fetchedAt: String(row[index['取得日時']] || '')
    };
  }
  return { headers: headers, byDate: byDate };
}

function usdJpyVolumeAutoWritePriceSheet_(sheet, byDate) {
  var headers = [
    '日付',
    'USD/JPY終値',
    'USD/JPY始値',
    'USD/JPY高値',
    'USD/JPY安値',
    'USD/JPY変化率',
    '取得元',
    '取得日時'
  ];
  var rows = Object.keys(byDate).sort().reverse().map(function(date) {
    var item = byDate[date];
    return [
      item.date,
      item.close,
      item.open,
      item.high,
      item.low,
      item.priceChangePct,
      item.sourceName || '',
      item.fetchedAt || ''
    ];
  });
  sheet.clearContents();
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  if (rows.length) sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, headers.length);
}

function usdJpyVolumeAutoResolveVolumeIndexes_(headers, sheet) {
  usdJpyVolumeAutoEnsureColumns_(sheet, [
    '対象日',
    '公表日',
    '元PDF',
    '元PDF URL',
    'USD/JPYスポット出来高',
    'USD/JPY終値',
    'USD/JPY始値',
    'USD/JPY高値',
    'USD/JPY安値',
    'USD/JPY変化率'
  ]);
  headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]
    .map(function(value) { return String(value || '').trim(); });
  var aliases = {
    targetDate: ['対象日', 'targetDate', 'target_date', '出来高対象日', '東京市場日'],
    publicationDate: ['公表日', 'publicationDate', 'publication_date', '日銀公表日', 'PDF公表日'],
    sourcePdfName: ['元PDF', 'sourcePdfName', 'source_pdf_name', 'PDF名'],
    sourcePdfUrl: ['元PDF URL', 'sourcePdfUrl', 'source_pdf_url', 'PDF URL'],
    spotVolume: ['USD/JPYスポット出来高', 'スポット出来高', 'spotVolume', 'spot_volume', '出来高'],
    volumeChange: ['出来高前営業日比', 'volumeChange', 'volume_change', '前営業日比'],
    volumeChangePct: ['出来高前営業日比率', 'volumeChangePct', 'volume_change_pct', '前営業日比率'],
    avg20: ['20営業日平均', 'avg20', '20日平均', '20日移動平均'],
    vs20: ['20日平均との差', 'vs20', '20営業日平均との差'],
    vs20Pct: ['20日平均比', 'vs20Pct', 'vs20_pct', '20営業日平均比'],
    close: ['USD/JPY終値', '終値', 'close'],
    open: ['USD/JPY始値', '始値', 'open'],
    high: ['USD/JPY高値', '高値', 'high'],
    low: ['USD/JPY安値', '安値', 'low'],
    priceChangePct: ['USD/JPY変化率', '価格変化率', 'priceChangePct', 'price_change_pct']
  };
  var normalizedHeaders = headers.map(usdJpyVolumeAutoNormalizeHeader_);
  var result = {};
  Object.keys(aliases).forEach(function(key) {
    var candidates = aliases[key].map(usdJpyVolumeAutoNormalizeHeader_);
    result[key] = normalizedHeaders.findIndex(function(header) {
      return candidates.indexOf(header) >= 0;
    });
  });
  ['targetDate', 'publicationDate', 'sourcePdfName', 'sourcePdfUrl', 'spotVolume'].forEach(function(key) {
    if (result[key] < 0) throw new Error('USDJPY_Volumeシートに必須列がありません: ' + aliases[key].join(' または '));
  });
  return result;
}

function uninstallUsdJpyVolumePageScheduledTriggers_(showAlert) {
  var handler = USDJPY_VOLUME_PAGE_AUTO_CONFIG.handler;
  var deleted = 0;
  ScriptApp.getProjectTriggers()
    .filter(function(trigger) { return trigger.getHandlerFunction() === handler; })
    .forEach(function(trigger) {
      ScriptApp.deleteTrigger(trigger);
      deleted += 1;
    });
  if (showAlert) usdJpyVolumeAutoAlert_('USD/JPYページ定時更新トリガーを削除しました。削除数: ' + deleted);
  return deleted;
}

function usdJpyVolumeAutoEnsureSheet_(name, headers) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);
  if (sheet.getLastRow() === 0 || sheet.getLastColumn() === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.setFrozenRows(1);
  } else {
    usdJpyVolumeAutoEnsureColumns_(sheet, headers);
  }
  return sheet;
}

function usdJpyVolumeAutoEnsureColumns_(sheet, requiredHeaders) {
  var lastColumn = Math.max(sheet.getLastColumn(), 1);
  var headers = sheet.getRange(1, 1, 1, lastColumn).getValues()[0]
    .map(function(value) { return String(value || '').trim(); });
  requiredHeaders.forEach(function(header) {
    if (headers.indexOf(header) >= 0) return;
    headers.push(header);
    sheet.getRange(1, headers.length).setValue(header);
  });
  return headers;
}

function usdJpyVolumeAutoBuildRowMap_(values, dateIndex) {
  var map = {};
  for (var i = 1; i < values.length; i += 1) {
    var date = usdJpyVolumeAutoDateKey_(values[i][dateIndex]);
    if (!date) continue;
    map[date] = {
      rowNumber: i + 1,
      row: values[i]
    };
  }
  return map;
}

function usdJpyVolumeAutoVolumeNeedsUpdate_(row, index, next) {
  return usdJpyVolumeAutoDateKey_(row[index.publicationDate]) !== next.publicationDate ||
    String(row[index.sourcePdfName] || '').trim() !== next.sourcePdfName ||
    String(row[index.sourcePdfUrl] || '').trim() !== next.sourcePdfUrl ||
    usdJpyVolumeAutoNumber_(row[index.spotVolume]) !== next.spotVolume;
}

function usdJpyVolumeAutoSavedBojRowIsCurrent_(row, index, publication) {
  return usdJpyVolumeAutoDateKey_(row[index.publicationDate]) === publication.date &&
    String(row[index.sourcePdfName] || '').trim() === publication.pdfName &&
    String(row[index.sourcePdfUrl] || '').trim() === publication.url &&
    usdJpyVolumeAutoNumber_(row[index.spotVolume]) !== null;
}

function usdJpyVolumeAutoPriceChanged_(before, next) {
  return before.close !== next.close ||
    before.open !== next.open ||
    before.high !== next.high ||
    before.low !== next.low ||
    before.priceChangePct !== next.priceChangePct ||
    before.sourceName !== next.sourceName;
}

function usdJpyVolumeAutoSetCell_(sheet, rowNumber, zeroBasedColumn, value) {
  if (zeroBasedColumn < 0) return;
  sheet.getRange(rowNumber, zeroBasedColumn + 1).setValue(value);
}

function usdJpyVolumeAutoSetCellIfChanged_(sheet, rowNumber, zeroBasedColumn, value) {
  if (zeroBasedColumn < 0) return 0;
  var range = sheet.getRange(rowNumber, zeroBasedColumn + 1);
  var current = range.getValue();
  if (String(current) === String(value)) return 0;
  range.setValue(value);
  return 1;
}

function usdJpyVolumeAutoSortSheetByDate_(sheet, oneBasedDateColumn) {
  if (sheet.getLastRow() <= 2) return;
  sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn())
    .sort({ column: oneBasedDateColumn, ascending: false });
}

function usdJpyVolumeAutoRejectSwapHeaders_(headers) {
  var swapHeaders = headers.filter(function(header) {
    return /swap|スワップ/i.test(String(header));
  });
  if (swapHeaders.length) {
    throw new Error('スワップ出来高の列は使用しません。列を同期対象から外してください: ' + swapHeaders.join(', '));
  }
}

function usdJpyVolumeAutoPreviousWeekday_(dateText) {
  var parts = dateText.split('-').map(Number);
  var date = new Date(parts[0], parts[1] - 1, parts[2] - 1);
  while (date.getDay() === 0 || date.getDay() === 6) {
    date.setDate(date.getDate() - 1);
  }
  return Utilities.formatDate(date, USDJPY_VOLUME_PAGE_AUTO_CONFIG.timezone, 'yyyy-MM-dd');
}

function usdJpyVolumeAutoAbsoluteUrl_(href) {
  if (/^https?:\/\//i.test(href)) return href;
  if (href.indexOf('/') === 0) return 'https://www.boj.or.jp' + href;
  return USDJPY_VOLUME_PAGE_AUTO_CONFIG.bojPdfBaseUrl + href.replace(/^\.\//, '');
}

function usdJpyVolumeAutoDateKey_(value) {
  if (Object.prototype.toString.call(value) === '[object Date]' && !isNaN(value)) {
    return Utilities.formatDate(value, USDJPY_VOLUME_PAGE_AUTO_CONFIG.timezone, 'yyyy-MM-dd');
  }
  var text = String(value || '').trim().replace(/\//g, '-');
  var jp = text.match(/^(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日/);
  if (jp) return jp[1] + '-' + ('0' + jp[2]).slice(-2) + '-' + ('0' + jp[3]).slice(-2);
  var match = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (!match) return '';
  return match[1] + '-' + ('0' + match[2]).slice(-2) + '-' + ('0' + match[3]).slice(-2);
}

function usdJpyVolumeAutoNumber_(value) {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  var text = String(value)
    .replace(/,/g, '')
    .replace(/%|％/g, '')
    .replace(/[＋]/g, '+')
    .replace(/[－−▲△]/g, '-')
    .trim();
  if (!text || text === '-' || text === '—' || text === '－') return null;
  var number = Number(text);
  return Number.isFinite(number) ? number : null;
}

function usdJpyVolumeAutoFinite_(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function usdJpyVolumeAutoRound_(value, decimals) {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  var factor = Math.pow(10, decimals);
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

function usdJpyVolumeAutoIsoJst_(date) {
  return Utilities.formatDate(date, USDJPY_VOLUME_PAGE_AUTO_CONFIG.timezone, "yyyy-MM-dd'T'HH:mm:ss") + '+09:00';
}

function usdJpyVolumeAutoHeaderIndex_(headers) {
  var index = {};
  (headers || []).forEach(function(header, i) {
    var key = String(header || '').trim();
    if (key && !Object.prototype.hasOwnProperty.call(index, key)) index[key] = i;
  });
  return index;
}

function usdJpyVolumeAutoNormalizeHeader_(value) {
  return String(value || '')
    .replace(/\s/g, '')
    .replace(/[（）]/g, function(match) { return match === '（' ? '(' : ')'; })
    .toLowerCase();
}

function usdJpyVolumeAutoHtmlToText_(html) {
  return usdJpyVolumeAutoDecodeHtml_(String(html || '')
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim());
}

function usdJpyVolumeAutoDecodeHtml_(text) {
  return String(text || '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'");
}

function usdJpyVolumeAutoAlert_(message) {
  try {
    SpreadsheetApp.getUi().alert(message);
  } catch (error) {
    Logger.log(message);
  }
}

function usdJpyVolumeAutoEscapeHtml_(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
