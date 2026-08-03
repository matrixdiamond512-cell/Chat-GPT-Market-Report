const MARKET_REPORT_AUTO_CONFIG = {
  timezone: 'Asia/Tokyo',
  minute: 30,
  scheduleHandlers: [
    { name: 'autoPublishMarketReport0700', hour: 7 },
    { name: 'autoPublishMarketReport1200', hour: 12 },
    { name: 'autoPublishMarketReport1600', hour: 16 },
    { name: 'autoPublishMarketReport2100', hour: 21 }
  ],
  legacyHandlers: [
    { name: 'autoPublishMarketReport0900', hour: 9 }
  ],
  lastResultProperty: 'MARKET_REPORT_AUTO_LAST_RESULT'
};

function installMarketReportAutoPublishTriggers() {
  deleteMarketReportAutoPublishTriggers_();

  MARKET_REPORT_AUTO_CONFIG.scheduleHandlers.forEach(item => {
    ScriptApp.newTrigger(item.name)
      .timeBased()
      .atHour(item.hour)
      .nearMinute(MARKET_REPORT_AUTO_CONFIG.minute)
      .everyDays(1)
      .inTimezone(MARKET_REPORT_AUTO_CONFIG.timezone)
      .create();
  });

  SpreadsheetApp.getUi().alert(
    'WEB版「マーケットレポート本文」の定時公開トリガーを設定しました。\n' +
    '平日: 07:30 / 12:30 / 16:30 / 21:30\n\n' +
    '各時刻に最新のGoogle Docsを確認し、未反映ならreports.jsonへ公開します。'
  );
}

function uninstallMarketReportAutoPublishTriggers() {
  const deleted = deleteMarketReportAutoPublishTriggers_();
  SpreadsheetApp.getUi().alert('WEB版「マーケットレポート本文」の定時公開トリガーを削除しました。削除数: ' + deleted);
}

function showMarketReportAutoPublishStatus() {
  const activeHandlers = MARKET_REPORT_AUTO_CONFIG.scheduleHandlers.map(item => item.name);
  const allHandlers = getMarketReportAutoPublishHandlerNames_();
  const installedTriggers = ScriptApp.getProjectTriggers()
    .filter(trigger => allHandlers.includes(trigger.getHandlerFunction()));
  const installedNames = installedTriggers.map(trigger => trigger.getHandlerFunction());
  const activeInstalled = installedNames.filter(name => activeHandlers.includes(name));
  const legacyInstalled = installedNames.filter(name => !activeHandlers.includes(name));
  const lastResult = PropertiesService.getScriptProperties()
    .getProperty(MARKET_REPORT_AUTO_CONFIG.lastResultProperty) || '実行履歴はまだありません。';

  SpreadsheetApp.getUi().alert(
    '有効な定時公開トリガー: ' + activeInstalled.length + '/' + activeHandlers.length + '件\n' +
    '登録済み: ' + (activeInstalled.length ? activeInstalled.join(' / ') : 'なし') + '\n' +
    '旧トリガー: ' + (legacyInstalled.length ? legacyInstalled.join(' / ') : 'なし') + '\n\n' +
    '最終実行結果:\n' + lastResult
  );
}

function autoPublishMarketReport0700() { return autoPublishScheduledMarketReport_(7); }
function autoPublishMarketReport1200() { return autoPublishScheduledMarketReport_(12); }
function autoPublishMarketReport1600() { return autoPublishScheduledMarketReport_(16); }
function autoPublishMarketReport2100() { return autoPublishScheduledMarketReport_(21); }

// Old trigger compatibility. If an old 09:30 trigger remains, it exits safely.
function autoPublishMarketReport0900() { return autoPublishScheduledMarketReport_(9); }

function autoPublishScheduledMarketReport_(hour) {
  const now = new Date();
  const day = Number(Utilities.formatDate(now, MARKET_REPORT_AUTO_CONFIG.timezone, 'u'));

  if (!isScheduledMarketReportSlot_(day, hour)) {
    return saveMarketReportAutoResult_({
      ok: true,
      skipped: true,
      reason: '運用対象外の曜日または時刻です',
      slot: formatMarketReportAutoSlot_(now, hour)
    });
  }

  try {
    const file = findLatestMarketReportDocForAutoPublish_();

    if (!file) {
      return saveMarketReportAutoResult_({
        ok: true,
        skipped: true,
        reason: 'マーケットレポートGoogle Docsがまだ見つかりません',
        slot: formatMarketReportAutoSlot_(now, hour)
      });
    }

    const fileVersion = String(file.getLastUpdated().getTime());
    const publishedVersionKey = 'MARKET_REPORT_AUTO_PUBLISHED_' + file.getId();
    const props = PropertiesService.getScriptProperties();

    if (props.getProperty(publishedVersionKey) === fileVersion) {
      return saveMarketReportAutoResult_({
        ok: true,
        skipped: true,
        reason: 'このGoogle Docs版はすでにWEB公開済みです',
        slot: formatMarketReportAutoSlot_(now, hour),
        fileName: file.getName(),
        fileUpdatedAt: formatMarketReportAutoDateTime_(file.getLastUpdated())
      });
    }

    const report = buildWebReportFromGoogleDoc_(file);
    const result = publishWebReportObject_(report);
    props.setProperty(publishedVersionKey, fileVersion);

    return saveMarketReportAutoResult_({
      ok: true,
      skipped: false,
      slot: formatMarketReportAutoSlot_(now, hour),
      fileName: file.getName(),
      fileUpdatedAt: formatMarketReportAutoDateTime_(file.getLastUpdated()),
      reportDate: report.date,
      reportTime: report.time,
      commitSha: result.commitSha,
      dashboardCommitSha: result.dashboardCommitSha || '',
      pagesUrl: result.pagesUrl
    });
  } catch (error) {
    saveMarketReportAutoResult_({
      ok: false,
      skipped: false,
      slot: formatMarketReportAutoSlot_(now, hour),
      error: error.message,
      stack: error.stack || ''
    });
    throw error;
  }
}

function findLatestMarketReportDocForAutoPublish_() {
  if (typeof findLatestMarketReportDoc_ === 'function') {
    try {
      return findLatestMarketReportDoc_();
    } catch (error) {
      if (String(error.message || '').indexOf('見つかりません') === -1) throw error;
    }
  }

  const prefix = (typeof WEB_REPORT_CONFIG === 'object' && WEB_REPORT_CONFIG.prefix) || 'マーケットレポート_';
  const files = DriveApp.searchFiles(
    'mimeType = "' + MimeType.GOOGLE_DOCS + '" and title contains "' + prefix + '" and trashed = false'
  );
  let latest = null;

  while (files.hasNext()) {
    const file = files.next();
    if (!/^マーケットレポート_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}/.test(file.getName())) continue;
    if (!latest || file.getLastUpdated().getTime() > latest.getLastUpdated().getTime()) latest = file;
  }

  return latest;
}

function isScheduledMarketReportSlot_(day, hour) {
  if (day === 6 || day === 7) return false;
  return [7, 12, 16, 21].includes(hour);
}

function deleteMarketReportAutoPublishTriggers_() {
  const handlers = getMarketReportAutoPublishHandlerNames_();
  let deleted = 0;

  ScriptApp.getProjectTriggers()
    .filter(trigger => handlers.includes(trigger.getHandlerFunction()))
    .forEach(trigger => {
      ScriptApp.deleteTrigger(trigger);
      deleted += 1;
    });

  return deleted;
}

function getMarketReportAutoPublishHandlerNames_() {
  return MARKET_REPORT_AUTO_CONFIG.scheduleHandlers
    .concat(MARKET_REPORT_AUTO_CONFIG.legacyHandlers)
    .map(item => item.name);
}

function formatMarketReportAutoSlot_(date, hour) {
  return Utilities.formatDate(date, MARKET_REPORT_AUTO_CONFIG.timezone, 'yyyy-MM-dd') + ' ' +
    ('0' + hour).slice(-2) + ':30';
}

function formatMarketReportAutoDateTime_(date) {
  return Utilities.formatDate(date, MARKET_REPORT_AUTO_CONFIG.timezone, 'yyyy-MM-dd HH:mm:ss');
}

function saveMarketReportAutoResult_(result) {
  const payload = Object.assign({
    executedAt: formatMarketReportAutoDateTime_(new Date())
  }, result);

  PropertiesService.getScriptProperties().setProperty(
    MARKET_REPORT_AUTO_CONFIG.lastResultProperty,
    JSON.stringify(payload, null, 2)
  );

  console.log(JSON.stringify(payload));
  return payload;
}
