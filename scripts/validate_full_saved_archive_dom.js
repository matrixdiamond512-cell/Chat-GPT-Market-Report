#!/usr/bin/env node
'use strict';
// Read-only, exhaustive public-site audit: 91 saved Google Docs report slots,
// both the full-text report and dashboard, plus source/provenance consistency.
// Never turns an archive into formal publication or invents a missing body.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const base = String(process.env.PORTAL_URL || '').replace(/\/$/, '') + '/';
const minimumKnownSourceCount = 91;
const manifestPath = 'data/report-archive-manifest.json';
const missingPath = 'data/report-content-gaps.json';
const concurrency = Math.max(1, Math.min(3, Number(process.env.QA_WORKERS || 2)));
const qaPath = process.env.QA_EVIDENCE_PATH || path.join(process.env.RUNNER_TEMP || '/tmp', 'archive-91-dual-view-evidence.json');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const key = r => r.date + ' ' + r.time;
const detail = err => (err && err.stack ? err.stack : String(err)).slice(0, 1600);
const recordId = r => r.title + ' [' + key(r) + ']';

function addCandidates(map, list) {
  for (const r of list || []) {
    if (typeof r.fullText !== 'string') continue;
    if (!map.has(key(r))) map.set(key(r), new Set());
    map.get(key(r)).add(r.fullText);
  }
}
async function remoteJson(rel) {
  const res = await fetch(base + rel + '?archiveAudit=' + Date.now(), {
    cache: 'no-store', signal: AbortSignal.timeout(60000)
  });
  assert(res.ok, 'public JSON unavailable ' + rel + ': HTTP ' + res.status);
  return await res.json();
}
async function loadArchive() {
  assert(/^https?:\/\//.test(base), 'PORTAL_URL must be HTTP(S)');
  const localManifest = read(manifestPath);
  const publicManifest = await remoteJson(manifestPath);
  assert.deepEqual(publicManifest, localManifest, 'public archive manifest differs from checked-out source');
  const gaps = read(missingPath);
  const publicGaps = await remoteJson(missingPath);
  assert.deepEqual(publicGaps, gaps, 'public missing-slot list differs from checked-out source');
  assert.equal(gaps.missingSlots.length, 5, 'known missing source slot count changed');
  const gapKeys = new Set(gaps.missingSlots);
  const candidates = new Map();
  addCandidates(candidates, read('data/report-recovery-2026-10.json').reports);
  let canonical;
  try { canonical = read('reports.json'); } catch { canonical = []; }
  addCandidates(candidates, Array.isArray(canonical) ? canonical : canonical.reports);
  const slots = [];
  const seen = new Set();
  for (const entry of localManifest.files) {
    assert(/^data\/dashboard-drive-archive-2026-\d{2}-(?:\d{2}(?:-\d{2})?|-?external)\.json$/.test(entry.path) ||
      /^data\/dashboard-drive-archive-2026-\d{2}-external\.json$/.test(entry.path), 'manifest path unsafe: ' + entry.path);
    const local = read(entry.path);
    const published = await remoteJson(entry.path);
    assert.deepEqual(published, local, 'published source differs: ' + entry.path);
    assert.equal(local.kind, 'HISTORICAL_ARCHIVE_NOT_OFFICIAL_PUBLICATION', entry.path);
    assert.equal(local.sourceFolderId, entry.sourceFolderId, entry.path);
    for (const r of local.reports) {
      assert(!seen.has(key(r)), 'duplicate archive source slot: ' + key(r));
      assert(!gapKeys.has(key(r)), 'known missing slot was silently backfilled: ' + key(r));
      seen.add(key(r));
      assert(r.title && r.fullText?.length > 250, 'invalid fullText/title: ' + recordId(r));
      slots.push({date:r.date,time:r.time,title:r.title,fullText:r.fullText,source:entry.path});
    }
    addCandidates(candidates, local.reports);
  }
  assert(slots.length >= minimumKnownSourceCount, 'saved source count unexpectedly fell below baseline of 91');
  return {slots, candidates, gaps};
}

async function reportPage(page, r, candidates) {
  const url = base + 'report.html?date=' + r.date + '&time=' + encodeURIComponent(r.time) + '&audit=' + Date.now();
  await page.goto(url, {waitUntil:'domcontentloaded',timeout:60000});
  await page.waitForFunction(({date,time}) => {
    const item = window.MarketReportLastRendered;
    return item?.date === date && item?.time === time &&
      document.querySelector('.report-title') && document.querySelector('.report-body') &&
      document.querySelector('#datePicker')?.value === date &&
      document.querySelector('.time-tab.is-active')?.textContent.trim() === time;
  }, {date:r.date,time:r.time}, {timeout:45000});
  const actual = await page.evaluate(() => {
    const item = window.MarketReportLastRendered;
    const body = document.querySelector('.report-body');
    return {
      date:item.date,time:item.time,title:item.title,fullText:item.fullText || '',
      archive:item.archiveStatus === 'HISTORICAL_ARCHIVE',
      verifiedAtSlot:item.verifiedAtSlot,
      formal:window.MarketReportPublicationPolicy?.isEligible(item) === true,
      visibleBody:body?.innerText?.length || 0,
      badge:document.querySelector('.source-badge')?.textContent || '',
      provenance:document.querySelector('.archive-provenance')?.textContent || '',
      missing:document.getElementById('app')?.classList.contains('empty') || false
    };
  });
  assert.equal(actual.date,r.date);
  assert.equal(actual.time,r.time);
  assert.equal(actual.title,r.title, 'report.html selected wrong title');
  assert.equal(actual.missing,false, 'report.html unexpectedly shows a missing state');
  assert(actual.visibleBody > 160, 'full report body blank or unexpectedly short');
  if (actual.archive) {
    assert.equal(actual.verifiedAtSlot,false,'archive promoted to verified at slot');
    assert(candidates.get(key(r))?.has(actual.fullText),'rendered archive text not found in verified source records');
    assert(/保存|修復/.test(actual.badge),'archive source badge not visible');
    assert(/正式/.test(actual.provenance),'archive provenance warning missing');
  } else {
    assert.equal(actual.formal,true, 'unsourced/unsupported body replaces saved archive');
  }
  return {archive:actual.archive,archiveBodyMatchesPrimary:actual.fullText===r.fullText};
}
async function dashboardPage(page, r, candidates) {
  const url = base + 'index.html?date=' + r.date + '&time=' + encodeURIComponent(r.time) + '&audit=' + Date.now();
  await page.goto(url,{waitUntil:'domcontentloaded',timeout:60000});
  await page.waitForFunction(({date,time}) => {
    const item = typeof selectedReport === 'undefined' ? null : selectedReport;
    return item?.date === date && item?.time === time &&
      document.querySelector('#dateInput')?.value === date &&
      document.querySelector('.time-tab.is-active')?.dataset.time === time &&
      !document.querySelector('.page-shell')?.classList.contains('dashboard-missing-slot') &&
      document.getElementById('reportStatus')?.textContent.includes(time);
  }, {date:r.date,time:r.time}, {timeout:45000});
  const actual = await page.evaluate(() => {
    const item = typeof selectedReport === 'undefined' ? null : selectedReport;
    return {
      date:item?.date,time:item?.time,title:item?.title,fullText:item?.fullText || '',
      archive:item?.archiveStatus === 'HISTORICAL_ARCHIVE' || item?.historicalArchiveDisplayOnly === true,
      verifiedAtSlot:item?.verifiedAtSlot,
      formal:window.MarketReportPublicationPolicy?.isEligible(item) === true,
      cardCount:document.querySelectorAll('#marketCards .market-card').length,
      missingNotice:!document.getElementById('dashboardMissingSlot')?.hidden,
      state:document.querySelector('#reportStatus')?.textContent || '',
      footnote:document.querySelector('#dataFootnote')?.textContent || '',
      urlDate:new URL(location.href).searchParams.get('date'),
      urlTime:new URL(location.href).searchParams.get('time')
    };
  });
  assert.equal(actual.date,r.date);
  assert.equal(actual.time,r.time);
  assert.equal(actual.urlDate,r.date,'dashboard URL date rewritten');
  assert.equal(actual.urlTime,r.time,'dashboard URL time rewritten');
  assert.equal(actual.title,r.title, 'dashboard shows wrong source title');
  assert.equal(actual.missingNotice,false,'saved source incorrectly displayed as missing');
  assert.equal(actual.cardCount,6,'dashboard did not build six asset cards');
  if(actual.archive) {
    assert.equal(actual.verifiedAtSlot,false,'dashboard archive incorrectly marked verified');
    assert(candidates.get(key(r))?.has(actual.fullText),'dashboard archive text not in source records');
    assert(/保存済み本文/.test(actual.state),'dashboard historical archive label missing');
    assert(/保存本文|原本欠損/.test(actual.footnote),'dashboard provenance footnote missing');
  } else {
    assert.equal(actual.formal,true,'dashboard selected an unverified, unsupported source');
  }
  return {archive:actual.archive,archiveBodyMatchesPrimary:actual.fullText===r.fullText};
}
async function run() {
  const {slots,candidates,gaps} = await loadArchive();
  const evidence = {
    audit:'full-saved-archive-dual-view',createdAt:new Date().toISOString(),
    base,expectedSlots:slots.length,baselineSlots:minimumKnownSourceCount,knownMissing:gaps.missingSlots,
    passedReport:0,passedDashboard:0,errors:[],alternateSources:[],results:[]
  };
  const browser = await chromium.launch({headless:true});
  try {
    let position=0;
    await Promise.all(Array.from({length:concurrency},async (_unused,workerId) => {
      const context = await browser.newContext({serviceWorkers:'block'});
      const fullPage = await context.newPage();
      const dashPage = await context.newPage();
      try {
        while(position<slots.length) {
          const i=position++;
          const r=slots[i];
          const entry={slot:key(r),source:r.source};
          for(const [pageName,page,fn] of [
            ['report',fullPage,reportPage],
            ['dashboard',dashPage,dashboardPage]
          ]) {
            try {
              const result=await fn(page,r,candidates);
              entry[pageName]='PASS';
              entry[pageName+'Type']=result.archive?'HISTORICAL_ARCHIVE':'FORMAL';
              if (!result.archiveBodyMatchesPrimary && result.archive)
                evidence.alternateSources.push({slot:key(r),screen:pageName,source:r.source});
              if (pageName==='report') evidence.passedReport++;
              if (pageName==='dashboard') evidence.passedDashboard++;
            } catch(err) {
              entry[pageName]='FAIL';
              const failure={slot:key(r),screen:pageName,error:detail(err)};
              evidence.errors.push(failure);
              console.error('FAIL ' + failure.slot + ' ' + pageName + ' ' + String(err.message || err).slice(0,260));
            }
          }
          evidence.results.push(entry);
          if((i+1)%10===0) console.log('audited ' + (i+1) + '/' + slots.length + ' worker=' + workerId);
        }
      } finally { await context.close(); }
    }));
  } finally { await browser.close(); }
  evidence.completedAt=new Date().toISOString();
  fs.writeFileSync(qaPath,JSON.stringify(evidence,null,2)+'\n');
  console.log('RESULT saved=' + slots.length +
    ' report.html=' + evidence.passedReport + '/' + slots.length +
    ' index.html=' + evidence.passedDashboard + '/' + slots.length +
    ' alternateSourceSelections=' + evidence.alternateSources.length +
    ' failures=' + evidence.errors.length +
    ' evidence=' + qaPath);
  if(evidence.errors.length) process.exitCode=1;
}
run().catch(err => {console.error('AUDIT ERROR: ' + detail(err));process.exitCode=1;});
