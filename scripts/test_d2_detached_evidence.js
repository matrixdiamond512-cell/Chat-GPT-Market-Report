'use strict';
/* Synthetic Ed25519 keys generated for this test run. No network or API. */
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const {verifyOne,verifyPair,canonical,PREFIX,SCHEMA,D2EvidenceBlocked}=
  require('./reporting/d2_detached_evidence');
let passed=0;
function test(title,action){action();passed++;console.log('PASS '+title);}
function rejected(title,fn,pattern){
  test(title,()=>assert.throws(fn,pattern||D2EvidenceBlocked));
}
function key(id){
  const {privateKey,publicKey}=crypto.generateKeyPairSync('ed25519');
  const public_key_pem=publicKey.export({format:'pem',type:'spki'}).toString('utf8');
  const fingerprint_sha256=crypto.createHash('sha256').update(
    publicKey.export({type:'spki',format:'der'})).digest('hex');
  return {privateKey,trust:{key_id:id,public_key_pem,fingerprint_sha256}};
}
const count=key('synthetic-count-key'),billing=key('synthetic-billing-key');
const base={
  attempt_id:'test-attempt',audience:'market-report-d2-shadow-offline',
  create_request_sha256:'a'.repeat(64),
  count_request_sha256:'1'.repeat(64),
  monthly_inputs_sha256:'b'.repeat(64),
  report_id:'2026-10-15_16-00',run_id:'test-run',
  snapshot_id:'snapshot-'+'c'.repeat(64),
};
function expected(scope,evidence_sha256){
  return {...base,scope,evidence_sha256};
}
const countExp=expected('input_count','d'.repeat(64));
const billExp=expected('monthly_billing','e'.repeat(64));
const t0=Date.parse('2026-10-15T00:00:00Z');
const now=t0+60000;
function sign(testKey,exp,overrides={},envOverrides={}){
  const payload={
    ...exp,issued_at:'2026-10-15T00:00:00Z',
    expires_at:'2026-10-15T00:03:00Z',
    issuer:testKey.trust.key_id,...overrides,
  };
  const data=Buffer.concat([PREFIX,Buffer.from(canonical(payload),'utf8')]);
  const signature_b64url=crypto.sign(null,data,testKey.privateKey).toString('base64url');
  const envelope={
    schema:SCHEMA,key_id:testKey.trust.key_id,payload,
    signature_b64url,...envOverrides,
  };
  return Buffer.from(canonical(envelope),'utf8');
}
const rawCount=sign(count,countExp),rawBilling=sign(billing,billExp);
const roots={input_count:count.trust,monthly_billing:billing.trust};
const exps={input_count:countExp,monthly_billing:billExp};
test('one valid detached signature checks bytes but cannot authorize',()=>{
  const x=verifyOne(rawCount,count.trust,countExp,now);
  assert.equal(x.signature_mathematically_valid,true);
  for(const key of ['transport_authority_independently_verified',
    'provider_authenticated','billing_authenticated','retry_allowed',
    'api_send_allowed','publication_allowed'])assert.equal(x[key],false,key);
});
test('two role-distinct signatures agree on request and remain BLOCKED',()=>{
  const x=verifyPair(rawCount,rawBilling,roots,exps,now);
  assert.equal(x.signatures_checked,2);
  assert.equal(x.count_signature_valid,true);
  assert.equal(x.billing_signature_valid,true);
  assert.equal(x.status,'OFFLINE_DUAL_SIGNATURES_VALID_WITHOUT_EXTERNAL_TRUST');
  for(const key of ['independent_trust_roots_configured',
    'actual_provider_evidence_verified','api_send_allowed','publication_allowed',
    'retry_allowed'])assert.equal(x[key],false,key);
});
rejected('unsigned self-claimed approval cannot pass',()=>{
  const bad=JSON.parse(rawCount.toString('utf8'));
  bad.payload.api_send_allowed=true;
  verifyOne(Buffer.from(canonical(bad)),count.trust,countExp,now);
},/INVALID_CANONICAL_KEY|PAYLOAD_SCHEMA_INVALID/);
rejected('signature cannot authenticate modified requested amount',()=>{
  const bad=JSON.parse(rawCount.toString('utf8'));
  bad.payload.evidence_sha256='f'.repeat(64);
  verifyOne(Buffer.from(canonical(bad)),count.trust,
            expected('input_count','f'.repeat(64)),now);
},/SIGNATURE_MISMATCH/);
rejected('old evidence hash cannot be replayed on a new generation',()=>{
  verifyOne(rawCount,count.trust,{...countExp,create_request_sha256:'0'.repeat(64)},now);
},/EVIDENCE_BINDING_MISMATCH_create_request_sha256/);
rejected('count input request digest cannot be substituted',()=>{
  verifyOne(rawCount,count.trust,{...countExp,count_request_sha256:'0'.repeat(64)},now);
},/EVIDENCE_BINDING_MISMATCH_count_request_sha256/);
rejected('other monthly input digest cannot be substituted',()=>{
  verifyOne(rawBilling,billing.trust,{...billExp,monthly_inputs_sha256:'0'.repeat(64)},now);
},/EVIDENCE_BINDING_MISMATCH_monthly_inputs_sha256/);
rejected('different slot ID is blocked',()=>{
  verifyOne(rawCount,count.trust,{...countExp,report_id:'2026-10-15_12-00'},now);
},/EVIDENCE_BINDING_MISMATCH_report_id/);
rejected('wrong sender public key blocked by fingerprint',()=>{
  const wrong={...count.trust,public_key_pem:billing.trust.public_key_pem};
  verifyOne(rawCount,wrong,countExp,now);
},/TRUST_FINGERPRINT_MISMATCH/);
rejected('unknown key ID blocked',()=>{
  const wrong={...count.trust,key_id:'untrusted-id'};
  verifyOne(rawCount,wrong,countExp,now);
},/SIGNER_KEY_ID_MISMATCH/);
rejected('key cannot be supplied inside envelope',()=>{
  const bad=JSON.parse(rawCount.toString('utf8'));
  bad.public_key_pem=count.trust.public_key_pem;
  verifyOne(Buffer.from(canonical(bad)),count.trust,countExp,now);
},/ENVELOPE_SCHEMA_INVALID/);
rejected('cannot use one key for both evidence roles',()=>{
  verifyPair(rawCount,rawBilling,
    {input_count:count.trust,monthly_billing:count.trust},exps,now);
},/DISTINCT_ROLE_TRUST_ROOTS_REQUIRED/);
rejected('cross-role request hash split blocked',()=>{
  verifyPair(rawCount,rawBilling,roots,{
    ...exps,monthly_billing:{...billExp,create_request_sha256:'9'.repeat(64)}
  },now);
},/CROSS_ROLE_BINDING_MISMATCH_create_request_sha256/);
rejected('cross-role report ID split blocked',()=>{
  verifyPair(rawCount,rawBilling,roots,{
    ...exps,monthly_billing:{...billExp,report_id:'2026-10-15_08-00'}
  },now);
},/CROSS_ROLE_BINDING_MISMATCH_report_id/);
rejected('other role scope blocked',()=>{
  verifyOne(rawCount,count.trust,{...countExp,scope:'monthly_billing'},now);
},/EVIDENCE_SCOPE_MISMATCH/);
rejected('expired signature blocked',()=>verifyOne(rawCount,count.trust,countExp,t0+200000),
         /EVIDENCE_EXPIRED_OR_NOT_YET_VALID/);
rejected('future-issued signature blocked',()=>verifyOne(rawCount,count.trust,countExp,t0-1),
         /EVIDENCE_EXPIRED_OR_NOT_YET_VALID/);
rejected('oversized validity window blocked even when cryptographically signed',()=>{
  verifyOne(sign(count,countExp,{expires_at:'2026-10-15T00:10:00Z'}),
            count.trust,countExp,now);
},/EVIDENCE_EXPIRED_OR_NOT_YET_VALID/);
rejected('non-UTC timestamp blocked even when cryptographically signed',()=>{
  verifyOne(sign(count,countExp,{issued_at:'2026-10-15T09:00:00+09:00'}),
            count.trust,countExp,now);
},/UTC_TIMESTAMP_REQUIRED/);
rejected('nanoseconds timestamp blocked',()=>{
  verifyOne(sign(count,countExp,{issued_at:'2026-10-15T00:00:00.000Z'}),
            count.trust,countExp,now);
},/UTC_TIMESTAMP_REQUIRED/);
rejected('JSON extra whitespace forbidden',()=>{
  verifyOne(Buffer.concat([Buffer.from('\n'),rawCount]),count.trust,countExp,now);
},/NONCANONICAL_OR_DUPLICATE_JSON/);
rejected('duplicate JSON keys forbidden',()=>{
  const t=rawCount.toString('utf8').replace('"schema":','"schema":"other","schema":');
  verifyOne(Buffer.from(t,'utf8'),count.trust,countExp,now);
},/NONCANONICAL_OR_DUPLICATE_JSON/);
rejected('unsafe large integer in JSON forbidden',()=>{
  const t=rawCount.toString('utf8').replace('"schema":', '"extra":9007199254740993,"schema":');
  verifyOne(Buffer.from(t),count.trust,countExp,now);
},/UNSAFE_OR_FRACTIONAL_NUMBER/);
rejected('tampered signature rejected',()=>{
  const bad=JSON.parse(rawCount.toString('utf8'));
  bad.signature_b64url='A'.repeat(86);
  verifyOne(Buffer.from(canonical(bad)),count.trust,countExp,now);
},/SIGNATURE_MISMATCH|SIGNATURE_NONCANONICAL/);
rejected('malformed base64url signature rejected',()=>{
  const bad=JSON.parse(rawCount.toString('utf8'));
  bad.signature_b64url='!'.repeat(86);
  verifyOne(Buffer.from(canonical(bad)),count.trust,countExp,now);
},/SIGNATURE_ENCODING_INVALID/);
rejected('invalid UTF-8 rejected',()=>{
  verifyOne(Buffer.from([0xff,0xfe]),count.trust,countExp,now);
},/ENVELOPE_JSON_INVALID/);
rejected('bad trust fingerprint blocked',()=>{
  verifyOne(rawCount,{...count.trust,fingerprint_sha256:'f'.repeat(64)},countExp,now);
},/TRUST_FINGERPRINT_MISMATCH/);
rejected('malformed trust key blocked',()=>{
  verifyOne(rawCount,{...count.trust,public_key_pem:'invalid'},countExp,now);
},/TRUST_KEY_MALFORMED/);
rejected('unrecognized audience blocked',()=>{
  const exp={...countExp,audience:'different'};
  verifyOne(sign(count,exp),count.trust,exp,now);
},/EVIDENCE_AUDIENCE_INVALID/);
rejected('binding to a different snapshot blocked',()=>{
  verifyOne(rawCount,count.trust,{...countExp,snapshot_id:'snapshot-'+'0'.repeat(64)},now);
},/EVIDENCE_BINDING_MISMATCH_snapshot_id/);
console.log('D2 dual detached Ed25519 offline tests: '+passed+' PASS, send/publish always false');
