#!/usr/bin/env node
'use strict';
// All historical recovery slots must be visible, accurately labeled and separately gated.
const {chromium} = require('playwright');
const fs = require('fs');
const base = String(process.env.PORTAL_URL || '').replace(/\/$/, '') + '/';
const records = JSON.parse(fs.readFileSync('data/report-recovery-2026-10.json','utf8')).reports;
(async()=>{
  if(!/^https?:\/\//.test(base)) throw Error('PORTAL_URL required');
  const browser=await chromium.launch({headless:true});
  try{
    for(const source of records){
      const page=await browser.newPage();
      const failures=[], errors=[];
      page.on('pageerror', e=>errors.push(e.message));
      const url=base+'report.html?date='+source.date+'&time='+encodeURIComponent(source.time)+'&recoveryQA='+Date.now();
      await page.goto(url,{waitUntil:'domcontentloaded',timeout:60000});
      await page.waitForFunction(()=>window.MarketReportArchiveInfo &&
        document.querySelector('.report-title') &&
        document.getElementById('reportStatus')?.textContent.includes('過去の記録'),null,{timeout:60000});
      const result=await page.evaluate(()=>({
        title:document.querySelector('.report-title')?.textContent.trim()||'',
        recovered:document.getElementById('app')?.classList.contains('report-archive-recovery'),
        archiveNotice:document.querySelector('.archive-provenance')?.innerText||'',
        status:document.getElementById('reportStatus')?.textContent||'',
        body:document.querySelector('.report-body')?.innerText||'',
        hidden:getComputedStyle(document.querySelector('.report-body')).display==='none',
        displayedReport:window.MarketReportLastRendered,
        archiveCount:window.MarketReportArchiveInfo.count,
        formalFlag:document.querySelector('.source-badge')?.textContent||'',
        time:document.querySelector('.time-tab.is-active')?.textContent.trim()||'',
        date:document.getElementById('datePicker')?.value||''
      }));
      if(result.archiveCount!==15)failures.push('archive count not 15');
      if(result.title!==source.title)failures.push('title mismatch');
      if(result.time!==source.time||result.date!==source.date)failures.push('selection mismatch');
      if(!result.recovered||!result.archiveNotice.includes('正式')||!result.formalFlag.includes('修復'))failures.push('archive provenance not visible');
      if(result.hidden||result.body.length<350)failures.push('body missing or hidden');
      if(result.displayedReport?.archiveStatus!=='HISTORICAL_ARCHIVE')failures.push('wrong loaded record');
      if(errors.length)failures.push('browser errors: '+errors.join(';'));
      await page.close();
      console.log(source.date+' '+source.time+': '+(failures.length?'FAIL '+failures.join(' | '):'PASS'));
      if(failures.length)throw Error(source.date+' '+source.time+': '+failures.join(' | '));
    }
  }finally{await browser.close();}
  console.log('PASS: all 15 historical archive reports visible, labeled and not presented as formally published.');
})().catch(e=>{console.error(e.stack||String(e));process.exit(1);});
