const fs = require('fs');
const vm = require('vm');

const source = fs.readFileSync('apps-script/MarketReportPrePublishValidation.gs', 'utf8');
const context = {};
vm.createContext(context);
vm.runInContext(source, context);

const periods = {
  '08:00': ['開場前', '寄り付き', '序盤', '中盤', '終盤', '東京への引き継ぎ'],
  '12:00': ['寄り付き前', '寄り付き', '前場序盤', '前場中盤', '前引け'],
  '16:00': ['寄り付き前', '寄り付き', '前場序盤', '前場中盤', '前引け', '後場序盤', '後場中盤', '大引け', '欧州への引き継ぎ'],
  '21:00': ['欧州開場前', '欧州寄り付き', '欧州序盤', '欧州中盤', 'NY開場前'],
};
const header = [
  '時間帯', 'JST時間範囲/観測制約', '出来事・確認可能な市場状態',
  '市場・業種・銘柄の反応', '相場上の意味・主導要因',
  '時刻・出典・観測制約', '次の時間帯への引き継ぎ',
];

function buildText(slot, opts = {}) {
  const rows = [
    '1．概要', '本文', '2．市場時系列', `|${header.join('|')}|`,
    '|---|---|---|---|---|---|---|',
  ];
  periods[slot].forEach((period, index) => {
    if (opts.omit === period) return;
    let event = '市場の状態を確認し、売買材料の変化を整理した。';
    if (opts.priceOnly === period) event = '日経225 -2.4%';
    if (opts.future && index === 0) event = '発表時刻 22:30の指標結果が出て、市場が反応した。';
    if (opts.planned && index === 0) event = '22:30発表予定の指標を控え、市場は結果を待っている。';
    const evidence = opts.missingTimeClass && index === 0
      ? '時刻未確認、根拠 F-001。'
      : '市場観測時刻 09:30、根拠 F-001。';
    const cells = [
      period,
      '09:00-10:00',
      event,
      '日経先物と半導体株が売られ、為替は円高方向へ動いた。',
      '金利低下との連動を示し、次の市場の主導要因として残る。',
      evidence,
      '次の時間帯は金利と先物の反応を確認する。',
    ];
    rows.push(`|${cells.join('|')}|`);
  });
  rows.push('', '3．次の項目', '本文');
  return rows.join('\n');
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

for (const slot of Object.keys(periods)) {
  assert(context.marketReportPrePublishTimelineIssues_(buildText(slot), slot).length === 0, `${slot} valid timeline rejected`);
  const missing = context.marketReportPrePublishTimelineIssues_(buildText(slot, { omit: periods[slot][0] }), slot);
  assert(missing.some(item => item.includes('必須時間帯が不足')), `${slot} missing period accepted`);
}

const numeric = context.marketReportPrePublishTimelineIssues_(buildText('16:00', { priceOnly: '前場序盤' }), '16:00');
assert(numeric.some(item => item.includes('出来事・市場状態')), `price-only row accepted: ${JSON.stringify(numeric)}`);

const mislabeled = context.marketReportPrePublishTimelineIssues_(buildText('12:00', { missingTimeClass: true }), '12:00');
assert(mislabeled.every(item => !item.includes('時刻区分が不明')), 'unexpected timestamp check result');
const actualNewsTime = buildText('12:00', { missingTimeClass: true }).replace(
  '市場の状態を確認し、売買材料の変化を整理した。', 'ニュース10:15に掲載され、市場が反応した。');
assert(context.marketReportPrePublishTimelineIssues_(actualNewsTime, '12:00').some(item => item.includes('時刻区分が不明')),
  'news publication time was accepted without a separate event/observation classification');

assert(context.marketReportPrePublishTimelineIssues_(buildText('21:00', { future: true }), '21:00')
  .some(item => item.includes('21:00時点より後')), 'future event accepted as observed in the 21:00 report');
assert(!context.marketReportPrePublishTimelineIssues_(buildText('21:00', { planned: true }), '21:00')
  .some(item => item.includes('21:00時点より後')), 'planned future event was rejected');

console.log('Market report timeline validation passed for all four slots and negative cases.');
