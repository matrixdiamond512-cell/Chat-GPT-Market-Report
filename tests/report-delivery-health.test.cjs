const test = require('node:test');
const assert = require('node:assert/strict');
const { assess } = require('../assets/js/report-delivery-health.js');
const schedule = require('../config/report_schedule.json');
test('fresh JSON ages at the next slot even without a rebuild', () => {
  const dashboard = { dataAsOf: '2026-11-24T08:00:00+09:00', isStale: false };
  assert.equal(assess(dashboard, schedule, new Date('2026-11-24T11:59:59+09:00')).behind, false);
  assert.equal(assess(dashboard, schedule, new Date('2026-11-24T12:00:00+09:00')).behind, true);
});
test('weekends and Monday morning retain Friday evening', () => {
  for (const now of ['2026-11-28T12:00:00+09:00','2026-11-29T22:00:00+09:00','2026-11-30T07:59:59+09:00']) {
    const result = assess({dataAsOf:'2026-11-27T21:00:00+09:00'}, schedule, new Date(now));
    assert.equal(result.expected, '2026-11-27 21:00'); assert.equal(result.behind, false);
  }
});
test('old healthy flags, missing and future data do not claim current delivery', () => {
  for (const dataAsOf of ['', '2026-10-13T16:00:00+09:00', '2026-11-25T12:00:00+09:00']) {
    assert.equal(assess({dataAsOf,isStale:false,status:'ok'},schedule,new Date('2026-11-24T12:00:00+09:00')).behind,true);
  }
});

test('current dataAsOf alone never verifies formal publication or Pages', () => {
  const d = {dataAsOf:'2026-11-24T12:00:00+09:00'};
  const now=new Date('2026-11-24T12:05:00+09:00');
  assert.equal(assess(d,schedule,now).formalPublication,'UNVERIFIED');
  for (const report_status of ['DOC_READBACK_PASS','SOURCE_ARCHIVED','DOC_READBACK_FAIL']) {
    const value=assess({...d,latestReport:{date:'2026-11-24',time:'12:00',report_status}},schedule,now);
    assert.equal(value.formalPublication,'UNVERIFIED');assert.equal(value.pagesDisplay,'NOT_VERIFIED');
  }
});
test('matching repository evidence does not imply Pages DOM acceptance', () => {
  const report={date:'2026-11-24',time:'12:00',report_status:'DOC_READBACK_PASS',bodyHash:'fixture-hash',revision:1};
  const formal={state:'VERIFIED',canonical:'PASS',receipt:'PASS',index:'PASS',reportKey:'2026-11-24_12-00',bodyHash:'fixture-hash',revision:1};
  const d={dataAsOf:'2026-11-24T12:00:00+09:00',latestReport:report,reportDelivery:{formalPublication:formal,pagesDisplay:{state:'VERIFIED'}}};
  const now=new Date('2026-11-24T12:05:00+09:00');
  assert.equal(assess(d,schedule,now).formalPublication,'VERIFIED');
  assert.equal(assess(d,schedule,now).pagesDisplay,'NOT_VERIFIED');
  assert.equal(assess({...d,latestReport:{...report,revision:2}},schedule,now).formalPublication,'UNVERIFIED');
});
