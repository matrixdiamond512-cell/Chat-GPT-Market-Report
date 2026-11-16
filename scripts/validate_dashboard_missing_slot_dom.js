#!/usr/bin/env node
'use strict';
// Validate the five source-missing slots in the actual dashboard DOM.
// A missing selection must not redirect to a different report or leave
// previous market cards visible. No market data is synthesized here.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
const gaps = JSON.parse(fs.readFileSync('data/report-content-gaps.json', 'utf8')).missingSlots;
const base = String(process.env.PORTAL_URL || '').replace(/\/$/, '') + '/';

(async () => {
  if (!/^https?:\/\//.test(base)) throw new Error('PORTAL_URL is required');
  assert.equal(gaps.length, 5, 'expected five documented missing source slots');
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const gap of gaps) {
      const [date, time] = gap.split(' ');
      const url = base + 'index.html?date=' + date + '&time=' + encodeURIComponent(time) + '&missingQA=' + Date.now();
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForFunction(() => document.getElementById('reportStatus')?.textContent.includes('対象データなし'), null, { timeout: 60000 });
      const result = await page.evaluate(() => {
        const main = document.querySelector('.page-shell');
        const notice = document.getElementById('dashboardMissingSlot');
        const previousMarket = document.querySelector('.market-summary');
        return {
          missingActive: main?.classList.contains('dashboard-missing-slot'),
          noticeVisible: Boolean(notice && !notice.hidden && getComputedStyle(notice).display !== 'none'),
          notice: notice?.textContent || '',
          reportStatus: document.getElementById('reportStatus')?.textContent || '',
          reportDate: document.getElementById('dateInput')?.value || '',
          selectedTime: document.querySelector('#timeTabs .time-tab.is-active')?.dataset.time || '',
          marketPanelVisible: Boolean(previousMarket && getComputedStyle(previousMarket).display !== 'none'),
          urlDate: new URL(location.href).searchParams.get('date'),
          urlTime: new URL(location.href).searchParams.get('time'),
          disabledTabCount: document.querySelectorAll('#timeTabs .time-tab:disabled').length
        };
      });
      assert.equal(result.missingActive, true, gap + ': missing-state class absent');
      assert.equal(result.noticeVisible, true, gap + ': missing notice invisible');
      assert.match(result.notice, /対象データなし/, gap);
      assert.match(result.notice, /前のレポート/, gap);
      assert.equal(result.reportDate, date, gap + ': selected date changed');
      assert.equal(result.selectedTime, time, gap + ': selected time changed');
      assert.equal(result.urlDate, date, gap + ': URL date changed');
      assert.equal(result.urlTime, time, gap + ': URL time changed');
      assert.equal(result.marketPanelVisible, false, gap + ': stale market card still visible');
      assert.equal(result.disabledTabCount, 0, gap + ': missing times must remain selectable');
      console.log('PASS missing dashboard slot: ' + gap);
    }
    // Navigate from a gap to an existing report without a page reload, and
    // ensure previously hidden panels and explicit gap notice are restored.
    await page.locator('#timeTabs .time-tab[data-time="16:00"]').click();
    await page.waitForFunction(() =>
      !document.querySelector('.page-shell')?.classList.contains('dashboard-missing-slot') &&
      !document.getElementById('reportStatus')?.textContent.includes('対象データなし'), null, { timeout: 60000 });
    const restored = await page.evaluate(() => ({
      noticeHidden: document.getElementById('dashboardMissingSlot')?.hidden,
      missingFenceCleared: !document.querySelector('.page-shell')?.classList.contains('dashboard-missing-slot'),
      scenarioGridVisible: getComputedStyle(document.querySelector('.scenario-grid')).display !== 'none',
      reportStatus: document.getElementById('reportStatus')?.textContent || '',
      // The separate data-quality guard intentionally hides the market summary
      // when no verified market cards exist. That is not a stale-slot failure.
      marketSummaryDisplay: getComputedStyle(document.querySelector('.market-summary')).display,
      date: document.getElementById('dateInput')?.value,
      selectedTime: document.querySelector('#timeTabs .time-tab.is-active')?.dataset.time
    }));
    assert.equal(restored.noticeHidden, true, 'missing notice persisted after real selection');
    assert.equal(restored.missingFenceCleared, true, 'missing-slot visibility fence persisted');
    assert.equal(restored.scenarioGridVisible, true, 'normal dashboard layout did not return');
    assert.match(restored.reportStatus, /2026\/11\/06.*16:00/, 'valid report identity was not rendered');
    assert.equal(restored.date, '2026-11-06');
    assert.equal(restored.selectedTime, '16:00');
    assert.deepEqual(errors, [], 'dashboard JavaScript errors');
    console.log('PASS missing-slot to valid-report navigation; data-quality-gated market summary=' + restored.marketSummaryDisplay);
    await page.close();
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.stack || String(error)); process.exit(1); });
