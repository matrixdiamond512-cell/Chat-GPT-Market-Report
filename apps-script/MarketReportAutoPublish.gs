const MARKET_REPORT_AUTO_CONFIG = {
  timezone: 'Asia/Tokyo',
  minute: 30,
  retryMinute: 30,
  lookbackDays: 4,
  reportHours: [8, 12, 16, 21],
  scheduleHandlers: [
    { name: 'autoPublishMarketReport0800', hour: 8 },
    { name: 'autoPublishMarketReport1200', hour: 12 },
    { name: 'autoPublishMarketReport1600', hour: 16 },
    { name: 'autoPublishMarketReport2100', hour: 21 }
  ],
  retryHandlers: [
    { name: 'autoPublishMarketReport0930Retry', hour: 9 },
    { name: 'autoPublishMarketReport1330Retry', hour: 13 },
    { name: 'autoPublishMarketReport1730Retry', hour: 17 },
    { name: 'autoPublishMarketReport2230Retry', hour: 22 }
  ],
  watchdogHandler: 'autoPublishMarketReportsWatchdog',
  legacyHandlers: [
    { name: 'autoPublishMarketReport0700', hour: 7 },
    { name: 'autoPublishMarketReport0830Retry', hour: 8 },
    { name: 'autoPublishMarketReport0900', hour: 9 }
  ],
  lastResultProperty: 'MARKET_REPORT_AUTO_LAST_RESULT',
  publishedPrefix: 'MARKET_REPORT_AUTO_PUBLISHED_'
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

  MARKET_REPORT_AUTO_CONFIG.retryHandlers.forEach(item => {
    ScriptApp.newTrigger(item.name)
      .timeBased()
      .atHour(item.hour)
      .nearMinute(MARKET_REPORT_AUTO_CONFIG.retryMinute)
      .everyDays(1)
      .inTimezone(MARKET_REPORT_AUTO_CONFIG.timezone)
      .create();
  });

  ScriptApp.newTrigger(MARKET_REPORT_AUTO_CONFIG.watchdogHandler)
    .timeBased()
    .everyMinutes(5)
    .create();

  SpreadsheetApp.getUi().alert(
    'Market report auto publish triggers were installed.\n' +
    'Main: 08:30 / 12:30 / 16:30 / 21:30\n' +
    'Retry once: 09:30 / 13:30 / 17:30 / 22:30\n\n' +
    'A 5-minute watchdog checks only due source documents. Incomplete reports and missing time-matched images are not published.'
  );
}

function uninstallMarketReportAutoPublishTriggers() {
  const deleted = deleteMarketReportAutoPublishTriggers_();
  SpreadsheetApp.getUi().alert('Market report auto publish triggers were deleted. Count: ' + deleted);
}

function showMarketReportAutoPublishStatus() {
  const activeHandlers = MARKET_REPORT_AUTO_CONFIG.scheduleHandlers
    .concat(MARKET_REPORT_AUTO_CONFIG.retryHandlers)
    .concat([{ name: MARKET_REPORT_AUTO_CONFIG.watchdogHandler }])
    .map(item => item.name);
  const allHandlers = getMarketReportAutoPublishHandlerNames_();
  const installedTriggers = ScriptApp.getProjectTriggers()
    .filter(trigger => allHandlers.includes(trigger.getHandlerFunction()));
  const installedNames = installedTriggers.map(trigger => trigger.getHandlerFunction());
  const activeInstalled = installedNames.filter(name => activeHandlers.includes(name));
  const legacyInstalled = installedNames.filter(name => !activeHandlers.includes(name));
  const lastResult = PropertiesService.getScriptProperties()
    .getProperty(MARKET_REPORT_AUTO_CONFIG.lastResultProperty) || 'No run history yet.';

  SpreadsheetApp.getUi().alert(
    'Active triggers: ' + activeInstalled.length + '/' + activeHandlers.length + '\n' +
    'Installed: ' + (activeInstalled.length ? activeInstalled.join(' / ') : 'none') + '\n' +
    'Legacy: ' + (legacyInstalled.length ? legacyInstalled.join(' / ') : 'none') + '\n\n' +
    'Last result:\n' + lastResult
  );
}

function testMarketReportAutoFindLatestDoc() {
  const file = findLatestMarketReportDocForAutoPublish_();

  if (!file) {
    SpreadsheetApp.getUi().alert(
      'No market report Google Docs file was found.\n' +
      'Example name: ' + marketReportAutoDocName_(
        Utilities.formatDate(new Date(), MARKET_REPORT_AUTO_CONFIG.timezone, 'yyyy-MM-dd'),
        8
      )
    );
    return;
  }

  SpreadsheetApp.getUi().alert(
    'Latest market report Google Docs file was found.\n\n' +
    'File name: ' + file.getName() + '\n' +
    'Updated at: ' + formatMarketReportAutoDateTime_(file.getLastUpdated()) + '\n\n' +
    'This test does not publish anything.'
  );
}

function testMarketReportAutoFind1600Doc() {
  const file = findMarketReportDocForAutoPublishSlot_(16);
  SpreadsheetApp.getUi().alert(file
    ? '16:00 file found:\n' + file.getName() + '\nUpdated at: ' + formatMarketReportAutoDateTime_(file.getLastUpdated())
    : '16:00 file was not found for today.');
}

function autoPublishMarketReport0800() { return autoPublishScheduledMarketReport_(8); }
function autoPublishMarketReport1200() { return autoPublishScheduledMarketReport_(12); }
function autoPublishMarketReport1600() { return autoPublishScheduledMarketReport_(16); }
function autoPublishMarketReport2100() { return autoPublishScheduledMarketReport_(21); }

function autoPublishMarketReport0930Retry() { return autoPublishDueMarketReports_('retry-0930'); }
function autoPublishMarketReport1330Retry() { return autoPublishDueMarketReports_('retry-1330'); }
function autoPublishMarketReport1730Retry() { return autoPublishDueMarketReports_('retry-1730'); }
function autoPublishMarketReport2230Retry() { return autoPublishDueMarketReports_('retry-2230'); }
function autoPublishMarketReportsWatchdog() { return autoPublishDueMarketReports_('watchdog-5-minute'); }

// Legacy trigger compatibility. These handlers no longer publish a 07:00 report.
function autoPublishMarketReport0700() { return autoPublishScheduledMarketReport_(7); }
function autoPublishMarketReport0830Retry() { return autoPublishDueMarketReports_('legacy-retry-0830'); }
function autoPublishMarketReport0900() { return autoPublishScheduledMarketReport_(9); }

function autoPublishScheduledMarketReport_(hour) {
  const now = new Date();
  const day = Number(Utilities.formatDate(now, MARKET_REPORT_AUTO_CONFIG.timezone, 'u'));

  if (!isScheduledMarketReportSlot_(day, hour)) {
    return saveMarketReportAutoResult_({
      ok: true,
      skipped: true,
      reason: 'Outside scheduled report slots.',
      slot: formatMarketReportAutoSlot_(now, hour)
    });
  }

  return publishMarketReportSlot_(hour, 'scheduled', true);
}

function autoPublishDueMarketReports_(reason) {
  const now = new Date();
  const day = Number(Utilities.formatDate(now, MARKET_REPORT_AUTO_CONFIG.timezone, 'u'));

  if (day === 7) {
    return saveMarketReportAutoResult_({
      ok: true,
      skipped: true,
      reason: 'Sunday retry skipped.',
      mode: reason
    });
  }

  const currentHour = Number(Utilities.formatDate(now, MARKET_REPORT_AUTO_CONFIG.timezone, 'H'));
  const currentMinute = Number(Utilities.formatDate(now, MARKET_REPORT_AUTO_CONFIG.timezone, 'm'));
  const results = [];

  MARKET_REPORT_AUTO_CONFIG.reportHours.forEach(hour => {
    if (!isScheduledMarketReportSlot_(day, hour)) return;
    if (hour < currentHour || (hour === currentHour && currentMinute >= MARKET_REPORT_AUTO_CONFIG.minute)) {
      results.push(publishMarketReportSlot_(hour, reason, false));
    }
  });

  const published = results.filter(item => item && item.ok && !item.skipped);
  const errors = results.filter(item => item && item.ok === false);

  const summary = {
    ok: errors.length === 0,
    skipped: published.length === 0,
    mode: reason,
    publishedCount: published.length,
    checkedCount: results.length,
    results: results
  };

  saveMarketReportAutoResult_(summary);

  if (errors.length) {
    throw new Error('Market report retry failed. See last result for details.');
  }

  return summary;
}

/**
 * Repair Drive→GitHub gaps for the last 5 calendar days, including today.
 * Safe to retry: the remote canonical+index readback short-circuits matching
 * revisions; source-readback and publication validation still fail closed.
 * This needs an Apps Script deployment and an installed time-based trigger.
 */
function repairMissingMarketReportsFromDrive() {
  const now = new Date();
  const today = Utilities.formatDate(now, MARKET_REPORT_AUTO_CONFIG.timezone, 'yyyy-MM-dd');
  const results = [];
  // The standard publisher also updates the latest-report pointer. Never run it
  // against an older key than the currently published newest report.
  const latestResponse = getGitHubJsonFile_('data/latest-report.json');
  const latestContainer = latestResponse && latestResponse.data;
  const latest = latestContainer && (latestContainer.latestReport || latestContainer.report || latestContainer);
  const publishedKey = latest && latest.date && latest.time ? latest.date + ' ' + latest.time : '';
  for (let offset = 4; offset >= 0; offset--) {
    const timestamp = new Date(now.getTime() - offset * 86400000);
    const targetDate = Utilities.formatDate(timestamp, MARKET_REPORT_AUTO_CONFIG.timezone, 'yyyy-MM-dd');
    const weekday = Number(Utilities.formatDate(timestamp, MARKET_REPORT_AUTO_CONFIG.timezone, 'u'));
    if (weekday >= 6) continue;
    MARKET_REPORT_AUTO_CONFIG.reportHours.forEach(function(hour) {
      const currentHour = Number(Utilities.formatDate(now, MARKET_REPORT_AUTO_CONFIG.timezone, 'H'));
      if (targetDate === today && hour >= currentHour) return;
      const slotKey = targetDate + ' ' + ('0' + hour).slice(-2) + ':00';
      if (publishedKey && slotKey < publishedKey) {
        const archivalFile = findMarketReportDocForAutoPublishSlot_(hour, targetDate);
        if (!archivalFile) {
          results.push({date: targetDate, hour: hour, status: 'WAITING_INPUT'});
          return;
        }
        try {
          const archived = archiveMarketReportFromDriveWithoutLatestRollback_(archivalFile, hour);
          results.push({date: targetDate, hour: hour, status: archived.skipped ? 'ALREADY_VERIFIED' : 'ARCHIVED'});
        } catch (error) {
          results.push({date: targetDate, hour: hour, status: 'FAILED', error: String(error.message || error)});
        }
        return;
      }
      // Never manufacture an absent source or change report titles.
      if (!findMarketReportDocForAutoPublishSlot_(hour, targetDate)) {
        results.push({ date: targetDate, hour: hour, status: 'WAITING_INPUT' });
        return;
      }
      const outcome = publishMarketReportSlot_(hour, 'drive-github-recovery', false, targetDate);
      results.push({date: targetDate, hour: hour, status: outcome.ok ? (outcome.skipped ? 'ALREADY_VERIFIED' : 'PUBLISHED') : (outcome.status || 'FAILED'), error: outcome.error || ''});
    });
  }
  const failed = results.filter(function(item) { return item.status === 'FAILED'; });
  const summary = { ok: failed.length === 0, mode: 'drive-github-recovery', checkedCount: results.length, results: results };
  saveMarketReportAutoResult_(summary);
  if (failed.length) throw new Error('Drive→GitHub recovery had failures. See script property log.');
  return summary;
}

/**
 * Archive older original documents without touching the latest-report pointer,
 * dashboard, or active infographic. Only the canonical archive and sorted index
 * are changed. Use the same strict validation and source readback as publishing.
 */
function archiveMarketReportFromDriveWithoutLatestRollback_(file, expectedHour) {
  if (marketReportAutoVerifyPublishedSource_(file, expectedHour)) {
    return {ok: true, skipped: true};
  }
  if (typeof getGitHubJsonFile_ !== 'function' ||
      typeof putGitHubJsonFile_ !== 'function' ||
      typeof verifyMarketReportSourceDocReadback_ !== 'function') {
    throw new Error('GitHub archival publication dependencies missing');
  }
  const report = buildWebReportFromGoogleDoc_(file);
  // The archival writer must enforce provenance before the first GitHub write.
  marketReportVerifyProducerProof_(report);
  runMarketReportAutoValidation_(report, expectedHour);
  verifyMarketReportSourceDocReadback_(report);
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const key = report.date + '_' + report.time.replace(':', '-');
    const path = 'reports/' + key + '.json';
    const existing = getGitHubJsonFile_(path);
    const old = existing.data && !Array.isArray(existing.data) &&
      (existing.data.latestReport || existing.data.report || existing.data);
    if (existing.sha && old && old.date && old.time) {
      const oldRevision = Number(old.revision || 0);
      const newRevision = Number(report.revision || 0);
      if (oldRevision > newRevision ||
          (oldRevision === newRevision && old.bodyHash !== report.bodyHash)) {
        throw new Error('Existing archived revision conflicts: ' + path);
      }
    }
    report.report_status = 'PUBLISHED';
    report.infographic_status = 'NOT_READY';
    delete report.infographic;
    // Commit canonical first; safe to retry if the index write fails.
    putGitHubJsonFile_(path, JSON.stringify(report, null, 2) + '\n',
      existing.sha, 'Recover archived market report ' + key);
    const index = getGitHubJsonFile_('reports.json');
    const list = normalizeWebReportList_(index.data);
    const next = upsertWebReportList_(list, report);
    putGitHubJsonFile_('reports.json', JSON.stringify(next, null, 2) + '\n',
      index.sha, 'Recover report history index ' + key);
    if (!marketReportAutoVerifyPublishedSource_(file, expectedHour)) {
      throw new Error('Archival GitHub readback did not match Drive source: ' + key);
    }
    return {ok: true, skipped: false};
  } finally {
    lock.releaseLock();
  }
}

function publishMarketReportSlot_(hour, mode, throwOnError, targetDate) {
  const now = new Date();

  try {
    const file = findMarketReportDocForAutoPublishSlot_(hour, targetDate);

    if (!file) {
      const missing = {
        ok: false,
        skipped: false,
        retryable: true,
        status: 'WAITING_INPUT',
        mode: mode,
        reason: 'Google Docs file for this slot was not found yet.',
        slot: formatMarketReportAutoSlot_(now, hour)
      };
      if (throwOnError) throw new Error(missing.reason + ' ' + missing.slot);
      return saveMarketReportSlotResult_(missing, mode);
    }

    const fileVersion = String(file.getLastUpdated().getTime());
    const publishedVersionKey = MARKET_REPORT_AUTO_CONFIG.publishedPrefix + file.getId();
    const props = PropertiesService.getScriptProperties();

    if (props.getProperty(publishedVersionKey) === fileVersion &&
        marketReportAutoVerifyPublishedSource_(file, hour)) {
      return saveMarketReportSlotResult_({
        ok: true,
        skipped: true,
        mode: mode,
        reason: 'This Google Docs version is already published.',
        slot: formatMarketReportAutoSlot_(now, hour),
        fileName: file.getName(),
        fileUpdatedAt: formatMarketReportAutoDateTime_(file.getLastUpdated())
      }, mode);
    }

    const report = buildWebReportFromGoogleDoc_(file);
    const validation = runMarketReportAutoValidation_(report, hour);
    const result = publishWebReportObject_(report);
    props.setProperty(publishedVersionKey, fileVersion);

    return saveMarketReportSlotResult_({
      ok: true,
      skipped: false,
      mode: mode,
      slot: formatMarketReportAutoSlot_(now, hour),
      fileName: file.getName(),
      fileUpdatedAt: formatMarketReportAutoDateTime_(file.getLastUpdated()),
      reportDate: report.date,
      reportTime: report.time,
      validationWarnings: validation.warnings || [],
      commitSha: result.commitSha,
      dashboardCommitSha: result.dashboardCommitSha || '',
      pagesUrl: result.pagesUrl
    }, mode);
  } catch (error) {
    const waitingForInput = /Google Docs file for this slot was not found yet\./.test(String(error && error.message || ''));
    const payload = saveMarketReportSlotResult_({
      ok: false,
      skipped: false,
      retryable: waitingForInput,
      status: waitingForInput ? 'WAITING_INPUT' : 'FAILED',
      mode: mode,
      slot: formatMarketReportAutoSlot_(now, hour),
      error: error.message,
      stack: error.stack || ''
    }, mode);

    if (throwOnError) throw error;
    return payload;
  }
}

function marketReportAutoVerifyPublishedSource_(file, expectedHour) {
  // A local success marker is not proof that GitHub retained the transaction.
  // Check the source-linked canonical and indexed item before skipping a retry.
  try {
    if (typeof getGitHubJsonFile_ !== 'function' ||
        typeof normalizeWebReportList_ !== 'function') return false;
    const report = buildWebReportFromGoogleDoc_(file);
    marketReportVerifyProducerProof_(report);
    if (Number(String(report.time).slice(0, 2)) !== Number(expectedHour)) return false;
    const key = report.date + '_' + report.time.replace(':', '-');
    const canonicalResponse = getGitHubJsonFile_('reports/' + key + '.json');
    const stored = canonicalResponse && canonicalResponse.data;
    const canonical = stored && (stored.latestReport || stored.report || stored);
    if (!canonical || !canonicalResponse.sha) return false;
    if (canonical.date !== report.date || canonical.time !== report.time ||
        canonical.title !== report.title) return false;
    if (!canonical.sourceDocument || canonical.sourceDocument.id !== file.getId()) return false;
    if (String(canonical.revision || '') !== String(report.revision || '')) return false;
    // Validate that the original document text has not changed since publication.
    if (typeof marketReportSha256_ !== 'function') return false;
    const expectedHash = marketReportSha256_(
      Utilities.newBlob(report.fullText, 'text/plain').getBytes());
    if (canonical.bodyHash !== expectedHash) return false;
    const indexResponse = getGitHubJsonFile_('reports.json');
    const matches = normalizeWebReportList_(indexResponse.data).filter(function(item) {
      return item.date === report.date && item.time === report.time &&
        item.bodyHash === expectedHash && item.sourceDocument &&
        item.sourceDocument.id === file.getId();
    });
    return matches.length === 1;
  } catch (error) {
    console.warn('Report remote readback unavailable; republishing is required: ' + error.message);
    return false;
  }
}

function saveMarketReportSlotResult_(result, mode) {
  if (mode === 'scheduled') {
    saveMarketReportAutoResult_(result);
  }
  return result;
}

function runMarketReportAutoValidation_(report, expectedHour) {
  if (typeof validateMarketReportBeforePublish_ === 'function') {
    return validateMarketReportBeforePublish_(report, expectedHour);
  }

  // Fail closed: publication cannot proceed without the full source validator.
  throw new Error('validateMarketReportBeforePublish_ is unavailable; publication blocked.');
}

function findLatestMarketReportDocForAutoPublish_() {
  const candidates = buildMarketReportAutoCandidateInfos_();
  let latest = null;
  let latestInfo = null;

  candidates.forEach(info => {
    const file = findMarketReportAutoBestFileByName_(info.name) ||
      findMarketReportAutoBestFileByPattern_(info.date, Number(info.time.slice(0, 2)));
    if (!file) return;

    if (
      !latestInfo ||
      info.key > latestInfo.key ||
      (info.key === latestInfo.key && file.getLastUpdated().getTime() > latest.getLastUpdated().getTime())
    ) {
      latest = file;
      latestInfo = info;
    }
  });

  return latest;
}

function findMarketReportDocForAutoPublishSlot_(hour, targetDate) {
  const now = new Date();
  const dateText = targetDate || Utilities.formatDate(now, MARKET_REPORT_AUTO_CONFIG.timezone, 'yyyy-MM-dd');
  const name = marketReportAutoDocName_(dateText, hour);
  return findMarketReportAutoBestFileByName_(name) ||
    findMarketReportAutoBestFileByPattern_(dateText, hour);
}

function findMarketReportAutoBestFileByName_(name) {
  const files = DriveApp.getFilesByName(name);
  let best = null;

  while (files.hasNext()) {
    const file = files.next();
    if (file.isTrashed()) continue;
    if (file.getMimeType() !== MimeType.GOOGLE_DOCS) continue;
    if (!best || file.getLastUpdated().getTime() > best.getLastUpdated().getTime()) {
      best = file;
    }
  }

  return best;
}

function findMarketReportAutoBestFileByPattern_(dateText, hour) {
  const tokens = [
    dateText,
    dateText.replace(/-/g, '/'),
    dateText.replace(/-/g, '')
  ];
  let best = null;

  tokens.forEach(token => {
    const files = searchMarketReportAutoFilesContaining_(token);
    while (files.hasNext()) {
      const file = files.next();
      if (file.isTrashed()) continue;
      if (file.getMimeType() !== MimeType.GOOGLE_DOCS) continue;
      if (!isMarketReportAutoSlotName_(file.getName(), dateText, hour)) continue;
      if (!best || file.getLastUpdated().getTime() > best.getLastUpdated().getTime()) {
        best = file;
      }
    }
  });

  return best;
}

function searchMarketReportAutoFilesContaining_(token) {
  return DriveApp.searchFiles(
    "title contains '" + escapeMarketReportAutoDriveQuery_(token) + "' and " +
    "mimeType = 'application/vnd.google-apps.document' and trashed = false"
  );
}

function isMarketReportAutoSlotName_(name, dateText, hour) {
  const normalized = String(name)
    .replace(/\uff1a/g, ':')
    .replace(/\u2010|\u2011|\u2012|\u2013|\u2014|\u2212/g, '-');
  const dateSlash = dateText.replace(/-/g, '/');
  const dateCompact = dateText.replace(/-/g, '');
  const hourText = ('0' + hour).slice(-2);
  const hasDate = normalized.indexOf(dateText) !== -1 ||
    normalized.indexOf(dateSlash) !== -1 ||
    normalized.indexOf(dateCompact) !== -1;
  const hasTime = normalized.indexOf('_' + hourText + '-00') !== -1 ||
    normalized.indexOf(hourText + '-00') !== -1 ||
    normalized.indexOf(hourText + ':00') !== -1 ||
    normalized.indexOf(hourText + '\u6642') !== -1;

  return hasDate && hasTime;
}

function escapeMarketReportAutoDriveQuery_(text) {
  return String(text).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function buildMarketReportAutoCandidateNames_() {
  return buildMarketReportAutoCandidateInfos_().map(info => info.name);
}

function buildMarketReportAutoCandidateInfos_() {
  const now = new Date();
  const candidates = [];

  for (let i = 0; i < MARKET_REPORT_AUTO_CONFIG.lookbackDays; i += 1) {
    const date = new Date(now.getTime());
    date.setDate(date.getDate() - i);
    const dateText = Utilities.formatDate(date, MARKET_REPORT_AUTO_CONFIG.timezone, 'yyyy-MM-dd');

    MARKET_REPORT_AUTO_CONFIG.reportHours.forEach(hour => {
      const time = ('0' + hour).slice(-2) + ':00';
      candidates.push({
        name: marketReportAutoDocName_(dateText, hour),
        date: dateText,
        time: time,
        key: dateText + ' ' + time
      });
    });
  }

  return candidates;
}

function marketReportAutoDocName_(dateText, hour) {
  const prefix = (typeof WEB_REPORT_CONFIG !== 'undefined' && WEB_REPORT_CONFIG.prefix)
    ? WEB_REPORT_CONFIG.prefix
    : '\u30de\u30fc\u30b1\u30c3\u30c8\u30ec\u30dd\u30fc\u30c8_';
  return prefix + dateText + '_' + ('0' + hour).slice(-2) + '-00';
}

function isScheduledMarketReportSlot_(day, hour) {
  if (day === 6 || day === 7) return false;
  return MARKET_REPORT_AUTO_CONFIG.reportHours.includes(hour);
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
    .concat(MARKET_REPORT_AUTO_CONFIG.retryHandlers)
    .concat(MARKET_REPORT_AUTO_CONFIG.legacyHandlers)
    .map(item => item.name)
    .concat([MARKET_REPORT_AUTO_CONFIG.watchdogHandler]);
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
