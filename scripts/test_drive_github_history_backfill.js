const assert=require('assert');const fs=require('fs');const vm=require('vm');
const s=fs.readFileSync('apps-script/MarketReportAutoPublish.gs','utf8');
assert(s.includes('function repairMissingMarketReportsFromDrive()'));
assert(s.includes("getGitHubJsonFile_('data/latest-report.json')"));
assert(s.includes('if (publishedKey && slotKey < publishedKey)'));
assert(s.includes("publishMarketReportSlot_(hour, 'drive-github-recovery', false, targetDate)"));
assert(s.includes("findMarketReportDocForAutoPublishSlot_(hour, targetDate)"));
assert(s.includes("marketReportAutoVerifyPublishedSource_(file, hour)"));
const start=s.indexOf('function findMarketReportDocForAutoPublishSlot_(');
const end=s.indexOf('\nfunction findMarketReportAutoBestFileByName_',start);
assert(start>=0&&end>start);
const ctx={
 Utilities:{formatDate:()=> '2026-10-13'},
 MARKET_REPORT_AUTO_CONFIG:{timezone:'Asia/Tokyo'},
 marketReportAutoDocName_:(d,h)=>d+'-'+h,
 findMarketReportAutoBestFileByName_:name=>name==='2026-10-13-8'?{id:'doc'}:null,
 findMarketReportAutoBestFileByPattern_:(d,h)=>({date:d,hour:h})
};
vm.createContext(ctx);vm.runInContext(s.slice(start,end),ctx);
assert.strictEqual(ctx.findMarketReportDocForAutoPublishSlot_(8,'2026-10-13').id,'doc');
assert.strictEqual(ctx.findMarketReportDocForAutoPublishSlot_(12,'2026-10-12').date,'2026-10-12');
console.log('Drive-to-GitHub historical recovery source-date routing PASS');