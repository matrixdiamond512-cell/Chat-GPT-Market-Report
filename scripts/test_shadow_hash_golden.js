'use strict';
/* Deliberately demonstrate where the current Python and GAS hashes diverge.
 * No keys, network calls, publisher operations, or production fixtures.
 */
const assert = require('assert');
const cp = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const vm = require('vm');

const vectors = JSON.parse(cp.execFileSync('python', [
  '-m', 'scripts.reporting.shadow_hash_golden',
], { encoding: 'utf8', timeout: 15000 }));
assert.strictEqual(vectors.schema_version, 'd1-golden/v1');
const env = {JSON, Number};
vm.createContext(env);
vm.runInContext(
  fs.readFileSync('apps-script/MarketReportProducerProof.gs', 'utf8'),
  env, {filename:'MarketReportProducerProof.gs'}
);
const sha = value => crypto.createHash('sha256').update(value,'utf8').digest('hex');
let equal = 0, different = 0;
for (const v of vectors.vectors) {
  const gasCanonical = env.marketReportProofCanonical_(v.payload);
  const gasHash = sha(gasCanonical);
  const parity = v.python_canonical === gasCanonical && v.python_sha256 === gasHash;
  assert.strictEqual(parity, v.expected_parity,
    v.id + ' canonicalization changed: review schema and existing snapshot IDs before any release');
  if (parity) equal++; else different++;
}
assert(equal >= 2 && different >= 3);
console.log(
  'D1 Python/GAS hash golden vectors: ' + equal +
  ' parity; ' + different + ' intentionally divergent and BLOCKED for production proofs'
);
