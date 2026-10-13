'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const sourcePath = path.join(__dirname, '..', 'apps-script', 'MarketReportWebSync.gs');
const source = fs.readFileSync(sourcePath, 'utf8');
const start = source.indexOf('function getGitHubJsonFile_(path) {');
const end = source.indexOf('\nfunction putGitHubJsonFile_(path, content, sha, message) {', start);
assert(start >= 0 && end > start, 'getGitHubJsonFile_ must exist');

const fixtures = {
  metadataUrl: 'https://api.github.example/repos/report/contents/reports.json?ref=main',
  rawUrl: 'https://raw.githubusercontent.com/report/main/reports.json',
  tokenStub: 'private-test-token'
};
const context = {
  WEB_REPORT_CONFIG: { branch: 'main' },
  githubContentsUrl_: () => 'https://api.github.example/repos/report/contents/reports.json',
  githubHeaders_: () => ({ Authorization: 'Bearer ' + fixtures.tokenStub }),
  getGitHubToken_: () => fixtures.tokenStub,
  UrlFetchApp: { fetch: null },
  Utilities: {
    base64Decode: value => Buffer.from(value, 'base64'),
    newBlob: value => ({ getDataAsString: () => Buffer.from(value).toString('utf8') })
  }
};
vm.runInNewContext(source.slice(start, end), context, { filename: 'MarketReportWebSync.gs' });

let rawIndex = JSON.stringify({ reports: [{ date: '2026-10-13', time: '16:00', fullText: 'x'.repeat(1_100_000) }] });
let calls = [];
context.UrlFetchApp.fetch = (url, options) => {
  calls.push({ url, method: options.method, headers: options.headers });
  if (calls.length === 1) return {
    getResponseCode: () => 200,
    getContentText: () => JSON.stringify({
      size: Buffer.byteLength(rawIndex),
      content: '',
      download_url: fixtures.rawUrl,
      sha: 'index-sha'
    })
  };
  return { getResponseCode: () => 200, getContentText: () => rawIndex };
};
const large = context.getGitHubJsonFile_('reports.json');
assert.equal(large.sha, 'index-sha', 'Contents API SHA is retained for safe update');
assert.equal(large.data.reports[0].time, '16:00');
assert.equal(large.data.reports[0].fullText.length, 1_100_000);
assert.equal(calls.length, 2, 'large files must use the download URL');
assert.equal(calls[1].url, fixtures.rawUrl);
assert.equal(calls[1].headers.Authorization, 'Bearer ' + fixtures.tokenStub);

const smallJson = JSON.stringify({ reports: [{ time: '08:00' }] });
calls = [];
context.UrlFetchApp.fetch = (url, options) => {
  calls.push(url);
  return {
    getResponseCode: () => 200,
    getContentText: () => JSON.stringify({
      size: Buffer.byteLength(smallJson),
      content: Buffer.from(smallJson).toString('base64'),
      sha: 'small-sha'
    })
  };
};
const small = context.getGitHubJsonFile_('reports.json');
assert.equal(small.sha, 'small-sha');
assert.equal(small.data.reports[0].time, '08:00');
assert.equal(calls.length, 1, 'small files continue using the Contents API body');

console.log('GitHub large report-index read fallback and small-file path PASS');

