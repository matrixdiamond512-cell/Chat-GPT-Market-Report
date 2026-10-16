/* Exercise the unchanged Apps Script consumer with producer outputs, not hand hashes. */
const fs = require('fs');
const vm = require('vm');
const crypto = require('crypto');
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const context = {Utilities: {newBlob: text => ({getBytes: () => [...Buffer.from(text)]})}, console};
vm.createContext(context);
vm.runInContext(fs.readFileSync('apps-script/MarketReportWebSync.gs', 'utf8'), context);
context.marketReportSha256_ = bytes => crypto.createHash('sha256').update(Buffer.from(bytes.map(v => v & 255))).digest('hex');
const report = payload.report;
const manifest = payload.manifest;
const expected = process.argv[3];
const result = context.evaluateInfographicReadiness_(report, manifest);
if (result.status !== expected) throw new Error(JSON.stringify(result));
if (expected === 'READY') {
  for (const key of ['revision','snapshot_id','body_hash']) {
    const wrong = {...manifest, [key]:key === 'revision' ? manifest.revision+1 : 'wrong'};
    if (context.evaluateInfographicReadiness_(report,wrong).status !== 'FAILED_VALIDATION') throw new Error('Identity drift accepted');
  }
  const bad = {...manifest, png_sha256:'0'.repeat(64)};
  if (context.evaluateInfographicReadiness_(report,bad).status === 'READY') throw new Error('Hash tampering accepted');
}
console.log(`Producer -> existing consumer: ${expected}`);
