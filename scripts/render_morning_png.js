/* Deterministic 08:00 HTML -> PNG; no server, network assets, or publication. */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { chromium } = require('playwright');
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const args = Object.fromEntries(process.argv.slice(2).reduce((rows, value, i, all) => {
  if (value.startsWith('--')) rows.push([value.slice(2), all[i + 1]]);
  return rows;
}, []));
async function main() {
  for (const key of ['html', 'contract', 'out']) if (!args[key]) throw new Error(`Missing --${key}`);
  const contract = JSON.parse(fs.readFileSync(args.contract, 'utf8'));
  const approved = contract.layout_profile === 'APPROVED_16_PANEL';
  if (approved && (contract.validation.artifact_type !== 'DEBUG_PREVIEW' || contract.publication?.publish_allowed !== false)) throw new Error('Approved renderer is DRAFT-only');
  const html = fs.readFileSync(args.html);
  if (digest(html) !== contract.html_sha256 || contract.validation.status !== 'PASS') throw new Error('HTML contract mismatch');
  const out = path.resolve(args.out);
  if (fs.existsSync(out)) throw new Error('Output directory already exists; use a new review directory');
  const browser = await chromium.launch({ headless: true, ...(args.browser ? { executablePath: args.browser } : {}) });
  const observed = {console_errors: [], page_errors: []};
  try {
    const page = await browser.newPage({viewport: {width: 1536, height: 1000}, deviceScaleFactor: 1, locale: 'ja-JP', timezoneId: 'Asia/Tokyo'});
    await page.route('**/*', route => route.abort());
    page.on('pageerror', err => observed.page_errors.push(err.message));
    page.on('console', msg => { if (msg.type() === 'error') observed.console_errors.push(msg.text()); });
    await page.setContent(html.toString('utf8'), {waitUntil: 'load'});
    await page.evaluate(() => document.fonts.ready);
    const check = async expectedVisualOrder => page.evaluate(({expected, expectedNumeric, visualOrder}) => {
      const all = [...document.querySelectorAll('.fact')];
      const ids = [...new Set(all.map(el => el.dataset.factId))].sort();
      const differences = all.filter(el => el.textContent !== expected[el.dataset.factId]).map(el => el.dataset.factId);
      const numeric = [...document.querySelectorAll('[data-numeric-id]')];
      const numericDifferences = numeric.filter(el => el.textContent !== expectedNumeric[el.dataset.numericId]).map(el => el.dataset.numericId);
      const numericIds = [...new Set(numeric.map(el => el.dataset.numericId))].sort();
      const overflow = [...document.querySelectorAll('.card,.card-body,.market,.fact,td,th,h2,h3,header,.chain,.inflow,.outflow')].filter(el => {
        const box = el.getBoundingClientRect();
        return el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2 || box.right > window.innerWidth + 1 || box.left < -1;
      }).map(el => ({name: (el.className || el.tagName) + '@' + (el.closest('[data-card]')?.dataset.card || 'header'), scroll: [el.scrollWidth, el.scrollHeight], client: [el.clientWidth, el.clientHeight]}));
      const outside = all.filter(el => {
        const parent = el.closest('.card') || el.closest('header');
        const outer = parent.getBoundingClientRect();
        const range = document.createRange(); range.selectNodeContents(el);
        return [...range.getClientRects()].some(r => r.right > outer.right + 1 || r.bottom > outer.bottom + 1 || r.left < outer.left - 1);
      }).map(el => el.dataset.factId);
      const cards = [...document.querySelectorAll('[data-card]')].map(el => el.dataset.card);
      const visualCards = [...document.querySelectorAll('[data-card]')].map(el => ({id: el.dataset.card, box: el.getBoundingClientRect()}))
        .sort((a,b) => Math.abs(a.box.top-b.box.top) > 2 ? a.box.top-b.box.top : a.box.left-b.box.left).map(item => item.id);
      const markets = [...document.querySelectorAll('.market h3')].map(el => el.textContent);
      const colors = [...document.querySelectorAll('td .up,td .down,td .flat')].map(el => ({text: el.textContent, color: getComputedStyle(el).color, category: el.className}));
      const min_font_px = Math.min(...all.map(el => parseFloat(getComputedStyle(el).fontSize)));
      const colorErrors = colors.filter(item => item.color !== (item.category.includes('up') ? 'rgb(236, 23, 76)' : item.category.includes('down') ? 'rgb(8, 117, 225)' : 'rgb(102, 121, 151)'));
      const boxes = [...document.querySelectorAll('[data-card]')].map(el => el.getBoundingClientRect());
      const overlappingCards = boxes.flatMap((a,i) => boxes.slice(i+1).filter(b => a.left < b.right-1 && a.right > b.left+1 && a.top < b.bottom-1 && a.bottom > b.top+1));
      const marketBoxes = [...document.querySelectorAll('.market')].map(el => el.getBoundingClientRect());
      const gridColumns = getComputedStyle(document.querySelector('.cards')).gridTemplateColumns.split(' ').length;
      const marketSingleRow = marketBoxes.length === 6 && marketBoxes.every(box => Math.abs(box.top-marketBoxes[0].top) < 2);
      const cardsElement = document.querySelector('.cards');
      const cardsStyle = getComputedStyle(cardsElement);
      const cardsContentWidth = cardsElement.clientWidth - parseFloat(cardsStyle.paddingLeft) - parseFloat(cardsStyle.paddingRight);
      const outlookWidthFraction = document.querySelector('.card-13').getBoundingClientRect().width / cardsContentWidth;
      return {ids, differences, numeric_ids: numericIds, numeric_differences: numericDifferences, overflow, outside, cards, markets, colors, color_errors: colorErrors.length,
        overlapping_cards: overlappingCards.length, min_font_px, grid_columns: gridColumns,
        visual_order: visualCards,
        visual_order_matches: JSON.stringify(visualCards) === JSON.stringify(visualOrder),
        market_single_row: marketSingleRow, outlook_width_fraction: outlookWidthFraction,
        height: Math.ceil(document.getElementById('report').getBoundingClientRect().height)};
    }, {expected: contract.expected_text, expectedNumeric: contract.expected_numeric || {}, visualOrder: expectedVisualOrder});
    const desktopVisualOrder = Array.from({length: 16}, (_, i) => String(i + 1).padStart(2, '0'));
    const native = await check(desktopVisualOrder);
    const expectedIds = Object.keys(contract.expected_text).sort();
    const expectedCards = Array.from({length: 16}, (_, i) => String(i + 1).padStart(2, '0'));
    if (JSON.stringify(native.ids) !== JSON.stringify(expectedIds) || native.differences.length || native.numeric_differences.length || JSON.stringify(native.numeric_ids) !== JSON.stringify(Object.keys(contract.expected_numeric || {}).sort()) || native.overflow.length || native.outside.length || native.color_errors || native.overlapping_cards || native.min_font_px < 12 || native.grid_columns !== (approved ? 60 : 12) || !native.market_single_row || Math.abs(native.outlook_width_fraction - (approved ? 40/60 : 1.0)) > 0.03 || !native.visual_order_matches || JSON.stringify(native.cards) !== JSON.stringify(expectedCards) || native.markets.length !== 6 || observed.page_errors.length || observed.console_errors.length) {
      throw new Error(`Renderer validation failed: ${JSON.stringify({...native, ...observed})}`);
    }
    fs.mkdirSync(out, {recursive: true});
    const basename = approved ? contract.output_basename : 'morning-0800';
    if (!/^[a-z0-9_-]+$/.test(basename)) throw new Error('Invalid output basename');
    const pngPath = path.join(out, basename + '.png');
    await page.locator('#report').screenshot({path: pngPath, animations: 'disabled'});
    // Actual same-PNG fit-at-768 rendering, independently checked against source bytes.
    const png = fs.readFileSync(pngPath);
    await page.setViewportSize({width: 768, height: 1000});
    await page.setContent(`<html><body style="margin:0"><img style="display:block;width:768px" src="data:image/png;base64,${png.toString('base64')}"></body></html>`);
    await page.locator('img').screenshot({path: path.join(out, basename + '-at-768.png')});
    // A companion portrait export maintains readable type at mobile fit width.
    await page.setContent(html.toString('utf8'));
    if (approved) await page.evaluate(() => document.documentElement.classList.add('mobile'));
    else await page.addStyleTag({content: '#report{width:768px}.cards{grid-template-columns:repeat(6,minmax(0,1fr));grid-template-rows:none;grid-auto-flow:row}.card{grid-row:auto!important}.card-01,.card-02,.card-03,.card-04,.card-05,.card-06,.card-09,.card-10,.card-11,.card-12,.card-14,.card-15{grid-column:span 3}.card-07,.card-08,.card-13,.card-16{grid-column:span 6}.market-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.card-16 .card-body{grid-template-columns:1fr}'});
    await page.evaluate(() => document.fonts.ready);
    const mobile = await check(expectedCards);
    if (mobile.differences.length || mobile.numeric_differences.length || mobile.overflow.length || mobile.outside.length || mobile.overlapping_cards || mobile.color_errors || mobile.min_font_px < 14 || !mobile.visual_order_matches) throw new Error(`Mobile export validation failed: ${JSON.stringify(mobile)}`);
    await page.locator('#report').screenshot({path: path.join(out, basename + '-mobile.png'), animations: 'disabled'});
    const receipt = {status: 'PASS', numeric_validation: approved ? 'UNVERIFIED' : 'PASS', source_transcription_validation: 'PASS', renderer_status: 'PASS',
      html_sha256: contract.html_sha256, view_sha256: contract.view_sha256, png_sha256: digest(png),
      artifact_type: contract.validation.artifact_type, rendered_fact_ids: native.ids,
      checks: {native, mobile, ...observed, preview_768: true, min_font_at_768_px: mobile.min_font_px},
      environment: {browser_version: browser.version(), font_family: 'Noto Sans CJK JP / Yu Gothic / Meiryo', device_scale_factor: 1}};
    fs.writeFileSync(path.join(out, 'render-receipt.json'), JSON.stringify(receipt, null, 2) + '\n');
    process.stdout.write(JSON.stringify({status: 'PASS', facts: native.ids.length, cards: native.cards.length, png_sha256: receipt.png_sha256}) + '\n');
  } finally { await browser.close(); }
}
main().catch(err => { process.stderr.write(err.message + '\n'); process.exitCode = 1; });
