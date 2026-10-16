const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const source = fs.readFileSync('apps-script/DashboardJsonSync.gs', 'utf8');
const context = {
  Date,
  JSON,
  Utilities: {
    formatDate(date, _timezone, pattern) {
      const day = date.toISOString().slice(0, 10);
      if (pattern === 'yyyy-MM-dd') return day;
      return `${day}T00:00:00+09:00`;
    }
  }
};
vm.createContext(context);
vm.runInContext(source, context);

const report = {
  date: '2020-01-01',
  time: '08:00',
  title: 'Canonical report',
  bodyHash: 'a'.repeat(64),
  fullText: 'Original report body',
  markets: [{ name: '金', price: '4,200ドル', outlook: '条件Aなら上昇' }]
};
const payload = JSON.parse(context.buildDashboardJsonFromReports_([report]));
assert.deepStrictEqual(payload.latestReport, report,
  'dashboard latestReport must be an exact copy of the canonical report');
assert.deepStrictEqual(payload.reports, [report],
  'dashboard reports must preserve the canonical report object');
assert.strictEqual(payload.currentReportKey, '2020-01-01_08-00',
  'dashboard report key must use the canonical slot identity');
console.log('Dashboard canonical report projection tests passed.');
