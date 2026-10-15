var MARKET_REPORT_PREPUBLISH_CONFIG = {
  requiredMarkets: ['金', '原油', '日経225先物', 'USD/JPY', 'EUR/USD', 'BTCUSD'],
  requiredReportFields: [
    'date', 'time', 'title', 'theme', 'leadingMarket', 'markets',
    'mainScenario', 'alternativeScenario', 'breakConditions', 'riskManagement'
  ],
  requiredMarketFields: ['name', 'direction'],
  recommendedMarketFields: [
    'price', 'outlook', 'material', 'positioning', 'levels',
    'mainScenario', 'alternativeScenario', 'breakCondition', 'risk'
  ],
  unavailablePatterns: [
    /^取得不能(?:（.*）)?$/,
    /^未取得(?:（.*）)?$/,
    /^本文参照$/,
    /^個別記載なし$/,
    /^個別見通し参照$/,
    /^記載なし$/
  ],
  manualEnforceFrom: '2026-08-13',
  requiredSlotFields: [
    'changes', 'consistency', 'news', 'crossAssetFlow', 'positioning', 'events', 'handover'
  ],
  commonSectionRules: [
    { label: '主要市場データ', pattern: /^(?:主要市場データ|主要市場の確認値|主要市場まとめ|主要価格|6市場の(?:個別)?見通し|個別市場見通し)$/ },
    { label: '今日の相場テーマ', pattern: /^(?:今日の相場テーマ|今日のテーマ)$/ },
    { label: '材料と値動きの整合性', pattern: /^材料.*値動き.*整合性$|^材料と値動きの整合性$/ },
    { label: '主導市場', pattern: /^(?:今日の)?主導市場$/ },
    { label: '重要ニュース', pattern: /^(?:重要ニュース|重要ニュース・金利|重要材料)$/ },
    { label: '金利', pattern: /^(?:金利|金利分析|金利・為替|金利・為替の連動|重要ニュース・金利)$/ },
    { label: 'クロスアセット資金フロー', pattern: /^(?:クロスアセット|クロスアセット資金フロー|資金フロー)$/ },
    { label: '需給・ポジション', pattern: /^(?:需給・ポジション|需給・ポジショニング|ポジションの偏り)$/ },
    { label: '重要イベント', pattern: /^(?:(?:今後の|その日の)?重要イベント|今後の予定)$/ },
    { label: '個別市場見通し', pattern: /^(?:6市場の(?:個別)?見通し|個別市場見通し|個別見通し)$/ },
    { label: 'メインシナリオ', pattern: /^(?:メインシナリオ|基本シナリオ|メイン[：:].*)$/ },
    { label: '代替シナリオ', pattern: /^(?:代替シナリオ|別シナリオ|代替[：:].*)$/ },
    { label: 'シナリオが崩れる条件', pattern: /^(?:シナリオが)?崩れる条件(?:[：:].*)?$/ },
    { label: 'リスク管理', pattern: /^(?:リスク管理|主なリスク|リスク要因|シナリオが崩れる条件|崩れる条件)$/ },
    { label: '結論', pattern: /^(?:結論|まとめ|最終判断)$/ }
  ],
  slotRules: {
    '08:00': {
      changeLabel: '前回からの変化',
      changePattern: /^(?:前回からの(?:主な)?変化|21:00からの変化|前日21:00からの変化|NY市場からの変化|前営業日からの変化|昨夜のNY市場)$/,
      handoverLabel: '東京時間への引き継ぎ',
      handoverPattern: /^(?:東京時間|東京市場|12:00|次の時間帯)への引き継ぎ$/
    },
    '12:00': {
      changeLabel: '08:00からの変化',
      changePattern: /^(?:08:00|08時|前回)からの(?:主な)?変化$/,
      handoverLabel: '欧州時間への引き継ぎ',
      handoverPattern: /^(?:欧州時間|欧州市場|次の時間帯)への引き継ぎ$/
    },
    '16:00': {
      changeLabel: '12:00からの変化',
      changePattern: /^(?:12:00|12時|前回)からの(?:主な)?変化$/,
      handoverLabel: 'NY時間への引き継ぎ',
      handoverPattern: /^(?:NY時間|NY市場|21:00|次の時間帯)への引き継ぎ$/
    },
    '21:00': {
      changeLabel: '16:00からの変化',
      changePattern: /^(?:(?:16:00|16時|前回)からの(?:主な)?変化|16:00から21:00のマーケットの動き)$/,
      handoverLabel: 'NY時間・翌東京時間への引き継ぎ',
      handoverPattern: /^(?:NY時間|NY市場|翌東京時間|明日|次の時間帯)への引き継ぎ$/
    }
  },
  morningRequiredLabels: [
    { label: 'NYダウ', pattern: /^(?:NYダウ|Dow|ダウ|NYダウ平均)$/i },
    { label: 'NASDAQ総合', pattern: /^(?:NASDAQ総合|Nasdaq総合|Nasdaq|NASDAQ)$/i },
    { label: 'S&P500', pattern: /^S&P\s*500$/i },
    { label: 'Russell 2000', pattern: /^Russell\s*2000$/i },
    { label: '日経225現物', pattern: /^(?:日経225現物|日経225|日経平均現物)$/ },
    { label: 'CME日経225先物', pattern: /^CME.*日経225先物/ },
    { label: '日経225先物（大阪取引所）', pattern: /^日経225先物(?:（大阪取引所）|\(大阪取引所\)|・大阪取引所)?$/ },
    { label: 'USD/JPY', pattern: /^(?:USD\/JPY|USDJPY|ドル円)$/i },
    { label: 'EUR/USD', pattern: /^(?:EUR\/USD|EURUSD|ユーロドル)$/i },
    { label: '金', pattern: /^(?:COMEX金先物|金|金先物|ゴールド)$/ },
    { label: 'WTI原油', pattern: /^(?:WTI原油|WTI|原油)$/ },
    { label: 'BTCUSD', pattern: /^(?:BTCUSD|BTC\/USD|Bitcoin|ビットコイン)$/i },
    { label: 'VIX', pattern: /^VIX(?:指数)?$/i },
    { label: '日経VI', pattern: /^日経VI$/ },
    { label: 'Fear & Greed Index', pattern: /^Fear\s*&\s*Greed(?:\s*Index)?$/i },
    { label: '米10年債利回り', pattern: /^(?:米10年債利回り|米10年債|米国10年債利回り)$/ },
    { label: '日本10年国債利回り', pattern: /^(?:日本10年国債利回り|日本10年債利回り|日本10年国債)$/ },
    { label: '日経225予想PER', pattern: /^(?:日経225予想PER|日経225PER|PER)$/ },
    { label: '日経225 PBR', pattern: /^(?:日経225\s*PBR|日経225PBR|PBR)$/ },
    { label: '日経225予想EPS', pattern: /^(?:日経225予想EPS|日経225EPS|EPS)$/ },
    { label: '25日移動平均乖離率', pattern: /^日経225\s*25日(?:移動平均)?乖離率$/ },
    { label: '200日移動平均乖離率', pattern: /^日経225\s*200日(?:移動平均)?乖離率$/ },
    { label: '東証プライム売買代金', pattern: /^東証プライム売買代金$/ },
    { label: '東証プライム売買高', pattern: /^東証プライム売買高$/ },
    { label: '値上がり銘柄数', pattern: /^(?:東証プライム)?値上がり銘柄数$/ },
    { label: '値下がり銘柄数', pattern: /^(?:東証プライム)?値下がり銘柄数$/ },
    { label: '騰落レシオ', pattern: /^(?:東証プライム)?(?:25日)?騰落レシオ$/ }
  ],
  forbiddenPublicPatterns: [
    { label: 'verified', pattern: /\bverified\b/i },
    { label: '未確認', pattern: /未確認/ },
    { label: 'JSON内部診断', pattern: /JSONにありません|構造化JSON|内部構造/ }
  ]
};

function validateMarketReportBeforePublish_(report, expectedHour) {
  var errors = [];
  var warnings = [];

  if (!report || typeof report !== 'object' || Array.isArray(report)) {
    throw new Error('公開前検証エラー: レポートオブジェクトが不正です。');
  }

  MARKET_REPORT_PREPUBLISH_CONFIG.requiredReportFields.forEach(function(field) {
    if (!Object.prototype.hasOwnProperty.call(report, field)) {
      errors.push('レポート必須項目不足: ' + field);
      return;
    }
    if (field !== 'markets' && marketReportPrePublishIsBlank_(report[field])) {
      errors.push('レポート必須項目が空です: ' + field);
    }
  });

  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(report.date || ''))) {
    errors.push('date形式不正: ' + String(report.date || ''));
  }

  if (!/^(07|08|09|12|16|21):00$/.test(String(report.time || ''))) {
    errors.push('time形式不正: ' + String(report.time || ''));
  }

  if (typeof expectedHour === 'number') {
    var expectedTime = ('0' + expectedHour).slice(-2) + ':00';
    if (String(report.time || '') !== expectedTime) {
      errors.push('予定時刻とレポート時刻が不一致: expected=' + expectedTime + ', actual=' + String(report.time || ''));
    }
  }

  var titleMatch = String(report.title || '').match(/^マーケットレポート｜(\d{4})\/(\d{2})\/(\d{2})（([月火水木金土日])）(\d{2}):(\d{2})$/);
  if (!titleMatch) {
    errors.push('タイトル形式不正: ' + String(report.title || ''));
  } else {
    var titleDate = titleMatch[1] + '-' + titleMatch[2] + '-' + titleMatch[3];
    var titleTime = titleMatch[5] + ':' + titleMatch[6];
    if (titleDate !== String(report.date || '') || titleTime !== String(report.time || '')) {
      errors.push('タイトルとdate/timeが不一致です。');
    }
    var weekday = ['日', '月', '火', '水', '木', '金', '土'][new Date(titleDate + 'T00:00:00Z').getUTCDay()];
    if (titleMatch[4] !== weekday) errors.push('タイトルの曜日と日本時間の日付が一致しません。');
  }

  var byName = {};
  if (!Array.isArray(report.markets)) {
    errors.push('marketsは配列である必要があります。');
  } else {
    report.markets.forEach(function(market, index) {
      if (!market || typeof market !== 'object' || Array.isArray(market)) {
        errors.push('markets[' + index + ']がオブジェクトではありません。');
        return;
      }
      var name = String(market.name || '');
      if (name) byName[name] = market;
    });

    MARKET_REPORT_PREPUBLISH_CONFIG.requiredMarkets.forEach(function(name) {
      if (!byName[name]) {
        errors.push('必須市場不足: ' + name);
        return;
      }

      var market = byName[name];
      MARKET_REPORT_PREPUBLISH_CONFIG.requiredMarketFields.forEach(function(field) {
        if (!Object.prototype.hasOwnProperty.call(market, field)) {
          errors.push(name + ': 必須項目不足: ' + field);
          return;
        }
        var value = market[field];
        if (marketReportPrePublishIsBlank_(value)) {
          errors.push(name + ': 必須項目が空です: ' + field);
          return;
        }
        if (marketReportPrePublishIsUnavailable_(value)) {
          warnings.push(name + ': ' + field + ' = ' + String(value));
        }
      });

      MARKET_REPORT_PREPUBLISH_CONFIG.recommendedMarketFields.forEach(function(field) {
        if (!Object.prototype.hasOwnProperty.call(market, field)) {
          warnings.push(name + ': 推奨項目不足: ' + field);
          return;
        }
        var value = market[field];
        if (marketReportPrePublishIsBlank_(value)) {
          warnings.push(name + ': 推奨項目が空です: ' + field);
          return;
        }
        if (marketReportPrePublishIsUnavailable_(value)) {
          warnings.push(name + ': ' + field + ' = ' + String(value));
        }
      });
    });
  }

  validateMarketReportManualContract_(report, byName, errors);

  if (errors.length) {
    throw new Error(
      '公開前検証に失敗しました。GitHubへの書き込みを中止します。\n- ' +
      errors.join('\n- ')
    );
  }

  return {
    ok: true,
    errors: [],
    warnings: warnings,
    checkedAt: Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd HH:mm:ss')
  };
}

function validateMarketReportManualContract_(report, byName, errors) {
  var dateText = String(report.date || '');
  var timeText = String(report.time || '');
  var slotRule = MARKET_REPORT_PREPUBLISH_CONFIG.slotRules[timeText];
  if (!slotRule || dateText < MARKET_REPORT_PREPUBLISH_CONFIG.manualEnforceFrom) return;

  MARKET_REPORT_PREPUBLISH_CONFIG.requiredSlotFields.forEach(function(field) {
    if (!Object.prototype.hasOwnProperty.call(report, field) || marketReportPrePublishIsBlank_(report[field])) {
      errors.push(timeText + ' SOP必須項目不足/空欄: ' + field);
    }
  });

  MARKET_REPORT_PREPUBLISH_CONFIG.requiredMarkets.forEach(function(name) {
    var market = byName[name];
    if (!market) return;
    if (!Object.prototype.hasOwnProperty.call(market, 'price') || marketReportPrePublishIsBlank_(market.price)) {
      errors.push(timeText + ' ' + name + ': 価格・水準が空です。');
    }
  });

  var source = String(report.fullText || report.rawText || report.body || '').replace(/\r/g, '').trim();
  if (!source) {
    errors.push(timeText + ' SOPでは公開本文 fullText/rawText/body が必須です。');
    return;
  }
  if (dateText >= MARKET_REPORT_PREPUBLISH_CONFIG.manualEnforceFrom && source.length < 1200) {
    errors.push(timeText + ' SOP公開本文は1,200文字以上の原文全文が必要です。');
  }
  marketReportPrePublishTimelineIssues_(source, timeText).forEach(function(issue) {
    errors.push(timeText + ' TIMELINE_CHECK: ' + issue);
  });
  var firstLine = source.split('\n').map(function(line) { return line.trim(); }).filter(Boolean)[0] || '';
  if (firstLine !== String(report.title || '')) {
    errors.push(timeText + ' 本文先頭のタイトルとdate/timeタイトルが一致しません。');
  }

  MARKET_REPORT_PREPUBLISH_CONFIG.forbiddenPublicPatterns.forEach(function(rule) {
    if (rule.pattern.test(source)) {
      errors.push(timeText + ' 公開本文に内部用語「' + rule.label + '」が残っています。');
    }
  });

  var headings = marketReportPrePublishHeadingLines_(source);
  MARKET_REPORT_PREPUBLISH_CONFIG.commonSectionRules.forEach(function(rule) {
    if (!marketReportPrePublishHasHeading_(headings, rule.pattern)) {
      errors.push(timeText + ' SOP必須セクション不足: ' + rule.label);
    }
  });

  if (!marketReportPrePublishHasHeading_(headings, slotRule.changePattern)) {
    errors.push(timeText + ' SOP必須セクション不足: ' + slotRule.changeLabel);
  }
  if (!marketReportPrePublishHasHeading_(headings, slotRule.handoverPattern)) {
    errors.push(timeText + ' SOP必須セクション不足: ' + slotRule.handoverLabel);
  }

  if (timeText === '08:00') {
    MARKET_REPORT_PREPUBLISH_CONFIG.morningRequiredLabels.forEach(function(rule) {
      if (!marketReportMorningHasSourceValue_(source, rule)) {
        errors.push('08:00 主要市場データ不足: ' + rule.label);
      }
    });
  }

  var headingOnly = /^(?:金利|金利分析|6市場の(?:個別)?見通し|個別市場見通し|結論|最終判断|シナリオが崩れる条件|東京時間への引き継ぎ|12:00への引き継ぎ|欧州時間への引き継ぎ|NY時間への引き継ぎ|明日への引き継ぎ|翌東京時間への引き継ぎ)$/;
  ['changes', 'consistency', 'news', 'crossAssetFlow', 'positioning', 'events', 'handover', 'riskManagement'].forEach(function(field) {
    var value = report[field];
    var items = Array.isArray(value) ? value : [value];
    items.forEach(function(item) {
      var text = String(item || '').trim();
      if (headingOnly.test(text)) {
        errors.push(timeText + ' ' + field + ': 見出しが本文項目へ混入しています: ' + text);
      }
    });
  });

  var foreignHeadings = {
    mainScenario: /(?:^|[。\s])(?:代替シナリオ|シナリオが崩れる条件|東京時間への引き継ぎ|12:00への引き継ぎ|欧州時間への引き継ぎ|NY時間への引き継ぎ|明日への引き継ぎ|翌東京時間への引き継ぎ|結論|最終判断)(?:\s|$)/,
    alternativeScenario: /(?:^|[。\s])(?:メインシナリオ|シナリオが崩れる条件|東京時間への引き継ぎ|12:00への引き継ぎ|欧州時間への引き継ぎ|NY時間への引き継ぎ|明日への引き継ぎ|翌東京時間への引き継ぎ|結論|最終判断)(?:\s|$)/,
    breakConditions: /(?:^|[。\s])(?:メインシナリオ|代替シナリオ|東京時間への引き継ぎ|12:00への引き継ぎ|欧州時間への引き継ぎ|NY時間への引き継ぎ|明日への引き継ぎ|翌東京時間への引き継ぎ|結論|最終判断)(?:\s|$)/
  };
  Object.keys(foreignHeadings).forEach(function(field) {
    if (foreignHeadings[field].test(String(report[field] || ''))) {
      errors.push(timeText + ' ' + field + ': 複数セクションが1フィールドへ連結されています。');
    }
  });
}

/**
 * Validate the narrative timeline table shared by the 08:00/12:00/16:00/21:00
 * publication slots. The gate checks coverage and explanatory fields; it does
 * not infer market causes from price rows or treat report time as event time.
 */
function marketReportPrePublishTimelineIssues_(source, timeText) {
  var periods = {
    '08:00': [
      ['開場前', ['開場前', '寄り付き前']],
      ['寄り付き', ['寄り付き', '開場']],
      ['序盤', ['序盤']],
      ['中盤', ['中盤']],
      ['終盤', ['終盤']],
      ['東京への引き継ぎ', ['東京への引き継ぎ', '東京時間への引き継ぎ']]
    ],
    '12:00': [
      ['寄り付き前', ['寄り付き前', '前場寄り前']],
      ['寄り付き', ['寄り付き']],
      ['前場序盤', ['前場序盤']],
      ['前場中盤', ['前場中盤']],
      ['前引け', ['前引け']]
    ],
    '16:00': [
      ['寄り付き前', ['寄り付き前', '前場寄り前']],
      ['寄り付き', ['寄り付き']],
      ['前場序盤', ['前場序盤']],
      ['前場中盤', ['前場中盤']],
      ['前引け', ['前引け']],
      ['後場序盤', ['後場序盤']],
      ['後場中盤', ['後場中盤']],
      ['大引け', ['大引け']],
      ['欧州への引き継ぎ', ['欧州への引き継ぎ', '欧州時間への引き継ぎ']]
    ],
    '21:00': [
      ['欧州開場前', ['欧州開場前', '欧州寄り前']],
      ['欧州寄り付き', ['欧州寄り付き', '欧州寄り']],
      ['欧州序盤', ['欧州序盤']],
      ['欧州中盤', ['欧州中盤']],
      ['NY開場前', ['NY開場前', 'NY寄り前']]
    ]
  };
  var columns = [
    '時間帯', 'JST時間範囲/観測制約', '出来事・確認可能な市場状態',
    '市場・業種・銘柄の反応', '相場上の意味・主導要因',
    '時刻・出典・観測制約', '次の時間帯への引き継ぎ'
  ];
  var issues = [];
  var lines = String(source || '').replace(/\r/g, '').split('\n');
  var starts = [];
  lines.forEach(function(line, index) {
    if (/^\s*(?:\d{1,2}[．.、)）]|[■◆◇●▶]).*時系列/.test(line)) starts.push(index);
  });
  if (starts.length !== 1) return ['時系列セクションが一意に見つかりません'];

  var sectionLines = [];
  for (var i = starts[0] + 1; i < lines.length; i++) {
    if (/^\s*\d{1,2}[．.、)）]\s*\S/.test(lines[i])) break;
    sectionLines.push(lines[i]);
  }
  var headerIndex = -1;
  var normalize = function(value) { return String(value || '').replace(/\s+/g, ''); };
  for (var h = 0; h < sectionLines.length; h++) {
    if (/^\s*\|.*\|\s*$/.test(sectionLines[h])) { headerIndex = h; break; }
  }
  if (headerIndex < 0) return ['時系列テーブルがありません'];
  var header = sectionLines[headerIndex].trim().slice(1, -1).split('|').map(normalize);
  if (header.length !== columns.length || !columns.every(function(value, index) { return header[index] === normalize(value); })) {
    return ['時系列テーブルの列が共通契約と一致しません'];
  }

  var slotPeriods = periods[timeText];
  var found = {};
  var cellSignals = {
    2: /確認|観測|報道|発表|材料|売買|続|転換|反転|急落|急騰|上昇|下落|横ばい|動|取引|休場|発生|形成|警戒/,
    3: /上昇|下落|反応|買い|売り|円高|円安|低下|上昇|広が|優勢|軟調|堅調|反発|急落|急騰|横ばい|縮小|拡大/,
    4: /ため|背景|示|意味|主導|重要|波及|影響|転換|続|反映|焦点|リスク|注目|警戒|評価|受け止|整合|乖離|局面|見極め|待ち/,
    5: /出典|根拠|観測|制約|報道|発表|未確認|確認できず|確認不能|fact[-_ ]?\w+/i,
    6: /引き継|次|注目|確認|継続|監視/
  };
  var timePattern = /(?:[01]?\d|2[0-3]):[0-5]\d/g;
  for (var rowIndex = headerIndex + 1; rowIndex < sectionLines.length; rowIndex++) {
    var rowText = sectionLines[rowIndex].trim();
    if (!/^\|.*\|$/.test(rowText) || /^\|[-: |]+\|$/.test(rowText)) continue;
    var cells = rowText.slice(1, -1).split('|').map(function(value) { return value.trim(); });
    if (cells.length !== columns.length) {
      issues.push('時系列の行に必須列の欠落があります');
      continue;
    }
    var canonical = null;
    slotPeriods.forEach(function(period) {
      if (period[1].indexOf(cells[0]) >= 0) canonical = period[0];
    });
    if (!canonical) {
      issues.push('対象時間帯ではない行があります: ' + cells[0]);
      continue;
    }
    if (found[canonical]) issues.push('時間帯が重複しています: ' + canonical);
    found[canonical] = true;
    [[2, '出来事・市場状態'], [3, '市場反応'], [4, '相場上の意味'], [5, '時刻・出典'], [6, '次時間帯への引き継ぎ']].forEach(function(field) {
      if (!cells[field[0]] || !cellSignals[field[0]].test(cells[field[0]])) {
        issues.push(canonical + ': ' + field[1] + 'が説明文になっていません');
      }
    });
    if (!/\d{1,2}:\d{2}/.test(cells[1]) && cells[1].indexOf('観測制約') < 0) {
      issues.push(canonical + ': JST時間範囲または観測制約がありません');
    }
    var timedText = cells[2] + ' ' + cells[3];
    if (/\d{1,2}:\d{2}/.test(timedText) && !/(?:発生|発表|報道|市場観測|観測)時刻/.test(cells[5])) {
      issues.push(canonical + ': 出来事/市場反応時刻と根拠欄の時刻区分が不明です');
    }
    if (timeText === '21:00') {
      var match;
      timePattern.lastIndex = 0;
      while ((match = timePattern.exec(timedText)) !== null) {
        var parts = match[0].split(':').map(Number);
        var aroundTime = timedText.slice(Math.max(0, match.index - 22), match.index + match[0].length + 28);
        var planned = /(?:予定|予想|未発表|今後|これから|控え|待機|見込み|翌日|明日)/.test(aroundTime);
        var historical = /(?:前日|昨日|昨夜|先週|過去)/.test(aroundTime);
        if (parts[0] * 60 + parts[1] > 1260 && !planned && !historical) {
          issues.push('21:00時点より後の出来事を発生済みとして記載しています');
        }
      }
    }
  }
  slotPeriods.forEach(function(period) {
    if (!found[period[0]]) issues.push('必須時間帯が不足しています: ' + period[0]);
  });
  return issues;
}

/**
 * In real morning reports, a market datum is a labeled numeric line,
 * not a stand-alone heading. Match within the explicit data section only.
 * Never infer values from the broader news or commentary paragraphs.
 */
function marketReportMorningHasSourceValue_(source, rule) {
  const text = String(source || '').replace(/\r/g, '');
  const start = text.search(/^\s*(?:\d+[．.、)]\s*)?(?:前営業日終値一覧と基準時刻|主要市場データ|主要市場の確認値)/m);
  if (start < 0) return false;
  const rest = text.slice(start);
  const stop = rest.search(/\n\s*\d+[．.、)]\s*(?:昨夜|市場の動き|前回|今日の相場テーマ|重要ニュース)/);
  const section = stop > 0 ? rest.slice(0, stop) : rest;
  const labels = {
    'Russell 2000': /Russell\s*2000/i,
    '日経225先物（大阪取引所）': /大阪取引所日経225先物(?:\d+月限)?/,
    '金': /COMEX金先物(?:\d+月限)?/,
    '日経225 PBR': /PBR\s*[：:]?\s*\d/i,
    '日経225予想EPS': /予想EPS\s*[：:]?\s*\d/i,
    '200日移動平均乖離率': /200日乖離率\s*[：:]?\s*[+\-]?\d/,
    '東証プライム売買代金': /売買代金\s*[\d,.]+/,
    '東証プライム売買高': /売買高\s*[\d,.]+/,
    '値上がり銘柄数': /値上がり銘柄\s*[\d,.]+/,
    '値下がり銘柄数': /値下がり\s*[\d,.]+/,
    '騰落レシオ': /騰落レシオ\s*[\d,.]+/
  };
  return section.split('\n').some(function(raw) {
    const line = raw.trim();
    // Prime breadth is legitimately written as one numeric sentence without
    // a colon in the original 2026-10-13 08:00 Google document.
    if (/^東証プライム値上がり銘柄\s*[\d,]+/.test(line)) {
      const primeEvidence = {
        '値上がり銘柄数': /値上がり銘柄\s*[\d,]+/,
        '値下がり銘柄数': /値下がり\s*[\d,]+/,
        '騰落レシオ': /騰落レシオ\s*[\d.]+/,
        '東証プライム売買代金': /売買代金\s*[\d,]+/,
        '東証プライム売買高': /売買高\s*[\d,]+/
      };
      if (primeEvidence[rule.label]) return primeEvidence[rule.label].test(line);
    }
    const colon = line.search(/[：:]/);
    if (colon < 1) return false;
    const label = line.slice(0, colon).trim();
    const value = line.slice(colon + 1).trim();
    if (!value || !/(?:\d|取得不能|休場)/.test(value)) return false;
    if (rule.pattern.test(label)) return true;
    // Explicit compound numeric lines used in the verified source documents.
    const compound = {
      '日経225 PBR': /^日経225予想PER$/,
      '日経225予想EPS': /^日経225予想PER$/,
      '25日移動平均乖離率': /^日経225・25日移動平均乖離率$/,
      '200日移動平均乖離率': /^日経225・25日移動平均乖離率$/,
      '東証プライム売買代金': /^東証プライム値上がり銘柄/,
      '東証プライム売買高': /^東証プライム値上がり銘柄/,
      '値上がり銘柄数': /^東証プライム値上がり銘柄/,
      '値下がり銘柄数': /^東証プライム値上がり銘柄/,
      '騰落レシオ': /^東証プライム値上がり銘柄/
    };
    const namePattern = compound[rule.label] || labels[rule.label];
    if (!namePattern || !namePattern.test(label)) return false;
    const evidence = labels[rule.label];
    return !evidence || evidence.test(line);
  });
}

function marketReportPrePublishHeadingLines_(source) {
  const headings = [];
  String(source || '').split('\n').forEach(function(raw) {
    const line = String(raw || '').trim();
    const normalized = marketReportPrePublishNormalizeHeading_(line);
    if (normalized) headings.push(normalized);
    // Only numbered/explicit heading lines are eligible for compound aliases.
    // Never infer missing report sections from incidental prose mentions.
    if (!/^(?:\d{1,2}[．.、)）]|【|[■◆◇●▶])/.test(line)) return;
    const aliases = [
      [/^主要市場データ(?:（.*）)?$/, ['主要市場データ']],
      [/^前営業日終値一覧と基準時刻$/, ['主要市場データ']],
      [/^材料と値動きの整合性・(?:今日の)?主導市場$/, ['材料と値動きの整合性', '今日の主導市場']],
      [/^重要ニュースと市場への影響$/, ['重要ニュース']],
      [/^金利・為替・(?:市場心理|センチメント)$/, ['金利・為替']],
      [/^需給・ポジション(?:・SQ(?:・.*)?|、SQ／オプション)$/, ['需給・ポジション']],
      [/^(?:主要)?6市場の(?:短期)?見通し(?:（.*）)?$/, ['6市場の見通し']],
      [/^今後のイベント$/, ['今後の予定']],
      [/^代替シナリオ(?:と|・)崩れる条件$/, ['代替シナリオ', '崩れる条件', 'リスク管理']],
      [/^結論・リスク管理$/, ['結論', 'リスク管理']],
      [/^結論・クロスチェック$/, ['結論']],
      [/^前回21:00からの変化$/, ['21:00からの変化']],
      [/^12:00への引き継ぎ・リスク管理$/, ['12:00への引き継ぎ', 'リスク管理']]
    ];
    aliases.forEach(function(entry) {
      if (entry[0].test(normalized)) headings.push.apply(headings, entry[1]);
    });
  });
  return headings;
}

function marketReportPrePublishNormalizeHeading_(line) {
  return String(line || '')
    .trim()
    .replace(/[（(][^）)]*[）)]?\s*$/, '')
    .replace(/^【|】$/g, '')
    .replace(/^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]\s*/, '')
    .replace(/^\s*(?:第?\d{1,2}|[一二三四五六七八九十]+)\s*[．.、)）]\s*/, '')
    .replace(/^[■◆◇●▶]\s*/, '')
    .trim();
}

function marketReportPrePublishHasHeading_(headings, pattern) {
  return headings.some(function(line) { return pattern.test(line); });
}

function testLatestMarketReportPrePublishValidation() {
  if (typeof findLatestMarketReportDocForAutoPublish_ !== 'function') {
    throw new Error('findLatestMarketReportDocForAutoPublish_ が見つかりません。');
  }
  if (typeof buildWebReportFromGoogleDoc_ !== 'function') {
    throw new Error('buildWebReportFromGoogleDoc_ が見つかりません。');
  }

  var file = findLatestMarketReportDocForAutoPublish_();
  if (!file) throw new Error('検証対象のマーケットレポートGoogle Docsが見つかりません。');

  var report = buildWebReportFromGoogleDoc_(file);
  var expectedHour = Number(String(report.time || '').slice(0, 2));
  var result = validateMarketReportBeforePublish_(report, expectedHour);

  SpreadsheetApp.getUi().alert(
    '公開前検証に合格しました。\n\n' +
    'ファイル名: ' + file.getName() + '\n' +
    'レポート: ' + report.date + ' ' + report.time + '\n' +
    '警告数: ' + result.warnings.length +
    (result.warnings.length ? '\n\n' + result.warnings.join('\n') : '')
  );
  return result;
}

function marketReportPrePublishIsBlank_(value) {
  if (value === null || typeof value === 'undefined') return true;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value).length === 0;
  return String(value).trim() === '';
}

function marketReportPrePublishIsUnavailable_(value) {
  if (Array.isArray(value)) {
    return value.some(function(item) { return marketReportPrePublishIsUnavailable_(item); });
  }
  var text = String(value || '').trim();
  return MARKET_REPORT_PREPUBLISH_CONFIG.unavailablePatterns.some(function(pattern) {
    return pattern.test(text);
  });
}

