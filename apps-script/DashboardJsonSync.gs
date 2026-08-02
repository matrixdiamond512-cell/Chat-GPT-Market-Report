var DASHBOARD_JSON_CONFIG = {
  targetPath: 'data/dashboard.json',
  reportsPath: 'reports.json',
  timezone: 'Asia/Tokyo',
  maxReports: 120,
  lastResultProperty: 'DASHBOARD_JSON_LAST_RESULT'
};

function previewDashboardJson() {
  var reports = dashboardFetchReportsJson_();
  var json = buildDashboardJsonFromReports_(reports);
  var html = HtmlService.createHtmlOutput(
    '<pre style="white-space:pre-wrap;font-size:12px">' + dashboardEscapeHtml_(json) + '</pre>'
  ).setWidth(920).setHeight(700);
  SpreadsheetApp.getUi().showModalDialog(html, 'ダッシュボードJSONプレビュー');
  return JSON.parse(json);
}

function syncDashboardJsonToGitHub() {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var reports = dashboardFetchReportsJson_();
    var result = syncDashboardJsonToGitHubFromReports_(reports);
    dashboardAlert_(
      'ダッシュボードJSONをGitHubへ反映しました。\n' +
      '対象: ' + result.latestKey + '\n' +
      '件数: ' + result.reportCount + '\n' +
      'コミット: ' + result.commitSha
    );
    return result;
  } catch (error) {
    dashboardSaveResult_({ ok: false, error: error.message });
    dashboardAlert_('ダッシュボードJSONを反映できませんでした。\n' + error.message);
    throw error;
  } finally {
    lock.releaseLock();
  }
}

function syncDashboardJsonToGitHubFromReports_(reports) {
  var payload = dashboardBuildPayloadFromReports_(reports);
  var json = JSON.stringify(payload, null, 2) + '\n';
  var current = dashboardGetGitHubJsonFile_(DASHBOARD_JSON_CONFIG.targetPath);
  var result = dashboardPutGitHubJsonFile_(
    DASHBOARD_JSON_CONFIG.targetPath,
    json,
    current.sha,
    'Update dashboard JSON from market reports'
  );
  return dashboardSaveResult_({
    ok: true,
    targetPath: DASHBOARD_JSON_CONFIG.targetPath,
    latestKey: payload.currentReportKey,
    reportCount: payload.reports.length,
    commitSha: result.commit.sha
  });
}

function buildDashboardJsonFromReports_(reports) {
  return JSON.stringify(dashboardBuildPayloadFromReports_(reports), null, 2) + '\n';
}

function dashboardBuildPayloadFromReports_(reports) {
  var normalizedReports = dashboardNormalizeReports_(reports);
  if (!normalizedReports.length) throw new Error('ダッシュボードに使えるマーケットレポートがありません。');

  var latest = normalizedReports[0];
  var generatedAt = dashboardIsoJst_(new Date());
  var latestKey = latest.date + ' ' + latest.time;
  return {
    schemaVersion: '1.0.0',
    pageId: 'dashboard',
    generatedAt: generatedAt,
    publishedAt: generatedAt,
    dataAsOf: latest.date + 'T' + latest.time + ':00+09:00',
    status: 'ok',
    isStale: dashboardIsStale_(latest.date),
    staleReason: dashboardIsStale_(latest.date) ? '最新レポートの日付が現在日から3日以上離れています。' : '',
    currentReportKey: latestKey,
    sources: [
      {
        id: 'MARKET_REPORTS_JSON',
        name: 'マーケットレポート本文の構造化JSON',
        path: DASHBOARD_JSON_CONFIG.reportsPath,
        asOf: latestKey,
        status: 'ok',
        note: 'Google Docsのマーケットレポート本文をGASで構造化したデータ。トップページはこのJSONを優先して表示します。'
      }
    ],
    errors: [],
    latestReport: latest,
    reports: normalizedReports.slice(0, DASHBOARD_JSON_CONFIG.maxReports)
  };
}

function dashboardFetchReportsJson_() {
  var current = dashboardGetGitHubJsonFile_(DASHBOARD_JSON_CONFIG.reportsPath);
  return dashboardNormalizeReports_(current.data);
}

function dashboardNormalizeReports_(reports) {
  var list = [];
  if (Array.isArray(reports)) {
    list = reports;
  } else if (reports && Array.isArray(reports.reports)) {
    list = reports.reports;
  } else if (reports && reports.latestReport) {
    list = [reports.latestReport];
  }
  return list
    .filter(function(report) {
      return report &&
        /^\d{4}-\d{2}-\d{2}$/.test(String(report.date || '')) &&
        /^\d{2}:\d{2}$/.test(String(report.time || ''));
    })
    .sort(function(a, b) {
      return (b.date + ' ' + b.time).localeCompare(a.date + ' ' + a.time);
    });
}

function dashboardIsStale_(dateText) {
  var todayText = Utilities.formatDate(new Date(), DASHBOARD_JSON_CONFIG.timezone, 'yyyy-MM-dd');
  var today = dashboardDateOnly_(todayText);
  var reportDate = dashboardDateOnly_(dateText);
  if (!today || !reportDate) return true;
  return (today.getTime() - reportDate.getTime()) / 86400000 >= 3;
}

function dashboardDateOnly_(dateText) {
  var match = String(dateText || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

function dashboardGetGitHubJsonFile_(path) {
  var config = dashboardGithubConfig_();
  var response = UrlFetchApp.fetch(
    dashboardGithubContentsUrl_(config, path) + '?ref=' + encodeURIComponent(config.branch),
    {
      method: 'get',
      headers: dashboardGithubHeaders_(config.token),
      muteHttpExceptions: true
    }
  );
  var code = response.getResponseCode();
  if (code === 404) return { data: [], sha: null };
  if (code !== 200) throw new Error('GitHubファイル取得失敗: HTTP ' + code + ' ' + response.getContentText());
  var payload = JSON.parse(response.getContentText());
  return {
    data: JSON.parse(Utilities.newBlob(Utilities.base64Decode(payload.content.replace(/\n/g, ''))).getDataAsString('UTF-8')),
    sha: payload.sha
  };
}

function dashboardPutGitHubJsonFile_(path, content, sha, message) {
  var config = dashboardGithubConfig_();
  var body = {
    message: message,
    content: Utilities.base64Encode(content, Utilities.Charset.UTF_8),
    branch: config.branch
  };
  if (sha) body.sha = sha;

  var response = UrlFetchApp.fetch(dashboardGithubContentsUrl_(config, path), {
    method: 'put',
    contentType: 'application/json',
    headers: dashboardGithubHeaders_(config.token),
    payload: JSON.stringify(body),
    muteHttpExceptions: true
  });
  var code = response.getResponseCode();
  if (code !== 200 && code !== 201) throw new Error('GitHub更新失敗: HTTP ' + code + ' ' + response.getContentText());
  return JSON.parse(response.getContentText());
}

function dashboardGithubConfig_() {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('スクリプトプロパティ GITHUB_TOKEN が未設定です。');
  return {
    token: token,
    owner: props.getProperty('GITHUB_OWNER') || (typeof WEB_REPORT_CONFIG !== 'undefined' ? WEB_REPORT_CONFIG.owner : 'matrixdiamond512-cell'),
    repo: props.getProperty('GITHUB_REPO') || (typeof WEB_REPORT_CONFIG !== 'undefined' ? WEB_REPORT_CONFIG.repo : 'Chat-GPT-Market-Report'),
    branch: props.getProperty('GITHUB_BRANCH') || (typeof WEB_REPORT_CONFIG !== 'undefined' ? WEB_REPORT_CONFIG.branch : 'main')
  };
}

function dashboardGithubContentsUrl_(config, path) {
  return 'https://api.github.com/repos/' + config.owner + '/' + config.repo + '/contents/' + path;
}

function dashboardGithubHeaders_(token) {
  return {
    Authorization: 'Bearer ' + token,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };
}

function dashboardIsoJst_(date) {
  return Utilities.formatDate(date, DASHBOARD_JSON_CONFIG.timezone, "yyyy-MM-dd'T'HH:mm:ss'+09:00'");
}

function dashboardSaveResult_(result) {
  var payload = Object.assign({
    executedAt: Utilities.formatDate(new Date(), DASHBOARD_JSON_CONFIG.timezone, 'yyyy-MM-dd HH:mm:ss')
  }, result);
  PropertiesService.getScriptProperties().setProperty(
    DASHBOARD_JSON_CONFIG.lastResultProperty,
    JSON.stringify(payload)
  );
  return payload;
}

function dashboardEscapeHtml_(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function dashboardAlert_(message) {
  try {
    SpreadsheetApp.getUi().alert(message);
  } catch (error) {
    Logger.log(message);
  }
}
