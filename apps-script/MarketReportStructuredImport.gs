/*
 * MarketReportStructuredImport.gs
 *
 * Root fix for sparse web reports.
 * Reads the COMPLETE Google Docs body, preserves it as fullText, converts the
 * standard market-report sections into structured JSON, merges by date/time,
 * and publishes reports.json to GitHub in one operation.
 *
 * Required Script Properties:
 *   GITHUB_TOKEN
 * Optional Script Properties:
 *   GITHUB_OWNER      default: matrixdiamond512-cell
 *   GITHUB_REPO       default: Chat-GPT-Market-Report
 *   GITHUB_BRANCH     default: main
 *   REPORT_FOLDER_ID  Google Drive folder containing market-report Docs
 */

var MR_MARKETS_ = [
  {name:'金', re:/(?:^|[【\s])(?:金|ゴールド|Gold)(?:[・】\s]|$)/i},
  {name:'原油', re:/(?:WTI|原油|ブレント|Brent)/i},
  {name:'日経225先物', re:/(?:日経225先物|日経先物)/i},
  {name:'USD\/JPY', re:/(?:USD\s*\/?\s*JPY|ドル円)/i},
  {name:'EUR\/USD', re:/(?:EUR\s*\/?\s*USD|ユーロドル)/i},
  {name:'BTCUSD', re:/(?:BTC\s*\/?\s*USD|BTCUSD|ビットコイン)/i}
];

var MR_SECTION_RULES_ = [
  ['theme', /相場テーマ|今日のテーマ/],
  ['changes', /前回から|からの変化|時間からの変化/],
  ['consistency', /整合性|材料と値動き/],
  ['leadingMarket', /主導市場|相場を主導/],
  ['positioning', /需給|ポジション|建玉|フローの偏り/],
  ['news', /重要ニュース|相場に影響|ニュース|重要材料/],
  ['crossAssetFlow', /クロスアセット|資金フロー|何が買われ|何が売られ/],
  ['sectors', /セクター|業種|買われた|売られた/],
  ['events', /イベント|今後の予定|経済指標/],
  ['handover', /引き継ぎ|次の時間帯|欧州時間|NY時間/],
  ['scenario', /全体シナリオ|メインシナリオ|代替シナリオ/],
  ['riskManagement', /リスク管理|主なリスク|リスク要因/]
];

function publishAllMarketReportsStructured() {
  var props = PropertiesService.getScriptProperties();
  var folderId = props.getProperty('REPORT_FOLDER_ID');
  if (!folderId) throw new Error('スクリプトプロパティ REPORT_FOLDER_ID を設定してください。');

  var folder = DriveApp.getFolderById(folderId);
  var files = folder.getFilesByType(MimeType.GOOGLE_DOCS);
  var reports = [];
  var failures = [];

  while (files.hasNext()) {
    var file = files.next();
    if (!/^マーケットレポート_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}$/.test(file.getName())) continue;
    try {
      reports.push(mrBuildReportFromDoc_(file));
    } catch (error) {
      failures.push(file.getName() + ': ' + error.message);
    }
  }

  reports.sort(function(a, b) {
    return (b.date + ' ' + b.time).localeCompare(a.date + ' ' + a.time);
  });

  if (!reports.length) throw new Error('対象のマーケットレポートが見つかりませんでした。');
  mrValidateReports_(reports);
  mrPublishReportsJson_(reports);

  var result = {
    published: reports.length,
    failures: failures,
    newest: reports[0].date + ' ' + reports[0].time
  };
  Logger.log(JSON.stringify(result, null, 2));
  return result;
}

function publishLatestMarketReportStructured() {
  var props = PropertiesService.getScriptProperties();
  var folderId = props.getProperty('REPORT_FOLDER_ID');
  if (!folderId) throw new Error('スクリプトプロパティ REPORT_FOLDER_ID を設定してください。');

  var folder = DriveApp.getFolderById(folderId);
  var files = folder.getFilesByType(MimeType.GOOGLE_DOCS);
  var newest = null;
  while (files.hasNext()) {
    var file = files.next();
    if (!/^マーケットレポート_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}$/.test(file.getName())) continue;
    if (!newest || file.getLastUpdated().getTime() > newest.getLastUpdated().getTime()) newest = file;
  }
  if (!newest) throw new Error('対象のマーケットレポートが見つかりませんでした。');

  var report = mrBuildReportFromDoc_(newest);
  var current = mrFetchReportsJson_();
  var key = report.date + ' ' + report.time;
  var merged = current.filter(function(item) { return item.date + ' ' + item.time !== key; });
  merged.push(report);
  merged.sort(function(a, b) { return (b.date + ' ' + b.time).localeCompare(a.date + ' ' + a.time); });
  mrValidateReports_(merged);
  mrPublishReportsJson_(merged);
  return report;
}

function mrBuildReportFromDoc_(file) {
  var doc = DocumentApp.openById(file.getId());
  var fullText = mrClean_(doc.getBody().getText());
  if (fullText.length < 200) throw new Error('本文が短すぎます。Google Docs本文を確認してください。');

  var identity = mrExtractIdentity_(file.getName(), fullText);
  var sections = mrSplitSections_(fullText);
  var extracted = {};
  MR_SECTION_RULES_.forEach(function(rule) {
    extracted[rule[0]] = mrFindSections_(sections, rule[1]);
  });

  var scenarioRows = mrParagraphs_(extracted.scenario);
  var report = {
    date: identity.date,
    time: identity.time,
    title: identity.title,
    tags: ['ドル円','ユーロドル','日経225先物','金','原油','BTCUSD'],
    theme: mrFirstMeaningful_(extracted.theme) || mrFirstMeaningful_(fullText),
    changes: mrParagraphs_(extracted.changes),
    consistency: mrParagraphs_(extracted.consistency),
    leadingMarket: mrFirstMeaningful_(extracted.leadingMarket),
    positioning: mrParagraphs_(extracted.positioning),
    news: mrParagraphs_(extracted.news),
    crossAssetFlow: mrParagraphs_(extracted.crossAssetFlow),
    sectors: mrParagraphs_(extracted.sectors),
    handover: mrParagraphs_(extracted.handover),
    events: mrParagraphs_(extracted.events),
    mainScenario: mrPick_(scenarioRows, /メイン|基本|中心/) || scenarioRows[0] || '',
    alternativeScenario: mrPick_(scenarioRows, /代替|別|反対/) || scenarioRows[1] || '',
    breakConditions: mrPick_(scenarioRows, /崩れる|無効|否定|見方を変える/) || mrFindSentence_(fullText, /崩れる条件|弱気判断を修正|強気判断を修正/),
    riskManagement: mrParagraphs_(extracted.riskManagement),
    markets: [],
    sources: [],
    fullText: fullText,
    sourceDocument: {
      id: file.getId(),
      name: file.getName(),
      url: file.getUrl(),
      updatedAt: file.getLastUpdated().toISOString()
    },
    structuredFromGoogleDocs: true,
    structureVersion: 3
  };

  mrFillFallbacks_(report, fullText);
  report.markets = MR_MARKETS_.map(function(market) {
    return mrExtractMarket_(market.name, market.re, sections, fullText);
  });
  return report;
}

function mrExtractIdentity_(fileName, fullText) {
  var match = fileName.match(/(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})$/);
  if (!match) throw new Error('ファイル名から日時を取得できません。');
  var date = match[1];
  var time = match[2] + ':' + match[3];
  var titleLine = fullText.split('\n').filter(function(line) { return /^マーケットレポート｜/.test(line.trim()); })[0];
  return {date: date, time: time, title: titleLine ? titleLine.trim() : 'マーケットレポート｜' + date.replace(/-/g,'/') + ' ' + time};
}

function mrSplitSections_(text) {
  var lines = mrClean_(text).split('\n');
  var sections = [];
  var current = {heading:'冒頭', body:[]};
  var headingRe = /^\s*(?:(?:第?\d+|[一二三四五六七八九十]+)\s*[．.、:：)）]|【([^】]+)】|[■◆◇●])\s*(.+?)\s*$/;

  lines.forEach(function(raw) {
    var line = raw.trim();
    var match = line.match(headingRe);
    var plain = line.length >= 2 && line.length <= 55 && !/[。！？]$/.test(line) && MR_SECTION_RULES_.some(function(rule){ return rule[1].test(line); });
    if (match || plain) {
      if (current.body.join('').trim()) sections.push({heading:current.heading, text:mrClean_(current.body.join('\n'))});
      current = {heading: mrClean_(match ? (match[1] || match[2]) : line), body:[]};
    } else {
      current.body.push(raw);
    }
  });
  if (current.body.join('').trim()) sections.push({heading:current.heading, text:mrClean_(current.body.join('\n'))});
  return sections;
}

function mrFindSections_(sections, pattern) {
  return sections.filter(function(s){ return pattern.test(s.heading); }).map(function(s){ return s.text; }).filter(String).join('\n\n');
}

function mrExtractMarket_(name, pattern, sections, fullText) {
  var matched = sections.filter(function(s){ return pattern.test(s.heading); });
  var text = matched.map(function(s){ return s.heading + '\n' + s.text; }).join('\n\n');
  if (!text) {
    var lines = fullText.split('\n');
    var chunks = [];
    lines.forEach(function(line, index) {
      if (pattern.test(line)) chunks = chunks.concat(lines.slice(Math.max(0,index-1), Math.min(lines.length,index+7)));
    });
    text = chunks.filter(function(value,index,array){ return array.indexOf(value) === index; }).join('\n');
  }

  var rows = mrParagraphs_(text);
  var price = text.split('\n').filter(function(line){ return /\d/.test(line) && /円|ドル|%|％|前後|台|ポイント/.test(line); })[0] || '';
  return {
    name: name,
    direction: mrInferDirection_(text),
    price: price.substring(0,180),
    change: mrPick_(rows, /前日比|前日清算値比|[＋+－-]\s*\d|上昇|下落/) || '',
    material: mrFirstMeaningful_(text) || '本文参照',
    positioning: mrPick_(rows, /需給|ポジション|買い戻し|ショート|ロング|建玉|フロー|レバレッジ/) || '',
    levels: mrPick_(rows, /注目水準|下値|上値|サポート|レジスタンス|上抜|下抜|割れ|超え/) || '',
    mainScenario: mrPick_(rows, /メイン|基本シナリオ|中心シナリオ/) || '',
    alternativeScenario: mrPick_(rows, /代替|別シナリオ|反対シナリオ/) || '',
    breakCondition: mrPick_(rows, /崩れる条件|見方を変える|無効|否定/) || '本文参照',
    risk: mrPick_(rows, /リスク|注意|警戒/) || ''
  };
}

function mrFillFallbacks_(report, fullText) {
  var sentences = mrSentences_(fullText);
  var fallback = {
    news: /発表|報道|ニュース|合意|協議|政策|FOMC|日銀|ECB|FRB/,
    positioning: /需給|ポジション|建玉|買い戻し|ショート|ロング|ETF|オプション|SQ|レバレッジ/,
    crossAssetFlow: /資金|流入|流出|買われ|売られ|株式から|債券へ|安全資産/,
    events: /予定|発表|会合|指標|決算|入札|会見/,
    handover: /欧州時間|NY時間|次の時間帯|引き継ぎ|今夜|今後/,
    riskManagement: /リスク|警戒|注意|急変|損切り|ポジションサイズ/
  };
  Object.keys(fallback).forEach(function(field) {
    if (!report[field] || !report[field].length) report[field] = sentences.filter(function(s){ return fallback[field].test(s); }).slice(0,6);
  });
}

function mrValidateReports_(reports) {
  reports.forEach(function(report) {
    if (!report.fullText || report.fullText.length < 200) throw new Error(report.title + ': fullTextが不足しています。');
    if (!report.theme) throw new Error(report.title + ': 相場テーマがありません。');
    if (!report.markets || report.markets.length !== 6) throw new Error(report.title + ': 6市場が揃っていません。');
  });
}

function mrFetchReportsJson_() {
  var config = mrGithubConfig_();
  var url = 'https://api.github.com/repos/' + config.owner + '/' + config.repo + '/contents/reports.json?ref=' + encodeURIComponent(config.branch);
  var response = UrlFetchApp.fetch(url, {headers:mrGithubHeaders_(config.token), muteHttpExceptions:true});
  if (response.getResponseCode() === 404) return [];
  if (response.getResponseCode() < 200 || response.getResponseCode() >= 300) throw new Error('reports.json取得失敗: ' + response.getContentText());
  var payload = JSON.parse(response.getContentText());
  return JSON.parse(Utilities.newBlob(Utilities.base64Decode(payload.content.replace(/\n/g,''))).getDataAsString('UTF-8'));
}

function mrPublishReportsJson_(reports) {
  var config = mrGithubConfig_();
  var path = 'reports.json';
  var url = 'https://api.github.com/repos/' + config.owner + '/' + config.repo + '/contents/' + path;
  var getResponse = UrlFetchApp.fetch(url + '?ref=' + encodeURIComponent(config.branch), {headers:mrGithubHeaders_(config.token), muteHttpExceptions:true});
  var sha = '';
  if (getResponse.getResponseCode() === 200) sha = JSON.parse(getResponse.getContentText()).sha;

  var body = {
    message: 'Import complete structured market reports from Google Docs',
    content: Utilities.base64Encode(JSON.stringify(reports, null, 2), Utilities.Charset.UTF_8),
    branch: config.branch
  };
  if (sha) body.sha = sha;

  var response = UrlFetchApp.fetch(url, {
    method:'put',
    contentType:'application/json',
    headers:mrGithubHeaders_(config.token),
    payload:JSON.stringify(body),
    muteHttpExceptions:true
  });
  if (response.getResponseCode() < 200 || response.getResponseCode() >= 300) throw new Error('GitHub更新失敗: ' + response.getContentText());
}

function mrGithubConfig_() {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('スクリプトプロパティ GITHUB_TOKEN を設定してください。');
  return {
    token: token,
    owner: props.getProperty('GITHUB_OWNER') || 'matrixdiamond512-cell',
    repo: props.getProperty('GITHUB_REPO') || 'Chat-GPT-Market-Report',
    branch: props.getProperty('GITHUB_BRANCH') || 'main'
  };
}

function mrGithubHeaders_(token) {
  return {
    Authorization:'Bearer ' + token,
    Accept:'application/vnd.github+json',
    'X-GitHub-Api-Version':'2022-11-28'
  };
}

function mrClean_(value) { return String(value || '').replace(/\r/g,'').trim(); }
function mrParagraphs_(text) {
  return mrClean_(text).split(/\n\s*\n/).map(function(block){ return block.replace(/\s*\n\s*/g,' ').replace(/^[・●■◆◇]\s*/,'').trim(); }).filter(String);
}
function mrSentences_(text) {
  var result = [];
  mrParagraphs_(text).forEach(function(p){ p.split(/(?<=[。！？])\s+/).forEach(function(s){ if (s.trim().length >= 12) result.push(s.trim()); }); });
  return result;
}
function mrFirstMeaningful_(text) {
  var rows = mrParagraphs_(text);
  for (var i=0;i<rows.length;i++) if (rows[i].length > 12 && !/作成日時|対象：|基準時刻/.test(rows[i])) return rows[i];
  return '';
}
function mrPick_(rows, pattern) {
  for (var i=0;i<rows.length;i++) if (pattern.test(rows[i])) return rows[i];
  return '';
}
function mrFindSentence_(text, pattern) { return mrPick_(mrSentences_(text), pattern); }
function mrInferDirection_(text) {
  var down = (text.match(/急落|下落|弱含み|売り優勢|上値重い|反落|軟調|弱気/g) || []).length;
  var up = (text.match(/急騰|上昇|強含み|買い優勢|反発|堅調|強気/g) || []).length;
  if (down > up) return '下落・弱気';
  if (up > down) return '上昇・強気';
  if (/横ばい|レンジ|拮抗|中立|方向感/.test(text)) return '中立・レンジ';
  return '本文参照';
}
