const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync('apps-script/MarketReportPrePublishValidation.gs', 'utf8'), context);
const source = [
  '1．今日の相場テーマ',
  '2．主要市場データ（確認値と観測時刻）',
  '5．材料と値動きの整合性・今日の主導市場',
  '6．重要ニュースと市場への影響',
  '7．金利・為替・市場心理',
  '9．需給・ポジション・SQ・ドル円出来高',
  '10．主要6市場の短期見通し（条件付き）',
  '12．代替シナリオと崩れる条件',
  '13．今後のイベント',
  '15．結論・リスク管理',
].join('\n');
const headings = context.marketReportPrePublishHeadingLines_(source);
const expected = [
  '主要市場データ', '材料と値動きの整合性', '今日の主導市場',
  '重要ニュース', '金利・為替', '需給・ポジション',
  '6市場の見通し', '代替シナリオ', '崩れる条件',
  '今後の予定', '結論', 'リスク管理'
];
for (const heading of expected) {
  assert(headings.includes(heading), 'missing compound alias: ' + heading);
}
const bodyOnly = context.marketReportPrePublishHeadingLines_('このニュースと市場への影響は重要だが、見出しではない。');
assert(!bodyOnly.includes('重要ニュース'));
const morning = context.marketReportPrePublishHeadingLines_([
  '2．前営業日終値一覧と基準時刻',
  '4．前回21:00からの変化',
  '15．12:00への引き継ぎ・リスク管理',
  '16．結論・クロスチェック'
].join('\n'));
for (const h of ['主要市場データ', '21:00からの変化', '12:00への引き継ぎ', 'リスク管理', '結論']) {
  assert(morning.includes(h), h);
}
console.log('Actual source headings and fail-closed negative control PASS');
