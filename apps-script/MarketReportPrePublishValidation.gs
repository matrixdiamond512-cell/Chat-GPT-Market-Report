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
    { label: '主要市場データ', pattern: /^(?:主要市場データ|主要市場まとめ|主要価格)$/ },
    { label: '今日の相場テーマ', pattern: /^(?:今日の相場テーマ|今日のテーマ)$/ },
    { label: '材料と値動きの整合性', pattern: /^材料.*値動き.*整合性$|^材料と値動きの整合性$/ },
    { label: '主導市場', pattern: /^(?:今日の)?主導市場$/ },
    { label: '重要ニュース', pattern: /^(?:重要ニュース|重要材料)$/ },
    { label: '金利', pattern: /^(?:金利|金利分析|金利・為替|金利・為替の連動)$/ },
    { label: 'クロスアセット資金フロー', pattern: /^(?:クロスアセット|クロスアセット資金フロー|資金フロー)$/ },
    { label: '需給・ポジション', pattern: /^(?:需給・ポジション|需給・ポジショニング|ポジションの偏り)$/ },
    { label: '重要イベント', pattern: /^(?:今後の)?重要イベント$|^今後の予定$/ },
    { label: '個別市場見通し', pattern: /^(?:6市場の(?:個別)?見通し|個別市場見通し|個別見通し)$/ },
    { label: 'メインシナリオ', pattern: /^(?:メインシナリオ|基本シナリオ)$/ },
    { label: '代替シナリオ', pattern: /^(?:代替シナリオ|別シナリオ)$/ },
    { label: 'シナリオが崩れる条件', pattern: /^(?:シナリオが)?崩れる条件$/ },
    { label: 'リスク管理', pattern: /^(?:リスク管理|主なリスク|リスク要因)$/ },
    { label: '結論', pattern: /^(?:結論|まとめ|最終判断)$/ }
  ],
  slotRules: {
    '08:00': {
      changeLabel: '前回からの変化',
      changePattern: /^(?:前回からの(?:主な)?変化|21:00からの変化|前日21:00からの変化|NY市場からの変化|前営業日からの変化)$/,
      handoverLabel: '東京時間への引き継ぎ',
      handoverPattern: /^(?:東京時間|東京市場|次の時間帯)への引き継ぎ$/
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
      handoverPattern: /^(?:NY時間|NY市場|次の時間帯)への引き継ぎ$/
    },
    '21:00': {
      changeLabel: '16:00からの変化',
      changePattern: /^(?:16:00|16時|前回)からの(?:主な)?変化$/,
      handoverLabel: 'NY時間・翌東京時間への引き継ぎ',
      handoverPattern: /^(?:NY時間|NY市場|翌東京時間|次の時間帯)への引き継ぎ$/
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

  var titleMatch = String(report.title || '').match(/^マーケットレポート｜(\d{4})\/(\d{2})\/(\d{2})（.）(\d{2}):(\d{2})$/);
  if (!titleMatch) {
    errors.push('タイトル形式不正: ' + String(report.title || ''));
  } else {
    var titleDate = titleMatch[1] + '-' + titleMatch[2] + '-' + titleMatch[3];
    var titleTime = titleMatch[4] + ':' + titleMatch[5];
    if (titleDate !== String(report.date || '') || titleTime !== String(report.time || '')) {
      errors.push('タイトルとdate/timeが不一致です。');
    }
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
    var normalizedLines = source.split('\n').map(function(line) {
      return marketReportPrePublishNormalizeHeading_(line);
    }).filter(Boolean);
    MARKET_REPORT_PREPUBLISH_CONFIG.morningRequiredLabels.forEach(function(rule) {
      if (!normalizedLines.some(function(line) { return rule.pattern.test(line); })) {
        errors.push('08:00 主要市場データ不足: ' + rule.label);
      }
    });
  }

  var headingOnly = /^(?:金利|金利分析|6市場の(?:個別)?見通し|個別市場見通し|結論|最終判断|シナリオが崩れる条件|東京時間への引き継ぎ|欧州時間への引き継ぎ|NY時間への引き継ぎ|翌東京時間への引き継ぎ)$/;
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

  var embeddedHeading = /(?:^|[。\s])(?:メインシナリオ|代替シナリオ|シナリオが崩れる条件|東京時間への引き継ぎ|欧州時間への引き継ぎ|NY時間への引き継ぎ|翌東京時間への引き継ぎ|結論|最終判断)(?:\s|$)/;
  ['mainScenario', 'alternativeScenario', 'breakConditions'].forEach(function(field) {
    if (embeddedHeading.test(String(report[field] || ''))) {
      errors.push(timeText + ' ' + field + ': 複数セクションが1フィールドへ連結されています。');
    }
  });
}

function marketReportPrePublishHeadingLines_(source) {
  return String(source || '').split('\n').map(function(line) {
    return marketReportPrePublishNormalizeHeading_(line);
  }).filter(Boolean);
}

function marketReportPrePublishNormalizeHeading_(line) {
  return String(line || '')
    .trim()
    .replace(/^【|】$/g, '')
    .replace(/^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]\s*/, '')
    .replace(/^\s*(?:第?\d{1,2}|[一二三四五六七八九十]+)\s*[．.、:：)）]\s*/, '')
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
