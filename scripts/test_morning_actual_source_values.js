const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('apps-script/MarketReportPrePublishValidation.gs','utf8');
const ctx={};vm.createContext(ctx);vm.runInContext(code,ctx);
const real=[
 '1．今日の相場テーマ',
 '2．前営業日終値一覧と基準時刻',
 'NYダウ：51,850.55、前日比+195.60',
 'S&P500：7,807.24、-4.30',
 'Nasdaq総合：27,245.90、-120.27',
 'Russell2000：2,794.48、-12.50',
 '日経225現物：69,030.92円',
 'CME日経225先物：68,450円',
 '大阪取引所日経225先物12月限：68,410円',
 'WTI原油：93.74ドル',
 'COMEX金先物12月限：4,192.00ドル',
 'USD/JPY：158.64円',
 'EUR/USD：1.1156',
 'BTCUSD：82,854.85ドル',
 'VIX：15.21',
 '日経VI：30.14',
 'Fear & Greed Index：45',
 '米10年債利回り：5.24%',
 '日本10年国債利回り：3.016%',
 '日経225予想PER：17.37倍、PBR：1.90倍、予想EPS：3,974.15円',
 '日経225・25日移動平均乖離率：+4.23%。200日乖離率：+13.55%',
 '東証プライム値上がり銘柄1,194、値下がり331（10/9）、25日騰落レシオ91.20（投資の森）。売買代金7兆8,454億円、売買高22億9,519万株は前回参照値。',
 '3．昨夜NY市場の時系列',
 'この節にだけ存在する他の市場はデータ行の代わりにならない'
].join('\n');
const required=ctx.MARKET_REPORT_PREPUBLISH_CONFIG.morningRequiredLabels;
const missing=required.filter(rule=>!ctx.marketReportMorningHasSourceValue_(real,rule));
assert.strictEqual(missing.length,0, 'Actual source data should be recognized: '+missing.map(x=>x.label).join(', '));
const without=real.replace(/^VIX：.*\n/m,'');
assert(!ctx.marketReportMorningHasSourceValue_(without,required.find(x=>x.label==='VIX')));
const noValue=real.replace(/^NYダウ：.*\n/m,'NYダウ：\n');
assert(!ctx.marketReportMorningHasSourceValue_(noValue,required.find(x=>x.label==='NYダウ')));
console.log('Morning real-source labels, value presence and missing-data fail-closed PASS');
