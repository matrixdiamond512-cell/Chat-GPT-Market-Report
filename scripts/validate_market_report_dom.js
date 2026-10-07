#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const base = String(process.env.PORTAL_URL || '').replace(/\/$/, '') + '/';
const fixturePath = process.env.PORTAL_REPORT_FIXTURE || '';

function validReports(payload) {
  const rows = Array.isArray(payload) ? payload : (Array.isArray(payload?.reports) ? payload.reports : []);
  return rows.filter(report => report
    && /^\d{4}-\d{2}-\d{2}$/.test(String(report.date || ''))
    && /^\d{2}:\d{2}$/.test(String(report.time || ''))
    && String(report.title || '').trim());
}

async function main() {
  if (!/^https?:\/\//.test(base)) throw new Error('PORTAL_URL is missing or invalid');
  let reports;
  let fixture = null;
  if (fixturePath) {
    fixture = JSON.parse(fs.readFileSync(path.resolve(fixturePath), 'utf8'));
    reports = validReports([fixture]);
    if (reports.length !== 1) throw new Error('Title-boundary fixture is not a valid report');
  } else {
    const response = await fetch(base + 'reports.json?domverify=' + Date.now(), {
      headers: {'cache-control': 'no-cache', pragma: 'no-cache'}
    });
    if (!response.ok) throw new Error('reports.json HTTP ' + response.status);
    reports = validReports(await response.json());
  }
  if (!reports.length) throw new Error('No valid report slots found');

  const latestDate = reports.map(report => report.date).sort().at(-1);
  const slots = reports.filter(report => report.date === latestDate)
    .sort((a, b) => a.time.localeCompare(b.time));
  const browser = await chromium.launch({headless: true});
  const allFailures = [];
  try {
    for (const report of slots) {
      const page = await browser.newPage();
      const pageErrors = [];
      const consoleErrors = [];
      page.on('pageerror', error => pageErrors.push(String(error && error.message || error)));
      page.on('console', message => {
        if (message.type() === 'error') consoleErrors.push(message.text());
      });
      if (fixture) {
        await page.route('**/reports.json*', route => route.fulfill({
          status: 200,
          contentType: 'application/json; charset=utf-8',
          body: JSON.stringify([fixture])
        }));
      }

      const url = base + 'report.html?date=' + encodeURIComponent(report.date)
        + '&time=' + encodeURIComponent(report.time) + '&domverify=' + Date.now();
      await page.goto(url, {waitUntil: 'domcontentloaded', timeout: 60000});
      await page.waitForFunction(() => {
        const app = document.getElementById('app');
        const status = document.getElementById('reportStatus');
        if (!app || !status) return false;
        const text = (app.textContent || '') + ' ' + (status.textContent || '');
        return text.trim()
          && !/本文データを読み込んでいます|マーケットレポートを読み込んでいます/.test(text)
          && !/読み込めません|読込エラー/.test(text);
      }, {timeout: 60000});

      const result = await page.evaluate(() => {
        const app = document.getElementById('app');
        const title = document.querySelector('.report-title');
        const body = document.querySelector('.report-body');
        const picker = document.getElementById('datePicker');
        const activeTab = document.querySelector('.time-tab.is-active');
        const sections = [...document.querySelectorAll('.sop-section')];
        const market = sections.find(section => /主要市場データ|主要市場まとめ|市場データ|前営業日終値|終値一覧|主要価格/.test(
          section.querySelector('h2')?.textContent || section.dataset.sopTitle || ''));
        const table = market?.querySelector('table.market-table');
        return {
          appText: app?.textContent || '',
          title: title?.textContent?.trim() || '',
          titleLength: (title?.textContent || '').trim().length,
          bodyText: body?.textContent || '',
          date: picker?.value || '',
          activeTime: activeTab?.textContent?.trim() || '',
          marketSectionFound: Boolean(market),
          marketTableFound: Boolean(table),
          marketRowCount: table?.querySelectorAll('tbody tr').length || 0,
          loadingTextPresent: /本文データを読み込んでいます|マーケットレポートを読み込んでいます/.test(
            (app?.textContent || '') + ' ' + (document.getElementById('reportStatus')?.textContent || ''))
        };
      });

      const failures = [];
      if (result.date !== report.date) failures.push('datePicker mismatch: ' + result.date);
      if (result.activeTime !== report.time) failures.push('active time mismatch: ' + result.activeTime);
      if (result.title !== report.title) failures.push('title mismatch: ' + result.title);
      if (result.titleLength > 160) failures.push('rendered title is abnormally long: ' + result.titleLength);
      if (!result.bodyText.trim()) failures.push('report body is empty');
      if (!result.marketSectionFound) failures.push('major market section missing');
      if (!result.marketTableFound) failures.push('major market data is not rendered as a table');
      if (result.marketRowCount < 6) failures.push('market table has fewer than 6 rows: ' + result.marketRowCount);
      if (result.loadingTextPresent) failures.push('loading text remains visible');
      if (fixture && !result.bodyText.includes(fixture.expectedBodyText || '')) {
        failures.push('canonical title remainder is missing from report body');
      }
      if (fixture && !result.bodyText.includes(fixture.expectedEmbeddedTitleText || '')) {
        failures.push('title-like text inside body was lost or split');
      }
      if (pageErrors.length) failures.push('page errors: ' + pageErrors.join(' | '));
      if (consoleErrors.length) failures.push('console errors: ' + consoleErrors.join(' | '));

      console.log(JSON.stringify({
        slot: report.date + ' ' + report.time,
        status: failures.length ? 'FAIL' : 'PASS',
        title: result.title,
        bodyLength: result.bodyText.length,
        marketRowCount: result.marketRowCount,
        pageErrors,
        consoleErrors,
        failures
      }, null, 2));
      await page.close();
      if (failures.length) allFailures.push(report.date + ' ' + report.time + ' DOM validation failed: ' + failures.join('; '));
    }
  } finally {
    await browser.close();
  }
  console.log('Current Report DOM slot results: ' + slots.map(report => report.date + ' ' + report.time).join(', '));
  if (allFailures.length) throw new Error(allFailures.join('\n'));
  console.log('Market Report DOM validation passed for ' + slots.length + ' slot(s) on ' + latestDate
    + (fixture ? ' using the malformed-title fixture.' : '.'));
}

main().catch(error => {
  console.error(error && error.stack || error);
  process.exit(1);
});
