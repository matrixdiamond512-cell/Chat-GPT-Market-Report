'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const file = 'apps-script/DashboardJsonSync.gs';
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync(file, 'utf8'), context, { filename: file });

// Only replace external I/O and unrelated market-data enrichment. Exercise the
// real dashboard payload, report sorting and sources construction functions.
context.dashboardFetchPriceSheetSource_ = () => ({ status: 'unavailable', asOf: '' });
context.dashboardPrepareReportForDashboard_ = report => ({ ...report });
context.dashboardIsoJst_ = () => '2026-10-14T23:30:00+09:00';
context.dashboardIsStale_ = () => false;

const older = { date: '2026-10-13', time: '08:00', title: 'Morning source' };
const latest = { date: '2026-10-13', time: '16:00', title: 'Afternoon source' };
const result = context.dashboardBuildPayloadFromReports_([older, latest]);

assert.strictEqual(result.currentReportKey, '2026-10-13_16-00',
  'dashboard key must equal report_identity.internal_report_key, never display datetime');
assert.strictEqual(result.latestReport.date, latest.date);
assert.strictEqual(result.latestReport.time, latest.time);
assert.strictEqual(result.reports.length, 1,
  'dashboard must retain a single latest report');
assert.strictEqual(result.sources[0].asOf, '2026-10-13 16:00',
  'human-readable source observation time must remain unchanged');
assert.strictEqual(result.dataAsOf, '2026-10-13T16:00:00+09:00',
  'dataAsOf must remain a timezone-aware timestamp');
assert.notStrictEqual(result.currentReportKey, result.sources[0].asOf,
  'display datetime and internal key must not be conflated');

console.log('Apps Script dashboard report-key identity PASS');
