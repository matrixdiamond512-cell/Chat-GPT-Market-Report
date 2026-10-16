const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

const base = (process.env.PORTAL_URL || 'http://127.0.0.1:8765').replace(/\/$/, '');
const output = process.env.REPORT_UI_OUTPUT || path.join(process.cwd(), 'validation/report-single-page-ui');

async function main() {
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1536,height:1024}, deviceScaleFactor:1});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${base}/index.html?date=2026-10-16&time=08%3A00#report-detail`, {waitUntil:'domcontentloaded'});
    await page.waitForFunction(() => {
      const frame = document.querySelector('#reportDocumentFrame');
      const status = document.querySelector('#reportInlineStatus')?.textContent || '';
      return frame && !frame.hidden && /同一本文・identityを確認/.test(status);
    }, null, {timeout:30000});

    const frame = page.frameLocator('#reportDocumentFrame');
    const title = await frame.locator('.report-title').innerText();
    assert.match(title, /2026\/10\/16/);
    assert.match(title, /08:00/);
    assert.equal(await page.locator('#timeTabs .is-active').innerText(), '08:00');
    assert.equal(await page.locator('#timeTabs .is-active').count(), 1);
    assert.equal(await frame.locator('.topbar').evaluate(el => getComputedStyle(el).display), 'none');
    assert.equal(await frame.locator('.controls').evaluate(el => getComputedStyle(el).display), 'none');
    assert.equal(await frame.locator('.report-title').count(), 1);

    const archiveNotice = frame.locator('.archive-provenance');
    if (await archiveNotice.count()) {
      await archiveNotice.waitFor({state:'visible'});
      assert.match(await archiveNotice.innerText(), /正式な発行原本とは区別/);
    }
    assert.deepEqual(errors, [], `browser errors: ${errors.join(' | ')}`);
    await page.screenshot({path:path.join(output, 'single-page-2026-10-16_08-00.png'), fullPage:true});

    await page.goto(`${base}/report.html?date=2026-10-16&time=08%3A00`, {waitUntil:'domcontentloaded'});
    await page.waitForURL(url => url.pathname.endsWith('/index.html') && url.searchParams.get('date') === '2026-10-16'
      && url.searchParams.get('time') === '08:00' && url.hash === '#report-detail', {timeout:10000});
    await page.waitForFunction(() => {
      const frame = document.querySelector('#reportDocumentFrame');
      return frame && !frame.hidden;
    }, null, {timeout:30000});
    await page.screenshot({path:path.join(output, 'legacy-report-route-same-page.png'), fullPage:true});
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });

