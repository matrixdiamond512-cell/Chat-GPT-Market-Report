// Regression test for the actual Apps Script publisher helper, no network required.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const source = fs.readFileSync('apps-script/UsdJpyVolumeJsonFlexibleSync.gs', 'utf8');
const match = source.match(/function usdJpyVolumeFlexiblePreservePublishedPrices_\([\s\S]*?\n}\n/);
assert.ok(match, 'Apps Script preservation helper is present');
const preserve = vm.runInNewContext(match[0] + '\n usdJpyVolumeFlexiblePreservePublishedPrices_;');
const good = (targetDate, close = 158.06) => ({
  targetDate, spotVolume: 3200, open: 158.10, high: 158.35,
  low: 157.60, close, priceChangePct: -0.15,
  priceSourceId: 'YAHOO_GLOBAL_USDJPY'
});
const missing = (targetDate, volume = 3400) => ({
  targetDate, spotVolume: volume, open: null, high: null,
  low: null, close: null, priceChangePct: null
});
const wrap = records => ({
  data: {records, priceRecords:[],priceSourceName:'Sheet price'},
  components:{usdjpyOhlc:{status:'warning',sourceId:'INV_USDJPY'}},
  sources:[{id:'INV_USDJPY',status:'warning'}]
});
const prior = wrap([good('2026-10-08'),good('2026-10-07',158.296)]);
prior.data.priceRecords=prior.data.records.map(r=>({date:r.targetDate, ...r}));
prior.data.priceSourceName='Yahoo Finance verified history';
prior.components.usdjpyOhlc={status:'ok',sourceId:'YAHOO_GLOBAL_USDJPY'};
prior.sources.push({id:'YAHOO_GLOBAL_USDJPY',status:'ok'});

// Volume sheet was refreshed but its OHLC cells were blank: do NOT erase price.
const next=wrap([missing('2026-10-09',4742),missing('2026-10-08',3212),missing('2026-10-07',3841)]);
const count=preserve(next,prior);
assert.equal(count,2);
assert.equal(next.data.records[1].close,158.06);
assert.equal(next.data.records[1].spotVolume,3212);
assert.equal(next.data.records[2].close,158.296);
assert.equal(next.data.priceRecords.length,2);
assert.equal(next.data.priceRange.endDate,'2026-10-08');
assert.equal(next.components.usdjpyOhlc.status,'partial');
assert.deepEqual(Array.from(next.components.usdjpyOhlc.missingLast20Dates),['2026-10-09']);
assert.equal(next.data.priceSourceName,'Yahoo Finance verified history');

// A full sheet price is newer authoritative data; do not substitute historical prices.
const sheetFull=wrap([good('2026-10-08',159.22)]);
assert.equal(preserve(sheetFull,prior),0);
assert.equal(sheetFull.data.records[0].close,159.22);
assert.equal(sheetFull.components.usdjpyOhlc.status,'ok');

// Partially populated sheet candle must be replaced as a coherent OHLC group.
const partial=wrap([{...missing('2026-10-08'),open:153.0}]);
assert.equal(preserve(partial,prior),1);
assert.equal(partial.data.records[0].open,158.10);
assert.equal(partial.data.records[0].close,158.06);
assert.equal(partial.data.records[0].priceChangePct,-0.15);
assert.equal(partial.components.usdjpyOhlc.status,'ok');
assert.equal(prior.data.records[0].close,158.06,'prior source is unchanged');

// A genuinely unknown new date must remain null, not be invented.
const fresh=wrap([missing('2026-10-15')]);
assert.equal(preserve(fresh,prior),0);
assert.equal(fresh.data.records[0].close,null);
assert.equal(fresh.components.usdjpyOhlc.status,'partial');
console.log('PASS Apps Script USDJPY price-preservation regression tests');
