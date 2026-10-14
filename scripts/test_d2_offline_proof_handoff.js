'use strict';
/* Local only: retrieve real Python D2 synthetic preparation bytes and verify
 * the detached evidence bridge without any remote service or real issuer. */
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const cp=require('node:child_process');
const {canonical,PREFIX,SCHEMA}=require('./reporting/d2_detached_evidence');
const {reviewPreparedHandoff,D2EvidenceBlocked}=
  require('./reporting/d2_offline_proof_handoff');
const pyFixture="import json,sys,base64,tempfile\nfrom pathlib import Path\nfrom dataclasses import asdict\nsys.path.insert(0,'tests')\nfrom test_shadow_worker_offline import fixture_context,fixture_snapshot\nfrom test_d2_responses_contract import provider_fixture\nfrom scripts.reporting.d2_private_store import LocalPrivateEvidenceStore\nfrom scripts.reporting.d2_offline_prepared_run import run_prepared_offline\nfrom scripts.reporting.d2_monthly_budget import MonthlySpendInputs\nfrom scripts.reporting.shadow_worker import json_bytes\nctx=fixture_context()\nsnapshot=fixture_snapshot(ctx)\nmonthly=MonthlySpendInputs(report_id=ctx.report_id,month_jst=ctx.report_date[:7],reported_month_spend_usd='0.80',outstanding_reservations_usd='0.20',approved_month_cap_usd='2.00',project_hard_limit_usd='1.50',org_hard_limit_usd='3.00',project_hard_limit_enabled=True,org_hard_limit_enabled=True)\nwith tempfile.TemporaryDirectory() as tmp:\n  store=LocalPrivateEvidenceStore(Path(tmp)/'private')\n  fixture=lambda request:json.dumps(provider_fixture(ctx,snapshot),ensure_ascii=False,indent=2).encode('utf8')\n  raw_count=b'{\"object\":\"response.input_tokens\",\"input_tokens\":9000}\\n'\n  result=run_prepared_offline(ctx,snapshot,store,fixture,raw_count_fixture=raw_count,monthly_inputs=monthly,run_id='handoff-run',attempt_id='handoff-attempt')\n  prep=store.read_verified(result.preparation_receipt)\n  monthly_bytes=json_bytes(asdict(monthly))\n  print(json.dumps({'preparation_b64':base64.b64encode(prep).decode(),'count_b64':base64.b64encode(raw_count).decode(),'monthly_b64':base64.b64encode(monthly_bytes).decode(),'execution_status':result.execution.status}))";
const source=JSON.parse(cp.execFileSync('python',['-c',pyFixture],
  {encoding:'utf8',timeout:15000,maxBuffer:1024*1024}));
assert.equal(source.execution_status,'OFFLINE_FIXTURE_VALIDATED');
const preparationBytes=Buffer.from(source.preparation_b64,'base64');
const countBytes=Buffer.from(source.count_b64,'base64');
const monthlyBytes=Buffer.from(source.monthly_b64,'base64');
const prep=JSON.parse(preparationBytes.toString('utf8'));
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
function key(id){
  const pair=crypto.generateKeyPairSync('ed25519');
  return {privateKey:pair.privateKey,trust:{
    key_id:id,
    public_key_pem:pair.publicKey.export({type:'spki',format:'pem'}).toString(),
    fingerprint_sha256:sha(pair.publicKey.export({type:'spki',format:'der'}))
  }};
}
const c=key('count-gateway-test'),b=key('billing-gateway-test');
function expected(role,original){
  return {
    attempt_id:prep.attempt_id,audience:'market-report-d2-shadow-offline',
    count_request_sha256:prep.count_request_sha256,
    create_request_sha256:prep.create_request_sha256,
    evidence_sha256:sha(original),monthly_inputs_sha256:prep.monthly_inputs_sha256,
    report_id:prep.report_id,run_id:prep.run_id,
    scope:role,snapshot_id:prep.snapshot_id
  };
}
const e={input_count:expected('input_count',countBytes),
  monthly_billing:expected('monthly_billing',monthlyBytes)};
function sign(k,exp){
  const payload={...exp,issuer:k.trust.key_id,
    issued_at:'2026-10-15T00:00:00Z',
    expires_at:'2026-10-15T00:03:00Z'};
  const raw=Buffer.concat([PREFIX,Buffer.from(canonical(payload),'utf8')]);
  return Buffer.from(canonical({key_id:k.trust.key_id,payload,schema:SCHEMA,
    signature_b64url:crypto.sign(null,raw,k.privateKey).toString('base64url')}),'utf8');
}
const base={
  preparationBytes,countBytes,monthlyBytes,
  countProof:sign(c,e.input_count),billingProof:sign(b,e.monthly_billing),
  trustRoots:{input_count:c.trust,monthly_billing:b.trust},
  expectations:e,nowMs:Date.parse('2026-10-15T00:01:00Z')
};
let passes=0;
function test(label,fn){fn();passes++;console.log('PASS '+label);}
function rejected(label,overrides,reason){
  test(label,()=>assert.throws(
    ()=>reviewPreparedHandoff({...base,...overrides}),reason||D2EvidenceBlocked));
}
test('real Python preparation to separate signed role data matches, never authorizes',()=>{
  const x=reviewPreparedHandoff(base);
  assert.equal(x.status,'OFFLINE_PREPARATION_DETACHED_PROOFS_MATCH_UNATTESTED');
  assert.equal(x.signatures_checked,2);
  assert.equal(x.local_preparation_sha256,sha(preparationBytes));
  for(const k of ['provider_authenticated','billing_authenticated',
    'independent_root_provenance_verified','externally_attested',
    'retry_allowed','api_send_allowed','publication_allowed'])
    assert.equal(x[k],false,k);
});
rejected('count raw changed after Python stage',
  {countBytes:Buffer.concat([countBytes,Buffer.from(' ')])},
  /HANDOFF_RAW_COUNT_DIGEST_MISMATCH/);
rejected('monthly raw changes despite the same sum and minimum cap',
  {monthlyBytes:Buffer.from(monthlyBytes.toString().replace('0.80','0.79'))},
  /HANDOFF_MONTHLY_INPUT_DIGEST_MISMATCH/);
rejected('create-request digest changed inside preparation receipt',(()=>{
  const d={...prep,create_request_sha256:'0'.repeat(64)};
  return {preparationBytes:Buffer.from(canonical(d))};
})(),/HANDOFF_PROOF_PREPARATION_MISMATCH_input_count_create_request_sha256/);
rejected('count-request digest changed inside preparation receipt',(()=>{
  const d={...prep,count_request_sha256:'0'.repeat(64)};
  return {preparationBytes:Buffer.from(canonical(d))};
})(),/HANDOFF_PROOF_PREPARATION_MISMATCH_input_count_count_request_sha256/);
rejected('other monthly inputs hash inside preparation blocked',(()=>{
  const d={...prep,monthly_inputs_sha256:'0'.repeat(64)};
  return {preparationBytes:Buffer.from(canonical(d))};
})(),/HANDOFF_MONTHLY_INPUT_DIGEST_MISMATCH/);
rejected('signed count proof does not match raw count bytes',
  {expectations:{...e,input_count:{...e.input_count,evidence_sha256:'1'.repeat(64)}}},
  /HANDOFF_PROOF_RAW_DIGEST_MISMATCH_input_count/);
rejected('billing and count proofs cannot be swapped',
  {countProof:base.billingProof,billingProof:base.countProof},
  /SIGNER_KEY_ID_MISMATCH/);
rejected('distinct key IDs reusing same actual signer cannot pass',(()=>{
  const another={privateKey:c.privateKey,trust:{...c.trust,key_id:'billing-alias'}};
  return {billingProof:sign(another,e.monthly_billing),
    trustRoots:{input_count:c.trust,monthly_billing:another.trust}};
})(),/SAME_PUBLIC_KEY_USED_FOR_DISTINCT_ROLES/);
rejected('old v1 preparation cannot be accepted',(()=>{
  const d={...prep,schema:'d2-offline-preparation/v1'};
  return {preparationBytes:Buffer.from(canonical(d))};
})(),/HANDOFF_PREPARATION_SCHEMA_INVALID/);
rejected('self-declared trust root embedded into preparation forbidden',(()=>{
  const d={...prep,trust_roots:base.trustRoots};
  return {preparationBytes:Buffer.from(canonical(d))};
})(),/HANDOFF_PREPARATION_SCHEMA_INVALID/);
rejected('altered report ID in preparation not accepted',(()=>{
  const d={...prep,report_id:'2026-10-15_12-00'};
  return {preparationBytes:Buffer.from(canonical(d))};
})(),/HANDOFF_MONTHLY_INPUT_SCHEMA_INVALID/);
rejected('unaligned monthly report identifier forbidden',(()=>{
  const d=JSON.parse(monthlyBytes.toString());
  d.report_id='2026-10-15_12-00';
  return {monthlyBytes:Buffer.from(canonical(d))};
})(),/HANDOFF_MONTHLY_INPUT_SCHEMA_INVALID/);
rejected('expired proof cannot be reused',{nowMs:Date.parse('2026-10-15T00:04:00Z')},
  /EVIDENCE_EXPIRED_OR_NOT_YET_VALID/);
rejected('no independent expectations is fail closed',{expectations:null},
  /HANDOFF_EXPECTATIONS_REQUIRED/);
rejected('noncanonical preparation whitespace rejected',
  {preparationBytes:Buffer.concat([Buffer.from('\n'),preparationBytes])},
  /HANDOFF_NONCANONICAL_JSON/);
rejected('noncanonical monthly JSON whitespace rejected',
  {monthlyBytes:Buffer.concat([monthlyBytes,Buffer.from('\n')])},
  /HANDOFF_NONCANONICAL_JSON/);
// Reconstruct a fully hash-consistent, freshly signed synthetic count to
// prove the bridge is checking semantic agreement, not just SHA/signatures.
function withResignedCount(raw){
  const prepNext={...prep,raw_count_sha256:sha(raw)};
  const countExpected={...e.input_count,evidence_sha256:sha(raw)};
  return {
    countBytes:raw,
    preparationBytes:Buffer.from(canonical(prepNext),'utf8'),
    expectations:{input_count:countExpected,monthly_billing:e.monthly_billing},
    countProof:sign(c,countExpected)
  };
}
rejected('validly resigned raw count of 9001 conflicts with frozen 9000',(()=>{
  const newBytes=Buffer.from('{"object":"response.input_tokens","input_tokens":9001}\n');
  return withResignedCount(newBytes);
})(),/HANDOFF_COUNTED_INPUT_TOKENS_MISMATCH/);
rejected('duplicate count JSON field rejected even when bytes SHA and signature agree',(()=>{
  const newBytes=Buffer.from('{"object":"response.input_tokens","input_tokens":9000,"input_tokens":9000}\n');
  return withResignedCount(newBytes);
})(),/HANDOFF_COUNT_DUPLICATE_OR_UNSAFE_KEYS/);
rejected('count object type changed and re-signed is not a token response',(()=>{
  const newBytes=Buffer.from('{"object":"response","input_tokens":9000}\n');
  return withResignedCount(newBytes);
})(),/HANDOFF_COUNT_SCHEMA_INVALID/);
rejected('prepared counted_input_tokens changed with signatures unchanged',(()=>{
  const changed={...prep,counted_input_tokens:8999};
  return {preparationBytes:Buffer.from(canonical(changed),'utf8')};
})(),/HANDOFF_COUNTED_INPUT_TOKENS_MISMATCH/);
test('whitespace-flexible count with identical token semantics still stays BLOCKED',()=>{
  const newBytes=Buffer.from(' { "input_tokens":9000, "object":"response.input_tokens" }\n');
  const x=reviewPreparedHandoff({...base,...withResignedCount(newBytes)});
  assert.equal(x.publication_allowed,false);
  assert.equal(x.api_send_allowed,false);
});
test('no network or writer dependency in bridge',()=>{
  const fs=require('node:fs');
  const txt=fs.readFileSync('scripts/reporting/d2_offline_proof_handoff.js','utf8');
  assert.doesNotMatch(txt,/require\(['"](?:node:)?(?:http|https|net|fs|child_process)/);
});
console.log('D2 synthetic signed evidence handoff: '+passes+
  ' PASS; no trust activation, sender, cost or public write');
