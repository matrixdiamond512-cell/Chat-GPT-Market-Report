const fs = require('fs');
const vm = require('vm');

const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync('apps-script/MarketReportWebSync.gs', 'utf8'), context);\nvm.runInContext(fs.readFileSync('apps-script/MarketReportPrePublishValidation.gs', 'utf8'), context);

function sample(generatedAt, value, asOf = generatedAt) {
  return {
    generatedAt,
    reportSlot: '16:00',
    overallStatus: 'verified',
    markets: {
      usdjpy: {
        value,
        displayValue: value.toFixed(3),
        unit: '円',
        displayName: 'USD/JPY',
        sourceId: 'quote-source',
        sourceName: 'Quote source',
        sourceUrl: 'https://example.test/usdjpy',
        asOf,
        fetchedAt: generatedAt,
        verificationStatus: 'verified',
      },
    },
  };
}
function assert(ok, message) { if (!ok) throw new Error(message); }

const report = { date: '2026-10-15', time: '16:00' };
const archives = [{
  path: 'data/market/timeseries/2026-10-15_16-00.json',
  sha: 'archive-sha',
  archive: {
    schemaVersion: '1.0',
    reportDate: '2026-10-15',
    reportSlot: '16:00',
    snapshots: [
      sample('2026-10-15T15:30:00+09:00', 157.100),
      sample('2026-10-15T15:39:00+09:00', 157.250),
      sample('2026-10-15T16:01:00+09:00', 999.000),
    ],
  },
}];
const evidence = context.buildMarketTimelineEvidence_(report, archives);
assert(evidence.rows.length === 9, '16:00 timeline should contain all nine periods');
assert(evidence.observations.length === 2, 'future observation must be excluded');
const closeRow = evidence.rows.find(row => row.period === '欧州への引き継ぎ');
assert(closeRow && closeRow.reaction.includes('157.100→157.250'), 'observed same-series change missing');
assert(closeRow.evidence.includes('quote-source'), 'source lineage missing from generated row');
const emptyRow = evidence.rows.find(row => row.period === '前場序盤');
assert(emptyRow.event.includes('保存されていません') && emptyRow.reaction.includes('記述しません'),
  'empty period must remain explicitly unreported');
assert(evidence.newsStatus === 'not_collected' && evidence.news.length === 0,
  'producer must not invent or imply timestamped news');
const generated = context.renderMarketTimeline_('1．概要\n本文', evidence);
assert(generated.includes('|時間帯|JST時間範囲/観測制約|出来事・確認可能な市場状態|市場・業種・銘柄の反応|相場上の意味・主導要因|時刻・出典・観測制約|次の時間帯への引き継ぎ|'),
  'producer did not generate the seven-column timeline');
assert(generated.includes('市場時系列') && generated.includes('sourceId/asOf'), 'generated evidence table incomplete');\nconst validationIssues = context.marketReportPrePublishTimelineIssues_(generated, '16:00');\nassert(validationIssues.length === 0, 'generated seven-column timeline fails the existing publish gate: ' + JSON.stringify(validationIssues));
let failed = false;
try { context.buildMarketTimelineEvidence_(report, []); } catch (error) { failed = /検証済み時系列観測がありません/.test(error.message); }
assert(failed, 'missing time-series evidence must fail closed');
console.log('Market report timeline evidence producer tests passed.');
