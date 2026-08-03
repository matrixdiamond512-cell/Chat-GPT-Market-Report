const USDJPY_BOJ_SPOT_IMPORT_CONFIG = {
  sheetName: 'USDJPY_Volume',
  timezone: 'Asia/Tokyo',
  apiCode: 'FXERD06',
  apiDb: 'FM08',
  apiUrls: [
    'https://www.stat-search.boj.or.jp/api/v1/getData',
    'https://www.stat-search.boj.or.jp/api/v1/getDataCode'
  ],
  sourceUrl: 'https://www.boj.or.jp/statistics/market/forex/fxdaily/fxlist/index.htm',
  pdfBaseUrl: 'https://www.boj.or.jp/statistics/market/forex/fxdaily/fxlist/',
  monthsBack: 5,
  maxPreviewRows: 12,
  columns: {
    targetDate: ['対象日', 'targetDate', 'target_date', '出来高対象日', '東京市場日'],
    publicationDate: ['公表日', 'publicationDate', 'publication_date', '日銀公表日', 'PDF公表日'],
    sourcePdfName: ['元PDF', 'sourcePdfName', 'source_pdf_name', 'PDF名'],
    sourcePdfUrl: ['元PDF URL', 'sourcePdfUrl', 'source_pdf_url', 'PDF URL'],
    spotVolume: ['USD/JPYスポット出来高', 'スポット出来高', 'spotVolume', 'spot_volume', '出来高'],
    close: ['終値', 'close', 'USD/JPY終値'],
    open: ['始値', 'open', 'USD/JPY始値'],
    high: ['高値', 'high', 'USD/JPY高値'],
    low: ['安値', 'low', 'USD/JPY安値']
  }
};

function previewUsdJpySpotVolumeImport() {
  const summary = typeof usdJpyVolumeAutoImportBojPdfSpotVolume_ === 'function'
    ? usdJpyVolumeAutoImportBojPdfSpotVolume_(true)
    : usdJpyBojImportSpotVolume_(true);
  const rows = summary.rowsToAdd.concat(summary.rowsToUpdate).slice(0, USDJPY_BOJ_SPOT_IMPORT_CONFIG.maxPreviewRows);
  const html = HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;padding:16px">' +
      '<h3>日銀USD/JPYスポット出来高 取込プレビュー</h3>' +
      '<p>取得件数: ' + summary.fetchedCount + ' / 追加予定: ' + summary.addCount +
      ' / 更新予定: ' + summary.updateCount + '</p>' +
      '<p>取得範囲: ' + summary.startDate + ' - ' + summary.endDate + '</p>' +
      '<p>最新対象日: ' + (summary.latestTargetDate || 'なし') +
      ' / 公表日: ' + (summary.latestPublicationDate || 'なし') + '</p>' +
      '<pre style="white-space:pre-wrap;font-size:12px">' +
        usdJpyBojEscapeHtml_(JSON.stringify(rows, null, 2)) +
      '</pre>' +
      '<p style="color:#9b1c1c"><b>価格未入力の日付:</b> ' +
        usdJpyBojEscapeHtml_(summary.missingPriceDates.join(', ') || 'なし') +
      '</p>' +
    '</div>'
  ).setWidth(840).setHeight(680);
  SpreadsheetApp.getUi().showModalDialog(html, '日銀USD/JPYスポット出来高プレビュー');
  return summary;
}

function importUsdJpySpotVolumeFromBoj() {
  const summary = typeof usdJpyVolumeAutoImportBojPdfSpotVolume_ === 'function'
    ? usdJpyVolumeAutoImportBojPdfSpotVolume_(false)
    : usdJpyBojImportSpotVolume_(false);
  usdJpyVolumeAlert_(
    '日銀USD/JPYスポット出来高を取り込みました。\n' +
    '取得件数: ' + summary.fetchedCount + '\n' +
    '追加: ' + summary.addCount + '\n' +
    '更新: ' + summary.updateCount + '\n' +
    '最新対象日: ' + (summary.latestTargetDate || 'なし') + '\n' +
    '最新公表日: ' + (summary.latestPublicationDate || 'なし') + '\n' +
    '価格未入力: ' + (summary.missingPriceDates.length ? summary.missingPriceDates.join(', ') : 'なし')
  );
  return summary;
}

function importUsdJpySpotVolumeFromBojAndSyncJson() {
  const importSummary = typeof usdJpyVolumeAutoImportBojPdfSpotVolume_ === 'function'
    ? usdJpyVolumeAutoImportBojPdfSpotVolume_(false)
    : usdJpyBojImportSpotVolume_(false);
  const syncSummary = typeof syncUsdJpyVolumeJsonToGitHubFlexible === 'function'
    ? syncUsdJpyVolumeJsonToGitHubFlexible()
    : syncUsdJpyVolumeJsonToGitHub();
  usdJpyVolumeAlert_(
    '日銀出来高の取込とJSON反映が完了しました。\n' +
    '追加: ' + importSummary.addCount + '\n' +
    '更新: ' + importSummary.updateCount + '\n' +
    'JSON対象日: ' + syncSummary.latestTargetDate + '\n' +
    'コミット: ' + syncSummary.commitSha
  );
  return { importSummary: importSummary, syncSummary: syncSummary };
}

function usdJpyBojImportSpotVolume_(previewOnly) {
  const lock = LockService.getDocumentLock();
  lock.waitLock(30000);
  try {
    const config = USDJPY_BOJ_SPOT_IMPORT_CONFIG;
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(config.sheetName);
    if (!sheet) throw new Error('シート「' + config.sheetName + '」が見つかりません。');

    const values = sheet.getDataRange().getValues();
    if (!values.length) throw new Error('シート「' + config.sheetName + '」にヘッダー行がありません。');

    const headers = values[0].map(value => String(value || '').trim());
    usdJpyBojRejectSwapHeaders_(headers);
    const indexes = usdJpyBojResolveHeaderIndexes_(headers);
    const existing = usdJpyBojBuildExistingRowMap_(values, indexes);
    const range = usdJpyBojBuildFetchRange_();
    const publications = usdJpyBojFetchPublicationFiles_();
    const sourceRecords = usdJpyBojFetchSpotVolumeRecords_(range.startDate, range.endDate);

    const rowsToAdd = [];
    const rowsToUpdate = [];
    const unchangedRows = [];
    const missingPriceDates = [];

    sourceRecords.forEach(record => {
      const publication = usdJpyBojFindPublicationForTarget_(record.targetDate, publications);
      const next = {
        targetDate: record.targetDate,
        publicationDate: publication.date,
        sourcePdfName: publication.pdfName,
        sourcePdfUrl: publication.url,
        spotVolume: record.spotVolume
      };
      const current = existing[next.targetDate];
      if (!current) {
        rowsToAdd.push(next);
        missingPriceDates.push(next.targetDate);
        return;
      }

      const changed = usdJpyBojNeedsSpotUpdate_(current.row, indexes, next);
      if (changed) {
        rowsToUpdate.push(Object.assign({ rowNumber: current.rowNumber }, next));
      } else {
        unchangedRows.push(next);
      }

      if (usdJpyBojIsPriceMissing_(current.row, indexes)) {
        missingPriceDates.push(next.targetDate);
      }
    });

    const latest = sourceRecords.length ? sourceRecords[sourceRecords.length - 1] : null;
    const latestPublication = latest ? usdJpyBojFindPublicationForTarget_(latest.targetDate, publications) : null;
    const uniqueMissingPriceDates = Array.from(new Set(missingPriceDates)).sort().reverse();

    if (!previewOnly) {
      usdJpyBojWriteRows_(sheet, headers.length, indexes, rowsToAdd, rowsToUpdate);
      usdJpyBojSortSheetByTargetDate_(sheet, indexes.targetDate + 1);
    }

    return {
      ok: true,
      previewOnly: previewOnly,
      source: '日本銀行 時系列統計API ' + config.apiCode,
      startDate: range.startDate,
      endDate: range.endDate,
      fetchedCount: sourceRecords.length,
      addCount: rowsToAdd.length,
      updateCount: rowsToUpdate.length,
      unchangedCount: unchangedRows.length,
      latestTargetDate: latest ? latest.targetDate : '',
      latestPublicationDate: latestPublication ? latestPublication.date : '',
      rowsToAdd: rowsToAdd,
      rowsToUpdate: rowsToUpdate,
      missingPriceDates: uniqueMissingPriceDates
    };
  } finally {
    lock.releaseLock();
  }
}

function usdJpyBojFetchSpotVolumeRecords_(startDate, endDate) {
  const config = USDJPY_BOJ_SPOT_IMPORT_CONFIG;
  const errors = [];

  for (let i = 0; i < config.apiUrls.length; i++) {
    const url = usdJpyBojBuildApiUrl_(config.apiUrls[i], startDate, endDate);
    try {
      const response = UrlFetchApp.fetch(url, {
        method: 'get',
        muteHttpExceptions: true,
        headers: { Accept: 'application/json' }
      });
      const code = response.getResponseCode();
      if (code !== 200) {
        errors.push('HTTP ' + code + ' ' + url);
        continue;
      }
      const payload = JSON.parse(response.getContentText('UTF-8'));
      const records = usdJpyBojExtractObservations_(payload, config.apiCode)
        .map(item => ({
          targetDate: usdJpyBojNormalizeApiDate_(item.date),
          spotVolume: usdJpyBojParseNumber_(item.value)
        }))
        .filter(item => item.targetDate && Number.isFinite(item.spotVolume))
        .sort((a, b) => a.targetDate.localeCompare(b.targetDate));
      if (records.length) return usdJpyBojDeduplicateRecords_(records);
      errors.push('データなし ' + url);
    } catch (error) {
      errors.push(error.message);
    }
  }

  throw new Error('日銀APIからUSD/JPYスポット出来高を取得できませんでした。' + errors.join(' / '));
}

function usdJpyBojBuildApiUrl_(baseUrl, startDate, endDate) {
  const config = USDJPY_BOJ_SPOT_IMPORT_CONFIG;
  const params = {
    format: 'json',
    lang: 'jp',
    code: config.apiCode,
    startDate: startDate.replace(/-/g, ''),
    endDate: endDate.replace(/-/g, '')
  };
  if (baseUrl.indexOf('getDataCode') >= 0) {
    params.db = config.apiDb;
  }
  const query = Object.keys(params)
    .map(key => encodeURIComponent(key) + '=' + encodeURIComponent(params[key]))
    .join('&');
  return baseUrl + '?' + query;
}

function usdJpyBojExtractObservations_(payload, code) {
  const results = [];
  const dateKeys = ['SURVEY_DATES', 'SURVEY_DATE', 'OBS_DATE', 'TIME_PERIOD', 'DATE', 'date'];
  const valueKeys = ['VALUES', 'VALUE', 'OBS_VALUE', 'DATA_VALUE', 'value'];

  function visit(value, seriesCode) {
    if (Array.isArray(value)) {
      value.forEach(item => visit(item, seriesCode));
      return;
    }
    if (!value || typeof value !== 'object') return;

    const localCode = value.SERIES_CODE || value.seriesCode || value.CODE || seriesCode;
    const dateKey = dateKeys.find(key => Object.prototype.hasOwnProperty.call(value, key));
    const valueKey = valueKeys.find(key => Object.prototype.hasOwnProperty.call(value, key));
    if ((!code || localCode === code || seriesCode === code) && dateKey && valueKey) {
      results.push({ date: value[dateKey], value: value[valueKey] });
    }

    Object.keys(value).forEach(key => visit(value[key], localCode));
  }

  visit(payload, '');
  return results;
}

function usdJpyBojFetchPublicationFiles_() {
  const config = USDJPY_BOJ_SPOT_IMPORT_CONFIG;
  const response = UrlFetchApp.fetch(config.sourceUrl, {
    method: 'get',
    muteHttpExceptions: true,
    headers: { Accept: 'text/html,application/xhtml+xml' }
  });
  if (response.getResponseCode() !== 200) {
    throw new Error('日銀外国為替市況一覧を取得できませんでした。HTTP ' + response.getResponseCode());
  }

  const html = response.getContentText('UTF-8');
  const results = [];
  const seen = {};
  const regex = /href=["']([^"']*fx(\d{6})\.pdf)["']/gi;
  let match;
  while ((match = regex.exec(html)) !== null) {
    const pdfName = 'fx' + match[2] + '.pdf';
    const date = usdJpyBojPublicationDateFromPdfName_(pdfName);
    if (seen[date]) continue;
    seen[date] = true;
    results.push({
      date: date,
      pdfName: pdfName,
      url: usdJpyBojAbsoluteBojUrl_(match[1])
    });
  }

  if (!results.length) throw new Error('日銀外国為替市況一覧からPDFリンクを取得できませんでした。');
  return results.sort((a, b) => a.date.localeCompare(b.date));
}

function usdJpyBojFindPublicationForTarget_(targetDate, publications) {
  const found = publications.find(item => item.date > targetDate);
  if (found) return found;

  const fallbackDate = usdJpyBojNextWeekday_(targetDate);
  const pdfName = usdJpyBojPdfNameFromPublicationDate_(fallbackDate);
  return {
    date: fallbackDate,
    pdfName: pdfName,
    url: USDJPY_BOJ_SPOT_IMPORT_CONFIG.pdfBaseUrl + pdfName
  };
}

function usdJpyBojWriteRows_(sheet, columnCount, indexes, rowsToAdd, rowsToUpdate) {
  rowsToUpdate.forEach(item => {
    usdJpyBojSetCellIfColumnExists_(sheet, item.rowNumber, indexes.publicationDate, item.publicationDate);
    usdJpyBojSetCellIfColumnExists_(sheet, item.rowNumber, indexes.sourcePdfName, item.sourcePdfName);
    usdJpyBojSetCellIfColumnExists_(sheet, item.rowNumber, indexes.sourcePdfUrl, item.sourcePdfUrl);
    usdJpyBojSetCellIfColumnExists_(sheet, item.rowNumber, indexes.spotVolume, item.spotVolume);
  });

  if (!rowsToAdd.length) return;

  const startRow = sheet.getLastRow() + 1;
  const values = rowsToAdd.map(item => {
    const row = new Array(columnCount).fill('');
    row[indexes.targetDate] = item.targetDate;
    row[indexes.publicationDate] = item.publicationDate;
    if (indexes.sourcePdfName >= 0) row[indexes.sourcePdfName] = item.sourcePdfName;
    if (indexes.sourcePdfUrl >= 0) row[indexes.sourcePdfUrl] = item.sourcePdfUrl;
    row[indexes.spotVolume] = item.spotVolume;
    return row;
  });
  sheet.getRange(startRow, 1, values.length, columnCount).setValues(values);
}

function usdJpyBojSortSheetByTargetDate_(sheet, targetDateColumn) {
  const lastRow = sheet.getLastRow();
  const lastColumn = sheet.getLastColumn();
  if (lastRow <= 2) return;
  sheet.getRange(2, 1, lastRow - 1, lastColumn).sort({ column: targetDateColumn, ascending: false });
}

function usdJpyBojBuildExistingRowMap_(values, indexes) {
  const map = {};
  values.slice(1).forEach((row, offset) => {
    const targetDate = usdJpyBojDate_(row[indexes.targetDate]);
    if (!targetDate) return;
    map[targetDate] = {
      rowNumber: offset + 2,
      row: row
    };
  });
  return map;
}

function usdJpyBojNeedsSpotUpdate_(row, indexes, next) {
  const currentSpot = usdJpyBojParseNumber_(row[indexes.spotVolume]);
  const currentPublication = usdJpyBojDate_(row[indexes.publicationDate]);
  const currentPdfName = indexes.sourcePdfName >= 0 ? String(row[indexes.sourcePdfName] || '').trim() : '';
  const currentPdfUrl = indexes.sourcePdfUrl >= 0 ? String(row[indexes.sourcePdfUrl] || '').trim() : '';
  return currentSpot !== next.spotVolume ||
    currentPublication !== next.publicationDate ||
    currentPdfName !== next.sourcePdfName ||
    currentPdfUrl !== next.sourcePdfUrl;
}

function usdJpyBojIsPriceMissing_(row, indexes) {
  return ['close', 'open', 'high', 'low'].some(key => indexes[key] >= 0 && row[indexes[key]] === '');
}

function usdJpyBojResolveHeaderIndexes_(headers) {
  const config = USDJPY_BOJ_SPOT_IMPORT_CONFIG;
  const result = {};
  const normalizedHeaders = headers.map(usdJpyBojNormalizeHeader_);
  Object.keys(config.columns).forEach(key => {
    const candidates = config.columns[key].map(usdJpyBojNormalizeHeader_);
    result[key] = normalizedHeaders.findIndex(header => candidates.includes(header));
  });
  ['targetDate', 'publicationDate', 'spotVolume'].forEach(key => {
    if (result[key] < 0) {
      throw new Error('必須列がありません: ' + config.columns[key].join(' または '));
    }
  });
  return result;
}

function usdJpyBojRejectSwapHeaders_(headers) {
  const swapHeaders = headers.filter(header => /swap|スワップ/i.test(String(header)));
  if (swapHeaders.length) {
    throw new Error('スワップ出来高の列は使用しません。列を同期対象から外してください: ' + swapHeaders.join(', '));
  }
}

function usdJpyBojBuildFetchRange_() {
  const timezone = USDJPY_BOJ_SPOT_IMPORT_CONFIG.timezone;
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth() - USDJPY_BOJ_SPOT_IMPORT_CONFIG.monthsBack, 1);
  return {
    startDate: Utilities.formatDate(start, timezone, 'yyyy-MM-dd'),
    endDate: Utilities.formatDate(today, timezone, 'yyyy-MM-dd')
  };
}

function usdJpyBojDeduplicateRecords_(records) {
  const map = {};
  records.forEach(record => {
    map[record.targetDate] = record;
  });
  return Object.keys(map).sort().map(key => map[key]);
}

function usdJpyBojSetCellIfColumnExists_(sheet, rowNumber, zeroBasedColumn, value) {
  if (zeroBasedColumn < 0) return;
  sheet.getRange(rowNumber, zeroBasedColumn + 1).setValue(value);
}

function usdJpyBojPublicationDateFromPdfName_(pdfName) {
  const match = String(pdfName).match(/^fx(\d{2})(\d{2})(\d{2})\.pdf$/i);
  if (!match) return '';
  return '20' + match[1] + '-' + match[2] + '-' + match[3];
}

function usdJpyBojPdfNameFromPublicationDate_(publicationDate) {
  return 'fx' + publicationDate.slice(2, 4) + publicationDate.slice(5, 7) + publicationDate.slice(8, 10) + '.pdf';
}

function usdJpyBojNextWeekday_(dateText) {
  const parts = dateText.split('-').map(Number);
  const date = new Date(parts[0], parts[1] - 1, parts[2] + 1);
  while (date.getDay() === 0 || date.getDay() === 6) {
    date.setDate(date.getDate() + 1);
  }
  return Utilities.formatDate(date, USDJPY_BOJ_SPOT_IMPORT_CONFIG.timezone, 'yyyy-MM-dd');
}

function usdJpyBojAbsoluteBojUrl_(href) {
  if (/^https?:\/\//i.test(href)) return href;
  if (href.indexOf('/') === 0) return 'https://www.boj.or.jp' + href;
  return USDJPY_BOJ_SPOT_IMPORT_CONFIG.pdfBaseUrl + href.replace(/^\.\//, '');
}

function usdJpyBojNormalizeApiDate_(value) {
  const text = String(value || '').trim().replace(/\//g, '-');
  const ymd = text.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (ymd) return ymd[1] + '-' + ymd[2] + '-' + ymd[3];
  return usdJpyBojDate_(text);
}

function usdJpyBojDate_(value) {
  if (Object.prototype.toString.call(value) === '[object Date]' && !isNaN(value)) {
    return Utilities.formatDate(value, USDJPY_BOJ_SPOT_IMPORT_CONFIG.timezone, 'yyyy-MM-dd');
  }
  const text = String(value || '').trim().replace(/\//g, '-');
  const match = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (!match) return '';
  return match[1] + '-' + ('0' + match[2]).slice(-2) + '-' + ('0' + match[3]).slice(-2);
}

function usdJpyBojParseNumber_(value) {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  const text = String(value)
    .replace(/,/g, '')
    .replace(/％/g, '%')
    .replace(/[＋]/g, '+')
    .replace(/[－−▲△]/g, '-')
    .trim();
  if (text === '' || text === '-' || text === '—' || text === '－') return null;
  const normalized = text.endsWith('%') ? text.slice(0, -1) : text;
  const number = Number(normalized);
  return Number.isFinite(number) ? number : null;
}

function usdJpyBojNormalizeHeader_(value) {
  return String(value || '')
    .replace(/\s/g, '')
    .replace(/[（）]/g, match => match === '（' ? '(' : ')')
    .toLowerCase();
}

function usdJpyBojEscapeHtml_(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
