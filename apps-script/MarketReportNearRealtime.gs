const MARKET_REPORT_NEAR_REALTIME_CONFIG = {
  timezone: 'Asia/Tokyo',
  pollMinutes: 5,
  handler: 'pollLatestMarketReportAndPublish',
  lastCheckedProperty: 'MARKET_REPORT_NEAR_REALTIME_LAST_CHECKED',
  lastPublishedFileIdProperty: 'MARKET_REPORT_NEAR_REALTIME_LAST_FILE_ID',
  lastPublishedVersionProperty: 'MARKET_REPORT_NEAR_REALTIME_LAST_FILE_VERSION',
  lastResultProperty: 'MARKET_REPORT_NEAR_REALTIME_LAST_RESULT'
};

function installMarketReportNearRealtimeTrigger() {
  uninstallMarketReportNearRealtimeTrigger_(false);

  ScriptApp.newTrigger(MARKET_REPORT_NEAR_REALTIME_CONFIG.handler)
    .timeBased()
    .everyMinutes(MARKET_REPORT_NEAR_REALTIME_CONFIG.pollMinutes)
    .create();

  SpreadsheetApp.getUi().alert(
    'Google Docs変更監視を設定しました。\n' +
    MARKET_REPORT_NEAR_REALTIME_CONFIG.pollMinutes + '分ごとに最新レポートを確認し、変更があればWEB版を更新します。'
  );
}

function uninstallMarketReportNearRealtimeTrigger() {
  const deleted = uninstallMarketReportNearRealtimeTrigger_(true);
  return deleted;
}

function uninstallMarketReportNearRealtimeTrigger_(showAlert) {
  let deleted = 0;
  ScriptApp.getProjectTriggers()
    .filter(trigger => trigger.getHandlerFunction() === MARKET_REPORT_NEAR_REALTIME_CONFIG.handler)
    .forEach(trigger => {
      ScriptApp.deleteTrigger(trigger);
      deleted += 1;
    });

  if (showAlert) {
    SpreadsheetApp.getUi().alert('Google Docs変更監視を停止しました。削除数: ' + deleted);
  }
  return deleted;
}

function showMarketReportNearRealtimeStatus() {
  const props = PropertiesService.getScriptProperties();
  const installed = ScriptApp.getProjectTriggers()
    .filter(trigger => trigger.getHandlerFunction() === MARKET_REPORT_NEAR_REALTIME_CONFIG.handler)
    .length;

  SpreadsheetApp.getUi().alert(
    '変更監視トリガー: ' + (installed ? '稼働中' : '停止中') + '\n' +
    '監視間隔: ' + MARKET_REPORT_NEAR_REALTIME_CONFIG.pollMinutes + '分\n' +
    '最終確認: ' + (props.getProperty(MARKET_REPORT_NEAR_REALTIME_CONFIG.lastCheckedProperty) || 'なし') + '\n\n' +
    '最終結果:\n' + (props.getProperty(MARKET_REPORT_NEAR_REALTIME_CONFIG.lastResultProperty) || '実行履歴なし')
  );
}

function pollLatestMarketReportAndPublish() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) return;

  try {
    const props = PropertiesService.getScriptProperties();
    const now = new Date();
    const nowText = Utilities.formatDate(now, MARKET_REPORT_NEAR_REALTIME_CONFIG.timezone, 'yyyy-MM-dd HH:mm:ss');
    props.setProperty(MARKET_REPORT_NEAR_REALTIME_CONFIG.lastCheckedProperty, nowText);

    const file = findLatestMarketReportDoc_();
    if (!file) {
      return saveNearRealtimeResult_({ ok: true, skipped: true, reason: '対象文書なし' });
    }

    const fileId = file.getId();
    const version = String(file.getLastUpdated().getTime());
    const lastFileId = props.getProperty(MARKET_REPORT_NEAR_REALTIME_CONFIG.lastPublishedFileIdProperty);
    const lastVersion = props.getProperty(MARKET_REPORT_NEAR_REALTIME_CONFIG.lastPublishedVersionProperty);

    if (fileId === lastFileId && version === lastVersion) {
      return saveNearRealtimeResult_({
        ok: true,
        skipped: true,
        reason: '変更なし',
        fileName: file.getName(),
        updatedAt: file.getLastUpdated().toISOString()
      });
    }

    const report = buildWebReportFromGoogleDoc_(file);
    const result = publishWebReportObject_(report);

    props.setProperty(MARKET_REPORT_NEAR_REALTIME_CONFIG.lastPublishedFileIdProperty, fileId);
    props.setProperty(MARKET_REPORT_NEAR_REALTIME_CONFIG.lastPublishedVersionProperty, version);

    return saveNearRealtimeResult_({
      ok: true,
      skipped: false,
      fileName: file.getName(),
      updatedAt: file.getLastUpdated().toISOString(),
      reportDate: report.date,
      reportTime: report.time,
      commitSha: result.commitSha,
      pagesUrl: result.pagesUrl
    });
  } catch (error) {
    saveNearRealtimeResult_({
      ok: false,
      skipped: false,
      error: error.message,
      stack: error.stack || ''
    });
    throw error;
  } finally {
    lock.releaseLock();
  }
}

function publishLatestMarketReportNow() {
  const result = pollLatestMarketReportAndPublish();
  SpreadsheetApp.getUi().alert(JSON.stringify(result, null, 2));
  return result;
}

function saveNearRealtimeResult_(result) {
  const payload = Object.assign({
    executedAt: Utilities.formatDate(new Date(), MARKET_REPORT_NEAR_REALTIME_CONFIG.timezone, 'yyyy-MM-dd HH:mm:ss')
  }, result);

  PropertiesService.getScriptProperties().setProperty(
    MARKET_REPORT_NEAR_REALTIME_CONFIG.lastResultProperty,
    JSON.stringify(payload, null, 2)
  );

  console.log(JSON.stringify(payload));
  return payload;
}
