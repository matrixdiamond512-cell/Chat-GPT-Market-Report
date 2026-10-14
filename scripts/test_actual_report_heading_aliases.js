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
const actualOctober14 = context.marketReportPrePublishHeadingLines_([
  '6．金利・為替・クロスアセットの因果関係',
  '10．主要6市場の短期見通し（条件付き）'
].join('\n'));
assert(actualOctober14.includes('クロスアセット資金フロー'), '08:00 causal-flow heading alias');
assert(actualOctober14.includes('6市場の見通し'), '12:00 conditional six-market heading alias');
const actualEvening = context.marketReportPrePublishHeadingLines_([
  '7．金利・為替・クロスアセット資金フロー',
  '14．NY時間への引き継ぎ・リスク管理'
].join('\n'));
assert(actualEvening.includes('金利・為替・クロスアセット資金フロー'), '21:00 combined interest/flow heading alias');
assert(actualEvening.includes('NY時間への引き継ぎ・リスク管理'), '21:00 combined handover heading alias');
assert(context.marketReportPrePublishHasHeading_(actualEvening, /^(?:金利|金利分析|金利・為替|金利・為替の連動|重要ニュース・金利|金利・為替・クロスアセット資金フロー)$/));
assert(context.marketReportPrePublishHasHeading_(actualEvening, /^(?:クロスアセット|クロスアセット資金フロー|資金フロー|金利・為替・クロスアセットの因果関係|金利・為替・クロスアセット資金フロー)$/));
assert(context.marketReportPrePublishHasHeading_(actualEvening, /^(?:(?:NY時間|NY市場|翌東京時間|明日|次の時間帯)への引き継ぎ)(?:・リスク管理)?$/));
const proseOnly = context.marketReportPrePublishHeadingLines_([
  '本文では金利・為替・クロスアセットの因果関係を確認する。',
  '本文では主要6市場の短期見通し（条件付き）を説明する。'
].join('\n'));
assert(!proseOnly.includes('クロスアセット資金フロー'));
assert(!proseOnly.includes('6市場の見通し'));
const eveningProse = context.marketReportPrePublishHeadingLines_('本文では金利・為替・クロスアセット資金フローとNY時間への引き継ぎ・リスク管理について説明する。');
assert(!context.marketReportPrePublishHasHeading_(eveningProse, /^(?:クロスアセット|クロスアセット資金フロー|資金フロー|金利・為替・クロスアセットの因果関係|金利・為替・クロスアセット資金フロー)$/));
assert(!context.marketReportPrePublishHasHeading_(eveningProse, /^(?:(?:NY時間|NY市場|翌東京時間|明日|次の時間帯)への引き継ぎ)(?:・リスク管理)?$/));
assert.strictEqual(context.marketReportPrePublishSectionBody_('6．金利・為替・クロスアセットの因果関係', /^金利・為替・クロスアセットの因果関係$/), '');
const causalSource = [
  '6．金利・為替・クロスアセットの因果関係',
  '金利低下はドルの上昇圧力を和らげる。一方、原油供給リスクは金利上昇を通じて株式に逆風となる。',
  '7．材料と値動きの整合性'
].join('\n');
const causalBody = context.marketReportPrePublishSectionBody_(causalSource, /^金利・為替・クロスアセットの因果関係$/);
assert(causalBody.length >= 20 && /[。！？]/.test(causalBody), 'causal section requires meaningful body');
const handoverSource = [
  '14．NY時間への引き継ぎ・リスク管理',
  '次の米国時間に向け、金利と為替の変化を確認し、急変時はポジションを縮小する。',
  '15．結論'
].join('\n');
const handoverBody = context.marketReportPrePublishSectionBody_(handoverSource, /^(?:(?:NY時間|NY市場|翌東京時間|明日|次の時間帯)への引き継ぎ)(?:・リスク管理)?$/);
assert(handoverBody.length >= 20 && /[。！？]/.test(handoverBody), 'handover section requires meaningful body');
const outlookSource = [
  '11．主要6市場の短期見通し（条件付き）',
  '金：中立。米金利とドルの動きを確認し、CPI上振れ時は下落リスクを見る。',
  'WTI原油：中立。供給懸念の継続と在庫統計の変化を見て方向を判断する。',
  '日経225先物（大阪）：中立。重要な価格節目を維持できるか確認する。',
  'USD/JPY：中立。米金利差と発表前後のドル需給を確認する。',
  'EUR/USD：中立。米欧の政策差と経済指標の影響を確認する。',
  'BTCUSD：中立。株式との相関と市場流動性の変化を確認する。',
  '12．シナリオ'
].join('\n');
const outlookBody = context.marketReportPrePublishSectionBody_(outlookSource, /^(?:主要)?6市場の短期見通し(?:（.*）)?$/);
assert(outlookBody.length >= 180, 'six-market outlook requires substantive body');
for (const pattern of [/^金\s*[：:][^\n]*/m, /^WTI原油\s*[：:][^\n]*/m,
  /^日経225先物[^\n：:]*\s*[：:][^\n]*/m, /^USD\/JPY\s*[：:][^\n]*/m,
  /^EUR\/USD\s*[：:][^\n]*/m, /^BTCUSD\s*[：:][^\n]*/m]) {
  const match = outlookBody.match(pattern);
  assert(match && match[0].trim().length >= 8, 'six-market section has empty or missing row');
}
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
