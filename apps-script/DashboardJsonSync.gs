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
  var normalizedReports = dashboardNormalizeReports_(reports).map(dashboardPrepareReportForDashboard_);
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

function dashboardPrepareReportForDashboard_(report) {
  var prepared = dashboardClonePlainObject_(report);
  var metricLines = dashboardCollectMarketMetricLines_(report);
  var markets = dashboardMarketsByName_(prepared.markets);

  prepared.markets = dashboardMarketDefinitions_().map(function(definition) {
    var original = markets[definition.name] || { name: definition.name };
    var metricLine = dashboardFirst_(metricLines[definition.name]);
    return {
      name: definition.name,
      direction: dashboardCleanDirection_(original.direction),
      price: metricLine,
      change: dashboardCleanMarketField_(original.change, definition, 80, false),
      material: dashboardCleanMarketField_(original.material, definition, 120, true) || '本文参照',
      positioning: dashboardCleanMarketField_(original.positioning, definition, 120, true),
      levels: dashboardCleanMarketField_(original.levels, definition, 120, true),
      mainScenario: dashboardCleanMarketField_(original.mainScenario, definition, 160, true),
      alternativeScenario: dashboardCleanMarketField_(original.alternativeScenario, definition, 160, true),
      breakCondition: dashboardCleanMarketField_(original.breakCondition, definition, 160, true),
      risk: dashboardCleanMarketField_(original.risk, definition, 120, true)
    };
  });

  return prepared;
}

function dashboardClonePlainObject_(value) {
  return JSON.parse(JSON.stringify(value || {}));
}

function dashboardMarketsByName_(markets) {
  var result = {};
  (Array.isArray(markets) ? markets : []).forEach(function(market) {
    if (market && market.name) result[String(market.name)] = market;
  });
  return result;
}

function dashboardMarketDefinitions_() {
  return [
    {
      name: '金',
      metricLabelRegex: '(?:金現物|金価格|金（XAU\\/USD）|ゴールド)',
      mentionRegex: /金現物|金価格|金は|金の|ゴールド|XAU\/USD/
    },
    {
      name: '原油',
      metricLabelRegex: '(?:WTI原油|原油（WTI）|原油)',
      mentionRegex: /WTI|原油/
    },
    {
      name: '日経225先物',
      metricLabelRegex: '(?:日経225先物[^：:\\n]{0,24})',
      mentionRegex: /日経225|日本株|東京市場/
    },
    {
      name: 'USD/JPY',
      metricLabelRegex: '(?:USD\\/JPY|ドル円)',
      mentionRegex: /USD\/JPY|ドル円|円相場|円ショート|ドル買い|円買い/
    },
    {
      name: 'EUR/USD',
      metricLabelRegex: '(?:EUR\\/USD|ユーロドル)',
      mentionRegex: /EUR\/USD|ユーロドル|ユーロ/
    },
    {
      name: 'BTCUSD',
      metricLabelRegex: '(?:BTCUSD|BTC\\/USD|BTC|ビットコイン)',
      mentionRegex: /BTCUSD|BTC\/USD|BTC|ビットコイン|暗号資産/
    }
  ];
}

function dashboardCollectMarketMetricLines_(report) {
  var result = {};
  var definitions = dashboardMarketDefinitions_();
  definitions.forEach(function(definition) {
    result[definition.name] = [];
  });

  dashboardCollectTextCandidates_(report).forEach(function(text) {
    definitions.forEach(function(definition) {
      var line = dashboardMetricLineFromText_(text, definition);
      if (line && result[definition.name].indexOf(line) === -1) {
        result[definition.name].push(line);
      }
    });
  });

  return result;
}

function dashboardCollectTextCandidates_(report) {
  var values = [
    report.theme,
    report.leadingMarket,
    report.mainScenario,
    report.alternativeScenario,
    report.breakConditions
  ];
  [
    report.changes,
    report.consistency,
    report.positioning,
    report.news,
    report.crossAssetFlow,
    report.handover,
    report.events,
    report.riskManagement
  ].forEach(function(items) {
    (Array.isArray(items) ? items : []).forEach(function(item) {
      values.push(dashboardTextOf_(item));
    });
  });
  (Array.isArray(report.markets) ? report.markets : []).forEach(function(market) {
    [
      'direction',
      'price',
      'change',
      'material',
      'positioning',
      'levels',
      'mainScenario',
      'alternativeScenario',
      'breakCondition',
      'risk'
    ].forEach(function(key) {
      values.push(market && market[key]);
    });
  });
  return values.map(dashboardNormalizeInlineText_).filter(Boolean);
}

function dashboardTextOf_(value) {
  if (typeof value === 'string') return value;
  if (!value) return '';
  return value.text || value.summary || value.title || '';
}

function dashboardMetricLineFromText_(value, definition) {
  var text = dashboardNormalizeInlineText_(value);
  if (!text) return '';

  var pattern = new RegExp(
    '(' + definition.metricLabelRegex + '\\s*[：:]\\s*[\\s\\S]*?)' +
    '(?=\\s*(?:' + dashboardAllMetricLabelRegex_() + ')\\s*[：:]|。|$)',
    'i'
  );
  var match = text.match(pattern);
  if (!match) return '';

  var line = dashboardTrimMetricLineTail_(dashboardNormalizeInlineText_(match[1]));
  if (!dashboardIsUsableMetricLine_(line, definition)) return '';
  return dashboardTrimText_(line, 150);
}

function dashboardTrimMetricLineTail_(line) {
  return dashboardNormalizeInlineText_(line).replace(
    /\s(?:日経VI|東証プライム|東証|騰落レシオ|日経225現物終値|米10年|日本10年|VIX|NYダウ|S&P500|Nasdaq|Russell)[^：:]{0,30}[：:][\s\S]*$/i,
    ''
  );
}

function dashboardAllMetricLabelRegex_() {
  return '(?:金現物|金価格|金（XAU\\/USD）|ゴールド|WTI原油|原油（WTI）|原油|日経225先物[^：:\\n]{0,24}|USD\\/JPY|ドル円|EUR\\/USD|ユーロドル|BTCUSD|BTC\\/USD|BTC|ビットコイン)';
}

function dashboardIsUsableMetricLine_(line, definition) {
  if (!line) return false;
  if (dashboardStartsWithOtherMetricLabel_(line, definition)) return false;
  if (!definition.mentionRegex.test(line)) return false;
  var valuePart = line.replace(/^[^：:]+[：:]\s*/, '');
  if (!/[0-9]/.test(valuePart) && valuePart.indexOf('取得不能') === -1) return false;
  if (/VIX/.test(line) && definition.name !== 'BTCUSD') return false;
  return true;
}

function dashboardCleanDirection_(value) {
  var text = dashboardNormalizeInlineText_(value);
  if (!text) return '中立・方向確認';
  if (text.length > 28) return '中立・方向確認';
  if (/上昇|強|買い|流入|下落|弱|売り|流出|中立|横ばい|もみ合い|方向確認|警戒/.test(text)) return text;
  return '中立・方向確認';
}

function dashboardCleanMarketField_(value, definition, maxLength, requireMention) {
  var text = dashboardNormalizeInlineText_(value);
  if (!text) return '';
  if (text.length > maxLength) return '';
  if (text.indexOf('取得不能') !== -1) return '';
  if (/マーケットレポート｜|復旧日時|Google Docsファイル名|当時の図解原本|TSV|ヘッダーなし/.test(text)) return '';
  if (dashboardStartsWithOtherMetricLabel_(text, definition)) return '';
  if (requireMention && !definition.mentionRegex.test(text)) return '';
  if (/VIX/.test(text) && definition.name !== 'BTCUSD') return '';
  return dashboardTrimText_(text, maxLength);
}

function dashboardStartsWithOtherMetricLabel_(value, definition) {
  var text = dashboardNormalizeInlineText_(value);
  var definitions = dashboardMarketDefinitions_();
  for (var i = 0; i < definitions.length; i += 1) {
    var other = definitions[i];
    if (other.name === definition.name) continue;
    var pattern = new RegExp('^\\s*' + other.metricLabelRegex + '\\s*[：:]', 'i');
    if (pattern.test(text)) return true;
  }
  return false;
}

function dashboardNormalizeInlineText_(value) {
  return String(value || '')
    .replace(/\r\n?/g, '\n')
    .replace(/\u00a0/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/^[・\s]+/, '')
    .trim();
}

function dashboardTrimText_(value, maxLength) {
  var text = dashboardNormalizeInlineText_(value);
  if (!text || text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + '...';
}

function dashboardFirst_(values) {
  return values && values.length ? values[0] : '';
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
