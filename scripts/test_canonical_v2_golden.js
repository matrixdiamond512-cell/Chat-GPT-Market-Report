'use strict';
/* Offline cross-runtime test. No network, no credentials, no publisher. */
const assert = require('assert');
const cp = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const vm = require('vm');
const received = JSON.parse(cp.execFileSync('python', [
  '-m','scripts.reporting.canonical_v2_golden'
], {encoding:'utf8',timeout:15000}));
assert.strictEqual(received.format,'report-canonical-json/v2');
const sha = value => crypto.createHash('sha256').update(value,'utf8').digest('hex');
const env = {
  Utilities: {newBlob: text => ({getBytes: () => [...Buffer.from(text,'utf8')]})},
  marketReportSha256_: bytes => sha(Buffer.from(bytes).toString('utf8')),
  PropertiesService: {getScriptProperties: () => ({getProperty: () => null})}
};
vm.createContext(env);
vm.runInContext(fs.readFileSync('apps-script/MarketReportProducerProof.gs','utf8'),
                env,{filename:'MarketReportProducerProof.gs'});
for (const v of received.vectors) {
  const canonical = env.marketReportProofCanonicalV2_(v.tagged);
  assert.strictEqual(canonical,v.canonical_v2, v.id + ' exact canonical bytes');
  assert.strictEqual(sha(canonical),v.sha256_v2,v.id + ' SHA-256 parity');
  const hmac = crypto.createHmac('sha256','golden-v2-test-key-not-for-production')
    .update(canonical,'utf8').digest('hex');
  assert.strictEqual(hmac,v.test_hmac_sha256_v2, v.id + ' HMAC parity');
}
assert.strictEqual(received.legacy_id_unchanged,true);
assert.strictEqual(received.evidence.snapshot.snapshot_id,received.legacy_snapshot_id);
assert.strictEqual(env.marketReportProofVerifyV2EvidenceDigests_(received.evidence),true);
function clone(value) {return JSON.parse(JSON.stringify(value));}
function rejects(label,mutate) {
  const proof=clone(received.evidence);
  mutate(proof);
  assert.throws(()=>env.marketReportProofVerifyV2EvidenceDigests_(proof),
                /PRODUCER_PROOF_BLOCKED/, label);
}
rejects('legacy proof cannot masquerade as v2',r=>r.canonicalization_version='v1');
rejects('snapshot modified',r=>r.snapshot.markets[1].instrument='tampered');
rejects('digest modified',r=>r.context_digest_v2='0'.repeat(64));
rejects('untagged raw financial numeric',r=>r.snapshot.markets[0].priceValue=100);
rejects('untagged raw negative zero',r=>r.snapshot.markets[0].changeValue=-0);
rejects('decimal tag invalid',r=>r.snapshot.markets[0].priceValue.decimal_v2='100foo');
rejects('legacy snapshot ID missing',r=>delete r.snapshot.snapshot_id);
assert.throws(()=>env.marketReportProofCanonicalV2_({value: 100.1}), /PRODUCER_PROOF_BLOCKED/);
assert.throws(()=>env.marketReportProofCanonicalV2_({unsafe: Number.MAX_SAFE_INTEGER+1}), /PRODUCER_PROOF_BLOCKED/);
assert.throws(()=>env.marketReportProofCanonicalV2_({bad:'\uD800'}), /PRODUCER_PROOF_BLOCKED/);
assert.throws(()=>env.marketReportProofCanonicalV2_({bad_key:'ok','日本語':'no'}), /PRODUCER_PROOF_BLOCKED/);
assert.strictEqual(env.marketReportProofCanonicalV2_({value:{"decimal_v2":"100.0"}}),
                   '{"value":{"decimal_v2":"100.0"}}');
console.log('Cross-language v2 canonical bytes + SHA/HMAC: '+
            received.vectors.length+' vectors PASS; typed snapshot/context digests PASS; '+
            'legacy snapshot ID preserved; negative checks PASS');
