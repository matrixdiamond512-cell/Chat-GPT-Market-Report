function previewUsdJpyVolumeJsonFlexible() {
  const json = buildUsdJpyVolumeJsonFlexible_();
  const html = HtmlService.createHtmlOutput(
    '<pre style="white-space:pre-wrap;font-size:12px">' + usdJpyVolumeEscapeHtml_(json) + '</pre>'
  ).setWidth(920).setHeight(700);
  SpreadsheetApp.getUi().showModalDialog(html, 'USD/JPY出来高JSONプレビュー');
}

function syncUsdJpyVolumeJsonToGitHubFlexible() {
  const lock = LockService.getDocumentLock();
  lock.waitLock(30000);
  try {
    const json = buildUsdJpyVolumeJsonFlexible_();
    const current = getGitHubJsonFile_(USDJPY_VOLUME_JSON_CONFIG.targetPath);
    const result = putGitHubJsonFile_(
      USDJPY_VOLUME_JSON_CONFIG.targetPath,
      json,
      current.sha,
      'Update USDJPY volume JSON from BOJ spot data'
    );
    const payload = JSON.parse(json);
    const summary = {
      ok: true,
      targetPath: USDJPY_VOLUME_JSON_CONFIG.targetPath,
      latestTargetDate: payload.components.bojSpotVolume.latestTargetDate,
      latestPublicationDate: payload.components.bojSpotVolume.latestPublicationDate,
      priceStatus: payload.components.usdjpyOhlc.status,
      recordCount: payload.data.records.length,
      commitSha: result.commit.sha
    };
    PropertiesService.getScriptProperties().setProperty(
      USDJPY_VOLUME_JSON_CONFIG.properties.lastResult,
      JSON.stringify(summary)
    );
    usdJpyVolumeAlert_(
      'USD/JPY出来高JSONをGitHubへ反映しました。\n' +
      '対象日: ' + summary.latestTargetDate + '\n' +
      '公表日: ' + summary.latestPublicationDate + '\n' +
      '価格: ' + summary.priceStatus + '\n' +
      '件数: ' + summary.recordCount + '\n' +
      'コミット: ' + summary.commitSha
    );
    return summary;
  } catch (error) {
    usdJpyVolumeAlert_('USD/JPY出来高JSONを反映できませんでした。\n' + error.message);
    throw error;
  } finally {
    lock.releaseLock();
  }
}

function importUsdJpySpotVolumeFromBojAndSyncJsonFlexible() {
  const importSummary = usdJpyBojImportSpotVolume_(false);
  const syncSummary = syncUsdJpyVolumeJsonToGitHubFlexible();
  return { importSummary: importSummary, syncSummary: syncSummary };
}

function buildUsdJpyVolumeJsonFlexible_() {
  return JSON.stringify(buildUsdJpyVolumePayloadFlexible_()) + '\n';
}

function buildUsdJpyVolumePayloadFlexible_() {
  const config = USDJPY_VOLUME_JSON_CONFIG;
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(config.sheetName);
  if (!sheet) throw new Error('シート「' + config.sheetName + '」が見つかりません。');

  const values = sheet.getDataRange().getValues();
  if (values.length < 2) throw new Error('シート「' + config.sheetName + '」にデータ行がありません。');

  const headers = values[0].map(value => String(value || '').trim());
  usdJpyVolumeRejectSwapHeaders_(headers);
  const indexes = usdJpyVolumeResolveFlexibleHeaderIndexes_(headers);
  const timezone = config.timezone;
  const rows = values.slice(1).map((row, offset) => {
    return usdJpyVolumeFlexibleRecordFromRow_(row, indexes, offset + 2, timezone);
  }).filter(Boolean).sort((a, b) => a.targetDate.localeCompare(b.targetDate));

  if (!rows.length) throw new Error('出力対象のUSD/JPYスポット出来高データがありません。');
  usdJpyVolumeValidateDuplicateDates_(rows);

  const enriched = usdJpyVolumeFlexibleEnrichRecords_(rows);
  const records = enriched.slice().reverse();
  const latest = records[0];
  const priceRecords = records
    .filter(record => record.close !== null || record.open !== null || record.high !== null || record.low !== null)
    .map(record => ({
      date: record.targetDate,
      close: record.close,
      open: record.open,
      high: record.high,
      low: record.low,
      priceChangePct: record.priceChangePct
    }));
  const latestPriceRecord = priceRecords.length ? priceRecords[0] : null;
  const hasLatestPrice = latestPriceRecord && latestPriceRecord.date === latest.targetDate;
  const now = new Date();
  const generatedAt = usdJpyVolumeIsoJst_(now, timezone);
  const priceRange = usdJpyVolumeFlexibleBuildPriceRange_(records, priceRecords);
  const staleInfo = usdJpyVolumeBuildStaleInfo_(latest.publicationDate, now, timezone);

  return {
    schemaVersion: '1.0.0',
    pageId: 'usdjpy-volume',
    reportDateTime: generatedAt,
    dataAsOf: latest.targetDate + 'T15:00:00+09:00',
    generatedAt: generatedAt,
    publishedAt: generatedAt,
    status: 'ok',
    isStale: staleInfo.isStale,
    staleReason: staleInfo.staleReason,
    sources: [
      {
        id: 'BOJ_FX_DAILY',
        name: '日本銀行 外国為替市況（日次）',
        url: config.sourceUrl,
        asOf: latest.publicationDate,
        status: 'ok',
        fields: ['USD/JPYスポット出来高', '公表日', '元PDF'],
        note: 'スポット出来高のみ。対象日は公表日の前営業日。'
      },
      {
        id: 'INV_USDJPY',
        name: config.priceSourceName,
        url: config.priceSourceUrl,
        asOf: latestPriceRecord ? latestPriceRecord.date : '',
        status: hasLatestPrice ? 'ok' : 'warning',
        fields: ['始値', '高値', '安値', '終値', '価格変化率'],
        note: hasLatestPrice ? '対象日を日銀スポット出来高の対象日と照合。' : '最新出来高日のInvesting.com USD/JPY日足OHLCが未入力です。'
      }
    ],
    components: {
      bojSpotVolume: {
        status: 'ok',
        sourceId: 'BOJ_FX_DAILY',
        latestTargetDate: latest.targetDate,
        latestPublicationDate: latest.publicationDate,
        rule: '日銀外国為替市況のUSD/JPYスポット出来高のみ。スワップ出来高は使用しない。'
      },
      usdjpyOhlc: {
        status: hasLatestPrice ? 'ok' : 'warning',
        sourceId: 'INV_USDJPY',
        latestDate: latestPriceRecord ? latestPriceRecord.date : '',
        note: hasLatestPrice ? '' : '最新出来高日のInvesting.com USD/JPY日足OHLCが未入力です。'
      }
    },
    errors: [],
    data: {
      sourceName: '日本銀行 外国為替市況（日次）',
      sourceUrl: config.sourceUrl,
      pdfBaseUrl: config.pdfBaseUrl,
      priceSourceName: config.priceSourceName,
      unit: '百万ドル',
      latestJudgement: {
        targetDate: latest.targetDate,
        publicationDate: latest.publicationDate,
        spotVolumeLevel: usdJpyVolumeLevel_(latest),
        summary: usdJpyVolumeFlexibleSummary_(latest)
      },
      records: records,
      priceRange: priceRange,
      priceRecords: priceRecords
    }
  };
}

function usdJpyVolumeResolveFlexibleHeaderIndexes_(headers) {
  const result = {};
  const normalizedHeaders = headers.map(usdJpyVolumeNormalizeHeader_);
  Object.keys(USDJPY_VOLUME_JSON_CONFIG.headers).forEach(key => {
    const candidates = USDJPY_VOLUME_JSON_CONFIG.headers[key].map(usdJpyVolumeNormalizeHeader_);
    result[key] = normalizedHeaders.findIndex(header => candidates.includes(header));
  });
  ['targetDate', 'publicationDate', 'spotVolume'].forEach(key => {
    if (result[key] < 0) {
      throw new Error('必須列がありません: ' + USDJPY_VOLUME_JSON_CONFIG.headers[key].join(' または '));
    }
  });
  return result;
}

function usdJpyVolumeFlexibleRecordFromRow_(row, indexes, rowNumber, timezone) {
  if (row.every(value => value === '' || value === null)) return null;
  const targetDate = usdJpyVolumeRequiredDate_(row[indexes.targetDate], timezone, rowNumber, '対象日');
  const publicationDate = usdJpyVolumeRequiredDate_(row[indexes.publicationDate], timezone, rowNumber, '公表日');
  if (!usdJpyVolumePublicationAfterTarget_(targetDate, publicationDate)) {
    throw new Error(rowNumber + '行目: 対象日と公表日の関係を確認してください（対象日: ' + targetDate + ' / 公表日: ' + publicationDate + '）。');
  }

  const sourcePdfName = usdJpyVolumeFlexibleText_(row, indexes.sourcePdfName) || usdJpyVolumePdfNameFromPublicationDate_(publicationDate);
  const sourcePdfUrl = usdJpyVolumeFlexibleText_(row, indexes.sourcePdfUrl) || USDJPY_VOLUME_JSON_CONFIG.pdfBaseUrl + sourcePdfName;
  return {
    targetDate: targetDate,
    publicationDate: publicationDate,
    sourcePdfName: sourcePdfName,
    sourcePdfUrl: sourcePdfUrl,
    spotVolume: usdJpyVolumeRequiredNumber_(row[indexes.spotVolume], rowNumber, 'USD/JPYスポット出来高'),
    volumeChange: usdJpyVolumeOptionalInteger_(row[indexes.volumeChange]),
    volumeChangePct: usdJpyVolumeOptionalPercentPoint_(row[indexes.volumeChangePct]),
    avg20: usdJpyVolumeOptionalInteger_(row[indexes.avg20]),
    vs20: usdJpyVolumeOptionalInteger_(row[indexes.vs20]),
    vs20Pct: usdJpyVolumeOptionalPercentPoint_(row[indexes.vs20Pct]),
    close: usdJpyVolumeFlexibleNumber_(row, indexes.close),
    open: usdJpyVolumeFlexibleNumber_(row, indexes.open),
    high: usdJpyVolumeFlexibleNumber_(row, indexes.high),
    low: usdJpyVolumeFlexibleNumber_(row, indexes.low),
    priceChangePct: usdJpyVolumeOptionalPercentPoint_(row[indexes.priceChangePct])
  };
}

function usdJpyVolumeFlexibleEnrichRecords_(rows) {
  return rows.map((record, index, list) => {
    const current = Object.assign({}, record);
    const previous = index > 0 ? list[index - 1] : null;
    if (current.volumeChange === null && previous) {
      current.volumeChange = usdJpyVolumeRound_(current.spotVolume - previous.spotVolume, 0);
    }
    if (current.volumeChangePct === null && previous && previous.spotVolume !== 0) {
      current.volumeChangePct = usdJpyVolumeRound_(current.volumeChange / previous.spotVolume * 100, 2);
    }
    if (current.avg20 === null && index >= 19) {
      current.avg20 = usdJpyVolumeRound_(usdJpyVolumeAverage_(list.slice(index - 19, index + 1).map(item => item.spotVolume)), 0);
    }
    if (current.vs20 === null && current.avg20 !== null) {
      current.vs20 = usdJpyVolumeRound_(current.spotVolume - current.avg20, 0);
    }
    if (current.vs20Pct === null && current.avg20 !== null && current.avg20 !== 0) {
      current.vs20Pct = usdJpyVolumeRound_(current.vs20 / current.avg20 * 100, 2);
    }
    if (current.priceChangePct === null && previous && current.close !== null && previous.close !== null && previous.close !== 0) {
      current.priceChangePct = usdJpyVolumeRound_((current.close - previous.close) / previous.close * 100, 2);
    }
    return current;
  });
}

function usdJpyVolumeFlexibleBuildPriceRange_(records, priceRecords) {
  const props = PropertiesService.getScriptProperties();
  const keys = USDJPY_VOLUME_JSON_CONFIG.properties;
  const latest = records[0];
  const oldest = records[records.length - 1];
  const latestPrice = priceRecords.length ? priceRecords[0] : null;
  const oldestPrice = priceRecords.length ? priceRecords[priceRecords.length - 1] : null;
  const count = usdJpyVolumeOptionalInteger_(props.getProperty(keys.priceRangeCount));
  return {
    startDate: props.getProperty(keys.priceRangeStart) || (oldestPrice ? oldestPrice.date : oldest.targetDate),
    endDate: props.getProperty(keys.priceRangeEnd) || (latestPrice ? latestPrice.date : latest.targetDate),
    count: count || (priceRecords.length || records.length)
  };
}

function usdJpyVolumeFlexibleSummary_(record) {
  if (record.vs20 === null) {
    if (record.close === null) return '直近のUSD/JPYスポット出来高は20営業日平均との比較対象外です。USD/JPY価格は未入力です。';
    return '直近のUSD/JPYスポット出来高は20営業日平均との比較対象外です。同日のUSD/JPY終値は' + usdJpyVolumeFormatNumber_(record.close, 2) + '円です。';
  }
  if (record.close === null) {
    return '直近のUSD/JPYスポット出来高は20営業日平均を' + (record.vs20 < 0 ? '下回っています' : '上回っています') + '。同日のUSD/JPY価格は未入力です。';
  }
  return '直近のUSD/JPYスポット出来高は20営業日平均を' +
    (record.vs20 < 0 ? '下回っています' : '上回っています') +
    '。同日のUSD/JPY終値は' + usdJpyVolumeFormatNumber_(record.close, 2) + '円です。';
}

function usdJpyVolumeFlexibleNumber_(row, index) {
  return index >= 0 ? usdJpyVolumeOptionalNumber_(row[index]) : null;
}

function usdJpyVolumeFlexibleText_(row, index) {
  return index >= 0 ? usdJpyVolumeText_(row[index]) : '';
}
