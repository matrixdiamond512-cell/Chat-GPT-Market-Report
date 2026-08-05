var MARKET_REPORT_MASTER_SCHEDULER_CONFIG = {
  timezone: 'Asia/Tokyo',
  lastResultProperty: 'MARKET_REPORT_MASTER_SCHEDULER_LAST_RESULT',
  reportHours: [7, 12, 16, 21],
  slots: [
    { handler: 'runMarketReportMaster0730', hour: 7, slotHour: 7, mode: 'main-0730', retry: false },
    { handler: 'runMarketReportMaster0830Retry', hour: 8, slotHour: 7, mode: 'retry-0830', retry: true },
    { handler: 'runMarketReportMaster1230', hour: 12, slotHour: 12, mode: 'main-1230', retry: false },
    { handler: 'runMarketReportMaster1330Retry', hour: 13, slotHour: 12, mode: 'retry-1330', retry: true },
    { handler: 'runMarketReportMaster1630', hour: 16, slotHour: 16, mode: 'main-1630', retry: false },
    { handler: 'runMarketReportMaster1730Retry', hour: 17, slotHour: 16, mode: 'retry-1730', retry: true },
    { handler: 'runMarketReportMaster2130', hour: 21, slotHour: 21, mode: 'main-2130', retry: false },
    { handler: 'runMarketReportMaster2230Retry', hour: 22, slotHour: 21, mode: 'retry-2230', retry: true }
  ],
  oldManagedHandlers: [
    'autoPublishMarketReport0700',
    'autoPublishMarketReport1200',
    'autoPublishMarketReport1600',
    'autoPublishMarketReport2100',
    'autoPublishMarketReport0830Retry',
    'autoPublishMarketReport1330Retry',
    'autoPublishMarketReport1730Retry',
    'autoPublishMarketReport2230Retry',
    'autoPublishMarketReport0900',
    'pollLatestMarketReportAndPublish',
    'continueHistoricalMarketReportImport',
    'updateUsdJpyVolumePageFromSources',
    'updateStockAnalysisPageFromSheet',
    'syncDashboardJsonToGitHub',
    'syncEventsJsonToGitHub'
  ]
};

function installMarketReportMasterSchedulerTriggers() {
  var cleanup = deleteMarketReportMasterManagedTriggers_();
  var created = [];

  try {
    MARKET_REPORT_MASTER_SCHEDULER_CONFIG.slots.forEach(function(slot) {
      ScriptApp.newTrigger(slot.handler)
        .timeBased()
        .atHour(slot.hour)
        .nearMinute(30)
        .everyDays(1)
        .inTimezone(MARKET_REPORT_MASTER_SCHEDULER_CONFIG.timezone)
        .create();
      created.push(slot.handler);
    });
  } catch (error) {
    var remaining = marketReportMasterTriggerNames_();
    SpreadsheetApp.getUi().alert(
      '共通トリガーの設定に失敗しました。\n' +
      '理由: ' + error.message + '\n\n' +
      '削除済みトリガー: ' + cleanup.deletedCount + '\n' +
      '作成済みトリガー: ' + created.length + '\n' +
      '現在残っているトリガー数: ' + remaining.length + '\n\n' +
      '残っているトリガー:\n' + (remaining.length ? remaining.join('\n') : 'なし')
    );
    throw error;
  }

  SpreadsheetApp.getUi().alert(
    '共通トリガーを設定しました。\n\n' +
    '通常: 07:30 / 12:30 / 16:30 / 21:30\n' +
    '再チェック: 08:30 / 13:30 / 17:30 / 22:30\n\n' +
    '削除した個別トリガー: ' + cleanup.deletedCount + '\n' +
    '作成した共通トリガー: ' + created.length
  );

  return showMarketReportMasterSchedulerStatus();
}

function uninstallMarketReportMasterSchedulerTriggers() {
  var deleted = deleteMarketReportMasterTriggers_();
  SpreadsheetApp.getUi().alert('共通トリガーを削除しました。削除数: ' + deleted);
  return deleted;
}

function cleanupOldMarketReportPageTriggersForMasterScheduler() {
  var cleanup = deleteMarketReportMasterManagedTriggers_();
  SpreadsheetApp.getUi().alert(
    '個別ページ用の古いトリガーを整理しました。\n' +
    '削除数: ' + cleanup.deletedCount + '\n\n' +
    '削除したトリガー:\n' + (cleanup.deletedHandlers.length ? cleanup.deletedHandlers.join('\n') : 'なし')
  );
  return cleanup;
}

function showMarketReportMasterSchedulerStatus() {
  var masterHandlers = marketReportMasterHandlerNames_();
  var allTriggers = ScriptApp.getProjectTriggers();
  var masterInstalled = [];
  var oldInstalled = [];
  var allNames = [];

  allTriggers.forEach(function(trigger) {
    var name = trigger.getHandlerFunction();
    allNames.push(name);
    if (masterHandlers.indexOf(name) >= 0) masterInstalled.push(name);
    if (MARKET_REPORT_MASTER_SCHEDULER_CONFIG.oldManagedHandlers.indexOf(name) >= 0) {
      oldInstalled.push(name);
    }
  });

  var lastResult = PropertiesService.getScriptProperties()
    .getProperty(MARKET_REPORT_MASTER_SCHEDULER_CONFIG.lastResultProperty) || 'まだ実行履歴はありません。';

  SpreadsheetApp.getUi().alert(
    '共通トリガー: ' + masterInstalled.length + '/' + masterHandlers.length + '\n' +
    '設定済み: ' + (masterInstalled.length ? masterInstalled.join(' / ') : 'なし') + '\n\n' +
    '残っている個別トリガー: ' + oldInstalled.length + '\n' +
    (oldInstalled.length ? oldInstalled.join(' / ') + '\n\n' : '\n') +
    '全トリガー数: ' + allTriggers.length + '\n\n' +
    'Last result:\n' + lastResult
  );

  return {
    masterInstalled: masterInstalled,
    oldInstalled: oldInstalled,
    allTriggers: allNames,
    lastResult: lastResult
  };
}

function runMarketReportMaster0730() { return runMarketReportMasterScheduler_(7, 'main-0730', false); }
function runMarketReportMaster0830Retry() { return runMarketReportMasterScheduler_(7, 'retry-0830', true); }
function runMarketReportMaster1230() { return runMarketReportMasterScheduler_(12, 'main-1230', false); }
function runMarketReportMaster1330Retry() { return runMarketReportMasterScheduler_(12, 'retry-1330', true); }
function runMarketReportMaster1630() { return runMarketReportMasterScheduler_(16, 'main-1630', false); }
function runMarketReportMaster1730Retry() { return runMarketReportMasterScheduler_(16, 'retry-1730', true); }
function runMarketReportMaster2130() { return runMarketReportMasterScheduler_(21, 'main-2130', false); }
function runMarketReportMaster2230Retry() { return runMarketReportMasterScheduler_(21, 'retry-2230', true); }

function runMarketReportMasterNow() {
  var now = new Date();
  var hour = Number(Utilities.formatDate(now, MARKET_REPORT_MASTER_SCHEDULER_CONFIG.timezone, 'H'));
  var slotHour = 7;
  if (hour >= 21) slotHour = 21;
  else if (hour >= 16) slotHour = 16;
  else if (hour >= 12) slotHour = 12;
  return runMarketReportMasterScheduler_(slotHour, 'manual', false);
}

function runMarketReportMasterScheduler_(slotHour, mode, isRetry) {
  var lock = LockService.getDocumentLock();
  if (lock && !lock.tryLock(5000)) {
    return saveMarketReportMasterResult_({
      ok: true,
      skipped: true,
      mode: mode,
      slotHour: slotHour,
      reason: '別の共通スケジューラーが実行中のためスキップしました。'
    });
  }

  var result = {
    ok: true,
    skipped: false,
    mode: mode,
    slotHour: slotHour,
    retry: !!isRetry,
    modules: []
  };

  try {
    var day = Number(Utilities.formatDate(new Date(), MARKET_REPORT_MASTER_SCHEDULER_CONFIG.timezone, 'u'));
    if (day === 6 || day === 7) {
      result.skipped = true;
      result.reason = '週末のため自動更新をスキップしました。';
      return saveMarketReportMasterResult_(result);
    }

    // 日銀の出来高は日次公表なので、21:30と22:30の再確認だけで更新する。
    // タイムアウト時にも出来高更新が後回しにならないよう、21時枠では最初に実行する。
    if (slotHour === 21) {
      runMarketReportMasterModule_(result, 'usdjpy_volume', '東京市場ドル円スポット出来高更新', function() {
        if (typeof runUsdJpyVolumeUpdateForMaster_ !== 'function') {
          return {
            ok: false,
            skipped: true,
            reason: 'UsdJpyVolumePageAutoUpdate.gsが旧版です。統合更新関数を追加してください。'
          };
        }
        return runUsdJpyVolumeUpdateForMaster_();
      });
    }

    runMarketReportMasterModule_(result, 'market_report', 'マーケットレポート本文・ダッシュボード公開', function() {
      if (typeof publishMarketReportSlot_ !== 'function') {
        throw new Error('publishMarketReportSlot_ が見つかりません。');
      }
      if (isRetry) return publishDueMarketReportsForMaster_(slotHour, mode);
      return publishMarketReportSlot_(slotHour, 'master-' + mode, false);
    });

    runMarketReportMasterModule_(result, 'dashboard_events', 'ダッシュボード・重要イベント更新', function() {
      if (typeof syncDashboardJsonToGitHub === 'function') return syncDashboardJsonToGitHub();
      if (typeof syncEventsJsonToGitHub === 'function') return syncEventsJsonToGitHub();
      throw new Error('syncDashboardJsonToGitHub / syncEventsJsonToGitHub が見つかりません。');
    });

    if (!isRetry) {
      runMarketReportMasterModule_(result, 'stock_analysis', '株式市場分析更新', function() {
        if (typeof updateStockAnalysisPageFromSheet !== 'function') {
          return { ok: true, skipped: true, reason: '株式市場分析更新関数が未導入です。' };
        }
        return updateStockAnalysisPageFromSheet();
      });

    }

    result.ok = result.modules.every(function(module) { return module.ok !== false; });
    return saveMarketReportMasterResult_(result);
  } catch (error) {
    result.ok = false;
    result.error = error.message;
    result.stack = error.stack || '';
    saveMarketReportMasterResult_(result);
    throw error;
  } finally {
    if (lock) lock.releaseLock();
  }
}

function publishDueMarketReportsForMaster_(slotHour, mode) {
  var reports = [];
  MARKET_REPORT_MASTER_SCHEDULER_CONFIG.reportHours.forEach(function(hour) {
    if (hour <= slotHour) {
      reports.push(publishMarketReportSlot_(hour, 'master-' + mode, false));
    }
  });
  return {
    ok: reports.every(function(item) { return item && item.ok !== false; }),
    checkedCount: reports.length,
    publishedCount: reports.filter(function(item) { return item && item.ok && !item.skipped; }).length,
    reports: reports
  };
}

function runMarketReportMasterModule_(summary, name, label, runner) {
  var startedAt = new Date();
  try {
    var value = runner();
    summary.modules.push({
      name: name,
      label: label,
      ok: !value || value.ok !== false,
      skipped: !!(value && value.skipped),
      durationSec: Math.round((new Date().getTime() - startedAt.getTime()) / 1000),
      result: compactMarketReportMasterResult_(value)
    });
  } catch (error) {
    summary.modules.push({
      name: name,
      label: label,
      ok: false,
      skipped: false,
      durationSec: Math.round((new Date().getTime() - startedAt.getTime()) / 1000),
      error: error.message,
      stack: error.stack || ''
    });
  }
}

function deleteMarketReportMasterManagedTriggers_() {
  var masterHandlers = marketReportMasterHandlerNames_();
  var managedHandlers = masterHandlers.concat(MARKET_REPORT_MASTER_SCHEDULER_CONFIG.oldManagedHandlers);
  var deleted = [];

  ScriptApp.getProjectTriggers().forEach(function(trigger) {
    var handler = trigger.getHandlerFunction();
    if (managedHandlers.indexOf(handler) >= 0) {
      ScriptApp.deleteTrigger(trigger);
      deleted.push(handler);
    }
  });

  return {
    deletedCount: deleted.length,
    deletedHandlers: deleted
  };
}

function deleteMarketReportMasterTriggers_() {
  var handlers = marketReportMasterHandlerNames_();
  var deleted = 0;
  ScriptApp.getProjectTriggers().forEach(function(trigger) {
    if (handlers.indexOf(trigger.getHandlerFunction()) >= 0) {
      ScriptApp.deleteTrigger(trigger);
      deleted += 1;
    }
  });
  return deleted;
}

function marketReportMasterHandlerNames_() {
  return MARKET_REPORT_MASTER_SCHEDULER_CONFIG.slots.map(function(slot) { return slot.handler; });
}

function marketReportMasterTriggerNames_() {
  return ScriptApp.getProjectTriggers().map(function(trigger) {
    return trigger.getHandlerFunction();
  });
}

function compactMarketReportMasterResult_(value) {
  if (!value || typeof value !== 'object') return value;
  var compact = {};
  [
    'ok', 'skipped', 'reason', 'mode', 'slot', 'fileName', 'reportDate', 'reportTime',
    'latestKey', 'commitSha', 'dashboardCommitSha', 'eventsCommitSha', 'targetPath',
    'latestTargetDate', 'latestPublicationDate', 'publishedCount', 'checkedCount',
    'error'
  ].forEach(function(key) {
    if (value[key] !== undefined && value[key] !== '') compact[key] = value[key];
  });
  return compact;
}

function saveMarketReportMasterResult_(result) {
  var payload = {};
  Object.keys(result || {}).forEach(function(key) { payload[key] = result[key]; });
  payload.executedAt = Utilities.formatDate(
    new Date(),
    MARKET_REPORT_MASTER_SCHEDULER_CONFIG.timezone,
    'yyyy-MM-dd HH:mm:ss'
  );
  PropertiesService.getScriptProperties().setProperty(
    MARKET_REPORT_MASTER_SCHEDULER_CONFIG.lastResultProperty,
    JSON.stringify(payload, null, 2)
  );
  console.log(JSON.stringify(payload));
  return payload;
}
