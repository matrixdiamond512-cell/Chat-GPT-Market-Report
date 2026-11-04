#!/usr/bin/env node
'use strict';

const fs = require('fs');
const crypto = require('crypto');
const { chromium } = require('playwright');

function normalize(value) {
  return String(value || '').replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n')
    .replace(/```[^\n]*\n?/g, '').replace(/[`*_>#]/g, '').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/\s+/g, '').trim();
}

async function main() {
  const base = String(process.env.PORTAL_URL || '').replace(/\/$/, '');
  const targetPath = process.env.ISSUANCE_CANONICAL_REPORT || '';
  if (!/^https?:\/\//.test(base) || !targetPath) throw new Error('PORTAL_URL and ISSUANCE_CANONICAL_REPORT are required');
  const target = JSON.parse(fs.readFileSync(targetPath, 'utf8'));
  const expectedId = `${target.date}_${String(target.time).replace(':', '-')}`;
  const raw = String(target.fullText || '');
  const digest = crypto.createHash('sha256').update(raw, 'utf8').digest('hex');
  if (target.report_id !== expectedId || !Number.isInteger(target.revision) || target.revision < 1 ||
      !target.bodyHash || target.bodyHash !== digest) {
    throw new Error('Canonical target identity/body hash is invalid');
  }
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e.message || e)));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    if (process.env.ISSUANCE_DOM_MODE === 'public') {
      const response = await fetch(`${base}/reports.json?issuance-dom=${Date.now()}`, {
        headers: {'cache-control': 'no-cache', pragma: 'no-cache'}
      });
      if (!response.ok) throw new Error('Public reports.json HTTP ' + response.status);
      const payload = await response.json();
      const rows = Array.isArray(payload) ? payload : (Array.isArray(payload?.reports) ? payload.reports : []);
      const identityRows = rows.filter(row => row?.report_id === target.report_id);
      const found = identityRows.length === 1 ? identityRows[0] : null;
      if (identityRows.length !== 1) {
        throw new Error('Public reports.json must contain exactly one row for the target reportId');
      }
      if (found && found.report_status && !['PUBLISHED', 'DOC_READBACK_PASS'].includes(String(found.report_status).toUpperCase())) {
        throw new Error('Public target report is not publication-eligible');
      }
      if (!found || found.revision !== target.revision || found.bodyHash !== digest || found.fullText !== raw ||
          found.date !== target.date || found.time !== target.time) {
        throw new Error('Public reports.json does not contain the exact target reportId/revision/date/time/body');
      }
    } else {
      await page.route('**/reports.json*', route => route.fulfill({
        status: 200, contentType: 'application/json; charset=utf-8', body: JSON.stringify([target])
      }));
    }
    await page.goto(`${base}/report.html?date=${encodeURIComponent(target.date)}&time=${encodeURIComponent(target.time)}`,
      {waitUntil: 'domcontentloaded', timeout: 60000});
    await page.waitForFunction(() => document.querySelector('#app[data-report-id] .report-body')?.textContent?.trim(),
      {timeout: 60000});
    const dom = await page.evaluate(() => ({
      reportId: document.getElementById('app')?.dataset.reportId || '',
      date: document.getElementById('app')?.dataset.reportDate || '',
      time: document.getElementById('app')?.dataset.reportTime || '',
      title: document.querySelector('.report-title')?.textContent?.trim() || '',
      body: document.querySelector('.report-body')?.textContent || '',
      selectedDate: document.getElementById('datePicker')?.value || '',
      selectedTime: document.querySelector('.time-tab.is-active')?.textContent?.trim() || ''
    }));
    const bodySource = raw.split(/\r?\n/).slice(1).filter(line => line.trim() && !/^\s*\|?\s*:?-{3,}/.test(line));
    const visible = normalize(dom.body);
    const missingLines = bodySource.filter(line => {
      const content = normalize(line.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').join(''));
      return content.length >= 4 && !visible.includes(content);
    });
    const failures = [];
    if (dom.reportId !== target.report_id) failures.push('DOM reportId mismatch');
    if (dom.date !== target.date || dom.selectedDate !== target.date) failures.push('DOM date mismatch');
    if (dom.time !== target.time || dom.selectedTime !== target.time) failures.push('DOM time mismatch');
    if (dom.title !== target.title) failures.push('DOM title mismatch');
    if (!dom.body.trim() || missingLines.length) failures.push('DOM body mismatch: ' + missingLines.length + ' source line(s) missing');
    if (errors.length) failures.push('browser errors: ' + errors.join(' | '));
    const result = {status: failures.length ? 'FAIL' : 'PASS', report_id: target.report_id,
      date: target.date, time: target.time, body_sha256: digest, rendered_body_length: dom.body.length, failures};
    console.log(JSON.stringify(result, null, 2));
    if (failures.length) process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error && error.stack || error); process.exit(1); });

