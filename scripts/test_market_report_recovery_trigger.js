const assert=require('assert');const fs=require('fs'),vm=require('vm');
const src=fs.readFileSync('apps-script/MarketReportMasterScheduler.gs','utf8');
assert(src.includes("recoveryHandler: 'runMarketReportMasterRecovery2330'"));
assert(src.includes(".atHour(23)"));
assert(src.includes("created.push(MARKET_REPORT_MASTER_SCHEDULER_CONFIG.recoveryHandler)"));
assert(src.includes(".concat([MARKET_REPORT_MASTER_SCHEDULER_CONFIG.recoveryHandler])"));
const a=src.indexOf('function runMarketReportMasterRecovery2330()'),b=src.indexOf('function runMarketReportMaster0830()',a);
assert(a>=0&&b>a);
let called=0;const ctx={MARKET_REPORT_MASTER_SCHEDULER_CONFIG:{timezone:'Asia/Tokyo'},
Utilities:{formatDate:()=> '2'},repairMissingMarketReportsFromDrive:()=>{called++;return {ok:true}},
saveMarketReportMasterResult_:x=>x};
vm.createContext(ctx);vm.runInContext(src.slice(a,b),ctx);
assert(ctx.runMarketReportMasterRecovery2330().ok);assert.strictEqual(called,1);
ctx.Utilities.formatDate=()=> '6';
assert(ctx.runMarketReportMasterRecovery2330().skipped);assert.strictEqual(called,1);
console.log('23:30 Drive-to-GitHub scheduled recovery PASS');
