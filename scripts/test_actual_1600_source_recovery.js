const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const crypto = require('node:crypto');
const source = fs.readFileSync('tests/fixtures/market_report_20261013_1600_original.txt', 'utf8');
const context = {
  Utilities: {
    DigestAlgorithm: { SHA_256: 'SHA_256' },
    formatDate: () => '2026-10-13 23:00:00',
    newBlob: (value) => ({ getBytes: () => Buffer.from(String(value || ''), 'utf8') }),
    computeDigest: (_algorithm, bytes) => [...crypto.createHash('sha256').update(Buffer.from(bytes)).digest()]
  },
  DocumentApp: { openById: () => ({ getBody: () => ({ getText: () => source }) }) }
};
vm.createContext(context);
for (const file of ['MarketReportWebSync', 'MarketReportPrePublishValidation']) {
  vm.runInContext(fs.readFileSync('apps-script/' + file + '.gs', 'utf8'), context);
}
const file = {
  getId: () => '1OMbliOnTVGpovJJ33LgD-ZEjGBjYrgxx2URhO4BSCTA',
  getName: () => 'マーケットレポート_2026-10-13_16-00',
  getUrl: () => 'https://docs.google.com/document/d/1OMbliOnTVGpovJJ33LgD-ZEjGBjYrgxx2URhO4BSCTA/edit',
  getLastUpdated: () => new Date('2026-10-13T07:12:51.770Z')
};
const report = context.buildWebReportFromGoogleDoc_(file);
assert.strictEqual(report.fullText, context.normalizeReportText_(source));
assert(context.validateMarketReportBeforePublish_(report, 16).ok);
const gold = report.markets.find(m => m.name === '金');
const nikkei = report.markets.find(m => m.name === '日経225先物');
assert(gold.price.includes('4,193.80ドル'), 'Gold must retain the observed quote, not the 4,220 watch level');
assert(nikkei.price.includes('67,960円') && nikkei.price.includes('15:45'), 'Futures must retain settlement timestamp');
for (const market of report.markets) assert(market.outlook, 'Original outlook was not extracted for ' + market.name);
assert(report.handover.some(x => x.includes('欧州株・米半導体株先物')));
// Aliases apply to explicit headings only, never incidental prose mentions.
assert(!context.marketReportPrePublishHeadingLines_('代替シナリオ・崩れる条件を確認する。').includes('代替シナリオ'));
const missingHandover = JSON.parse(JSON.stringify(report));
missingHandover.fullText = report.fullText.replace('14．21:00への引き継ぎ', '14．別項目');
assert.throws(() => context.validateMarketReportBeforePublish_(missingHandover, 16), /NY時間への引き継ぎ/);
const missingScenario = JSON.parse(JSON.stringify(report));
missingScenario.fullText = report.fullText.replace('12．代替シナリオ・崩れる条件', '12．別項目');
assert.throws(() => context.validateMarketReportBeforePublish_(missingScenario, 16), /代替シナリオ/);
const missingPrice = JSON.parse(JSON.stringify(report));
missingPrice.markets.find(m => m.name === '金').price = '';
assert.throws(() => context.validateMarketReportBeforePublish_(missingPrice, 16), /価格・水準が空/);
const forbidden = JSON.parse(JSON.stringify(report));
forbidden.fullText += '\n未確認の21時価格';
assert.throws(() => context.validateMarketReportBeforePublish_(forbidden, 16), /内部用語/);
console.log('Actual 16:00 original recovery and fail-closed controls PASS');
