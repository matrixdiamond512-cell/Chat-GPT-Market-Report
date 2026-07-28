const WEB_REPORT_CONFIG = {
  owner: 'matrixdiamond512-cell',
  repo: 'Chat-GPT-Market-Report',
  branch: 'main',
  targetPath: 'reports.json',
  pagesUrl: 'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/'
};

function showWebReportSidebar() {
  const html = HtmlService.createHtmlOutputFromFile('MarketReportSidebar')
    .setTitle('WEB版レポート登録');
  SpreadsheetApp.getUi().showSidebar(html);
}

function publishWebReport(reportJsonText) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const report = parseAndValidateWebReport_(reportJsonText);
    const current = getGitHubJsonFile_(WEB_REPORT_CONFIG.targetPath);
    const reports = Array.isArray(current.data) ? current.data : [];

    const key = report.date + ' ' + report.time;
    const filtered = reports.filter(item => (item.date + ' ' + item.time) !== key);
    filtered.push(report);
    filtered.sort((a, b) => (`${b.date} ${b.time}`).localeCompare(`${a.date} ${a.time}`));

    const content = JSON.stringify(filtered, null, 2) + '\n';
    const result = putGitHubJsonFile_(WEB_REPORT_CONFIG.targetPath, content, current.sha,
      'Publish market report ' + report.date + ' ' + report.time);

    return {
      ok: true,
      title: report.title,
      date: report.date,
      time: report.time,
      commitSha: result.commit.sha,
      pagesUrl: WEB_REPORT_CONFIG.pagesUrl
    };
  } finally {
    lock.releaseLock();
  }
}

function previewWebReport(reportJsonText) {
  return parseAndValidateWebReport_(reportJsonText);
}

function parseAndValidateWebReport_(text) {
  let report;
  try {
    report = JSON.parse(String(text || '').trim());
  } catch (error) {
    throw new Error('JSON形式が正しくありません。' + error.message);
  }

  if (Array.isArray(report)) {
    if (report.length !== 1) throw new Error('1件のレポートだけを貼り付けてください。');
    report = report[0];
  }
  if (!report || typeof report !== 'object') throw new Error('レポートオブジェクトがありません。');

  const required = ['date', 'time', 'title', 'theme', 'leadingMarket', 'markets'];
  required.forEach(key => {
    if (report[key] === undefined || report[key] === null || report[key] === '') {
      throw new Error('必須項目がありません: ' + key);
    }
  });

  if (!/^\d{4}-\d{2}-\d{2}$/.test(report.date)) {
    throw new Error('date は YYYY-MM-DD 形式にしてください。');
  }
  if (!/^\d{2}:\d{2}$/.test(report.time)) {
    throw new Error('time は HH:MM 形式にしてください。');
  }
  if (!Array.isArray(report.markets) || report.markets.length === 0) {
    throw new Error('markets は1件以上必要です。');
  }

  const requiredMarkets = ['金', '原油', '日経225先物', 'USD/JPY', 'EUR/USD', 'BTCUSD'];
  const marketNames = report.markets.map(item => item && item.name).filter(Boolean);
  const missingMarkets = requiredMarkets.filter(name => !marketNames.includes(name));
  if (missingMarkets.length) {
    throw new Error('必須市場が不足しています: ' + missingMarkets.join('、'));
  }

  report.tags = Array.isArray(report.tags) ? report.tags : [];
  ['changes', 'consistency', 'positioning', 'news', 'handover', 'crossAssetFlow', 'sectors', 'events', 'riskManagement'].forEach(key => {
    if (report[key] !== undefined && !Array.isArray(report[key])) report[key] = [report[key]];
  });

  return report;
}

function getGitHubJsonFile_(path) {
  const token = getGitHubToken_();
  const url = githubContentsUrl_(path) + '?ref=' + encodeURIComponent(WEB_REPORT_CONFIG.branch);
  const response = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: githubHeaders_(token),
    muteHttpExceptions: true
  });
  const code = response.getResponseCode();
  if (code === 404) return { data: [], sha: null };
  if (code !== 200) throw new Error('GitHubファイル取得失敗: HTTP ' + code + ' ' + response.getContentText());

  const payload = JSON.parse(response.getContentText());
  const decoded = Utilities.newBlob(Utilities.base64Decode(payload.content)).getDataAsString('UTF-8');
  return { data: JSON.parse(decoded), sha: payload.sha };
}

function putGitHubJsonFile_(path, content, sha, message) {
  const token = getGitHubToken_();
  const payload = {
    message: message,
    content: Utilities.base64Encode(content, Utilities.Charset.UTF_8),
    branch: WEB_REPORT_CONFIG.branch
  };
  if (sha) payload.sha = sha;

  const response = UrlFetchApp.fetch(githubContentsUrl_(path), {
    method: 'put',
    contentType: 'application/json',
    headers: githubHeaders_(token),
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
  const code = response.getResponseCode();
  if (code !== 200 && code !== 201) {
    throw new Error('GitHub更新失敗: HTTP ' + code + ' ' + response.getContentText());
  }
  return JSON.parse(response.getContentText());
}

function getGitHubToken_() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('スクリプトプロパティ GITHUB_TOKEN が未設定です。');
  return token;
}

function githubContentsUrl_(path) {
  return 'https://api.github.com/repos/' + WEB_REPORT_CONFIG.owner + '/' + WEB_REPORT_CONFIG.repo + '/contents/' + path;
}

function githubHeaders_(token) {
  return {
    Authorization: 'Bearer ' + token,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };
}
