const fs=require('fs'), assert=require('assert'), vm=require('vm');
const s=fs.readFileSync('apps-script/MarketReportAutoPublish.gs','utf8');
const a=s.indexOf('function archiveMarketReportFromDriveWithoutLatestRollback_('),e=s.indexOf('\nfunction publishMarketReportSlot_',a);
assert(a>0&&e>a);const archival=s.slice(a,e);
assert(!archival.includes("data/latest-report.json"));
assert(!archival.includes("syncDashboardJsonToGitHub"));
assert(!archival.includes("publishWebReportObject_"));
const record=[];
const doc={getId:()=> 'doc1'};
const report={date:'2026-10-10',time:'08:00',title:'マーケットレポート｜2026/10/10（土）08:00',revision:'42',fullText:'original body'};
const ctx={
marketReportAutoVerifyPublishedSource_:()=>record.length===2,
buildWebReportFromGoogleDoc_:()=>({...report}),
runMarketReportAutoValidation_:()=>({}),
marketReportSha256_:()=> 'body-sha',
Utilities:{newBlob:()=>({getBytes:()=>[]})},
verifyMarketReportSourceDocReadback_:()=>true,
LockService:{getScriptLock:()=>({waitLock:()=>{},releaseLock:()=>{}})},
getGitHubJsonFile_:p=>p==='reports.json'?{sha:'index-sha',data:[]}:{sha:null,data:[]},
putGitHubJsonFile_:(...args)=>{record.push(args);return {commit:{sha:'sha'}}},
normalizeWebReportList_:x=>x,
upsertWebReportList_:(old,r)=>old.concat([r])
};
vm.createContext(ctx);vm.runInContext(archival,ctx);
const result=ctx.archiveMarketReportFromDriveWithoutLatestRollback_(doc,8);
assert.strictEqual(result.ok,true);assert.deepStrictEqual(record.map(x=>x[0]),['reports/2026-10-10_08-00.json','reports.json']);
assert(record.every(x=>!x[0].includes('latest-report')));
console.log('Older source archive readback and latest-pointer isolation PASS');
