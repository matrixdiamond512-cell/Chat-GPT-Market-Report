const MARKET_REPORT_AUTO_CONFIG = {
  timezone: 'Asia/Tokyo',
  handlers: [
    { name: 'autoPublishMarketReport0700', hour: 7 },
    { name: 'autoPublishMarketReport0900', hour: 9 },
    { name: 'autoPublishMarketReport1200', hour: 12 },
    { name: 'autoPublishMarketReport1600', hour: 16 },
    { name: 'autoPublishMarketReport2100', hour: 21 }
  ],
  minute: 30,
  lastResultProperty: 'MARKET_REPORT_AUTO_LAST_RESULT'
};

function installMarketReportAutoPublishTriggers() {
  deleteMarketReportAutoPublishTriggers_();

  MARKET_REPORT_AUTO_CONFIG.handlers.forEach(item => {
    ScriptApp.newTrigger(item.name)
      .timeBased()
      .atHour(item.hour)
      .nearMinute(MARKET_REPORT_AUTO_CONFIG.minute)
      .everyDays(1)
      .inTimezone(MARKET_REPORT_AUTO_CONFIG.timezone)
      .create();
  });

  SpreadsheetApp.getUi().alert(
    'WEB版の自動公開トリガーを設定しました。\n' +
    '平日: 07:30・12:30・16:30・21:30\n' +
    '土曜: 07:30・09:30\n' +
    '日曜: 公開なし\n\n' +
    'Google Apps Scriptの時刻トリガーは、指定時刻から多少遅れて実行される場合があります。'
  );
}

function uninstallMarketReportAutoPublishTriggers() {
  const deleted = deleteMarketReportAutoPublishTriggers_();
  SpreadsheetApp.getUi().alert('WEB版の自動公開トリガーを削除しました。削除数: ' + deleted);
}

function showMarketReportAutoPublishStatus() {
  const handlers = MARKET_REPORT_AUTO_CONFIG.handlers.map(item => item.name);
  const installed = ScriptApp.getProjectTriggers()
    .filter(trigger => handlers.includes(trigger.getHandlerFunction()))
    .map(trigger => trigger.getHandlerFunction());

  const lastResult = PropertiesService.getScriptProperties()
    .getProperty(MARKET_REPORT_AUTO_CONFIG.lastResultProperty) || '実行履歴なし';

  SpreadsheetApp.getUi().alert(
    '自動公開トリガー: ' + installed.length + '/' + handlers.length + '件\n' +
    '登録済み: ' + (installed.length ? installed.join('、') : 'なし') + '\n\n' +
    '最終実行結果:\n' + lastResult
  );
}

function autoPublishMarketReport0700() { return autoPublishScheduledMarketReport_(7); }
function autoPublishMarketReport0900() { return autoPublishScheduledMarketReport_(9); }
function autoPublishMarketReport1200() { return autoPublishScheduledMarketReport_(12); }
function autoPublishMarketReport1600() { return autoPublishScheduledMarketReport_(16); }
function autoPublishMarketReport2100() { return autoPublishScheduledMarketReport_(21); }

function autoPublishScheduledMarketReport_(hour) {
  const now = new Date();
  const day = Number(Utilities.formatDate(now, MARKET_REPORT_AUTO_CONFIG.timezone, 'u'));
  const allowed = isScheduledMarketReportSlot_(day, hour);

  if (!allowed) {
    return saveMarketReportAutoResult_({
      ok: true,
      skipped: true,
      reason: '運用対象外の曜日・時刻',
      day: day,
      hour: hour
    });
  }

  try {
    const expected = expectedMarketReportFileName_(now, hour);
    const file = findMarketReportDocByName_(expected);

    if (!file) {
      throw new Error('対象のGoogle Docsが見つかりません: ' + expected);
    }

    const fileVersion = String(file.getLastUpdated().getTime());
    const publishedVersionKey = 'MARKET_REPORT_PUBLISHED_' + expected;
    const props = PropertiesService.getScriptProperties();

    if (props.getProperty(publishedVersionKey) === fileVersion) {
      return saveMarketReportAutoResult_({
        ok: true,
        skipped: true,
        reason: '同じ文書版は公開済み',
        fileName: expected,
        updatedAt: file.getLastUpdated().toISOString()
      });
    }

    const report = buildWebReportFromGoogleDoc_(file);
    const result = publishWebReportObject_(report);
    props.setProperty(publishedVersionKey, fileVersion);

    return saveMarketReportAutoResult_({
      ok: true,
      skipped: false,
      fileName: expected,
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
      hour: hour,
      error: error.message,
      stack: error.stack || ''
    });
    throw error;
  }
}

function isScheduledMarketReportSlot_(day, hour) {
  if (day === 7) return false;
  if (day === 6) return hour === 7 || hour === 9;
  return [7, 12, 16, 21].includes(hour);
}

function expectedMarketReportFileName_(date, hour) {
  return 'マーケットレポート_' +
    Utilities.formatDate(date, MARKET_REPORT_AUTO_CONFIG.timezone, 'yyyy-MM-dd') + '_' +
    ('0' + hour).slice(-2) + '-00';
}

function findMarketReportDocByName_(name) {
  const files = DriveApp.getFilesByName(name);
  let latest = null;

  while (files.hasNext()) {
    const file = files.next();
    if (file.isTrashed()) continue;
    if (file.getMimeType() !== MimeType.GOOGLE_DOCS) continue;
    if (!latest || file.getLastUpdated().getTime() > latest.getLastUpdated().getTime()) latest = file;
  }

  return latest;
}

function deleteMarketReportAutoPublishTriggers_() {
  const handlers = MARKET_REPORT_AUTO_CONFIG.handlers.map(item => item.name);
  let deleted = 0;

  ScriptApp.getProjectTriggers()
    .filter(trigger => handlers.includes(trigger.getHandlerFunction()))
    .forEach(trigger => {
      ScriptApp.deleteTrigger(trigger);
      deleted += 1;
    });

  return deleted;
}

function saveMarketReportAutoResult_(result) {
  const payload = Object.assign({
    executedAt: Utilities.formatDate(new Date(), MARKET_REPORT_AUTO_CONFIG.timezone, 'yyyy-MM-dd HH:mm:ss')
  }, result);

  PropertiesService.getScriptProperties().setProperty(
    MARKET_REPORT_AUTO_CONFIG.lastResultProperty,
    JSON.stringify(payload, null, 2)
  );

  console.log(JSON.stringify(payload));
  return payload;
}
