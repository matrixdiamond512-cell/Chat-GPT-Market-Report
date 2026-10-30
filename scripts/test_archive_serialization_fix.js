const fs=require('fs'),assert=require('assert');
const s=fs.readFileSync('apps-script/MarketReportAutoPublish.gs','utf8');
const i=s.indexOf('function archiveMarketReportFromDriveWithoutLatestRollback_(');
const j=s.indexOf('function publishMarketReportSlot_(',i);
assert(i>=0&&j>i);
const body=s.slice(i,j);
const invalid=String.fromCharCode(92,92,110);
assert(!body.includes(" + '"+invalid+"'"));
console.log('Archive writer newline check PASS');
