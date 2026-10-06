const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, {id, textContent:'', innerHTML:'', className:'', querySelectorAll:()=>[], addEventListener:()=>{}});
  return elements.get(id);
};
const timers = [];
let fetchMode = 'pending';
const context = {window: {dispatchEvent:()=>{}}, document:{getElementById:element}, URL, URLSearchParams, AbortController,
  location:{href:'https://example.test/report.html',search:''}, history:{replaceState:()=>{}}, CustomEvent:function(){},
  setTimeout:fn=>{timers.push(fn);return timers.length;}, clearTimeout:()=>{},
  fetch:async()=>fetchMode==='body-pending' ? {ok:true,json:()=>new Promise(()=>{})} : new Promise(()=>{})};
vm.createContext(context);
vm.runInContext(fs.readFileSync('assets/js/report-core-v3.js','utf8'), context);
const registry = JSON.parse(fs.readFileSync('config/report_heading_registry.json','utf8'));
const gas = {Utilities:{formatDate:()=>''}};
vm.createContext(gas);
vm.runInContext(fs.readFileSync('apps-script/MarketReportContext.gs','utf8'), gas);
vm.runInContext(fs.readFileSync('apps-script/MarketReportWebSync.gs','utf8'), gas);
vm.runInContext(fs.readFileSync('apps-script/MarketReportStructuredImport.gs','utf8'), gas);
const explicitContext={report_date:'2026-10-02',report_time:'21:00',report_id:'2026-10-02_21-00',data_cutoff:'2026-10-02T20:55:00+09:00',previous_report_id:'2026-10-02_16-00',previous_business_day:'2026-10-01',revision:2,mode:'recovery'};
assert(Object.isFrozen(gas.validateImmutableReportContext_(explicitContext)));
assert.strictEqual(gas.marketReportDocInfoFromName_('マーケットレポート_2026-10-02_21-00',explicitContext).date,'2026-10-02');
assert.strictEqual(gas.mrExtractIdentity_('マーケットレポート_2026-10-02_21-00','本文',explicitContext).time,'21:00');
assert.throws(()=>gas.marketReportDocInfoFromName_('マーケットレポート_2026-10-01_21-00',explicitContext),/identity mismatch/);
assert.throws(()=>gas.validateImmutableReportContext_({...explicitContext,report_date:'2026-10-04',report_id:'2026-10-04_21-00',mode:'new'}),/weekend/);
for (const alias of registry.sections['主要市場データ']) {
  assert(context.headingInfo(alias), `JS plain heading: ${alias}`);
  assert(context.isMarketSection(alias), `JS market heading: ${alias}`);
  assert(gas.looksLikeHeading_(alias), `GAS plain heading: ${alias}`);
}
for (const aliases of Object.values(registry.sections)) {
  for (const alias of aliases) {
    assert(context.headingInfo(alias), `JS shared heading fixture: ${alias}`);
    assert(gas.looksLikeHeading_(alias), `GAS shared heading fixture: ${alias}`);
  }
}
const report = JSON.parse(fs.readFileSync('tests/fixtures/2026-10-02_08-00.json','utf8'));
const rows = context.legacyMarketRowsFromFullText(report);
for (const label of ['金','BTCUSD']) {
  const row = rows.find(r=>r.label===label);
  assert(row, `${label} retained as explicit unavailable`);
  assert.notStrictEqual(row.value, '08');
  assert.strictEqual(row.direction, 'UNAVAILABLE');
}
assert(rows.find(r=>r.label==='BTCUSD').value.includes('取得できない'));
assert.strictEqual(context.legacyMarketRowsFromFullText({fullText:'ニュース\n金利は08:00に上昇。BTCUSDは08:00。\n'}).length,0);
assert.strictEqual(context.legacyMarketRowsFromFullText({fullText:'主要市場データ\n金利：08:00に上昇\nBTCUSD：取得不能（08:00時点）'}).find(r=>r.label==='BTCUSD').direction,'UNAVAILABLE');
const preferred = {marketDataTable:{rows:[{label:'金',value:'table',change:0,rate:0}]},markets:[{name:'金',price:'markets'}],fullText:'主要市場データ\n金：4200ドル'};
assert.strictEqual(context.marketRows(preferred)[0].value,'table');
delete preferred.marketDataTable;
assert.strictEqual(context.marketRows(preferred)[0].value,'markets');
delete preferred.markets;
assert.strictEqual(context.legacyMarketRowsFromFullText(preferred)[0].value,'4200ドル');
const html = context.renderMarketTable(report, [], '主要市場データ');
assert(html.includes('market-table-wrap') && html.includes('market-table-five'));
assert(!/<td>08<\/td>/.test(html));
async function run() {
  timers.shift()();
  await new Promise(resolve=>setImmediate(resolve));
  assert(element('app').innerHTML.includes('タイムアウト'), 'timeout becomes visible error');
  fetchMode = 'body-pending';
  const pending = context.loadReportsWithTimeout('fixture',10);
  timers.shift()();
  await assert.rejects(pending,/タイムアウト/);
  console.log('Report foundation UI: shared aliases, real 08 fixture, precedence, unavailable, timeout including body passed.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
