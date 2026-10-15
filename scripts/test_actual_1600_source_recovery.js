const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync('tests/fixtures/market_report_20261013_1600_original.txt', 'utf8');
const context = {
  Utilities: { formatDate: () => '2026-10-13 23:00:00' },
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
assert.throws(() => context.validateMarketReportBeforePublish_(report, 16), /TIMELINE_CHECK/,
  'The historical price/time list must not pass as an explanatory timeline');
const timelinePeriods = [
  '寄り付き前', '寄り付き', '前場序盤', '前場中盤', '前引け',
  '後場序盤', '後場中盤', '大引け', '欧州への引き継ぎ'
];
const timelineHeader = '|時間帯|JST時間範囲/観測制約|出来事・確認可能な市場状態|市場・業種・銘柄の反応|相場上の意味・主導要因|時刻・出典・観測制約|次の時間帯への引き継ぎ|';
const timelineRows = timelinePeriods.map((period, index) =>
  `|${period}|${8 + index}:00-${9 + index}:00|市場材料を確認し、売買の変化を観測しました。|日経先物が下落し、半導体株への売りが広がりました。|金利と株価の連動を示し、次の時間帯も確認が必要です。|根拠 F-${index + 1}, 市場観測時刻 ${8 + index}:30。|次の時間帯は金利と先物の反応を確認します。|`
).join('\n');
const compliantReport = JSON.parse(JSON.stringify(report));
compliantReport.fullText = source.replace(
  '3．市場の動き（日本時間・時系列）',
  `3．市場の動き（日本時間・時系列）\n${timelineHeader}\n|---|---|---|---|---|---|---|\n${timelineRows}`
);
assert(context.validateMarketReportBeforePublish_(compliantReport, 16).ok,
  'A compliant narrative timeline should clear the existing source checks');
const gold = report.markets.find(m => m.name === '金');
const nikkei = report.markets.find(m => m.name === '日経225先物');
assert(gold.price.includes('4,193.80ドル'), 'Gold must retain the observed quote, not the 4,220 watch level');
assert(nikkei.price.includes('67,960円') && nikkei.price.includes('15:45'), 'Futures must retain settlement timestamp');
for (const market of report.markets) assert(market.outlook, 'Original outlook was not extracted for ' + market.name);
assert(report.handover.some(x => x.includes('欧州株・米半導体株先物')));
// Aliases apply to explicit headings only, never incidental prose mentions.
assert(!context.marketReportPrePublishHeadingLines_('代替シナリオ・崩れる条件を確認する。').includes('代替シナリオ'));
const missingHandover = JSON.parse(JSON.stringify(compliantReport));
missingHandover.fullText = compliantReport.fullText.replace('14．21:00への引き継ぎ', '14．別項目');
assert.throws(() => context.validateMarketReportBeforePublish_(missingHandover, 16), /NY時間への引き継ぎ/);
const missingScenario = JSON.parse(JSON.stringify(compliantReport));
missingScenario.fullText = compliantReport.fullText.replace('12．代替シナリオ・崩れる条件', '12．別項目');
assert.throws(() => context.validateMarketReportBeforePublish_(missingScenario, 16), /代替シナリオ/);
const missingPrice = JSON.parse(JSON.stringify(compliantReport));
missingPrice.markets.find(m => m.name === '金').price = '';
assert.throws(() => context.validateMarketReportBeforePublish_(missingPrice, 16), /価格・水準が空/);
const forbidden = JSON.parse(JSON.stringify(compliantReport));
forbidden.fullText += '\n未確認の21時価格';
assert.throws(() => context.validateMarketReportBeforePublish_(forbidden, 16), /内部用語/);
console.log('Actual 16:00 original recovery and fail-closed controls PASS');
