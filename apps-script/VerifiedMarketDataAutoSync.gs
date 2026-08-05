var VERIFIED_MARKET_DATA_AUTO_SYNC_CONFIG = {
  handler: 'syncVerifiedMarketDataIfChanged',
  intervalMinutes: 5,
  latestUrl: 'https://raw.githubusercontent.com/matrixdiamond512-cell/Chat-GPT-Market-Report/main/data/market/latest.json',
  lastSnapshotProperty: 'VERIFIED_MARKET_DATA_LAST_SYNCED_SNAPSHOT'
};

/**
 * Installs one lightweight watcher. It checks the GitHub snapshot every five
 * minutes, but writes to Sheets only when generatedAt/reportSlot changed.
 */
function installVerifiedMarketDataAutoSync() {
  uninstallVerifiedMarketDataAutoSync_();

  ScriptApp.newTrigger(VERIFIED_MARKET_DATA_AUTO_SYNC_CONFIG.handler)
    .timeBased()
    .everyMinutes(VERIFIED_MARKET_DATA_AUTO_SYNC_CONFIG.intervalMinutes)
    .create();

  var result = syncVerifiedMarketDataIfChanged();
  SpreadsheetApp.getUi().alert(
    'Verified market data auto sync is enabled.\n' +
    'The watcher runs every 5 minutes and writes only when GitHub data changed.'
  );
  return result;
}

function uninstallVerifiedMarketDataAutoSync() {
  var deleted = uninstallVerifiedMarketDataAutoSync_();
  SpreadsheetApp.getUi().alert('Deleted auto-sync triggers: ' + deleted);
  return deleted;
}

function showVerifiedMarketDataAutoSyncStatus() {
  var handler = VERIFIED_MARKET_DATA_AUTO_SYNC_CONFIG.handler;
  var active = ScriptApp.getProjectTriggers().filter(function(trigger) {
    return trigger.getHandlerFunction() === handler;
  }).length;
  var lastSnapshot = PropertiesService.getScriptProperties()
    .getProperty(VERIFIED_MARKET_DATA_AUTO_SYNC_CONFIG.lastSnapshotProperty) || 'none';

  var message =
    'Active triggers: ' + active + '\n' +
    'Last synced snapshot: ' + lastSnapshot;
  SpreadsheetApp.getUi().alert(message);
  return message;
}

function syncVerifiedMarketDataIfChanged() {
  if (typeof syncVerifiedMarketDataToChatGptSheets !== 'function') {
    throw new Error('syncVerifiedMarketDataToChatGptSheets is not defined.');
  }

  var payload = fetchVerifiedMarketDataSnapshot_();
  var snapshotKey = String(payload.generatedAt || '') + '|' + String(payload.reportSlot || '');
  if (!payload.generatedAt || !payload.reportSlot || payload.reportSlot === 'manual') {
    throw new Error('The GitHub market snapshot has no valid scheduled report slot.');
  }

  var properties = PropertiesService.getScriptProperties();
  var previousKey = properties.getProperty(
    VERIFIED_MARKET_DATA_AUTO_SYNC_CONFIG.lastSnapshotProperty
  );
  if (previousKey === snapshotKey) {
    return {
      ok: true,
      skipped: true,
      reason: 'Snapshot is already synced.',
      snapshot: snapshotKey
    };
  }

  var result = syncVerifiedMarketDataToChatGptSheets();
  if (!result || result.ok !== false) {
    properties.setProperty(
      VERIFIED_MARKET_DATA_AUTO_SYNC_CONFIG.lastSnapshotProperty,
      snapshotKey
    );
  }
  return result;
}

function fetchVerifiedMarketDataSnapshot_() {
  var response = UrlFetchApp.fetch(
    VERIFIED_MARKET_DATA_AUTO_SYNC_CONFIG.latestUrl + '?t=' + new Date().getTime(),
    {
      muteHttpExceptions: true,
      followRedirects: true,
      headers: { Accept: 'application/json' }
    }
  );
  var status = response.getResponseCode();
  if (status < 200 || status >= 300) {
    throw new Error('Could not fetch verified market data. HTTP ' + status);
  }

  var payload = JSON.parse(response.getContentText('UTF-8'));
  if (!payload || payload.overallStatus === 'blocked') {
    throw new Error('The verified market snapshot is blocked.');
  }
  return payload;
}

function uninstallVerifiedMarketDataAutoSync_() {
  var handler = VERIFIED_MARKET_DATA_AUTO_SYNC_CONFIG.handler;
  var deleted = 0;
  ScriptApp.getProjectTriggers().forEach(function(trigger) {
    if (trigger.getHandlerFunction() === handler) {
      ScriptApp.deleteTrigger(trigger);
      deleted += 1;
    }
  });
  return deleted;
}
