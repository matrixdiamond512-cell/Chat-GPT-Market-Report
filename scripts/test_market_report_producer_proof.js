'use strict';
const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const vm = require('vm');

const proofSource = fs.readFileSync('apps-script/MarketReportProducerProof.gs', 'utf8');
const publisherSource = fs.readFileSync('apps-script/MarketReportWebSync.gs', 'utf8');
const autoSource = fs.readFileSync('apps-script/MarketReportAutoPublish.gs', 'utf8');
const structuredSource = fs.readFileSync('apps-script/MarketReportStructuredImport.gs', 'utf8');
const historicalSource = fs.readFileSync('apps-script/MarketReportHistoricalImport.gs', 'utf8');
const secret = 'test-only-independent-producer-secret-at-least-32-characters';
const hash = text => crypto.createHash('sha256').update(text).digest('hex');
const canonical = value => {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort()
    .map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
  return JSON.stringify(value);
};
const report = {
  date: '2026-10-15', time: '16:00',
  fullText: 'マーケットレポート｜2026/10/15（木）16:00\n記録済みの検証用原文。',
  sourceDocument: {id: 'trusted-google-doc-id'}, title: 'test title'
};
const key = '2026-10-15_16-00';
const contextData = {
  report_id: key, report_date: report.date, report_time: report.time,
  data_cutoff: '2026-10-15T16:00:00+09:00', previous_report_id: null,
  previous_business_day: '2026-10-14', revision: 1, mode: 'new'
};
const mkMarkets = () => ['gold','wti','nikkei225','usdjpy','eurusd','btcusd'].map(instrument => ({
  instrument, marketType: 'spot', priceValue: 100, status: 'VALID',
  asOf: '2026-10-15T15:45:00+09:00',
  source: [{id: 'trusted-market-source', url: 'https://example.org/test'}]
}));
const snapshot = {
  report_id: key, revision: 1, schema_version: 1,
  captured_at: '2026-10-15T15:50:00+09:00',
  data_cutoff: contextData.data_cutoff, markets: mkMarkets()
};
snapshot.snapshot_id = 'snapshot-' + hash(canonical(snapshot));
const record = {
  schema_version: 1, report_id: key, revision: 1, producer_run_id: 'producer-run-123',
  producer_created_at: '2026-10-15T15:55:00+09:00',
  chat_evidence_id: 'chat-source-id-123',
  body_sha256: hash(report.fullText), chat_body_sha256: hash(report.fullText),
  source_document_id: 'trusted-google-doc-id',
  context: contextData, context_id: 'context-' + hash(canonical(contextData)),
  snapshot
};
const sign = value => {
  const result = structuredClone(value);
  delete result.signature;
  result.signature = crypto.createHmac('sha256', secret).update(canonical(result)).digest('hex');
  return result;
};
const state = { data: sign(record), requests: [], writes: 0 };
const TestDate = class extends Date {
  static now() { return new Date('2026-10-15T17:00:00+09:00').getTime(); }
};
const context = {
  Date: TestDate, console,
  PropertiesService: {getScriptProperties: () => ({
    getProperty: name => name === 'MARKET_REPORT_PRODUCER_HMAC_KEY' ? secret : ''
  })},
  Utilities: {
    newBlob: data => ({getBytes: () => [...Buffer.from(data)]}),
    computeHmacSha256Signature: (data, key) =>
      [...crypto.createHmac('sha256', key).update(data).digest()]
  },
  marketReportSha256_: bytes => hash(Buffer.from(bytes)),
  getGitHubJsonFile_: path => {
    state.requests.push(path);
    return {sha: state.data ? 'pinned-origin-commit-hash' : null, data: state.data};
  },
};
vm.createContext(context);
vm.runInContext(proofSource, context, {filename: 'MarketReportProducerProof.gs'});
const verify = () => context.marketReportVerifyProducerProof_({...report, sourceDocument: {...report.sourceDocument}});
const checked = verify();
assert.strictEqual(checked.body_sha256, hash(report.fullText));
assert.strictEqual(state.requests[0], 'producer-proof/' + key + '.json');

function rejects(label, change, breakSignature = false) {
  const altered = structuredClone(record);
  change(altered);
  state.data = sign(altered);
  if (breakSignature) state.data.signature = 'f'.repeat(64);
  assert.throws(verify, /PRODUCER_PROOF_BLOCKED/, label);
}
rejects('unsigned producer record', x => {x.producer_run_id = '';});
state.data = structuredClone(record);
assert.throws(verify, /PRODUCER_PROOF_BLOCKED/, 'unsigned producer record must fail');
rejects('wrong producer body hash', x => x.body_sha256 = '0'.repeat(64));
rejects('wrong chat body hash', x => x.chat_body_sha256 = '0'.repeat(64));
rejects('wrong context digest', x => x.context_id = 'context-' + '0'.repeat(64));
rejects('wrong snapshot digest', x => x.snapshot.snapshot_id = 'snapshot-' + '0'.repeat(64));
rejects('wrong document identity', x => x.source_document_id = 'other-document');
rejects('missing producer run identity', x => x.producer_run_id = '');
rejects('missing chat evidence reference', x => x.chat_evidence_id = '');
rejects('wrong revision', x => x.context.revision = 2);
rejects('wrong slot', x => x.report_id = '2026-10-15_12-00');
rejects('captured after report slot', x => x.snapshot.captured_at = '2026-10-15T16:30:00+09:00');
rejects('market observation after cutoff', x => x.snapshot.markets[0].asOf = '2026-10-15T16:00:01+09:00');
rejects('duplicate source series', x => x.snapshot.markets[1].instrument = x.snapshot.markets[0].instrument);
rejects('invalid signed source record', x => {}, true);
state.data = null;
assert.throws(verify, /PRODUCER_PROOF_BLOCKED/, 'missing signed record must fail');

// Extract the actual publication functions to confirm a missing upstream proof
// blocks ALL GitHub writers, independent of the SOP validation implementation.
function extract(source, begin, end) {
  const start = source.indexOf(begin), finish = source.indexOf(end, start);
  assert(start >= 0 && finish > start, 'source function anchors exist');
  return source.slice(start, finish);
}
const manual = extract(publisherSource, 'function publishWebReportObject_(report)',
  '\nfunction evaluateInfographicReadiness_');
const archive = extract(autoSource, 'function archiveMarketReportFromDriveWithoutLatestRollback_',
  '\nfunction publishMarketReportSlot_');
const dry = {
  validateWebReportObject_: x => x,
  marketReportVerifyProducerProof_: () => {throw Error('PRODUCER_PROOF_BLOCKED: missing producer proof');},
  marketReportAutoVerifyPublishedSource_: () => false,
  buildWebReportFromGoogleDoc_: () => report,
  runMarketReportAutoValidation_: () => ({ok:true}),
  getGitHubJsonFile_: () => ({sha:null, data:null}),
  putGitHubJsonFile_: () => {state.writes += 1; throw Error('no write allowed');},
  verifyMarketReportSourceDocReadback_: () => {throw Error('unreachable');},
  LockService: {getScriptLock: () => ({waitLock: () => {}, releaseLock: () => {}})}
};
vm.createContext(dry);
vm.runInContext(manual + '\n' + archive, dry);
assert.throws(() => dry.publishWebReportObject_({...report}), /PRODUCER_PROOF_BLOCKED/);
assert.throws(() => dry.archiveMarketReportFromDriveWithoutLatestRollback_(
  {getId: () => report.sourceDocument.id}, 16), /PRODUCER_PROOF_BLOCKED/);
assert.strictEqual(state.writes, 0, 'missing producer proof must never reach GitHub write');
assert(manual.indexOf('marketReportVerifyProducerProof_(report)') <
  manual.indexOf('putGitHubJsonFile_'), 'proof gate must precede canonical write');
assert(archive.indexOf('marketReportVerifyProducerProof_(report)') <
  archive.indexOf("putGitHubJsonFile_(path, JSON.stringify(report"),
  'archive proof gate must precede actual canonical write, not dependency checking');

// Legacy structured import has a separate reports.json writer. Validate every
// serialized row at that writer boundary before any GitHub API request.
const structuredWriter = extract(structuredSource, 'function mrPublishReportsJson_(reports)',
  String.fromCharCode(10) + 'function mrGithubConfig_');
const structuredState = {fetches: 0, writes: 0};
const structuredDry = {
  marketReportVerifyProducerProof_: () => {
    throw Error('PRODUCER_PROOF_BLOCKED: absent trusted record');
  },
  mrGithubConfig_: () => ({owner: 'test', repo: 'test', branch: 'main', token: 'unused'}),
  UrlFetchApp: {fetch: () => {structuredState.fetches += 1; return {getResponseCode: () => 200};}},
};
vm.createContext(structuredDry);
vm.runInContext(structuredWriter, structuredDry);
assert.throws(() => structuredDry.mrPublishReportsJson_([report]), /PRODUCER_PROOF_BLOCKED/);
assert.strictEqual(structuredState.fetches, 0, 'structured import must reject before GitHub reads/writes');

// The historical continuation importer writes reports.json directly. Verify
// missing evidence aborts a batch before its putGitHubJsonFile_ call.
const historicalBatch = extract(historicalSource, 'function processHistoricalMarketReportBatch_()',
  String.fromCharCode(10) + 'function listHistoricalMarketReportDocs_');
const historyState = {writes: 0, saves: 0};
const historyFile = {getName: () => 'マーケットレポート_2026-10-15_16-00'};
const historyProps = {
  getProperty: key => key === 'MARKET_REPORT_HISTORY_IMPORT_STATE'
    ? JSON.stringify({offset: 0, imported: 0, fallback: 0, failed: 0}) : null,
  setProperty: () => {},
  deleteProperty: () => {},
};
const historyDry = {
  WEB_REPORT_CONFIG: {targetPath: 'reports.json', prefix: 'マーケットレポート_'},
  MARKET_REPORT_HISTORY_CONFIG: {
    stateProperty: 'MARKET_REPORT_HISTORY_IMPORT_STATE',
    resultProperty: 'MARKET_REPORT_HISTORY_IMPORT_RESULT',
    timezone: 'Asia/Tokyo', batchSize: 20,
  },
  LockService: {getScriptLock: () => ({waitLock: () => {}, releaseLock: () => {}})},
  PropertiesService: {getScriptProperties: () => historyProps},
  listHistoricalMarketReportDocs_: () => [historyFile],
  getGitHubJsonFile_: () => ({data: [], sha: 'existing-index-sha'}),
  buildWebReportFromGoogleDoc_: () => ({...report, sourceDocument: {...report.sourceDocument}}),
  buildLegacyWebReportFromGoogleDoc_: () => ({...report, sourceDocument: {...report.sourceDocument}}),
  marketReportVerifyProducerProof_: () => {throw Error('PRODUCER_PROOF_BLOCKED: no signed proof');},
  putGitHubJsonFile_: () => {historyState.writes += 1;},
  saveHistoricalImportResult_: () => {historyState.saves += 1;},
  clearHistoricalImportTriggers_: () => {},
  Utilities: {formatDate: () => '2026-10-15 17:00:00'},
};
vm.createContext(historyDry);
vm.runInContext(historicalBatch, historyDry);
assert.throws(() => historyDry.processHistoricalMarketReportBatch_(), /PRODUCER_PROOF_BLOCKED/);
assert.strictEqual(historyState.writes, 0, 'unproved historical batch must not rewrite reports.json');
assert.strictEqual(historyState.saves, 0, 'blocked batch must not save a success receipt');

console.log('Signed producer-owned report gate / no-write regressions PASS');
