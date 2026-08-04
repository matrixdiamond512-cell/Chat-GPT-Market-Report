const WEB_REPORT_CONFIG = {
  owner: 'matrixdiamond512-cell',
  repo: 'Chat-GPT-Market-Report',
  branch: 'main',
  targetPath: 'reports.json',
  pagesUrl: 'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/',
  prefix: 'マーケットレポート_',
  timezone: 'Asia/Tokyo'
};

function showWebReportSidebar() {
  SpreadsheetApp.getUi().showSidebar(
    HtmlService.createHtmlOutputFromFile('MarketReportSidebar')
      .setTitle('WEB版レポート登録')
  );
}

function publishWebReport(text) {
  return publishWebReportObject_(parseAndValidateWebReport_(text));
}

function previewWebReport(text) {
  return parseAndValidateWebReport_(text);
}

function previewLatestMarketReportFromDrive() {
  const file = findLatestMarketReportDoc_();
  const report = buildWebReportFromGoogleDoc_(file);
  const html = HtmlService.createHtmlOutput(
    '<p><b>元文書:</b> ' + escapeWebHtml_(file.getName()) + '</p>' +
    '<pre style="white-space:pre-wrap;font-size:12px">' +
    escapeWebHtml_(JSON.stringify(report, null, 2)) +
    '</pre>'
  ).setWidth(840).setHeight(680);

  SpreadsheetApp.getUi().showModalDialog(html, '最新Google Docs → WEB版プレビュー');
  return report;
}

function publishLatestMarketReportFromDrive() {
  const file = findLatestMarketReportDoc_();
  const report = buildWebReportFromGoogleDoc_(file);
  const result = publishWebReportObject_(report);

  SpreadsheetApp.getUi().alert(
    'WEB版へ反映しました。\n' +
    '元文書: ' + file.getName() + '\n' +
    'レポート: ' + result.commitSha + '\n' +
    'ダッシュボード: ' + (result.dashboardCommitSha || '未更新')
  );

  return result;
}

function publishMarketReportFromDocUrlPrompt() {
  const ui = SpreadsheetApp.getUi();
  const res = ui.prompt(
    'Google DocsからWEB版へ反映',
    'Google Docs URLまたはファイルIDを入力してください。',
    ui.ButtonSet.OK_CANCEL
  );

  if (res.getSelectedButton() !== ui.Button.OK) return null;

  const file = DriveApp.getFileById(extractDriveId_(res.getResponseText()));
  const result = publishWebReportObject_(buildWebReportFromGoogleDoc_(file));
  ui.alert('WEB版へ反映しました。\n元文書: ' + file.getName() + '\nコミット: ' + result.commitSha);
  return result;
}

function publishWebReportObject_(report) {
  report = validateWebReportObject_(report);
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    const current = getGitHubJsonFile_(WEB_REPORT_CONFIG.targetPath);
    const reports = normalizeWebReportList_(current.data);
    const next = upsertWebReportList_(reports, report);
    const key = report.date + ' ' + report.time;

    const result = putGitHubJsonFile_(
      WEB_REPORT_CONFIG.targetPath,
      JSON.stringify(next, null, 2) + '\n',
      current.sha,
      'Publish market report ' + key
    );

    const dashboardResult = typeof syncDashboardJsonToGitHubFromReports_ === 'function'
      ? syncDashboardJsonToGitHubFromReports_(next)
      : null;

    return {
      ok: true,
      title: report.title,
      date: report.date,
      time: report.time,
      commitSha: result.commit.sha,
      dashboardCommitSha: dashboardResult ? dashboardResult.commitSha : '',
      pagesUrl: WEB_REPORT_CONFIG.pagesUrl
    };
  } finally {
    lock.releaseLock();
  }
}

function normalizeWebReportList_(data) {
  let list = [];

  if (Array.isArray(data)) {
    list = data;
  } else if (data && Array.isArray(data.reports)) {
    list = data.reports;
  } else if (data && data.latestReport) {
    list = [data.latestReport];
  } else if (data && data.date && data.time) {
    list = [data];
  }

  return list.filter(item =>
    item &&
    /^\d{4}-\d{2}-\d{2}$/.test(String(item.date || '')) &&
    /^\d{2}:\d{2}$/.test(String(item.time || ''))
  );
}

function upsertWebReportList_(reports, report) {
  const key = report.date + ' ' + report.time;
  const next = normalizeWebReportList_(reports)
    .filter(item => (item.date + ' ' + item.time) !== key);

  next.push(report);
  next.sort((a, b) => (b.date + ' ' + b.time).localeCompare(a.date + ' ' + a.time));
  return next;
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

  return validateWebReportObject_(report);
}

function validateWebReportObject_(report) {
  if (!report || typeof report !== 'object') throw new Error('レポートデータがありません。');

  ['date', 'time', 'title', 'theme', 'leadingMarket', 'markets'].forEach(key => {
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

  const required = ['金', '原油', '日経225先物', 'USD/JPY', 'EUR/USD', 'BTCUSD'];
  const names = (report.markets || []).map(item => item && item.name).filter(Boolean);
  const missing = required.filter(name => !names.includes(name));
  if (missing.length) throw new Error('必須市場が不足しています: ' + missing.join('、'));

  report.tags = Array.isArray(report.tags) ? report.tags : [];
  [
    'changes',
    'consistency',
    'positioning',
    'news',
    'handover',
    'crossAssetFlow',
    'sectors',
    'events',
    'riskManagement'
  ].forEach(key => {
    if (report[key] !== undefined && !Array.isArray(report[key])) report[key] = [report[key]];
  });

  return report;
}

function findLatestMarketReportDoc_() {
  const query = "mimeType='application/vnd.google-apps.document' and trashed=false and title contains '" +
    WEB_REPORT_CONFIG.prefix + "'";
  const files = DriveApp.searchFiles(query);
  let latest = null;
  let latestInfo = null;

  while (files.hasNext()) {
    const file = files.next();
    if (file.isTrashed && file.isTrashed()) continue;
    if (file.getMimeType && file.getMimeType() !== MimeType.GOOGLE_DOCS) continue;

    const info = marketReportDocInfoFromName_(file.getName());
    if (!info) continue;

    if (
      !latestInfo ||
      info.key > latestInfo.key ||
      (info.key === latestInfo.key && file.getLastUpdated().getTime() > latest.getLastUpdated().getTime())
    ) {
      latest = file;
      latestInfo = info;
    }
  }

  if (!latest) throw new Error('マーケットレポートのGoogle Docsが見つかりません。');
  return latest;
}

function marketReportDocInfoFromName_(fileName) {
  const match = String(fileName || '').match(/_(\d{4})-(\d{1,2})-(\d{1,2})_(\d{1,2})-(\d{2})$/);
  if (!match) return null;

  const date = match[1] + '-' + pad2_(match[2]) + '-' + pad2_(match[3]);
  const time = pad2_(match[4]) + ':' + match[5];
  return {
    date: date,
    time: time,
    key: date + ' ' + time
  };
}

function buildWebReportFromGoogleDoc_(file) {
  const text = normalizeReportText_(DocumentApp.openById(file.getId()).getBody().getText());
  const meta = parseReportMetadata_(text, file.getName());

  const report = {
    date: meta.date,
    time: meta.time,
    title: meta.title,
    tags: ['ドル円', 'ユーロドル', '日経225先物', '金', '原油', 'BTCUSD'],
    theme: smartSectionText_(text, ['今日の相場テーマ', '相場テーマ', '本日のテーマ']) || inferTheme_(text),
    changes: smartSectionLines_(text, ['前回からの変化', '07:00からの変化', '12:00からの変化', '16:00からの変化', '前回比']),
    consistency: smartSectionLines_(text, ['材料と値動きの整合性', '材料と価格反応', '材料→市場→価格反応']),
    leadingMarket: smartSectionText_(text, ['今日の主導市場', '主導市場', '相場を主導している市場']) || inferLeadingMarket_(text),
    positioning: smartSectionLines_(text, ['需給・ポジション', '需給とポジション', 'ポジションの偏り', 'ポジショニング・需給']),
    news: smartSectionLines_(text, ['重要ニュースと影響', '重要ニュース', '市場を動かすニュース', '相場に影響する重要ニュース', 'ニュース・材料']),
    crossAssetFlow: smartSectionLines_(text, ['クロスアセット資金フロー', '資金フロー', '何が買われ、何が売られたか']),
    sectors: smartSectionLines_(text, ['セクター・業種動向', '買われた業種・売られた業種', 'セクター動向']),
    handover: smartSectionLines_(text, ['NY時間への引き継ぎ', '欧州時間への引き継ぎ', '東京時間への引き継ぎ', '次の時間帯への引き継ぎ']),
    events: smartSectionLines_(text, ['今後のイベント', '重要イベント', '本日の重要イベント', '今後の予定']),
    mainScenario: smartSectionText_(text, ['メインシナリオ', '基本シナリオ']),
    alternativeScenario: smartSectionText_(text, ['代替シナリオ', 'サブシナリオ', '弱気シナリオ', '強気シナリオ']),
    breakConditions: smartSectionText_(text, ['シナリオが崩れる条件', '崩れる条件', '見方を変える条件']),
    riskManagement: smartSectionLines_(text, ['リスク管理', 'リスク要因', '注意点']),
    markets: parseMarketsLenient_(text),
    sources: smartSectionLines_(text, ['主な確認情報源', '情報源', '参照元', '参照情報']).map(item => ({ name: item })),
    fullText: text,
    sourceDocument: {
      id: file.getId(),
      name: file.getName(),
      url: file.getUrl(),
      updatedAt: file.getLastUpdated().toISOString()
    },
    structuredFromFullText: true,
    structureVersion: 7
  };

  enrichSparseReport_(report, text);
  return validateWebReportObject_(report);
}

function buildLegacyWebReportFromGoogleDoc_(file, parseError) {
  const report = buildWebReportFromGoogleDoc_(file);
  report.migrationNote = '標準解析の一部を補完して取り込み: ' + parseError;
  return report;
}

function parseReportMetadata_(text, fileName) {
  const titleMatch = text.match(/マーケットレポート[｜|]\s*(\d{4})\/(\d{1,2})\/(\d{1,2})[（(][^）)]+[）)]\s*(\d{1,2}):(\d{2})/);
  if (titleMatch) {
    return {
      date: titleMatch[1] + '-' + pad2_(titleMatch[2]) + '-' + pad2_(titleMatch[3]),
      time: pad2_(titleMatch[4]) + ':' + titleMatch[5],
      title: titleMatch[0]
    };
  }

  const fileMatch = String(fileName || '').match(/^マーケットレポート_(\d{4})-(\d{1,2})-(\d{1,2})_(\d{1,2})-(\d{2})/);
  if (fileMatch) {
    return {
      date: fileMatch[1] + '-' + pad2_(fileMatch[2]) + '-' + pad2_(fileMatch[3]),
      time: pad2_(fileMatch[4]) + ':' + fileMatch[5],
      title: 'マーケットレポート｜' + fileMatch[1] + '/' + pad2_(fileMatch[2]) + '/' + pad2_(fileMatch[3]) + ' ' + pad2_(fileMatch[4]) + ':' + fileMatch[5]
    };
  }

  throw new Error('タイトルまたはファイル名から日時を取得できません。');
}

function parseMarkets_(text) {
  return parseMarketsLenient_(text);
}

function parseMarketsLenient_(text) {
  const definitions = [
    { name: '金', aliases: ['金', 'ゴールド', 'XAU/USD', 'XAUUSD', '金（スポット）', '金スポット'] },
    { name: '原油', aliases: ['WTI原油', '原油', 'WTI', 'Brent', 'ブレント'] },
    { name: '日経225先物', aliases: ['日経225先物（大阪取引所）', '日経225先物', '日経先物', '日経平均先物'] },
    { name: 'USD/JPY', aliases: ['USD/JPY', 'ドル円', 'USDJPY'] },
    { name: 'EUR/USD', aliases: ['EUR/USD', 'ユーロドル', 'EURUSD'] },
    { name: 'BTCUSD', aliases: ['BTCUSD', 'BTC/USD', 'ビットコイン', 'BTC'] }
  ];

  return definitions.map(definition => {
    const block = smartMarketBlock_(text, definition.aliases);
    const fallback = extractMarketSentence_(text, definition.name);
    const material = fieldValueFlexible_(block, ['材料', '主な材料', '背景', '判断']) || fallback || '本文参照';

    return {
      name: definition.name,
      direction: fieldValueFlexible_(block, ['方向', '方向性', '短期見通し', '見通し']) || inferDirection_(block || fallback, definition.name),
      price: fieldValueFlexible_(block, ['現状', '価格', '現在値', '確認値', '終値']),
      change: fieldValueFlexible_(block, ['前日比', '変化', '騰落率']),
      material: material,
      positioning: fieldValueFlexible_(block, ['需給', 'ポジション', 'ポジショニング']),
      levels: fieldValueFlexible_(block, ['注目水準', '水準', 'サポート・レジスタンス', '注意水準']),
      mainScenario: fieldValueFlexible_(block, ['メインシナリオ', '基本シナリオ']) || material,
      alternativeScenario: fieldValueFlexible_(block, ['代替シナリオ', 'サブシナリオ']),
      breakCondition: fieldValueFlexible_(block, ['崩れる条件', '見方を変える条件']),
      risk: fieldValueFlexible_(block, ['リスク', '注意点'])
    };
  });
}

function enrichSparseReport_(report, text) {
  if (!report.theme || report.theme === '本文参照') report.theme = inferTheme_(text);
  if (!report.leadingMarket || report.leadingMarket === '本文参照') report.leadingMarket = inferLeadingMarket_(text);

  if (!report.news.length) {
    report.news = extractKeywordSentences_(text, ['発表', '報道', 'ニュース', 'FOMC', '日銀', 'ECB', '雇用', 'CPI', 'PCE'], 6);
  }
  if (!report.crossAssetFlow.length) {
    report.crossAssetFlow = extractKeywordSentences_(text, ['買われ', '売られ', '資金', '流入', '流出', 'リスクオン', 'リスクオフ'], 5);
  }
  if (!report.positioning.length) {
    report.positioning = extractKeywordSentences_(text, ['ポジション', '需給', '建玉', 'ショート', 'ロング', '買い戻し', 'ガンマ'], 5);
  }
  if (!report.consistency.length) {
    report.consistency = extractKeywordSentences_(text, ['反応', '整合', '織り込み', '逆行', '主導'], 4);
  }
  if (!report.handover.length) {
    report.handover = extractKeywordSentences_(text, ['欧州時間', 'NY時間', '東京時間', '次の時間帯', '注目'], 4);
  }
  if (!report.riskManagement.length) {
    report.riskManagement = extractKeywordSentences_(text, ['リスク', '警戒', '注意', '崩れる', '急変'], 5);
  }

  report.markets = report.markets.map(market => {
    if (!market.material) market.material = extractMarketSentence_(text, market.name) || '本文参照';
    if (!market.direction || market.direction === '取得不能') market.direction = inferDirection_(market.material + ' ' + text, market.name);
    if (!market.breakCondition) market.breakCondition = report.breakConditions || '重要材料と直近水準の突破で見方を再評価';
    return market;
  });
}

function smartSectionBlock_(text, headings) {
  const lines = String(text || '').split('\n');
  const normalizedHeadings = headings.map(normalizeHeading_);
  let start = -1;

  for (let i = 0; i < lines.length; i += 1) {
    const lineHeading = normalizeHeading_(lines[i]);
    if (normalizedHeadings.some(heading => lineHeading === heading || lineHeading.indexOf(heading) >= 0)) {
      start = i + 1;
      break;
    }
  }

  if (start < 0) return '';

  const output = [];
  for (let i = start; i < lines.length; i += 1) {
    if (looksLikeHeading_(lines[i]) && output.length) break;
    output.push(lines[i]);
  }

  return output.join('\n').trim();
}

function smartSectionText_(text, headings) {
  const block = smartSectionBlock_(text, headings) || sectionBlock_(text, headings);
  return String(block || '').replace(/\n+/g, ' ').replace(/\s+/g, ' ').trim();
}

function smartSectionLines_(text, headings) {
  const block = smartSectionBlock_(text, headings) || sectionBlock_(text, headings);
  return splitMeaningfulLines_(block);
}

function sectionBlock_(text, headings) {
  for (const heading of headings) {
    const match = String(text || '').match(
      new RegExp('【\\s*' + escapeRegExp_(heading) + '\\s*】\\s*\\n?([\\s\\S]*?)(?=\\n\\s*【|$)', 'i')
    );
    if (match) return match[1].trim();
  }
  return '';
}

function splitMeaningfulLines_(block) {
  return String(block || '').split('\n')
    .map(line => line.replace(/^\s*(?:[-・●■◆◇▶▷※]|\d+[.)．、]|[①-⑳])\s*/, '').trim())
    .filter(line => line && !looksLikeHeading_(line));
}

function smartMarketBlock_(text, aliases) {
  const lines = String(text || '').split('\n');
  let start = -1;

  for (let i = 0; i < lines.length; i += 1) {
    const normalizedLine = normalizeHeading_(lines[i]).toLowerCase();
    if (aliases.some(alias => {
      const normalizedAlias = normalizeHeading_(alias).toLowerCase();
      return normalizedLine === normalizedAlias || normalizedLine.indexOf(normalizedAlias) >= 0;
    })) {
      start = i + 1;
      break;
    }
  }

  if (start < 0) return '';

  const output = [];
  for (let i = start; i < lines.length; i += 1) {
    if (looksLikeHeading_(lines[i]) && output.length) break;
    output.push(lines[i]);
  }

  return output.join('\n').trim();
}

function fieldValueFlexible_(block, labels) {
  const lines = String(block || '').split('\n');

  for (const line of lines) {
    const normalized = line.replace(/^\s*[-・●■◆◇]\s*/, '').trim();
    for (const label of labels) {
      const pattern = new RegExp('^' + escapeRegExp_(label) + '\\s*(?:[：:]|→|＝|=|-)?\\s*(.+)$', 'i');
      const match = normalized.match(pattern);
      if (match && match[1]) return match[1].trim();
    }
  }

  return '';
}

function normalizeHeading_(value) {
  return String(value || '')
    .replace(/[【】\[\]■●◆◇▶▷#：:]/g, '')
    .replace(/^\s*\d+[.)．、]\s*/, '')
    .replace(/\s+/g, '')
    .trim();
}

function looksLikeHeading_(line) {
  const text = String(line || '').trim();
  if (!text) return false;
  if (/^[【\[].+[】\]]$/.test(text)) return true;
  if (/^(?:■|●|◆|◇|▶|▷|#{1,4})\s*\S+/.test(text)) return true;
  if (/^\d+[.)．、]\s*\S+/.test(text) && text.length < 45) return true;
  return /^(今日の相場テーマ|前回からの変化|材料と値動き|今日の主導市場|重要ニュース|クロスアセット|需給|ポジション|今後のイベント|個別見通し|メインシナリオ|代替シナリオ|リスク管理|まとめ)/.test(text) && text.length < 50;
}

function inferTheme_(text) {
  const candidates = extractKeywordSentences_(text, ['テーマ', '主役', '焦点', '市場は', '相場は'], 2);
  return candidates[0] || firstMeaningfulLine_(text) || '市場全体の材料と資金フローを確認';
}

function inferLeadingMarket_(text) {
  const source = String(text || '');
  const scores = [
    ['米金利', ['米金利', '米10年債', '長期金利']],
    ['ドル・為替', ['ドル円', 'USD/JPY', 'ドル高', 'ドル安']],
    ['株式・日経225先物', ['日経225先物', '日経先物', '株式市場', '半導体株']],
    ['原油・エネルギー', ['原油', 'WTI', 'ブレント']],
    ['金・安全資産', ['ゴールド', '金価格', '安全資産']],
    ['BTC・暗号資産', ['BTC', 'ビットコイン', '暗号資産']]
  ].map(item => [
    item[0],
    item[1].reduce((total, keyword) => total + (source.match(new RegExp(escapeRegExp_(keyword), 'gi')) || []).length, 0)
  ]);

  scores.sort((a, b) => b[1] - a[1]);
  return scores[0][1] ? scores[0][0] : '複数市場の綱引き';
}

function inferDirection_(text, marketName) {
  const source = String(text || '');
  if (/上昇|強含み|反発|買い優勢|底堅い|強気|支え/.test(source)) return '上昇・強含み';
  if (/下落|弱含み|反落|売り優勢|上値が重い|弱気|逆風/.test(source)) return '下落・弱含み';
  return '中立・方向確認';
}

function extractKeywordSentences_(text, keywords, limit) {
  const seen = {};
  return String(text || '').split(/\n|。|！|？/)
    .map(line => line.replace(/^\s*[-・●■◆◇]\s*/, '').trim())
    .filter(line => line.length >= 12 && line.length <= 220)
    .filter(line => keywords.some(keyword => line.indexOf(keyword) >= 0))
    .filter(line => !seen[line] && (seen[line] = true))
    .slice(0, limit);
}

function extractMarketSentence_(text, marketName) {
  const aliases = {
    '金': ['金', 'ゴールド', 'XAU'],
    '原油': ['原油', 'WTI', 'ブレント'],
    '日経225先物': ['日経225先物', '日経先物', '日経平均先物'],
    'USD/JPY': ['USD/JPY', 'ドル円', 'USDJPY'],
    'EUR/USD': ['EUR/USD', 'ユーロドル', 'EURUSD'],
    'BTCUSD': ['BTCUSD', 'BTC/USD', 'ビットコイン', 'BTC']
  }[marketName] || [marketName];

  return extractKeywordSentences_(text, aliases, 1)[0] || '';
}

function normalizeReportText_(text) {
  return String(text || '')
    .replace(/\r\n?/g, '\n')
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function firstMeaningfulLine_(text) {
  return String(text || '').split('\n')
    .map(line => line.trim())
    .find(line => line && !/^マーケットレポート[｜_]/.test(line)) || '';
}

function pad2_(value) {
  return ('0' + String(value)).slice(-2);
}

function extractDriveId_(value) {
  const match = String(value || '').trim().match(/[-\w]{25,}/);
  if (!match) throw new Error('Google Docs URLまたはファイルIDを確認してください。');
  return match[0];
}

function escapeRegExp_(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function escapeWebHtml_(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function getGitHubJsonFile_(path) {
  const response = UrlFetchApp.fetch(
    githubContentsUrl_(path) + '?ref=' + encodeURIComponent(WEB_REPORT_CONFIG.branch),
    {
      method: 'get',
      headers: githubHeaders_(getGitHubToken_()),
      muteHttpExceptions: true
    }
  );

  const code = response.getResponseCode();
  if (code === 404) return { data: [], sha: null };
  if (code !== 200) throw new Error('GitHubファイル取得失敗: HTTP ' + code + ' ' + response.getContentText());

  const payload = JSON.parse(response.getContentText());
  return {
    data: JSON.parse(Utilities.newBlob(Utilities.base64Decode(payload.content)).getDataAsString('UTF-8')),
    sha: payload.sha
  };
}

function putGitHubJsonFile_(path, content, sha, message) {
  const payload = {
    message: message,
    content: Utilities.base64Encode(content, Utilities.Charset.UTF_8),
    branch: WEB_REPORT_CONFIG.branch
  };
  if (sha) payload.sha = sha;

  const response = UrlFetchApp.fetch(githubContentsUrl_(path), {
    method: 'put',
    contentType: 'application/json',
    headers: githubHeaders_(getGitHubToken_()),
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
  return 'https://api.github.com/repos/' +
    WEB_REPORT_CONFIG.owner + '/' +
    WEB_REPORT_CONFIG.repo + '/contents/' + path;
}

function githubHeaders_(token) {
  return {
    Authorization: 'Bearer ' + token,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };
}
