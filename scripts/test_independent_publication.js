const fs = require('fs');
const vm = require('vm');
const crypto = require('crypto');

const webSource = fs.readFileSync('apps-script/MarketReportWebSync.gs', 'utf8');
const rendererSource = fs.readFileSync('assets/js/report-core-v3.js', 'utf8');
const validationSource = fs.readFileSync('apps-script/MarketReportPrePublishValidation.gs', 'utf8');
const workflowSource = fs.readFileSync('.github/workflows/apps-script-prepublish-validation.yml', 'utf8');
const context = {
  Utilities: { newBlob: text => ({ getBytes: () => Array.from(Buffer.from(text, 'utf8')) }) },
  LockService: { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }) },
  Date,
  JSON,
  console
};
vm.createContext(context);
vm.runInContext(webSource, context);

const bodyHash = value => crypto.createHash('sha256').update(value).digest('hex');
const fixtureBodyHash = bodyHash('fixture body');
function sortObject(value) {
  if (Array.isArray(value)) return value.map(sortObject);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, sortObject(value[key])]));
  return value;
}
const manifestHash = value => crypto.createHash('sha256').update(JSON.stringify(sortObject(value))).digest('hex');
context.validateWebReportObject_ = report => report;
context.validateMarketReportBeforePublish_ = report => {
  if (report.bodyValidationFails) throw new Error('body validation failed');
  return { ok: true };
};
context.marketReportSha256_ = bytes => crypto.createHash('sha256').update(Buffer.from(bytes.map(v => v & 255))).digest('hex');
context.verifyMarketReportSourceDocReadback_ = () => {};
context.verifyPublicMarketReport_ = report => {
  if (report.report_status !== 'PUBLISHED') throw new Error('body was not published first');
  return { ok: true, url: 'https://fixture.invalid/report', verifiedAt: '2026-10-09T00:00:00Z' };
};
const files = new Map();
const writes = [];
context.getGitHubJsonFile_ = path => ({ data: files.has(path) ? files.get(path) : (path === 'reports.json' ? [] : null), sha: files.has(path) ? 'sha' : null });
context.putGitHubJsonFile_ = (path, content) => {
  writes.push(path);
  const parsed = JSON.parse(content);
  files.set(path, parsed);
  return { commit: { sha: 'fixture-commit' } };
};
context.normalizeWebReportList_ = data => Array.isArray(data) ? data : [];
context.upsertWebReportList_ = (items, report) => [...items.filter(item => item.date !== report.date || item.time !== report.time), report];
context.syncDashboardJsonToGitHubFromReports_ = () => ({ commitSha: 'dashboard-fixture' });

function report(extra = {}) {
  return Object.assign({ date: '2026-10-09', time: '08:00', title: 'fixture report', fullText: 'fixture body', revision: 1, snapshot_id: 'snap-1' }, extra);
}
function runBodyPublish(input) {
  writes.length = 0;
  return context.publishWebReportObject_(input);
}
const readyManifest = { status: 'READY_FOR_PUBLICATION', manifest_id: 'm-1', report_id: '2026-10-09_08-00', revision: 1,
  snapshot_id: 'snap-1', body_hash: fixtureBodyHash, drive_file_id: 'drive-1', png_filename: 'fixture.png', png_sha256: 'b'.repeat(64),
  required_fact_ids: ['f1'], rendered_fact_ids: ['f1'], missing_fact_ids: [], numeric_validation: 'PASS', renderer_status: 'PASS', vision_status: 'NOT_RUN' };
readyManifest.manifest_hash = manifestHash(readyManifest);

// Body PASS + missing infographic facts publishes body and leaves image lane NOT_READY.
const missingFactManifest = Object.assign({}, readyManifest, {
  required_fact_ids: ['f1'], rendered_fact_ids: [], missing_fact_ids: ['f1'], manifest_hash: undefined
});
delete missingFactManifest.manifest_hash;
missingFactManifest.manifest_hash = manifestHash(missingFactManifest);
const noFacts = runBodyPublish(report({ infographicManifest: missingFactManifest }));
if (noFacts.reportStatus !== 'PUBLISHED' || noFacts.infographicStatus !== 'NOT_READY') throw new Error('Missing infographic facts blocked body publication');
if (!files.has('reports/2026-10-09_08-00.json') || !files.has('reports.json')) throw new Error('Body artifacts were not published');

// A failed infographic renderer is an independent failed lane.
const failedManifest = { status: 'READY_FOR_PUBLICATION', manifest_id: 'm-1', report_id: '2026-10-09_08-00', revision: 1,
  snapshot_id: 'snap-1', body_hash: fixtureBodyHash, drive_file_id: 'drive-1', png_filename: 'fixture.png', png_sha256: 'b'.repeat(64),
  required_fact_ids: ['f1'], rendered_fact_ids: ['f1'], missing_fact_ids: [], numeric_validation: 'PASS', renderer_status: 'FAIL' };
failedManifest.manifest_hash = manifestHash(failedManifest);
const rendererFail = context.evaluateInfographicReadiness_(
  Object.assign(report(), { bodyHash: fixtureBodyHash, snapshot_id: 'snap-1' }), failedManifest
);
if (rendererFail.status !== 'FAILED_VALIDATION') throw new Error('Renderer failure was not classified independently');
const rendererReportResult = runBodyPublish(report({ infographicManifest: failedManifest }));
if (rendererReportResult.reportStatus !== 'PUBLISHED' || rendererReportResult.infographicStatus !== 'FAILED_VALIDATION') throw new Error('Renderer failure blocked body publication');

// Optional OCR/Vision is not part of structured readiness.
const ready = context.evaluateInfographicReadiness_(Object.assign(report(), { bodyHash: fixtureBodyHash, snapshot_id: 'snap-1' }), readyManifest);
if (ready.status !== 'READY') throw new Error('Vision NOT_RUN blocked an otherwise valid infographic');
const pngBytes = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10, 1, 2, 3]);
readyManifest.png_sha256 = crypto.createHash('sha256').update(pngBytes).digest('hex');
delete readyManifest.manifest_hash;
readyManifest.manifest_hash = manifestHash(readyManifest);
context.Utilities.base64Encode = bytes => Buffer.from(bytes.map(value => value & 255)).toString('base64');
context.getGitHubContentSha_ = () => null;
context.getGitHubToken_ = () => 'fixture-token';
context.githubHeaders_ = () => ({ Accept: 'application/vnd.github+json' });
context.buildDashboardJsonFromReports_ = reports => JSON.stringify({ reports });
context.DriveApp = { getFileById: id => ({
  getId: () => id,
  getName: () => readyManifest.png_filename,
  getMimeType: () => 'image/png',
  isTrashed: () => false,
  getBlob: () => ({ getBytes: () => Array.from(pngBytes) })
}) };
let fixtureHead = 'fixture-parent';
let refUpdates = 0;
const fixtureBlobs = new Map();
let fixtureTreeEntries = [];
context.UrlFetchApp = { fetch: (url, options = {}) => {
  const method = String(options.method || 'get').toLowerCase();
  const path = String(url).replace(/^https:\/\/api\.github\.com\/repos\/matrixdiamond512-cell\/Chat-GPT-Market-Report/, '').split('?')[0];
  let response = {};
  if (method === 'get' && path === '/git/ref/heads/main') response = { object: { sha: fixtureHead } };
  else if (method === 'get' && path === '/git/commits/fixture-parent') response = { tree: { sha: 'fixture-base-tree' } };
  else if (method === 'post' && path === '/git/blobs') {
    const payload = JSON.parse(options.payload);
    const bytes = payload.encoding === 'base64' ? Buffer.from(payload.content, 'base64') : Buffer.from(payload.content, 'utf8');
    const header = Buffer.from(`blob ${bytes.length}\0`);
    const sha = crypto.createHash('sha1').update(Buffer.concat([header, bytes])).digest('hex');
    fixtureBlobs.set(sha, bytes);
    response = { sha };
  } else if (method === 'post' && path === '/git/trees') {
    fixtureTreeEntries = JSON.parse(options.payload).tree;
    response = { sha: 'fixture-tree' };
  }
  else if (method === 'post' && path === '/git/commits') response = { sha: 'fixture-commit-ready' };
  else if (method === 'patch' && path === '/git/refs/heads/main') {
    fixtureHead = JSON.parse(options.payload).sha;
    refUpdates += 1;
    fixtureTreeEntries.filter(entry => entry.path.endsWith('.json')).forEach(entry => {
      files.set(entry.path, JSON.parse(fixtureBlobs.get(entry.sha).toString('utf8')));
    });
    response = { ref: 'refs/heads/main' };
  } else throw new Error(`Unexpected mocked GitHub request ${method} ${path}`);
  return { getResponseCode: () => method === 'patch' ? 200 : (method === 'post' ? 201 : 200), getContentText: () => JSON.stringify(response) };
} };
const readyPublishResult = runBodyPublish(report({ infographicManifest: readyManifest }));
if (readyPublishResult.reportStatus !== 'PUBLISHED' || readyPublishResult.infographicStatus !== 'READY' || refUpdates !== 1) {
  throw new Error('Valid manifest/PNG did not publish independently as READY');
}
if (!files.get('reports.json').some(item => item.infographic_status === 'READY')) throw new Error('READY infographic metadata was not committed to the Portal projection');

context.DriveApp = { getFileById: () => { throw new Error('fixture PNG missing'); } };
context.UrlFetchApp = undefined;
const missingPngResult = runBodyPublish(report({ infographicManifest: readyManifest }));
if (missingPngResult.reportStatus !== 'PUBLISHED' || missingPngResult.infographicStatus !== 'FAILED_VALIDATION') throw new Error('Missing PNG blocked body publication or was not isolated');
if (refUpdates !== 1) throw new Error('Missing PNG performed an infographic Git registration');

// Body FAIL exits before any canonical/index/dashboard or infographic side effect.
files.clear();
let bodyFailed = false;
let blockedReport;
try { blockedReport = report({ bodyValidationFails: true, infographicManifest: readyManifest }); runBodyPublish(blockedReport); }
catch (error) { bodyFailed = error.reportStatus === 'BLOCKED' && error.infographicStatus === 'NOT_READY'; }
if (!bodyFailed || writes.length !== 0 || files.size !== 0) throw new Error('Body validation failure had publication side effects or wrong status');

// Portal display requires READY formal identity; debug, incomplete and hash-mismatched objects stay hidden.
const start = rendererSource.indexOf('function renderInfographic(report) {');
const end = rendererSource.indexOf('\nfunction headingInfo(', start);
if (start < 0 || end < 0) throw new Error('Portal infographic renderer could not be isolated for testing');
const portalContext = { esc: value => String(value), RegExp };
vm.createContext(portalContext);
vm.runInContext(rendererSource.slice(start, end), portalContext);
const formal = { date: '2026-10-09', time: '08:00', title: 'fixture', revision: 1, snapshot_id: 'snap-1', bodyHash: 'a'.repeat(64), infographic_status: 'READY',
  infographic: { artifact_type: 'FORMAL_INFOGRAPHIC', slotKey: '2026-10-09_08-00', src: 'images/reports/2026-10-09_08-00.png',
    report_id: '2026-10-09_08-00', revision: 1, snapshot_id: 'snap-1', body_hash: 'a'.repeat(64), manifest_id: 'm-1',
    manifest_hash: 'c'.repeat(64), sha256: 'b'.repeat(64), numeric_validation: 'PASS', renderer_status: 'PASS' } };
if (!portalContext.renderInfographic(formal).includes('<img')) throw new Error('Valid formal infographic was not rendered');
if (portalContext.renderInfographic(Object.assign({}, formal, { infographic_status: 'NOT_READY' })) !== '') throw new Error('NOT_READY infographic was rendered');
if (portalContext.renderInfographic(Object.assign({}, formal, { infographic: Object.assign({}, formal.infographic, { artifact_type: 'DEBUG_PREVIEW' }) })) !== '') throw new Error('DEBUG_PREVIEW reached the Portal');
if (portalContext.renderInfographic(Object.assign({}, formal, { infographic: Object.assign({}, formal.infographic, { manifest_hash: 'bad' }) })) !== '') throw new Error('Mismatched manifest hash reached the Portal');

if (/DRAFT ONLY|BLOCKED \/ NOT APPROVED|NOT APPROVED/.test(rendererSource)) throw new Error('Debug/approval copy leaked into production UI');
if (!/function publishInfographicGitTransaction_[\s\S]*?\/git\/trees[\s\S]*?\/git\/commits[\s\S]*?force: false/.test(webSource)) throw new Error('Infographic artifacts are not committed atomically with a non-force ref update');
const bodyEntry = webSource.indexOf('function publishWebReportObject_(report)');
const bodyVerify = webSource.indexOf('const live = verifyPublicMarketReport_(report);', bodyEntry);
const infographicStart = webSource.indexOf('publishInfographicAfterBody_(report, canonicalPath)', bodyEntry);
if (bodyEntry < 0 || bodyVerify < bodyEntry || infographicStart < bodyVerify) throw new Error('Infographic work runs before body publication verification');
if (/DriveApp\.getFilesByName\(name\)[\s\S]{0,500}getLastUpdated\(\)/.test(webSource)) throw new Error('Latest-by-name image selection remains in production source');
if (/approval_status|reviewer_approval|user_approval|chatgpt_approval/i.test(webSource + rendererSource)) throw new Error('Approval dependency remains in production runtime');
for (const [label, pattern, source] of [
  ['body validation before writes', /function publishWebReportObject_\(report\)[\s\S]*?validateWebReportObject_\(report\)[\s\S]*?validateMarketReportBeforePublish_\(report, expectedHour\)[\s\S]*?verifyMarketReportSourceDocReadback_\(report\)[\s\S]*?putGitHubJsonFile_/, webSource],
  ['body verification before optional infographic', /const live = verifyPublicMarketReport_\(report\)[\s\S]*?publishInfographicAfterBody_\(report, canonicalPath\)/, webSource],
  ['manifest identity/hash Drive binding', /function publishInfographicAfterBody_[\s\S]*?getFileById\(String\(manifest\.drive_file_id\)\)[\s\S]*?marketReportSha256_\(bytes\)/, webSource],
  ['atomic Git registration', /function publishInfographicGitTransaction_[\s\S]*?\/git\/trees[\s\S]*?\/git\/commits[\s\S]*?force: false/, webSource],
  ['Portal READY/hash gates', /function renderInfographic\(report\)[\s\S]*?report\.infographic_status !== "READY"[\s\S]*?image\.artifact_type !== "FORMAL_INFOGRAPHIC"[\s\S]*?image\.manifest_hash/, rendererSource],
  ['body-only deployment verification', /function verifyPublicMarketReport_\(report\)[\s\S]*?published\.bodyHash !== report\.bodyHash[\s\S]*?if \(report\.infographic_status === 'READY'\)/, webSource],
  ['JST weekday validator', /getUTCDay\(\)/, validationSource],
  ['incomplete body validator', /source\.length < 1200/, validationSource]
]) if (!pattern.test(source)) throw new Error('CI publication safeguard missing: ' + label);
if (!workflowSource.includes('node scripts/test_independent_publication.js') ||
    !workflowSource.includes("python -m unittest discover -s tests -p 'test_independent_publication_status.py' -v")) {
  throw new Error('Focused independent status tests are not wired into CI');
}
console.log('Independent report/infographic production-path tests passed.');
