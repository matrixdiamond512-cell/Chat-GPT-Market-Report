// USD/JPY volume JSON support definitions
// Required by UsdJpyVolumeJsonFlexibleSync.gs when the legacy base file is not installed.

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
  }
};

function usdJpyVolumeBuildStaleInfo_(publicationDate, now, timezone) {
  const today = Utilities.formatDate(now, timezone, 'yyyy-MM-dd');
  const elapsedDays = usdJpyVolumeDayDiff_(publicationDate, today);
  const isStale = elapsedDays > USDJPY_VOLUME_JSON_CONFIG.staleDays;
  return {
    isStale: isStale,
    staleReason: isStale ? '最新公表日から' + elapsedDays + '日経過しています。' : ''
  };
}

function usdJpyVolumeLevel_(record) {
  if (record.vs20Pct === null) return '判定対象外';
  if (record.vs20Pct >= 20) return '多い';
  if (record.vs20Pct <= -20) return '少ない';
  return '通常';
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
  return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : null;
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
