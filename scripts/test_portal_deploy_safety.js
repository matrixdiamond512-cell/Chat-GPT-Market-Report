'use strict';

const fs = require('fs');

const workflow = fs.readFileSync('.github/workflows/deploy-pages.yml', 'utf8').replace(/\r\n?/g, '\n');
const regressionWorkflow = fs.readFileSync('.github/workflows/report-21-ui-validation.yml', 'utf8').replace(/\r\n?/g, '\n');
const localValidator = fs.readFileSync('scripts/validate_market_report_dom.js', 'utf8');
const core = fs.readFileSync('assets/js/report-core-v3.js', 'utf8');

const pushMatch = workflow.match(/^  push:\r?\n([\s\S]*?)(?=^  [A-Za-z_]+:|^permissions:)/m);
if (!pushMatch) throw new Error('main push trigger is missing');
const pushBlock = pushMatch[1];
if (!/^    branches:\r?\n      - main\s*$/m.test(pushBlock)) {
  throw new Error('Pages push trigger must remain scoped to main');
}
const pathBlock = pushBlock.match(/^    paths:\r?\n((?:      - .+\r?\n?)+)/m);
if (!pathBlock) throw new Error('main push trigger is not restricted by paths');
const paths = [...pathBlock[1].matchAll(/^      - ['"]?([^'"\r\n]+)['"]?\s*$/gm)].map(match => match[1]);

function matches(glob, file) {
  if (glob.endsWith('/**')) return file.startsWith(glob.slice(0, -2));
  if (glob.startsWith('*.')) return !file.includes('/') && file.endsWith(glob.slice(1));
  return glob === file;
}
function isIncluded(file) { return paths.some(glob => matches(glob, file)); }

for (const file of [
  'report.html', 'index.html', 'assets/js/report-core-v3.js',
  'reports.json', 'reports/2026-10-07_12-00.json', 'data/dashboard.json',
  'images/reports/2026-10-07_12-00.png', 'publication-receipts/receipt.json',
  'scripts/validate_report_index.py', 'scripts/validate_market_report_dom.js',
  '.github/workflows/deploy-pages.yml'
]) {
  if (!isIncluded(file)) throw new Error('Portal-impacting path does not trigger deployment: ' + file);
}
for (const file of [
  'docs/INFOGRAPHIC_VALIDATOR.md', 'scripts/reporting/vision_signer.py',
  'apps-script/MarketReportWebSync.gs', 'tests/test_vision_signer.py',
  'docs/project-control/OBJECTIVE_CARD.md'
]) {
  if (isIncluded(file)) throw new Error('Non-Portal path unexpectedly triggers deployment: ' + file);
}

const breadthWorkflow = fs.readFileSync('.github/workflows/update-us-stock-breadth.yml', 'utf8').replace(/\r\n?/g, '\n');
const moversWorkflow = fs.readFileSync('.github/workflows/update-us-stock-movers-contributions.yml', 'utf8').replace(/\r\n?/g, '\n');
for (const [name, source] of [
  ['Update US stock table and daily archive', breadthWorkflow],
  ['Update US stock table and daily archive', moversWorkflow]
]) {
  const trigger = source.match(/^  workflow_run:\n([\s\S]*?)(?=^permissions:|^concurrency:|^jobs:)/m);
  if (!trigger || !trigger[1].includes(name)) {
    throw new Error('Existing workflow_run dependency missing from its consumer workflow: ' + name);
  }
}

if (!regressionWorkflow.startsWith('name: Market Report UI Validation\n')) {
  throw new Error('Portal UI validation workflow name is missing');
}
if (!regressionWorkflow.includes('  validate:\n')
  || !regressionWorkflow.includes('Browser renderer regression for malformed title fixture')
  || !regressionWorkflow.includes('PORTAL_REPORT_FIXTURE: tests/fixtures/report_title_boundary_malformed.json')
  || /PORTAL_URL: http:\/\/127\.0\.0\.1:8765\n\s+run: node scripts\/validate_market_report_dom\.js/.test(regressionWorkflow)) {
  throw new Error('Renderer regression workflow must explicitly scope browser validation to the malformed-title fixture');
}
if (!regressionWorkflow.includes('  strict-current-report:\n')
  || !regressionWorkflow.includes('Validate every latest-date current report slot strictly')
  || !regressionWorkflow.includes('PORTAL_URL: http://127.0.0.1:8765\n          NODE_PATH:')
  || !regressionWorkflow.includes('run: node scripts/validate_market_report_dom.js')) {
  throw new Error('Strict current-report job must run the validator without a fixture on the PR artifact');
}

const stageNames = [
  'Normalize dashboard extensions and cache bust',
  'Install Chromium validator',
  'Start local static site for pre-deploy DOM validation',
  'Validate malformed legacy title fixture in local DOM',
  'Validate normalized local Portal artifact before upload',
  'Upload static site',
  'Deploy to GitHub Pages',
  'Verify the public report index and exact infographic bytes',
  'Verify live market-report DOM after deployment'
];
const positions = stageNames.map(name => workflow.indexOf('- name: ' + name));
if (positions.some(position => position < 0)) throw new Error('A required deploy safety stage is missing');
if (positions.some((position, index) => index && position <= positions[index - 1])) {
  throw new Error('Deploy safety stages are out of order');
}
if ((workflow.match(/node scripts\/validate_market_report_dom\.js/g) || []).length !== 3) {
  throw new Error('The same strict DOM validator must run for fixture, local artifact, and live Portal');
}
if (!workflow.includes('npm install --prefix "$RUNNER_TEMP/portal-validation" --no-save playwright')
  || !workflow.includes('NODE_PATH: ${{ runner.temp }}/portal-validation/node_modules')) {
  throw new Error('Browser validator dependencies must stay outside the Pages upload artifact');
}
if (!localValidator.includes('result.title !== report.title')) {
  throw new Error('Exact report.title DOM validation is missing');
}
if (!localValidator.includes('pageErrors.length') || !localValidator.includes('consoleErrors.length')) {
  throw new Error('Live/local browser error checks are missing');
}
if (!localValidator.includes("status: failures.length ? 'FAIL' : 'PASS'")
  || !localValidator.includes('Current Report DOM slot results: ')
  || !localValidator.includes('if (allFailures.length) throw new Error(allFailures.join')) {
  throw new Error('Strict current-report validation must report every slot before failing the workflow');
}
if (!core.includes('splitCanonicalTitleFromSource_') || !core.includes('bodySource:text.slice(title.length)')) {
  throw new Error('Canonical title split and malformed-body recovery are missing');
}

console.log('Portal deploy paths, workflow_run consumers, fail-closed stage order, and strict DOM contract passed.');
