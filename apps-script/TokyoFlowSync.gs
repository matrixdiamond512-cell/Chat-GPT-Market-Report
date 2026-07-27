const TOKYO_FLOW_CONFIG = {
  sheetName: '終値一覧',
  targetPath: 'tokyo-usdjpy-volume.json',
  owner: 'matrixdiamond512-cell',
  repo: 'Chat-GPT-Market-Report',
  branch: 'main',
  headers: {
    date: ['日付', 'Date'],
    volume: ['東京市場USDJPYスポット出来高（百万ドル）'],
    dayChange: ['東京市場USDJPY出来高前日比'],
    vs20d: ['東京市場USDJPY出来高20営業日平均との差'],
    gotoBi: ['ゴトー日'],
    gotoBiType: ['ゴトー日種類', '種類'],
    memo: ['ゴトー日メモ', 'メモ']
  }
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('マーケットレポート')
    .addItem('東京USDJPYフローをGitHubへ反映', 'syncTokyoFlowToGitHub')
    .addItem('東京USDJPYフローJSONを確認', 'previewTokyoFlowJson')
    .addSeparator()
    .addItem('GitHub設定を確認', 'showTokyoFlowConfigStatus')
    .addToUi();
}

function syncTokyoFlowToGitHub() {
  const lock = LockService.getDocumentLock();
  lock.waitLock(30000);
  try {
    const json = buildTokyoFlowJson_();
    const result = putGitHubFile_(json);
    SpreadsheetApp.getUi().alert(
      'GitHubへ反映しました。\n' +
      'ファイル: ' + TOKYO_FLOW_CONFIG.targetPath + '\n' +
      'コミット: ' + result.commit.sha
    );
  } catch (error) {
    SpreadsheetApp.getUi().alert('反映できませんでした。\n' + error.message);
    throw error;
  } finally {
    lock.releaseLock();
  }
}

function previewTokyoFlowJson() {
  const json = buildTokyoFlowJson_();
  const html = HtmlService.createHtmlOutput(
    '<pre style="white-space:pre-wrap;font-size:12px">' + escapeHtml_(json) + '</pre>'
  ).setWidth(760).setHeight(620);
  SpreadsheetApp.getUi().showModalDialog(html, '東京USDJPYフローJSON');
}

function showTokyoFlowConfigStatus() {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('GITHUB_TOKEN');
  SpreadsheetApp.getUi().alert(
    'リポジトリ: ' + TOKYO_FLOW_CONFIG.owner + '/' + TOKYO_FLOW_CONFIG.repo + '\n' +
    'ブランチ: ' + TOKYO_FLOW_CONFIG.branch + '\n' +
    '対象シート: ' + TOKYO_FLOW_CONFIG.sheetName + '\n' +
    'GitHubトークン: ' + (token ? '設定済み' : '未設定')
  );
}

function buildTokyoFlowJson_() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(TOKYO_FLOW_CONFIG.sheetName);
  if (!sheet) throw new Error('シート「' + TOKYO_FLOW_CONFIG.sheetName + '」が見つかりません。');

  const values = sheet.getDataRange().getValues();
  if (values.length < 2) throw new Error('データ行がありません。');

  const headers = values[0].map(value => String(value).trim());
  const indexes = resolveHeaderIndexes_(headers);
  const timezone = SpreadsheetApp.getActive().getSpreadsheetTimeZone() || 'Asia/Tokyo';

  const rows = values.slice(1).map((row, offset) => {
    const rowNumber = offset + 2;
    const rawDate = row[indexes.date];
    const rawVolume = row[indexes.volume];

    if (rawDate === '' && rawVolume === '') return null;
    if (!rawDate) throw new Error(rowNumber + '行目: 日付がありません。');

    const volume = parseNumber_(rawVolume);
    if (!Number.isFinite(volume)) throw new Error(rowNumber + '行目: 出来高が数値ではありません。');

    return {
      date: formatDate_(rawDate, timezone, rowNumber),
      volume: volume,
      dayChange: parseRatio_(row[indexes.dayChange]),
      vs20d: parseRatio_(row[indexes.vs20d]),
      gotoBi: parseGotoBi_(indexes.gotoBi >= 0 ? row[indexes.gotoBi] : ''),
      gotoBiType: indexes.gotoBiType >= 0 ? String(row[indexes.gotoBiType] || '').trim() : '',
      memo: indexes.memo >= 0 ? String(row[indexes.memo] || '').trim() : ''
    };
  }).filter(Boolean).sort((a, b) => a.date.localeCompare(b.date));

  const duplicateDates = rows.map(row => row.date).filter((date, index, list) => list.indexOf(date) !== index);
  if (duplicateDates.length) throw new Error('日付が重複しています: ' + [...new Set(duplicateDates)].join(', '));
  if (!rows.length) throw new Error('出力対象データがありません。');

  return JSON.stringify(rows, null, 2) + '\n';
}

function resolveHeaderIndexes_(headers) {
  const result = {};
  Object.keys(TOKYO_FLOW_CONFIG.headers).forEach(key => {
    const candidates = TOKYO_FLOW_CONFIG.headers[key];
    result[key] = headers.findIndex(header => candidates.includes(header));
  });

  ['date', 'volume', 'dayChange', 'vs20d'].forEach(key => {
    if (result[key] < 0) {
      throw new Error('必須列がありません: ' + TOKYO_FLOW_CONFIG.headers[key].join(' または '));
    }
  });
  return result;
}

function parseNumber_(value) {
  if (typeof value === 'number') return value;
  const normalized = String(value || '').replace(/,/g, '').trim();
  return normalized === '' ? NaN : Number(normalized);
}

function parseRatio_(value) {
  if (typeof value === 'number') return value;
  const text = String(value || '').replace(/,/g, '').trim();
  if (text === '') return 0;
  if (text.endsWith('%')) return Number(text.slice(0, -1)) / 100;
  const number = Number(text);
  return Number.isFinite(number) ? number : 0;
}

function parseGotoBi_(value) {
  if (value === true || value === false) return value;
  const text = String(value || '').trim().toLowerCase();
  if (['true', '1', 'yes', 'y', '○', '〇', '対象', 'ゴトー日'].includes(text)) return true;
  if (['false', '0', 'no', 'n', '×', '対象外', '通常日'].includes(text)) return false;
  return null;
}

function formatDate_(value, timezone, rowNumber) {
  if (Object.prototype.toString.call(value) === '[object Date]' && !isNaN(value)) {
    return Utilities.formatDate(value, timezone, 'yyyy-MM-dd');
  }
  const text = String(value || '').trim().replace(/\//g, '-');
  const match = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (!match) throw new Error(rowNumber + '行目: 日付形式を yyyy-MM-dd にしてください。');
  return match[1] + '-' + ('0' + match[2]).slice(-2) + '-' + ('0' + match[3]).slice(-2);
}

function putGitHubFile_(content) {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('スクリプトプロパティ GITHUB_TOKEN が未設定です。');

  const apiUrl = 'https://api.github.com/repos/' + TOKYO_FLOW_CONFIG.owner + '/' + TOKYO_FLOW_CONFIG.repo + '/contents/' + TOKYO_FLOW_CONFIG.targetPath;
  const headers = {
    Authorization: 'Bearer ' + token,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };

  const currentResponse = UrlFetchApp.fetch(apiUrl + '?ref=' + encodeURIComponent(TOKYO_FLOW_CONFIG.branch), {
    method: 'get',
    headers: headers,
    muteHttpExceptions: true
  });

  const currentCode = currentResponse.getResponseCode();
  if (currentCode !== 200 && currentCode !== 404) {
    throw new Error('GitHubの既存ファイル確認に失敗しました: HTTP ' + currentCode + ' ' + currentResponse.getContentText());
  }

  const payload = {
    message: 'Update Tokyo USDJPY flow data from Google Sheets',
    content: Utilities.base64Encode(content, Utilities.Charset.UTF_8),
    branch: TOKYO_FLOW_CONFIG.branch
  };
  if (currentCode === 200) payload.sha = JSON.parse(currentResponse.getContentText()).sha;

  const updateResponse = UrlFetchApp.fetch(apiUrl, {
    method: 'put',
    contentType: 'application/json',
    headers: headers,
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  const updateCode = updateResponse.getResponseCode();
  if (updateCode !== 200 && updateCode !== 201) {
    throw new Error('GitHub更新に失敗しました: HTTP ' + updateCode + ' ' + updateResponse.getContentText());
  }
  return JSON.parse(updateResponse.getContentText());
}

function escapeHtml_(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
