const fs=require('fs'),assert=require('assert'),vm=require('vm');
const source=fs.readFileSync('apps-script/MarketReportAutoPublish.gs','utf8');
const start=source.indexOf('function marketReportAutoVerifyPublishedSource_(');
const end=source.indexOf('\nfunction saveMarketReportSlotResult_',start);
assert(start>=0 && end>start,'remote verification function exists');
const script=source.slice(start,end);
const file={getId:()=> 'document-abc'};
const report={date:'2026-10-13',time:'08:00',title:'マーケットレポート｜2026/10/13（火）08:00',revision:'123',fullText:'sample source'};
const data={...report,bodyHash:'expected-sha',sourceDocument:{id:'document-abc'}};
const ctx={
 buildWebReportFromGoogleDoc_:()=>report,
 marketReportVerifyProducerProof_:(report)=>{report.bodyHash='expected-sha'; return {revision:123}},
 marketReportSha256_:()=> 'expected-sha',
 Utilities:{newBlob:()=>({getBytes:()=>[]})},
 normalizeWebReportList_:x=>x,
 getGitHubJsonFile_:path=> path==='reports/2026-10-13_08-00.json'
   ? {sha:'gitsha',data}
   : {sha:'gitsha2',data:[data]}
};
vm.createContext(ctx);vm.runInContext(script,ctx);
assert.strictEqual(ctx.marketReportAutoVerifyPublishedSource_(file,8),true);
ctx.getGitHubJsonFile_=(path)=>path.startsWith('reports/')?{sha:null,data:null}:{sha:'gitsha2',data:[data]};
assert.strictEqual(ctx.marketReportAutoVerifyPublishedSource_(file,8),false,'lost canonical must republish');
ctx.getGitHubJsonFile_=(path)=>path.startsWith('reports/')?{sha:'gitsha',data}:{sha:'gitsha2',data:[]};
assert.strictEqual(ctx.marketReportAutoVerifyPublishedSource_(file,8),false,'lost index must republish');
ctx.getGitHubJsonFile_=(path)=>path.startsWith('reports/')?{sha:'gitsha',data}:{sha:'gitsha2',data:[data]};
ctx.buildWebReportFromGoogleDoc_=()=>({...report,fullText:'modified source'});
ctx.marketReportSha256_=()=> 'modified-sha';
assert.strictEqual(ctx.marketReportAutoVerifyPublishedSource_(file,8),false,'changed source must republish');
ctx.buildWebReportFromGoogleDoc_=()=>report;
ctx.marketReportSha256_=()=> 'expected-sha';
assert.strictEqual(ctx.marketReportAutoVerifyPublishedSource_(file,12),false,'wrong hour must fail');
assert(source.includes('marketReportAutoVerifyPublishedSource_(file, hour)'),'skip is remotely verified');
console.log('Report GitHub canonical/index recheck PASS');
