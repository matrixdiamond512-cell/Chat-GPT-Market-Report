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
   await page.waitForFunction(()=>document.querySelector('#dateInput')?.value==='2026-10-27' && document.querySelector('.time-tab.is-active')?.textContent.trim()==='08:00',null,{timeout:60000});
   const dash=await page.evaluate(()=>({date:document.querySelector('#dateInput')?.value,time:document.querySelector('.time-tab.is-active')?.textContent.trim(),cards:document.querySelectorAll('#marketCards .market-card').length,status:document.querySelector('#reportStatus')?.textContent||''}));
   assert(dash.cards>=6,'Dashboard market cards missing: '+dash.cards);
   assert(dash.status.includes('2026/10/27（火）'),'JST weekday/date label incorrect: '+dash.status);
   assert(!errors.length,'Dashboard JS errors: '+errors.join(';'));
   console.log('PASS live index.html date/time selector 2026-10-27 08:00; cards='+dash.cards+'; status='+dash.status);
   await page.close();
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack||String(e));process.exit(1);});
