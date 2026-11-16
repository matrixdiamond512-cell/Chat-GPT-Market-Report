import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const root = new URL('../', import.meta.url);
const read = p => fs.readFileSync(new URL(p,root),'utf8');
const nodes={};
const window={location:{search:'',href:'https://example.test/index.html'}};
const context=vm.createContext({window,URLSearchParams,URL,console,document:{getElementById:id => nodes[id] ||= {innerHTML:""}},Date});
vm.runInContext(read('assets/js/report-archive-source.js'),context);
vm.runInContext(read('assets/js/top-dashboard.js').replace(/init\(\);\s*$/, '')+'\nwindow.hooks={archiveDashboardSummary,isDashboardHistoricalArchive,conclusionFrom,renderFlow};',context);
const manifest=JSON.parse(read('data/report-archive-manifest.json'));
test('all saved archive formats adapt without source mutation or publication promotion',()=>{
 let count=0;
 for(const entry of manifest.files){const payload=JSON.parse(read(entry.path));for(const record of payload.reports){
 const original=JSON.stringify(record),view=window.MarketReportArchiveSource.normalize(record,payload.sourceFolderId);
 assert.ok(view,entry.path+' '+record.time);assert.ok(window.hooks.isDashboardHistoricalArchive(view));
 const dashboard=window.hooks.archiveDashboardSummary(view);
 assert.equal(dashboard.fullText,record.fullText);assert.equal(dashboard.verifiedAtSlot,false);
 assert.equal(dashboard.report_status,'HISTORICAL_ARCHIVE_DISPLAY_ONLY');assert.equal(JSON.stringify(record),original);count++;
 }} assert.ok(count>=70); console.log('saved source slots:',count);
});
test('November 16 source sections appear in the intended dashboard cards',()=>{
 const payload=JSON.parse(read('data/dashboard-drive-archive-2026-11-16.json'));
 const r=window.MarketReportArchiveSource.normalize(payload.reports.find(r=>r.time==='16:00'),payload.sourceFolderId);
 const d=window.hooks.archiveDashboardSummary(r);
 assert.match(d.leadingMarket,/東京株/);assert.match(d.mainScenario,/中立/);assert.match(d.alternativeScenario,/弱気/);
 assert.ok(d.changes.length);assert.match(window.hooks.conclusionFrom(d),/日本株は朝/);
});
test('bad provenance, contradictory identity, altered body length and published records stay excluded',()=>{
 const p=JSON.parse(read('data/dashboard-drive-archive-2026-11-16.json'));const r=p.reports[0];
 for(const change of [{sourceFolderId:'wrong'},{driveTextLength:1},{originalReportStatus:'PUBLISHED'},{sourceDocument:{id:'wrong',url:r.sourceDocument.url}},{driveRevisionId:''}])assert.equal(window.MarketReportArchiveSource.normalize({...r,...change},p.sourceFolderId),null);
});

test('archive timeline is not dropped because it lacks legacy pipe delimiters',()=>{
 const p=JSON.parse(read('data/dashboard-drive-archive-2026-11-16.json'));
 for(const r of p.reports){const d=window.hooks.archiveDashboardSummary(window.MarketReportArchiveSource.normalize(r,p.sourceFolderId));assert.ok(d.archiveTimelineRows.length,r.time);}
});
test('archive flow never turns conditional or unavailable data into confirmed inflow',()=>{
 const p=JSON.parse(read('data/dashboard-drive-archive-2026-11-16.json'));
 const d=window.hooks.archiveDashboardSummary(window.MarketReportArchiveSource.normalize(p.reports[1],p.sourceFolderId));
 window.hooks.renderFlow(d);assert.match(nodes.flowInItems.innerHTML,/確認済みの流入資産の記載なし/);assert.match(nodes.flowOutItems.innerHTML,/確認済みの流出資産の記載なし/);
});
