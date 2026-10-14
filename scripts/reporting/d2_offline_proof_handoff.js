'use strict';
/*
 * OFFLINE ONLY: match the strict, synthetic Python D2 preparation receipts
 * to separately signed count and billing bytes. These are locally supplied
 * proofs and test roots, NOT independently trusted issuer or provider evidence.
 * There is no network, key store, sender, retry or publisher.
 */
const crypto=require('node:crypto');
const {verifyPair,D2EvidenceBlocked,canonical}=
  require('./d2_detached_evidence');
const SHA=/^[0-9a-f]{64}$/;
const PREP_KEYS=[
  'api_send_allowed','attempt_id','billing_evidence_kind',
  'count_evidence_kind','count_request_sha256','counted_input_tokens',
  'counted_model_cost_usd','create_request_sha256','lane',
  'max_input_tokens','max_model_cost_usd','max_output_tokens',
  'monthly_effective_cap_usd','monthly_inputs_sha256',
  'monthly_total_with_reservation_usd','publication_allowed','raw_count_sha256',
  'report_id','revision','run_id','schema','snapshot_id'
];
const MONTH_KEYS=[
  'approved_month_cap_usd','month_jst','org_hard_limit_enabled',
  'org_hard_limit_usd','outstanding_reservations_usd',
  'project_hard_limit_enabled','project_hard_limit_usd',
  'report_id','reported_month_spend_usd'
];
function fail(s){throw new D2EvidenceBlocked(s);}
function exact(x,keys){
  return x&&Object.getPrototypeOf(x)===Object.prototype &&
    JSON.stringify(Object.keys(x).sort())===JSON.stringify(keys.slice().sort());
}
function sha(b){return crypto.createHash('sha256').update(b).digest('hex');}
function parseCanonical(b,limit){
  if(!Buffer.isBuffer(b)||b.length===0||b.length>limit)fail('HANDOFF_BYTES_INVALID');
  let parsed;
  try{
    parsed=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(b));
  }catch(_){fail('HANDOFF_JSON_INVALID');}
  if(!b.equals(Buffer.from(canonical(parsed),'utf8')))
    fail('HANDOFF_NONCANONICAL_JSON');
  return parsed;
}
// Recheck the meaning of Python's saved count response, not only its hash.
// Responses input_tokens objects are flat. Lex the member names to reject
// duplicate JSON keys (JSON.parse alone silently uses the last occurrence).
// Do not require canonical response bytes: the provider may add whitespace.
function reviewCountSemantics(raw,prep){
  let object,text;
  try{
    text=new TextDecoder('utf-8',{fatal:true}).decode(raw);
    object=JSON.parse(text);
  }catch(_){fail('HANDOFF_COUNT_JSON_INVALID');}
  if(!exact(object,['object','input_tokens'])||
      object.object!=='response.input_tokens')
    fail('HANDOFF_COUNT_SCHEMA_INVALID');
  const memberNames=[];
  const keyPattern=/"(?:[^"\\\u0000-\u001f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"\s*:/g;
  try{
    for(const match of text.matchAll(keyPattern)){
      memberNames.push(JSON.parse(match[0].slice(0,match[0].lastIndexOf(':')).trim()));
    }
  }catch(_){fail('HANDOFF_COUNT_DUPLICATE_OR_UNSAFE_KEYS');}
  if(memberNames.length!==2||
      new Set(memberNames).size!==2||
      !memberNames.includes('object')||!memberNames.includes('input_tokens'))
    fail('HANDOFF_COUNT_DUPLICATE_OR_UNSAFE_KEYS');
  if(!Number.isSafeInteger(prep.max_input_tokens)||
      prep.max_input_tokens<1||prep.max_input_tokens>12000||
      !Number.isSafeInteger(object.input_tokens)||
      object.input_tokens<0||object.input_tokens>prep.max_input_tokens||
      object.input_tokens!==prep.counted_input_tokens)
    fail('HANDOFF_COUNTED_INPUT_TOKENS_MISMATCH');
}

function reviewPreparedHandoff({
  preparationBytes,countBytes,monthlyBytes,countProof,billingProof,
  trustRoots,expectations,nowMs
}){
  // Never read arbitrary local paths or let a proof file choose its own root.
  const prep=parseCanonical(preparationBytes,16384);
  const monthly=parseCanonical(monthlyBytes,8192);
  if(!exact(prep,PREP_KEYS)||prep.schema!=='d2-offline-preparation/v2'||
      prep.lane!=='api-shadow'||prep.api_send_allowed!==false||
      prep.publication_allowed!==false||
      prep.count_evidence_kind!=='SYNTHETIC_FIXTURE_NOT_AUTHENTICATED'||
      prep.billing_evidence_kind!=='SYNTHETIC_VALUES_NOT_AUTHENTICATED')
    fail('HANDOFF_PREPARATION_SCHEMA_INVALID');
  if(!exact(monthly,MONTH_KEYS)||monthly.report_id!==prep.report_id)
    fail('HANDOFF_MONTHLY_INPUT_SCHEMA_INVALID');
  for(const field of ['create_request_sha256','count_request_sha256',
    'monthly_inputs_sha256','raw_count_sha256']){
    if(typeof prep[field]!=='string'||!SHA.test(prep[field]))
      fail('HANDOFF_PREPARATION_DIGEST_INVALID');
  }
  if(!Buffer.isBuffer(countBytes)||countBytes.length===0||
      countBytes.length>16384)fail('HANDOFF_COUNT_BYTES_INVALID');
  if(sha(countBytes)!==prep.raw_count_sha256)
    fail('HANDOFF_RAW_COUNT_DIGEST_MISMATCH');
  reviewCountSemantics(countBytes,prep);
  if(sha(monthlyBytes)!==prep.monthly_inputs_sha256)
    fail('HANDOFF_MONTHLY_INPUT_DIGEST_MISMATCH');

  if(!expectations||!exact(expectations,['input_count','monthly_billing']))
    fail('HANDOFF_EXPECTATIONS_REQUIRED');
  const actual={input_count:sha(countBytes),monthly_billing:sha(monthlyBytes)};
  for(const role of ['input_count','monthly_billing']){
    const e=expectations[role];
    if(!e||e.evidence_sha256!==actual[role])
      fail('HANDOFF_PROOF_RAW_DIGEST_MISMATCH_'+role);
    for(const [key,value] of Object.entries({
      report_id:prep.report_id,snapshot_id:prep.snapshot_id,
      run_id:prep.run_id,attempt_id:prep.attempt_id,
      create_request_sha256:prep.create_request_sha256,
      count_request_sha256:prep.count_request_sha256,
      monthly_inputs_sha256:prep.monthly_inputs_sha256
    })){
      if(e[key]!==value)fail('HANDOFF_PROOF_PREPARATION_MISMATCH_'+role+'_'+key);
    }
  }
  const verified=verifyPair(
    countProof,billingProof,trustRoots,expectations,nowMs);
  if(verified.signatures_checked!==2||
      verified.api_send_allowed!==false||
      verified.publication_allowed!==false)
    fail('HANDOFF_UNSAFE_VERDICT');
  return Object.freeze({
    status:'OFFLINE_PREPARATION_DETACHED_PROOFS_MATCH_UNATTESTED',
    signatures_checked:2,
    local_preparation_sha256:sha(preparationBytes),
    provider_authenticated:false,
    billing_authenticated:false,
    independent_root_provenance_verified:false,
    externally_attested:false,
    retry_allowed:false,api_send_allowed:false,publication_allowed:false
  });
}
module.exports={reviewPreparedHandoff,D2EvidenceBlocked};
