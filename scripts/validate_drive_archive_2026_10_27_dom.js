#!/usr/bin/env node
'use strict';
// Verify this slot in the actual published date/time UI, not only local GitHub JSON.
const fs=require('fs');
const assert=require('assert');
const {chromium}=require('playwright');
const base=String(process.env.PORTAL_URL||'').replace(/\/$/,'')+'/';
const archive=JSON.parse(fs.readFileSync('data/dashboard-drive-archive-2026-10-27.json','utf8'));
const expected=archive.reports.find(x=>x.date==='2026-10-27'&&x.time==='08:00');
(async()=>{
 if(!/^https?:\/\//.test(base))throw Error('PORTAL_URL required');
 assert(expected && expected.report_status==='HISTORICAL_ARCHIVE_DISPLAY_ONLY');
 const res=await fetch(base+'data/dashboard-drive-archive-2026-10-27.json?qa='+Date.now(),{cache:'no-store'});
 if(!res.ok)throw Error('Published archive HTTP '+res.status);
 const live=await res.json();
 assert.strictEqual(live.reports[0].fullText,expected.fullText,'Published JSON fullText mismatch');
 const browser=await chromium.launch({headless:true});
 try{
   const page=await browser.newPage();
   const errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(base+'report.html?date=2026-10-27&time=08%3A00&qa='+Date.now(),{waitUntil:'domcontentloaded',timeout:60000});
   await page.waitForFunction(()=>window.MarketReportLastRendered && document.querySelector('.report-title'),null,{timeout:60000});
   const v=await page.evaluate(()=>({
     title:document.querySelector('.report-title')?.textContent.trim(),
     date:document.querySelector('#datePicker')?.value,
     time:document.querySelector('.time-tab.is-active')?.textContent.trim(),
     text:window.MarketReportLastRendered?.fullText,
     archiveStatus:window.MarketReportLastRendered?.archiveStatus,
     verifiedAtSlot:window.MarketReportLastRendered?.verifiedAtSlot,
     body:document.querySelector('.report-body')?.innerText||'',
     status:document.querySelector('#reportStatus')?.textContent||''
   }));
   assert.strictEqual(v.title,expected.title,'Report title mismatch');
   assert.strictEqual(v.date,'2026-10-27');
   assert.strictEqual(v.time,'08:00');
   assert.strictEqual(v.text,expected.fullText,'Report page fullText mismatch');
   assert.strictEqual(v.archiveStatus,'HISTORICAL_ARCHIVE');
   assert.strictEqual(v.verifiedAtSlot,false);
   assert(v.body.includes('11｜出典とデータ制約'),'Report body missing final section');
   assert(v.body.length>5000,'Report body truncated');
   assert(!errors.length,'Report page JS errors: '+errors.join(';'));
   console.log('PASS live report.html 2026-10-27 08:00; fullText='+v.text.length+'; visibleBody='+v.body.length+'; display-only');
   await page.goto(base+'index.html?date=2026-10-27&time=08%3A00&qa='+Date.now(),{waitUntil:'domcontentloaded',timeout:60000});
   await page.waitForTimeout(4000);
   console.log('DEBUG 08 dashboard',JSON.stringify(await page.evaluate(()=>({
     date:document.querySelector('#dateInput')?.value,
     time:document.querySelector('.time-tab.is-active')?.textContent.trim(),
     reportStatus:document.querySelector('#reportStatus')?.textContent,
     bodyText:document.body?.innerText?.slice(0,700),
     url:location.href,
     errors:window.onerror?.toString().slice(0,200)
   }))), 'pageErrors='+errors.join(' | '));
   await page.waitForFunction(()=>document.querySelector('#dateInput')?.value==='2026-10-27' && document.querySelector('.time-tab.is-active')?.textContent.trim()==='08:00',null,{timeout:15000});
   const dash=await page.evaluate(()=>({date:document.querySelector('#dateInput')?.value,time:document.querySelector('.time-tab.is-active')?.textContent.trim(),cards:document.querySelectorAll('#marketCards .market-card').length,status:document.querySelector('#reportStatus')?.textContent||''}));
   assert(dash.cards>=6,'Dashboard market cards missing: '+dash.cards);
   assert(dash.status.includes('2026/10/27（火）'),'JST weekday/date label incorrect: '+dash.status);
   assert(!errors.length,'Dashboard JS errors: '+errors.join(';'));
   console.log('PASS live index.html date/time selector 2026-10-27 08:00; cards='+dash.cards+'; status='+dash.status);

   // The noon analytical report must also be visible in both existing date/time selectors.
   const noon=archive.reports.find(x=>x.date==='2026-10-27'&&x.time==='12:00');
   assert(noon && noon.report_status==='HISTORICAL_ARCHIVE_DISPLAY_ONLY','Noon archive missing');
   const liveNoon=live.reports.find(x=>x.date==='2026-10-27'&&x.time==='12:00');
   assert(liveNoon,'Published noon archive missing');
   assert.strictEqual(liveNoon.fullText,noon.fullText,'Published noon fullText mismatch');
   await page.goto(base+'report.html?date=2026-10-27&time=12%3A00&qa='+Date.now(),{waitUntil:'domcontentloaded',timeout:60000});
   await page.waitForFunction(()=>window.MarketReportLastRendered &&
     document.querySelector('.report-title') &&
     document.querySelector('.time-tab.is-active')?.textContent.trim()==='12:00',null,{timeout:60000});
   const noonView=await page.evaluate(()=>({
     title:document.querySelector('.report-title')?.textContent.trim(),
     date:document.querySelector('#datePicker')?.value,
     time:document.querySelector('.time-tab.is-active')?.textContent.trim(),
     text:window.MarketReportLastRendered?.fullText,
     archiveStatus:window.MarketReportLastRendered?.archiveStatus,
     verifiedAtSlot:window.MarketReportLastRendered?.verifiedAtSlot,
     body:document.querySelector('.report-body')?.innerText||'',
     status:document.querySelector('#reportStatus')?.textContent||''
   }));
   assert.strictEqual(noonView.title,noon.title,'Noon title mismatch');
   assert.strictEqual(noonView.date,'2026-10-27');
   assert.strictEqual(noonView.time,'12:00');
   assert.strictEqual(noonView.text,noon.fullText,'Noon report page fullText mismatch');
   assert.strictEqual(noonView.archiveStatus,'HISTORICAL_ARCHIVE');
   assert.strictEqual(noonView.verifiedAtSlot,false);
   assert(noonView.body.includes('09｜出典・観測時刻・制約'),'Noon final section missing');
   assert(noonView.body.length>3000,'Noon visible body truncated');
   assert(!errors.length,'Noon report page JS errors: '+errors.join(';'));
   console.log('PASS live report.html 2026-10-27 12:00; fullText='+noonView.text.length+'; visibleBody='+noonView.body.length+'; display-only');
   await page.goto(base+'index.html?date=2026-10-27&time=12%3A00&qa='+Date.now(),{waitUntil:'domcontentloaded',timeout:60000});
   await page.waitForFunction(()=>document.querySelector('#dateInput')?.value==='2026-10-27' &&
     document.querySelector('.time-tab.is-active')?.textContent.trim()==='12:00',null,{timeout:60000});
   const noonDash=await page.evaluate(()=>({
     date:document.querySelector('#dateInput')?.value,
     time:document.querySelector('.time-tab.is-active')?.textContent.trim(),
     cards:document.querySelectorAll('#marketCards .market-card').length,
     status:document.querySelector('#reportStatus')?.textContent||''
   }));
   assert(noonDash.cards>=6,'Noon dashboard market cards missing: '+noonDash.cards);
   assert(noonDash.status.includes('2026/10/27（火）'),'Noon JST weekday/date label incorrect: '+noonDash.status);
   assert(!errors.length,'Noon dashboard JS errors: '+errors.join(';'));
   console.log('PASS live index.html date/time selector 2026-10-27 12:00; cards='+noonDash.cards);

   // Verify 16:00 analytical report and all six cards on the actual public DOM.
   const afternoon=archive.reports.find(x=>x.date==='2026-10-27'&&x.time==='16:00');
   assert(afternoon && afternoon.report_status==='HISTORICAL_ARCHIVE_DISPLAY_ONLY','16:00 archive missing');
   const liveAfternoon=live.reports.find(x=>x.date==='2026-10-27'&&x.time==='16:00');
   assert(liveAfternoon,'Published 16:00 archive missing');
   assert.strictEqual(liveAfternoon.fullText,afternoon.fullText,'Published 16:00 fullText mismatch');
   await page.goto(base+'report.html?date=2026-10-27&time=16%3A00&qa='+Date.now(),{waitUntil:'domcontentloaded',timeout:60000});
   await page.waitForFunction(()=>window.MarketReportLastRendered &&
     document.querySelector('.report-title') &&
     document.querySelector('.time-tab.is-active')?.textContent.trim()==='16:00',null,{timeout:60000});
   const afternoonView=await page.evaluate(()=>({
     title:document.querySelector('.report-title')?.textContent.trim(),
     date:document.querySelector('#datePicker')?.value,
     time:document.querySelector('.time-tab.is-active')?.textContent.trim(),
     text:window.MarketReportLastRendered?.fullText,
     archiveStatus:window.MarketReportLastRendered?.archiveStatus,
     verifiedAtSlot:window.MarketReportLastRendered?.verifiedAtSlot,
     body:document.querySelector('.report-body')?.innerText||''
   }));
   assert.strictEqual(afternoonView.title,afternoon.title,'16:00 title mismatch');
   assert.strictEqual(afternoonView.date,'2026-10-27');
   assert.strictEqual(afternoonView.time,'16:00');
   assert.strictEqual(afternoonView.text,afternoon.fullText,'16:00 report page fullText mismatch');
   assert.strictEqual(afternoonView.archiveStatus,'HISTORICAL_ARCHIVE');
   assert.strictEqual(afternoonView.verifiedAtSlot,false);
   assert(afternoonView.body.includes('11｜出典・データ制約'),'16:00 final section missing');
   assert(afternoonView.body.length>3000,'16:00 visible body truncated');
   assert(!errors.length,'16:00 report page JS errors: '+errors.join(';'));
   console.log('PASS live report.html 2026-10-27 16:00; fullText='+afternoonView.text.length+'; visibleBody='+afternoonView.body.length+'; display-only');
   await page.goto(base+'index.html?date=2026-10-27&time=16%3A00&qa='+Date.now(),{waitUntil:'domcontentloaded',timeout:60000});
   await page.waitForFunction(()=>document.querySelector('#dateInput')?.value==='2026-10-27' &&
     document.querySelector('.time-tab.is-active')?.textContent.trim()==='16:00',null,{timeout:60000});
   const afternoonDash=await page.evaluate(()=>({
     date:document.querySelector('#dateInput')?.value,
     time:document.querySelector('.time-tab.is-active')?.textContent.trim(),
     cards:document.querySelectorAll('#marketCards .market-card').length,
     status:document.querySelector('#reportStatus')?.textContent||''
   }));
   assert(afternoonDash.cards>=6,'16:00 dashboard market cards missing: '+afternoonDash.cards);
   assert(afternoonDash.status.includes('2026/10/27（火）'),'16:00 JST weekday/date label incorrect: '+afternoonDash.status);
   assert(!errors.length,'16:00 dashboard JS errors: '+errors.join(';'));
   console.log('PASS live index.html date/time selector 2026-10-27 16:00; cards='+afternoonDash.cards);
   await page.close();
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack||String(e));process.exit(1);});
