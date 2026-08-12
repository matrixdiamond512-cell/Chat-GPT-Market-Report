var MARKET_REPORT_PREPUBLISH_CONFIG = {
  requiredMarkets: ['金', '原油', '日経225先物', 'USD/JPY', 'EUR/USD', 'BTCUSD'],
  requiredReportFields: [
    'date', 'time', 'title', 'theme', 'leadingMarket', 'markets',
    'mainScenario', 'alternativeScenario', 'breakConditions', 'riskManagement'
  ],
  requiredMarketFields: [
    'name', 'direction'
  ],
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
  manual21EnforceFrom: '2026-08-13',
  required21Fields: [
    'changes', 'consistency', 'news', 'crossAssetFlow', 'positioning', 'events', 'handover'
  ],
  required21Sections: [
    { label: '主要市場データ', pattern: /^\s*(?:\d+[．.]\s*)?主要市場データ(?:（.*）)?\s*$/m },
    { label: '今日の相場テーマ', pattern: /^\s*(?:\d+[．.]\s*)?今日の相場テーマ\s*$/m },
    { label: '16:00からの変化', pattern: /^\s*(?:\d+[．.]\s*)?(?:16:00|16時|前回)からの(?:主な)?変化\s*$/m },
    { label: '材料と値動きの整合性', pattern: /^\s*(?:\d+[．.]\s*)?材料と値動きの整合性\s*$/m },
    { label: '主導市場', pattern: /^\s*(?:\d+[．.]\s*)?(?:今日の)?主導市場\s*$/m },
    { label: '重要ニュース', pattern: /^\s*(?:\d+[．.]\s*)?重要ニュース\s*$/m },
    { label: 'クロスアセット資金フロー', pattern: /^\s*(?:\d+[．.]\s*)?クロスアセット(?:資金フロー)?\s*$/m },
    { label: '需給・ポジション', pattern: /^\s*(?:\d+[．.]\s*)?需給・ポジション\s*$/m },
    { label: '重要イベント', pattern: /^\s*(?:\d+[．.]\s*)?(?:今後の)?重要イベント\s*$/m },
    { label: '6市場の見通し', pattern: /^\s*(?:\d+[．.]\s*)?6市場の(?:個別)?見通し\s*$/m },
    { label: 'メインシナリオ', pattern: /^\s*(?:\d+[．.]\s*)?メインシナリオ\s*$/m },
    { label: '代替シナリオ', pattern: /^\s*(?:\d+[．.]\s*)?代替シナリオ\s*$/m },
    { label: 'シナリオが崩れる条件', pattern: /^\s*(?:\d+[．.]\s*)?(?:シナリオが)?崩れる条件\s*$/m },
    { label: '引き継ぎ', pattern: /^\s*(?:\d+[．.]\s*)?(?:NY時間|次の時間帯|翌東京時間)への引き継ぎ\s*$/m }
  ],
  required21MarketRows: [
    { label: '金', pattern: /^\s*\|?\s*(?:金|ゴールド|COMEX金先物)(?:[・（|：:].*)?$/mi },
    { label: '原油', pattern: /^\s*\|?\s*(?:WTI原油|原油)(?:[（|：:].*)?$/mi },
    { label: '日経225先物', pattern: /^\s*\|?\s*日経225先物(?:（大阪取引所）)?\s*[|：:].*$/mi },
    { label: 'USD/JPY', pattern: /^\s*\|?\s*(?:USD\/JPY|USDJPY|ドル円)\s*[|：:].*$/mi },
    { label: 'EUR/USD', pattern: /^\s*\|?\s*(?:EUR\/USD|EURUSD|ユーロドル)\s*[|：:].*$/mi },
    { label: 'BTCUSD', pattern: /^\s*\|?\s*(?:BTCUSD|BTC\/USD|ビットコイン)\s*[|：:].*$/mi }
  ],
  forbidden21PublicPatterns: [
    { label: 'verified', pattern: /\bverified\b/i },
    { label: '未確認', pattern: /未確認/ }
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

  if (!/^(07|09|12|16|21):00$/.test(String(report.time || ''))) {
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

  if (!Array.isArray(report.markets)) {
    errors.push('marketsは配列である必要があります。');
  } else {
    var byName = {};
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

  validate21MarketReportManualContract_(report, errors);

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

function validate21MarketReportManualContract_(report, errors) {
  var dateText = String(report.date || '');
  var timeText = String(report.time || '');
  if (timeText !== '21:00' || dateText < MARKET_REPORT_PREPUBLISH_CONFIG.manual21EnforceFrom) return;

  MARKET_REPORT_PREPUBLISH_CONFIG.required21Fields.forEach(function(field) {
    if (!Object.prototype.hasOwnProperty.call(report, field) || marketReportPrePublishIsBlank_(report[field])) {
      errors.push('21:00 SOP必須項目不足/空欄: ' + field);
    }
  });

  var source = String(report.fullText || report.rawText || report.body || '').replace(/\r/g, '').trim();
  if (!source) {
    errors.push('21:00 SOPでは公開本文 fullText/rawText/body が必須です。');
    return;
  }

  MARKET_REPORT_PREPUBLISH_CONFIG.forbidden21PublicPatterns.forEach(function(rule) {
    if (rule.pattern.test(source)) {
      errors.push('公開本文に内部確認用語「' + rule.label + '」が残っています。');
    }
  });

  MARKET_REPORT_PREPUBLISH_CONFIG.required21Sections.forEach(function(rule) {
    if (!rule.pattern.test(source)) {
      errors.push('21:00 SOP必須セクション不足: ' + rule.label);
    }
  });

  MARKET_REPORT_PREPUBLISH_CONFIG.required21MarketRows.forEach(function(rule) {
    if (!rule.pattern.test(source)) {
      errors.push('主要市場データで表変換可能な市場行が不足: ' + rule.label);
    }
  });

  var headingOnly = /^(?:金利|6市場の(?:個別)?見通し|結論|シナリオが崩れる条件|翌東京時間への引き継ぎ)$/;
  ['changes', 'consistency', 'news', 'crossAssetFlow', 'positioning', 'events', 'handover', 'riskManagement'].forEach(function(field) {
    var value = report[field];
    var items = Array.isArray(value) ? value : [value];
    items.forEach(function(item) {
      var text = String(item || '').trim();
      if (headingOnly.test(text)) {
        errors.push(field + ': 見出しが本文項目へ混入しています: ' + text);
      }
    });
  });

  var embeddedHeading = /(?:^|[。\s])(?:シナリオが崩れる条件|翌東京時間への引き継ぎ|NY時間への引き継ぎ|結論)(?:\s|$)/;
  ['mainScenario', 'alternativeScenario', 'breakConditions'].forEach(function(field) {
    if (embeddedHeading.test(String(report[field] || ''))) {
      errors.push(field + ': 複数セクションが1フィールドへ連結されています。');
    }
  });
}

function testLatestMarketReportPrePublishValidation() {
  if (typeof findLatestMarketReportDocForAutoPublish_ !== 'function') {
    throw new Error('findLatestMarketReportDocForAutoPublish_ が見つかりません。');
  }
  if (typeof buildWebReportFromGoogleDoc_ !== 'function') {
    throw new Error('buildWebReportFromGoogleDoc_ が見つかりません。');
  }

  var file = findLatestMarketReportDocForAutoPublish_();
  if (!file) {
    throw new Error('検証対象のマーケットレポートGoogle Docsが見つかりません。');
  }

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
