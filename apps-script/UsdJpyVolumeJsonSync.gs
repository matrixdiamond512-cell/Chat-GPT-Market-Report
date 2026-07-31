const USDJPY_VOLUME_JSON_CONFIG = {
  sheetName: 'USDJPY_Volume',
  targetPath: 'data/usdjpy-volume.json',
  timezone: 'Asia/Tokyo',
  staleDays: 3,
  sourceUrl: 'https://www.boj.or.jp/statistics/market/forex/fxdaily/fxlist/index.htm',
  pdfBaseUrl: 'https://www.boj.or.jp/statistics/market/forex/fxdaily/fxlist/',
  priceSourceName: 'Investing.com USD/JPY日足OHLC',
  priceSourceUrl: 'https://jp.investing.com/currencies/usd-jpy-historical-data',
  properties: {
    priceRangeStart: 'USDJPY_VOLUME_PRICE_RANGE_START',
    priceRangeEnd: 'USDJPY_VOLUME_PRICE_RANGE_END',
    priceRangeCount: 'USDJPY_VOLUME_PRICE_RANGE_COUNT',
    lastResult: 'USDJPY_VOLUME_JSON_LAST_RESULT'
  },
  headers: {
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
    close: ['終値', 'close', 'USD/JPY終値'],
    open: ['始値', 'open', 'USD/JPY始値'],
    high: ['高値', 'high', 'USD/JPY高値'],
    low: ['安値', 'low', 'USD/JPY安値'],
    priceChangePct: ['価格変化率', 'priceChangePct', 'price_change_pct', 'USD/JPY変化率']
  },
  requiredHeaders: ['targetDate', 'publicationDate', 'spotVolume', 'close', 'open', 'high', 'low']
};

function previewUsdJpyVolumeJson() {
  const json = buildUsdJpyVolumeJson_();
  const html = HtmlService.createHtmlOutput(
    '<pre style="white-space:pre-wrap;font-size:12px">' + usdJpyVolumeEscapeHtml_(json) + '</pre>'
  ).setWidth(920).setHeight(700);
  SpreadsheetApp.getUi().showModalDialog(html, 'USD/JPY出来高JSONプレビュー');
}

function syncUsdJpyVolumeJsonToGitHub() {
  const lock = LockService.getDocumentLock();
  lock.waitLock(30000);
  try {
    const json = buildUsdJpyVolumeJson_();
    const current = getGitHubJsonFile_(USDJPY_VOLUME_JSON_CONFIG.targetPath);
    const result = putGitHubJsonFile_(
      USDJPY_VOLUME_JSON_CONFIG.targetPath,
      json,
      current.sha,
      'Update USDJPY volume JSON from Google Sheets'
    );
    const payload = JSON.parse(json);
    const summary = {
      ok: true,
      targetPath: USDJPY_VOLUME_JSON_CONFIG.targetPath,
      latestTargetDate: payload.components.bojSpotVolume.latestTargetDate,
      latestPublicationDate: payload.components.bojSpotVolume.latestPublicationDate,
      recordCount: payload.data.records.length,
      commitSha: result.commit.sha
    };
    PropertiesService.getScriptProperties().setProperty(
      USDJPY_VOLUME_JSON_CONFIG.properties.lastResult,
      JSON.stringify(summary)
    );
    usdJpyVolumeAlert_(
      'USD/JPY出来高JSONをGitHubへ反映しました。\n' +
      'ファイル: ' + summary.targetPath + '\n' +
      '対象日: ' + summary.latestTargetDate + '\n' +
      '公表日: ' + summary.latestPublicationDate + '\n' +
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

function buildUsdJpyVolumeJson_() {
  return JSON.stringify(buildUsdJpyVolumePayload_()) + '\n';
}

function buildUsdJpyVolumePayload_() {
  const config = USDJPY_VOLUME_JSON_CONFIG;
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(config.sheetName);
  if (!sheet) throw new Error('シート「' + config.sheetName + '」が見つかりません。');

  const values = sheet.getDataRange().getValues();
  if (values.length < 2) throw new Error('シート「' + config.sheetName + '」にデータ行がありません。');

  const headers = values[0].map(value => String(value || '').trim());
  usdJpyVolumeRejectSwapHeaders_(headers);
  const indexes = usdJpyVolumeResolveHeaderIndexes_(headers);
  const timezone = config.timezone;

  const rows = values.slice(1).map((row, offset) => {
    return usdJpyVolumeRecordFromRow_(row, indexes, offset + 2, timezone);
  }).filter(Boolean).sort((a, b) => a.targetDate.localeCompare(b.targetDate));

  if (!rows.length) throw new Error('出力対象のUSD/JPYスポット出来高データがありません。');
  usdJpyVolumeValidateDuplicateDates_(rows);
  const enriched = usdJpyVolumeEnrichRecords_(rows);
  const records = enriched.slice().reverse();
  const latest = records[0];
  const now = new Date();
  const generatedAt = usdJpyVolumeIsoJst_(now, timezone);
  const priceRange = usdJpyVolumeBuildPriceRange_(records);
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
        asOf: priceRange.endDate,
        status: 'ok',
        fields: ['始値', '高値', '安値', '終値', '価格変化率'],
        note: '対象日を日銀スポット出来高の対象日と照合。'
      }
    ],
    components: {
      bojSpotVolume: {
        status: 'ok',
        sourceId: 'BOJ_FX_DAILY',
        latestTargetDate: latest.targetDate,
        latestPublicationDate: latest.publicationDate,
        rule: '日銀PDFのUSD/JPYスポット出来高のみ。スワップ出来高は使用しない。'
      },
      usdjpyOhlc: {
        status: 'ok',
        sourceId: 'INV_USDJPY',
        latestDate: latest.targetDate
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
        summary: usdJpyVolumeSummary_(latest)
      },
      records: records,
      priceRange: priceRange
    }
  };
}

function usdJpyVolumeRecordFromRow_(row, indexes, rowNumber, timezone) {
  if (row.every(value => value === '' || value === null)) return null;

  const targetDate = usdJpyVolumeRequiredDate_(row[indexes.targetDate], timezone, rowNumber, '対象日');
  const publicationDate = usdJpyVolumeRequiredDate_(row[indexes.publicationDate], timezone, rowNumber, '公表日');
  if (!usdJpyVolumePublicationAfterTarget_(targetDate, publicationDate)) {
    throw new Error(rowNumber + '行目: 対象日と公表日の関係を確認してください（対象日: ' + targetDate + ' / 公表日: ' + publicationDate + '）。');
  }

  const sourcePdfName = usdJpyVolumeText_(row[indexes.sourcePdfName]) || usdJpyVolumePdfNameFromPublicationDate_(publicationDate);
  const sourcePdfUrl = usdJpyVolumeText_(row[indexes.sourcePdfUrl]) || USDJPY_VOLUME_JSON_CONFIG.pdfBaseUrl + sourcePdfName;
  const record = {
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
    close: usdJpyVolumeRequiredNumber_(row[indexes.close], rowNumber, '終値'),
    open: usdJpyVolumeRequiredNumber_(row[indexes.open], rowNumber, '始値'),
    high: usdJpyVolumeRequiredNumber_(row[indexes.high], rowNumber, '高値'),
    low: usdJpyVolumeRequiredNumber_(row[indexes.low], rowNumber, '安値'),
    priceChangePct: usdJpyVolumeOptionalPercentPoint_(row[indexes.priceChangePct])
  };

  return record;
}

function usdJpyVolumeEnrichRecords_(rows) {
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
      const window = list.slice(index - 19, index + 1).map(item => item.spotVolume);
      current.avg20 = usdJpyVolumeRound_(usdJpyVolumeAverage_(window), 0);
    }
    if (current.vs20 === null && current.avg20 !== null) {
      current.vs20 = usdJpyVolumeRound_(current.spotVolume - current.avg20, 0);
    }
    if (current.vs20Pct === null && current.avg20 !== null && current.avg20 !== 0) {
      current.vs20Pct = usdJpyVolumeRound_(current.vs20 / current.avg20 * 100, 2);
    }
    if (current.priceChangePct === null && previous && previous.close !== 0) {
      current.priceChangePct = usdJpyVolumeRound_((current.close - previous.close) / previous.close * 100, 2);
    }

    return current;
  });
}

function usdJpyVolumeBuildPriceRange_(records) {
  const props = PropertiesService.getScriptProperties();
  const keys = USDJPY_VOLUME_JSON_CONFIG.properties;
  const latest = records[0];
  const oldest = records[records.length - 1];
  const count = usdJpyVolumeOptionalInteger_(props.getProperty(keys.priceRangeCount));

  return {
    startDate: props.getProperty(keys.priceRangeStart) || oldest.targetDate,
    endDate: props.getProperty(keys.priceRangeEnd) || latest.targetDate,
    count: count || records.length
  };
}

function usdJpyVolumeBuildStaleInfo_(publicationDate, now, timezone) {
  const today = Utilities.formatDate(now, timezone, 'yyyy-MM-dd');
  const elapsedDays = usdJpyVolumeDayDiff_(publicationDate, today);
  const isStale = elapsedDays > USDJPY_VOLUME_JSON_CONFIG.staleDays;
  return {
    isStale: isStale,
    staleReason: isStale ? '最新公表日から' + elapsedDays + '日経過しています。' : ''
  };
}

function usdJpyVolumeSummary_(record) {
  if (record.vs20 === null) {
    return '直近のUSD/JPYスポット出来高は20営業日平均との比較対象外です。同日のUSD/JPY終値は' + usdJpyVolumeFormatNumber_(record.close, 2) + '円です。';
  }
  return '直近のUSD/JPYスポット出来高は20営業日平均を' +
    (record.vs20 < 0 ? '下回っています' : '上回っています') +
    '。同日のUSD/JPY終値は' + usdJpyVolumeFormatNumber_(record.close, 2) + '円です。';
}

function usdJpyVolumeLevel_(record) {
  if (record.vs20Pct === null) return '判定対象外';
  if (record.vs20Pct >= 20) return '多い';
  if (record.vs20Pct <= -20) return '少ない';
  return '通常';
}

function usdJpyVolumeResolveHeaderIndexes_(headers) {
  const result = {};
  const normalizedHeaders = headers.map(usdJpyVolumeNormalizeHeader_);
  Object.keys(USDJPY_VOLUME_JSON_CONFIG.headers).forEach(key => {
    const candidates = USDJPY_VOLUME_JSON_CONFIG.headers[key].map(usdJpyVolumeNormalizeHeader_);
    result[key] = normalizedHeaders.findIndex(header => candidates.includes(header));
  });

  USDJPY_VOLUME_JSON_CONFIG.requiredHeaders.forEach(key => {
    if (result[key] < 0) {
      throw new Error('必須列がありません: ' + USDJPY_VOLUME_JSON_CONFIG.headers[key].join(' または '));
    }
  });
  return result;
}

function usdJpyVolumeRejectSwapHeaders_(headers) {
  const swapHeaders = headers.filter(header => /swap|スワップ/i.test(String(header)));
  if (swapHeaders.length) {
    throw new Error('スワップ出来高の列は使用しません。列を同期対象から外してください: ' + swapHeaders.join(', '));
  }
}

function usdJpyVolumeValidateDuplicateDates_(rows) {
  const seen = {};
  const duplicates = [];
  rows.forEach(row => {
    if (seen[row.targetDate]) duplicates.push(row.targetDate);
    seen[row.targetDate] = true;
  });
  if (duplicates.length) throw new Error('対象日が重複しています: ' + [...new Set(duplicates)].join(', '));
}

function usdJpyVolumeRequiredDate_(value, timezone, rowNumber, label) {
  const date = usdJpyVolumeDate_(value, timezone);
  if (!date) throw new Error(rowNumber + '行目: ' + label + 'を yyyy-mm-dd 形式で入力してください。');
  return date;
}

function usdJpyVolumeDate_(value, timezone) {
  if (Object.prototype.toString.call(value) === '[object Date]' && !isNaN(value)) {
    return Utilities.formatDate(value, timezone, 'yyyy-MM-dd');
  }
  const text = String(value || '').trim().replace(/\//g, '-');
  const match = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (!match) return '';
  return match[1] + '-' + ('0' + match[2]).slice(-2) + '-' + ('0' + match[3]).slice(-2);
}

function usdJpyVolumePublicationAfterTarget_(targetDate, publicationDate) {
  return usdJpyVolumeDateMs_(publicationDate) > usdJpyVolumeDateMs_(targetDate);
}

function usdJpyVolumeDayDiff_(fromDate, toDate) {
  const dayMs = 24 * 60 * 60 * 1000;
  return Math.floor((usdJpyVolumeDateMs_(toDate) - usdJpyVolumeDateMs_(fromDate)) / dayMs);
}

function usdJpyVolumeDateMs_(date) {
  const parts = String(date).split('-').map(Number);
  return new Date(parts[0], parts[1] - 1, parts[2]).getTime();
}

function usdJpyVolumeRequiredNumber_(value, rowNumber, label) {
  const number = usdJpyVolumeOptionalNumber_(value);
  if (number === null) throw new Error(rowNumber + '行目: ' + label + 'が数値ではありません。');
  return number;
}

function usdJpyVolumeOptionalInteger_(value) {
  const number = usdJpyVolumeOptionalNumber_(value);
  return number === null ? null : usdJpyVolumeRound_(number, 0);
}

function usdJpyVolumeOptionalPercentPoint_(value) {
  return usdJpyVolumeOptionalNumber_(value);
}

function usdJpyVolumeOptionalNumber_(value) {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  const text = String(value)
    .replace(/,/g, '')
    .replace(/％/g, '%')
    .replace(/▲/g, '-')
    .replace(/△/g, '-')
    .replace(/[＋]/g, '+')
    .replace(/[－−]/g, '-')
    .trim();
  if (text === '' || text === '-' || text === '—' || text === '－') return null;
  const normalized = text.endsWith('%') ? text.slice(0, -1) : text;
  const number = Number(normalized);
  return Number.isFinite(number) ? number : null;
}

function usdJpyVolumeText_(value) {
  if (value === null || value === undefined) return '';
  return String(value).trim();
}

function usdJpyVolumePdfNameFromPublicationDate_(publicationDate) {
  const year = publicationDate.slice(2, 4);
  const month = publicationDate.slice(5, 7);
  const day = publicationDate.slice(8, 10);
  return 'fx' + year + month + day + '.pdf';
}

function usdJpyVolumeNormalizeHeader_(value) {
  return String(value || '')
    .replace(/\s/g, '')
    .replace(/[（）]/g, match => match === '（' ? '(' : ')')
    .toLowerCase();
}

function usdJpyVolumeAverage_(values) {
  const valid = values.filter(value => Number.isFinite(value));
  return valid.reduce((sum, value) => sum + value, 0) / valid.length;
}

function usdJpyVolumeRound_(value, decimals) {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  const factor = Math.pow(10, decimals);
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

function usdJpyVolumeIsoJst_(date, timezone) {
  return Utilities.formatDate(date, timezone, "yyyy-MM-dd'T'HH:mm:ss") + '+09:00';
}

function usdJpyVolumeFormatNumber_(value, decimals) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '';
  return value.toLocaleString('ja-JP', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

function usdJpyVolumeAlert_(message) {
  try {
    SpreadsheetApp.getUi().alert(message);
  } catch (error) {
    Logger.log(message);
  }
}

function usdJpyVolumeEscapeHtml_(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
