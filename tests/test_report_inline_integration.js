const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const index = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const dashboard = fs.readFileSync(path.join(root, 'assets/js/top-dashboard.js'), 'utf8');
const reportCore = fs.readFileSync(path.join(root, 'assets/js/report-core-v3.js'), 'utf8');
const contentCss = fs.readFileSync(path.join(root, 'assets/css/report-content-inline.css'), 'utf8');

assert.match(index, /<body data-report-inline="dashboard">/);
assert.match(index, /<div id="app" class="empty">/);
assert.doesNotMatch(index, /<iframe\b|reportDocumentFrame|report-inline-integration\.js/,
  'report body is part of the dashboard DOM; a nested page is forbidden');
assert.equal((index.match(/id="dateInput"/g) || []).length, 1, 'there is one date selector');
assert.equal((index.match(/id="timeTabs"/g) || []).length, 1, 'there is one time selector');
assert.match(dashboard, /MarketDashboardSelectedReport = report/);
assert.match(dashboard, /market-dashboard-report-selected/);
assert.match(reportCore, /dashboardInlineMode\(\)/);
assert.match(reportCore, /acceptDashboardReport_\(window\.MarketDashboardSelectedReport\)/);
assert.match(reportCore, /isPublicReport\(report\) \|\| isArchivedRecovery\(report\)/,
  'inline rendering retains the existing publication/archive eligibility gate');
assert.match(contentCss, /\.report-inline \.report-body/);
assert.match(contentCss, /\.report-inline \.archive-provenance/,
  'archival recovery provenance stays visible in the same page');

process.stdout.write('report same-DOM integration contract: PASS\n');
