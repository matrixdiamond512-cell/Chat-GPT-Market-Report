var EVENTS_JSON_CONFIG = {
  targetPath: 'data/events.json',
  reportsPath: 'reports.json',
  timezone: 'Asia/Tokyo',
  maxEvents: 260,
  lastResultProperty: 'EVENTS_JSON_LAST_RESULT'
};

function previewEventsJson() {
  var reports = eventsFetchReportsJson_();
  var current = eventsGetGitHubJson_(EVENTS_JSON_CONFIG.targetPath);
  var json = buildEventsJsonFromReports_(reports, current.data);
  var html = HtmlService.createHtmlOutput(
    '<pre style="white-space:pre-wrap;font-size:12px">' + eventsEscapeHtml_(json) + '</pre>'
  ).setWidth(920).setHeight(700);
  SpreadsheetApp.getUi().showModalDialog(html, '重要イベントJSONプレビュー');
  return JSON.parse(json);
}

function syncEventsJsonToGitHub() {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var reports = eventsFetchReportsJson_();
    var result = syncEventsJsonToGitHubFromReports_(reports);
    eventsAlert_(
      '重要イベントJSONをGitHubへ反映しました。\n' +
      '対象: ' + result.latestKey + '\n' +
      '日数: ' + result.dayCount + '\n' +
      'イベント数: ' + result.eventCount + '\n' +
      'コミット: ' + result.commitSha
    );
    return result;
  } catch (error) {
    eventsSaveResult_({ ok: false, error: error.message });
    eventsAlert_('重要イベントJSONを反映できませんでした。\n' + error.message);
    throw error;
  } finally {
    lock.releaseLock();
  }
}

function syncEventsJsonToGitHubFromReports_(reports) {
  var current = eventsGetGitHubJson_(EVENTS_JSON_CONFIG.targetPath);
  var payload = eventsBuildPayloadFromReports_(reports, current.data);
  var json = JSON.stringify(payload, null, 2) + '\n';
  var result = eventsPutGitHubJson_(
    EVENTS_JSON_CONFIG.targetPath,
    json,
    current.sha,
    'Update important events JSON history'
  );
  return eventsSaveResult_({
    ok: true,
    targetPath: EVENTS_JSON_CONFIG.targetPath,
    latestKey: payload.currentReportKey,
    dayCount: payload.days.length,
    eventCount: payload.events.length,
    commitSha: result.commit.sha
  });
}

function buildEventsJsonFromReports_(reports, existingPayload) {
  return JSON.stringify(eventsBuildPayloadFromReports_(reports, existingPayload), null, 2) + '\n';
}

function eventsBuildPayloadFromReports_(reports, existingPayload) {
  var normalizedReports = eventsNormalizeReports_(reports);
  if (!normalizedReports.length) throw new Error('重要イベントに使えるマーケットレポートがありません。');

  var latest = normalizedReports[0];
  var generatedAt = eventsIsoJst_(new Date());
  var existingEvents = eventsNormalizeExistingEvents_(existingPayload);
  var extractedEvents = [];

  normalizedReports.slice(0, 120).forEach(function(report) {
    extractedEvents = extractedEvents.concat(eventsExtractFromReport_(report));
  });

  var mergedById = {};
  existingEvents.forEach(function(event) {
    var prepared = eventsNormalizeStoredEvent_(event);
    if (prepared && prepared.id) mergedById[prepared.id] = prepared;
  });

  extractedEvents.forEach(function(event) {
    var prepared = eventsNormalizeStoredEvent_(event);
    if (!prepared) return;
    if (!prepared.id) prepared.id = eventsStableId_(prepared);
    mergedById[prepared.id] = eventsMergeEvent_(mergedById[prepared.id], prepared);
  });

  var eventList = Object.keys(mergedById).map(function(id) {
    return eventsRefreshStatus_(mergedById[id], generatedAt);
  }).filter(function(event) {
    return event && event.date && event.title && !eventsIsGenericEventTitle_(event.title);
  }).sort(eventsCompareEventDesc_).slice(0, EVENTS_JSON_CONFIG.maxEvents);

  var days = eventsBuildDays_(eventList);
  var latestKey = latest.date + ' ' + latest.time;
  return {
    schemaVersion: '1.1.0',
    pageId: 'events',
    generatedAt: generatedAt,
    publishedAt: generatedAt,
    dataAsOf: latest.date + 'T' + latest.time + ':00+09:00',
    status: 'ok',
    mode: 'daily_history',
    currentReportKey: latestKey,
    retention: {
      mode: 'append_and_merge',
      maxEvents: EVENTS_JSON_CONFIG.maxEvents,
      preserveResultFields: true
    },
    days: days,
    events: eventList,
    sources: [
      {
        id: 'MARKET_REPORTS_JSON',
        name: 'マーケットレポート本文の構造化JSON',
        path: EVENTS_JSON_CONFIG.reportsPath,
        asOf: latestKey,
        status: 'ok',
        note: '重要イベントは本文から抽出し、予想・結果・説明は履歴として保存します。'
      },
      {
        id: 'MANUAL_RESULT_FIELDS',
        name: '市場予想・結果・発表後説明の補完欄',
        type: 'manual',
        status: 'available',
        note: '既存JSONに入力済みの結果、比較、説明は新しい抽出で空欄上書きしません。'
      }
    ],
    errors: []
  };
}

function eventsExtractFromReport_(report) {
  var rows = [];
  var values = []
    .concat(eventsArray_(report.events))
    .concat(eventsArray_(report.importantEvents))
    .concat(eventsArray_(report.calendarEvents));

  values.forEach(function(item) {
    if (item && typeof item === 'object') {
      var normalized = eventsNormalizeEventObject_(item, report);
      if (normalized) rows.push(normalized);
      return;
    }

    var chunks = eventsExpandEventTexts_(String(item || ''), report);
    chunks.forEach(function(text) {
      var event = eventsBuildEventFromText_(text, report, rows);
      if (event) rows.push(event);
    });
  });

  return eventsUniqueEvents_(rows);
}

function eventsNormalizeEventObject_(item, report) {
  var title = eventsCleanText_(item.title || item.name || item.event || item.text || '', 90);
  var datetime = String(item.datetimeJst || item.datetime || '');
  var date = String(item.date || datetime.slice(0, 10) || report.date || '').trim();
  var time = eventsNormalizeTime_(item.time || datetime.slice(11, 16) || '');
  var timingLabel = eventsCleanText_(item.timingLabel || item.timing || item.when || '', 16);
  if (!title || !eventsIsDate_(date)) return null;

  return eventsWithDefaults_({
    id: item.id || '',
    date: date,
    time: time,
    datetimeJst: time ? date + 'T' + time + ':00+09:00' : '',
    timingLabel: time ? '' : timingLabel || '予定確認',
    country: eventsCleanText_(item.country || item.region || eventsCountryFromText_(title), 20),
    title: title,
    category: item.category || (time ? 'scheduled_event' : 'scheduled_check'),
    importance: eventsImportanceNumber_(item.importance || title),
    forecast: eventsCleanText_(item.forecast || item.estimate || item.consensus || '手入力待ち', 60),
    previous: eventsCleanText_(item.previous || item.prev || '手入力待ち', 60),
    actual: eventsCleanText_(item.actual || item.result || '', 60),
    resultComparison: eventsCleanText_(item.resultComparison || item.surprise || '', 80),
    resultExplanation: eventsCleanText_(item.resultExplanation || item.marketInterpretation || '', 180),
    status: item.status || '',
    affectedMarkets: eventsArray_(item.affectedMarkets || item.affected || eventsAffectedMarkets_(title)),
    reason: eventsCleanText_(item.reason || item.sourceNote || '重要イベント専用JSONから表示', 160),
    sourceType: item.sourceType || 'structured_event',
    sourceReportKey: report.date + ' ' + report.time,
    sourceNote: item.sourceNote || 'マーケットレポート本文から抽出',
    watchPoints: eventsArray_(item.watchPoints || eventsWatchPoints_(title)),
    postReleaseReactions: eventsArray_(item.postReleaseReactions || item.reactions),
    comparison: eventsArray_(item.comparison),
    conclusion: item.conclusion || null
  });
}

function eventsBuildEventFromText_(text, report, rows) {
  text = eventsCleanText_(text, 360);
  if (!text || !eventsIsEventText_(text)) return null;

  var detailTarget = eventsApplyDetailToExisting_(text, rows);
  if (detailTarget) return null;

  var time = eventsNormalizeTime_(text);
  var date = eventsDateFromText_(text, report.date);
  var title = eventsTitleFromText_(text);
  var category = time ? 'scheduled_event' : eventsCategoryFromText_(text);
  var timingLabel = time ? '' : eventsTimingLabelFromText_(text);
  if (!title || !eventsIsDate_(date)) return null;

  return eventsWithDefaults_({
    date: date,
    time: time,
    datetimeJst: time ? date + 'T' + time + ':00+09:00' : '',
    timingLabel: timingLabel,
    country: eventsCountryFromText_(text),
    title: title,
    category: category,
    importance: eventsImportanceNumber_(text),
    forecast: '手入力待ち',
    previous: '手入力待ち',
    actual: '',
    resultComparison: '',
    resultExplanation: '',
    status: '',
    affectedMarkets: eventsAffectedMarkets_(text),
    reason: eventsReasonFromText_(text),
    sourceType: 'market_report_extraction',
    sourceReportKey: report.date + ' ' + report.time,
    sourceNote: 'マーケットレポート本文から抽出',
    watchPoints: eventsWatchPoints_(text),
    postReleaseReactions: [],
    comparison: [],
    conclusion: null
  });
}

function eventsWithDefaults_(event) {
  event.id = event.id || eventsStableId_(event);
  event.forecast = eventsCleanText_(event.forecast || '手入力待ち', 60);
  event.previous = eventsCleanText_(event.previous || '手入力待ち', 60);
  event.actual = eventsCleanText_(event.actual || '', 60);
  event.resultComparison = eventsCleanText_(event.resultComparison || '', 80);
  event.resultExplanation = eventsCleanText_(event.resultExplanation || '', 180);
  event.affectedMarkets = eventsArray_(event.affectedMarkets).filter(Boolean).slice(0, 8);
  event.watchPoints = eventsArray_(event.watchPoints).filter(Boolean).slice(0, 6);
  event.postReleaseReactions = eventsArray_(event.postReleaseReactions);
  event.comparison = eventsArray_(event.comparison);
  event.isTimed = Boolean(event.time);
  event.isImportantEvent = event.category !== 'monitoring_headline';
  return eventsRefreshStatus_(event, eventsIsoJst_(new Date()));
}

function eventsMergeEvent_(existing, incoming) {
  if (!existing) return incoming;
  var merged = {};
  var key;
  for (key in existing) merged[key] = existing[key];
  for (key in incoming) {
    if (!eventsIsBlank_(incoming[key])) merged[key] = incoming[key];
  }

  [
    'forecast',
    'previous',
    'actual',
    'resultComparison',
    'resultExplanation',
    'marketReaction',
    'resultSavedAt',
    'resultSource',
    'resultUpdatedAt'
  ].forEach(function(field) {
    if (!eventsIsBlank_(existing[field]) && eventsIsBlank_(incoming[field])) merged[field] = existing[field];
  });

  ['postReleaseReactions', 'comparison'].forEach(function(field) {
    if (Array.isArray(existing[field]) && existing[field].length && (!Array.isArray(incoming[field]) || !incoming[field].length)) {
      merged[field] = existing[field];
    }
  });

  if (existing.conclusion && !incoming.conclusion) merged.conclusion = existing.conclusion;
  merged.updatedAt = incoming.updatedAt || eventsIsoJst_(new Date());
  return merged;
}

function eventsRefreshStatus_(event, generatedAt) {
  if (!event) return event;
  if (!event.createdAt) event.createdAt = generatedAt;
  event.updatedAt = generatedAt;
  if (!eventsIsBlank_(event.actual) || !eventsIsBlank_(event.resultComparison) || !eventsIsBlank_(event.resultExplanation)) {
    event.status = 'released';
  } else if (event.category === 'monitoring_headline') {
    event.status = 'monitoring';
  } else if (event.time && eventsEventMillis_(event) < new Date().getTime()) {
    event.status = 'needs_result';
  } else if (!event.time) {
    event.status = 'scheduled_check';
  } else {
    event.status = 'scheduled';
  }
  return event;
}

function eventsBuildDays_(events) {
  var byDate = {};
  events.forEach(function(event) {
    if (!byDate[event.date]) {
      byDate[event.date] = { date: event.date, label: eventsDateLabel_(event.date), eventCount: 0, releasedCount: 0, needsResultCount: 0 };
    }
    byDate[event.date].eventCount += 1;
    if (event.status === 'released') byDate[event.date].releasedCount += 1;
    if (event.status === 'needs_result') byDate[event.date].needsResultCount += 1;
  });
  return Object.keys(byDate).sort().reverse().map(function(date) {
    return byDate[date];
  });
}

function eventsNormalizeExistingEvents_(payload) {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.events)) return payload.events;
  return [];
}

function eventsNormalizeStoredEvent_(event) {
  if (!event || typeof event !== 'object') return null;
  var date = String(event.date || String(event.datetimeJst || '').slice(0, 10) || '').trim();
  var time = eventsNormalizeTime_(event.time || String(event.datetimeJst || '').slice(11, 16) || '');
  var title = eventsCleanText_(event.title || event.name || event.event || '', 90);
  if (!eventsIsDate_(date) || !title) return null;
  var prepared = {};
  var key;
  for (key in event) prepared[key] = event[key];
  prepared.date = date;
  prepared.time = time;
  prepared.datetimeJst = time ? date + 'T' + time + ':00+09:00' : '';
  prepared.timingLabel = time ? '' : eventsCleanText_(event.timingLabel || event.time || '予定確認', 16);
  prepared.title = title;
  prepared.country = eventsCleanText_(event.country || event.region || eventsCountryFromText_(title), 20);
  prepared.importance = eventsImportanceNumber_(event.importance || title);
  prepared.category = event.category || (time ? 'scheduled_event' : 'scheduled_check');
  prepared.affectedMarkets = eventsArray_(event.affectedMarkets || event.affected || eventsAffectedMarkets_(title));
  prepared.watchPoints = eventsArray_(event.watchPoints || eventsWatchPoints_(title));
  prepared.postReleaseReactions = eventsArray_(event.postReleaseReactions || event.reactions);
  prepared.comparison = eventsArray_(event.comparison);
  prepared.id = event.id || eventsStableId_(prepared);
  return prepared;
}

function eventsExpandEventTexts_(value, report) {
  var base = eventsSplitEventText_(value);
  var expanded = [];
  base.forEach(function(text) {
    var additions = eventsSpecificEventExpansions_(text, report);
    if (additions.length) {
      expanded = expanded.concat(additions);
    } else {
      expanded.push(text);
    }
  });
  return expanded;
}

function eventsSpecificEventExpansions_(text, report) {
  var rows = [];
  var source = String(text || '');
  if (/水曜日/.test(source) && /ADP/.test(source) && /雇用統計/.test(source)) {
    rows.push(eventsNextWeekdayDate_(report.date, 3) + ' 予定確認 ADP雇用統計');
  }
  if (/金曜日/.test(source) && /米雇用統計|雇用統計/.test(source)) {
    rows.push(eventsNextWeekdayDate_(report.date, 5) + ' 予定確認 米雇用統計');
  }
  if (/決算|AMD|Caterpillar|McDonald|McDonald’s|Pfizer|Eli Lilly|Microsoft|Meta|Apple|Amazon/.test(source)) {
    ['AMD', 'Caterpillar', 'McDonald', 'McDonald’s', 'Pfizer', 'Eli Lilly', 'Microsoft', 'Meta', 'Apple', 'Amazon'].forEach(function(name) {
      if (source.indexOf(name) !== -1) rows.push(report.date + ' 予定確認 ' + name.replace('McDonald’s', 'McDonald') + '決算');
    });
  }
  return rows;
}

function eventsApplyDetailToExisting_(text, rows) {
  if (/JOLTS求人件数/.test(text) && /前回/.test(text)) {
    for (var i = rows.length - 1; i >= 0; i -= 1) {
      if (/JOLTS求人件数/.test(rows[i].title || '')) {
        rows[i].reason = eventsCleanText_(text, 160);
        var previous = String(text).match(/前回\s*([0-9.,]+万人?)/);
        if (previous) rows[i].previous = previous[1];
        return true;
      }
    }
  }
  return false;
}

function eventsSplitEventText_(value) {
  var text = eventsCleanText_(value, 1200).replace(/^今後の重要イベント[:：\s]*/, '').replace(/。$/, '');
  if (!text) return [];
  var numbered = text
    .replace(/(?:^|\s)(\d+[.)．]|[①-⑳])/g, '\n$1')
    .split(/\n+/)
    .map(function(item) { return item.trim(); })
    .filter(Boolean);
  var chunks = numbered.length > 1 ? numbered : [text];
  var result = [];
  chunks.forEach(function(item) {
    if (item.length >= 48 && /、/.test(item)) {
      result = result.concat(item.split(/、/));
    } else {
      result.push(item);
    }
  });
  return result
    .map(function(item) { return item.replace(/[。,\s]+$/, '').trim(); })
    .filter(function(item) { return item.length >= 2; });
}

function eventsIsEventText_(item) {
  if (/今日の相場テーマ|6市場の見通し|メインシナリオ|代替シナリオ|総合判断|最終判断/.test(item)) return false;
  if (/^(金|原油|WTI原油|日経225先物|USD\/JPY|EUR\/USD|BTCUSD|BTC)[:：\s]/.test(item)) return false;
  return /\b[0-2]?\d:[0-5]\d\b|FOMC|FRB|PCE|CPI|雇用|ISM|PMI|GDP|政策|会見|決算|在庫|OPEC|協議|ホルムズ|介入|日銀|指標|発言|観測|求人件数/.test(item);
}

function eventsIsGenericEventTitle_(title) {
  return /今週のADP雇用統計と米雇用統計|米求人件数など米労働市場指標/.test(String(title || ''));
}

function eventsBuildFromReportDateAndTime_(report) {
  return report.date + ' ' + report.time;
}

function eventsDateFromText_(text, fallbackDate) {
  var iso = String(text || '').match(/(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if (iso) return iso[1] + '-' + iso[2].padStart(2, '0') + '-' + iso[3].padStart(2, '0');
  var monthDay = String(text || '').match(/(?:^|[^\d])(\d{1,2})\/(\d{1,2})(?:[^\d]|$)/);
  if (monthDay && eventsIsDate_(fallbackDate)) {
    return fallbackDate.slice(0, 4) + '-' + monthDay[1].padStart(2, '0') + '-' + monthDay[2].padStart(2, '0');
  }
  return eventsIsDate_(fallbackDate) ? fallbackDate : '';
}

function eventsTitleFromText_(text) {
  return eventsCleanText_(String(text || '')
    .replace(/^\d{4}[-/]\d{1,2}[-/]\d{1,2}\s*/, '')
    .replace(/^\d{1,2}\/\d{1,2}\s*/, '')
    .replace(/^\b[0-2]?\d:[0-5]\d\s*/, '')
    .replace(/^(米国|日本|欧州|中国|複数)\s+/, '')
    .replace(/^随時\s*/, '')
    .replace(/^予定確認\s*/, ''), 90);
}

function eventsCategoryFromText_(text) {
  if (/随時|協議|ホルムズ|介入|発言|観測|OPEC/.test(text) && !eventsNormalizeTime_(text)) return 'monitoring_headline';
  return 'scheduled_check';
}

function eventsTimingLabelFromText_(text) {
  if (/随時|協議|ホルムズ|介入|発言|観測|OPEC/.test(text)) return '随時';
  return '予定確認';
}

function eventsReasonFromText_(text) {
  return eventsCleanText_(text, 160) || 'マーケットレポート本文から抽出';
}

function eventsCountryFromText_(text) {
  if (/米|FOMC|FRB|PCE|CPI|雇用|ISM|JOLTS|ADP|AMD|Caterpillar|McDonald|Pfizer/.test(text)) return '米国';
  if (/日銀|日本|東京|介入/.test(text)) return '日本';
  if (/ECB|ユーロ|欧州|ドイツ/.test(text)) return '欧州';
  if (/中国/.test(text)) return '中国';
  return '複数';
}

function eventsImportanceNumber_(value) {
  var numeric = Number(value);
  if (isFinite(numeric)) return Math.max(1, Math.min(3, Math.round(numeric)));
  var text = String(value || '');
  if (/FOMC|日銀|PCE|CPI|米雇用統計|政策|会見|JOLTS/.test(text)) return 3;
  if (/ADP|PMI|ISM|GDP|在庫|決算|求人件数|耐久財|貿易収支/.test(text)) return 2;
  return 1;
}

function eventsAffectedMarkets_(text) {
  if (/原油|OPEC|イラン|ホルムズ|在庫/.test(text)) return ['原油', '金', '米金利', 'USD/JPY', '株式'];
  if (/日銀|介入|円/.test(text)) return ['USD/JPY', '日経225先物', '日本株', '日本金利'];
  if (/FRB|FOMC|PCE|CPI|雇用|ISM|GDP|JOLTS|ADP|求人件数/.test(text)) return ['米金利', 'USD/JPY', '米国株', '日経225先物', '金'];
  if (/決算|AMD|Caterpillar|McDonald|Pfizer|Microsoft|Meta|Apple|Amazon/.test(text)) return ['米国株', '日経225先物', 'USD/JPY'];
  return ['USD/JPY', '株式', '金利'];
}

function eventsWatchPoints_(text) {
  if (/原油|OPEC|イラン|ホルムズ|在庫/.test(text)) return ['WTIの反応', '米10年債利回り', '金の安全資産需要', '株価指数先物'];
  if (/日銀|介入|円/.test(text)) return ['USD/JPYの初動', '日本金利', '日経225先物', '輸出株'];
  if (/FRB|FOMC|PCE|CPI|雇用|ISM|GDP|JOLTS|ADP|求人件数/.test(text)) return ['米2年債利回り', 'USD/JPY', '米株先物', '金・BTC'];
  if (/決算|AMD|Caterpillar|McDonald|Pfizer|Microsoft|Meta|Apple|Amazon/.test(text)) return ['発表後の株価反応', 'Nasdaq先物', '日経225先物', 'ドル円'];
  return ['発表時刻の確認', '米金利', 'USD/JPY', '株価指数先物'];
}

function eventsNormalizeTime_(value) {
  var match = String(value || '').match(/\b([01]?\d|2[0-3]):([0-5]\d)\b/);
  return match ? match[1].padStart(2, '0') + ':' + match[2] : '';
}

function eventsNextWeekdayDate_(baseDate, weekday) {
  if (!eventsIsDate_(baseDate)) return baseDate;
  var date = new Date(baseDate + 'T00:00:00+09:00');
  var diff = weekday - date.getDay();
  if (diff <= 0) diff += 7;
  date.setDate(date.getDate() + diff);
  return Utilities.formatDate(date, EVENTS_JSON_CONFIG.timezone, 'yyyy-MM-dd');
}

function eventsIsDate_(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(value || ''));
}

function eventsEventMillis_(event) {
  if (!event || !event.date || !event.time) return 0;
  var date = new Date(event.date + 'T' + event.time + ':00+09:00');
  return date.getTime();
}

function eventsCompareEventDesc_(a, b) {
  return (String(b.date || '') + ' ' + String(b.time || b.timingLabel || '') + ' ' + String(b.title || ''))
    .localeCompare(String(a.date || '') + ' ' + String(a.time || a.timingLabel || '') + ' ' + String(a.title || ''));
}

function eventsUniqueEvents_(rows) {
  var seen = {};
  var result = [];
  rows.forEach(function(event) {
    if (!event || !event.id) return;
    if (seen[event.id]) {
      result[seen[event.id] - 1] = eventsMergeEvent_(result[seen[event.id] - 1], event);
      return;
    }
    seen[event.id] = result.length + 1;
    result.push(event);
  });
  return result;
}

function eventsStableId_(event) {
  var key = [
    event.date || '',
    event.time || event.timingLabel || '',
    event.country || '',
    eventsCleanText_(event.title || '', 120).toLowerCase()
  ].join('|');
  return 'event-' + eventsSimpleHash_(key);
}

function eventsSimpleHash_(text) {
  var hash = 0;
  for (var i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) - hash) + text.charCodeAt(i);
    hash = hash | 0;
  }
  return Math.abs(hash).toString(36);
}

function eventsDateLabel_(date) {
  var parsed = new Date(date + 'T00:00:00+09:00');
  if (isNaN(parsed.getTime())) return date;
  var weekdays = ['日', '月', '火', '水', '木', '金', '土'];
  return date.replace(/-/g, '/') + '（' + weekdays[parsed.getDay()] + '）';
}

function eventsArray_(value) {
  if (Array.isArray(value)) return value;
  if (value === null || typeof value === 'undefined' || value === '') return [];
  return [value];
}

function eventsCleanText_(value, max) {
  var text = String(value === null || typeof value === 'undefined' ? '' : value)
    .replace(/\s+/g, ' ')
    .replace(/^[・\s]+/, '')
    .trim();
  if (max && text.length > max) return text.slice(0, max) + '...';
  return text;
}

function eventsIsBlank_(value) {
  if (Array.isArray(value)) return value.length === 0;
  if (value && typeof value === 'object') return false;
  return String(value === null || typeof value === 'undefined' ? '' : value).trim() === '' ||
    String(value).trim() === '—' ||
    String(value).trim() === '-';
}

function eventsFetchReportsJson_() {
  if (typeof dashboardFetchReportsJson_ === 'function') return dashboardFetchReportsJson_();
  var current = eventsGetGitHubJson_(EVENTS_JSON_CONFIG.reportsPath);
  return eventsNormalizeReports_(current.data);
}

function eventsNormalizeReports_(reports) {
  if (typeof dashboardNormalizeReports_ === 'function') return dashboardNormalizeReports_(reports);
  var list = [];
  if (Array.isArray(reports)) {
    list = reports;
  } else if (reports && Array.isArray(reports.reports)) {
    list = reports.reports;
  } else if (reports && reports.latestReport) {
    list = [reports.latestReport];
  }
  return list.filter(function(report) {
    return report && eventsIsDate_(report.date) && /^\d{2}:\d{2}$/.test(String(report.time || ''));
  }).sort(function(a, b) {
    return (b.date + ' ' + b.time).localeCompare(a.date + ' ' + a.time);
  });
}

function eventsGetGitHubJson_(path) {
  if (typeof dashboardGetGitHubJsonFile_ === 'function') return dashboardGetGitHubJsonFile_(path);
  var config = eventsGithubConfig_();
  var response = UrlFetchApp.fetch(eventsGithubContentsUrl_(config, path) + '?ref=' + encodeURIComponent(config.branch), {
    method: 'get',
    headers: eventsGithubHeaders_(config.token),
    muteHttpExceptions: true
  });
  var code = response.getResponseCode();
  if (code === 404) return { data: [], sha: null };
  if (code !== 200) throw new Error('GitHubファイル取得失敗: HTTP ' + code + ' ' + response.getContentText());
  var payload = JSON.parse(response.getContentText());
  return {
    data: JSON.parse(Utilities.newBlob(Utilities.base64Decode(payload.content.replace(/\n/g, ''))).getDataAsString('UTF-8')),
    sha: payload.sha
  };
}

function eventsPutGitHubJson_(path, content, sha, message) {
  if (typeof dashboardPutGitHubJsonFile_ === 'function') return dashboardPutGitHubJsonFile_(path, content, sha, message);
  var config = eventsGithubConfig_();
  var body = {
    message: message,
    content: Utilities.base64Encode(content, Utilities.Charset.UTF_8),
    branch: config.branch
  };
  if (sha) body.sha = sha;
  var response = UrlFetchApp.fetch(eventsGithubContentsUrl_(config, path), {
    method: 'put',
    contentType: 'application/json',
    headers: eventsGithubHeaders_(config.token),
    payload: JSON.stringify(body),
    muteHttpExceptions: true
  });
  var code = response.getResponseCode();
  if (code !== 200 && code !== 201) throw new Error('GitHub更新失敗: HTTP ' + code + ' ' + response.getContentText());
  return JSON.parse(response.getContentText());
}

function eventsGithubConfig_() {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('スクリプトプロパティ GITHUB_TOKEN が未設定です。');
  return {
    token: token,
    owner: props.getProperty('GITHUB_OWNER') || 'matrixdiamond512-cell',
    repo: props.getProperty('GITHUB_REPO') || 'Chat-GPT-Market-Report',
    branch: props.getProperty('GITHUB_BRANCH') || 'main'
  };
}

function eventsGithubContentsUrl_(config, path) {
  return 'https://api.github.com/repos/' + config.owner + '/' + config.repo + '/contents/' + path;
}

function eventsGithubHeaders_(token) {
  return {
    Authorization: 'Bearer ' + token,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
  };
}

function eventsIsoJst_(date) {
  return Utilities.formatDate(date, EVENTS_JSON_CONFIG.timezone, "yyyy-MM-dd'T'HH:mm:ss'+09:00'");
}

function eventsSaveResult_(result) {
  var payload = {};
  var key;
  for (key in result) payload[key] = result[key];
  payload.executedAt = Utilities.formatDate(new Date(), EVENTS_JSON_CONFIG.timezone, 'yyyy-MM-dd HH:mm:ss');
  PropertiesService.getScriptProperties().setProperty(
    EVENTS_JSON_CONFIG.lastResultProperty,
    JSON.stringify(payload)
  );
  return payload;
}

function eventsEscapeHtml_(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function eventsAlert_(message) {
  try {
    SpreadsheetApp.getUi().alert(message);
  } catch (error) {
    Logger.log(message);
  }
}
