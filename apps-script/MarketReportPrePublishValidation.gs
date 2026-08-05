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
