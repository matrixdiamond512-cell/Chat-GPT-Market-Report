const fs = require('fs');
const vm = require('vm');

const context = {
  Utilities: { formatDate: () => '2026-09-26 00:00:00' },
  SpreadsheetApp: { getUi: () => ({ alert: () => {} }) },
};
vm.createContext(context);
for (const file of [
  'apps-script/MarketReportWebSync.gs',
  'apps-script/MarketReportPrePublishValidation.gs',
]) {
  vm.runInContext(fs.readFileSync(file, 'utf8'), context, { filename: file });
}

const fullText = [
  'マーケットレポート｜2026/09/25（金）21:00',
  '作成基準：日本時間21:00',
  '1．16:00からの変化',
  '東京市場の上昇が広がり、米金利は低下しました。',
  '2．今日の相場テーマ',
  '高金利相場から金融株も含む上昇へ移るかを確認します。',
  '3．材料と値動きの整合性',
  '材料と値動きは概ね整合しています。',
  '4．今日の主導市場',
  '東京市場の後は米国債市場が主導します。',
  '5．重要ニュース',
  '日経平均は上昇し、銀行株にも買いが広がりました。',
  '6．金利・為替',
  '米10年債利回りは5.16%近辺へ低下しました。',
  '7．クロスアセット資金フロー',
  '日本株は上昇し、米債利回りとドルは低下しました。',
  '8．需給・ポジション',
  '市場全体は強い一方、上昇寄与は半導体株に偏っています。',
  '9．その日の重要イベント',
  '21:30に米国の耐久財受注が発表されます。',
  '10．6市場の見通し',
  '金：中立～やや強気',
  '金先物は25日に4,300ドル台で推移しています。',
  'WTI原油：短期弱気、中期高ボラティリティ',
  '25日は93ドル近辺へ反落しました。',
  '日経225先物（大阪取引所）：基調強気',
  '日中ラージは66,300円で終了し、前日比+840円でした。',
  'USD/JPY：中立～やや円高方向',
  '157.95円まで調整し、158円近辺が攻防点です。',
  'EUR/USD：中立～やや強気',
  '17時に1.1390まで上昇しました。',
  'BTCUSD：中立～やや弱気',
  'BTCは84,000ドル台で推移しています。',
  '11．メインシナリオ',
  'メインシナリオは、',
  '米指標が極端に上振れせず、ドル円が158円前後となる展開です。',
  '12．代替シナリオ',
  '強い指標で米金利が5.20%を超える場合は株価が調整します。',
  '13．シナリオが崩れる条件',
  '日経225先物が66,000円を割れ、NASDAQ先物も弱くなる場合です。',
  '14．翌東京時間への引き継ぎ',
  'NY市場が日本株の強さを追認するかを確認します。',
  '15．結論',
  '東京市場は幅広く上昇しましたが、次は米金利が焦点です。',
  'クロスチェック結果',
  '市場データは各市場の説明に記載された確認値を使用しています。',
].join('\n') + '\n' + 'クロスチェックでは本文内の確認値を基準時刻と照合しました。'.repeat(50);

const title = 'マーケットレポート｜2026/09/25（金）21:00';
const markets = context.parseMarketsLenient_(fullText);
const named = Object.fromEntries(markets.map(market => [market.name, market]));
const expectedPrices = {
  '金': '4,300ドル台',
  '原油': '93ドル近辺',
  '日経225先物': '66,300円',
  'USD/JPY': '157.95円',
  'EUR/USD': '1.1390',
  'BTCUSD': '84,000ドル台',
};
for (const [name, expected] of Object.entries(expectedPrices)) {
  if (!named[name] || named[name].price !== expected) {
    throw new Error(`${name} narrative price mismatch: ${named[name] && named[name].price} !== ${expected}`);
  }
}

const riskManagement = context.smartSectionLines_(fullText, ['リスク管理', 'リスク要因', '注意点']);
const report = {
  date: '2026-09-25',
  time: '21:00',
  title,
  theme: context.smartSectionText_(fullText, ['今日の相場テーマ']),
  changes: context.smartSectionLines_(fullText, ['16:00からの変化']),
  consistency: context.smartSectionLines_(fullText, ['材料と値動きの整合性']),
  leadingMarket: context.smartSectionText_(fullText, ['今日の主導市場']),
  news: context.smartSectionLines_(fullText, ['重要ニュース']),
  crossAssetFlow: context.smartSectionLines_(fullText, ['クロスアセット資金フロー']),
  positioning: context.smartSectionLines_(fullText, ['需給・ポジション']),
  events: context.smartSectionLines_(fullText, ['重要イベント']),
  handover: context.smartSectionLines_(fullText, ['翌東京時間への引き継ぎ']),
  mainScenario: context.smartSectionText_(fullText, ['メインシナリオ']),
  alternativeScenario: context.smartSectionText_(fullText, ['代替シナリオ']),
  breakConditions: context.smartSectionText_(fullText, ['シナリオが崩れる条件']),
  riskManagement: riskManagement.length ? riskManagement : context.extractKeywordSentences_(fullText, ['リスク', '警戒', '注意', '崩れる', '急変'], 5),
  fullText,
  markets,
};
if (!report.mainScenario.includes('ドル円が158円前後')) {
  throw new Error('mainScenario content was mistaken for a heading or truncated');
}
context.validateMarketReportBeforePublish_(report, 21);
console.log('Apps Script narrative report parser test passed.');
