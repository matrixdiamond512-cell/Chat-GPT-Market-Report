'use strict';
/*
 * Offline-only detached Ed25519 verification of proof SHAPES.
 * Test-generated signatures are NOT OpenAI attestations. There are no
 * production trust roots, network clients, API senders or publishers.
 * All results remain non-authorizing.
 */
const crypto=require('node:crypto');
const SCHEMA='d2-external-evidence-proof/v1';
const PREFIX=Buffer.from('MARKET_REPORT_D2_EXTERNAL_EVIDENCE_V1\n','utf8');
const HASH=/^[0-9a-f]{64}$/;
const IDENT=/^[A-Za-z0-9_-]{1,80}$/;
const UTC=/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const ROLES=new Set(['input_count','monthly_billing']);
const ENVELOPE_KEYS=['key_id','payload','schema','signature_b64url'];
const PAYLOAD_KEYS=[
  'attempt_id','audience','count_request_sha256','create_request_sha256','evidence_sha256',
  'expires_at','issued_at','issuer','monthly_inputs_sha256','report_id',
  'run_id','scope','snapshot_id'
];
class D2EvidenceBlocked extends Error{
  constructor(reason){super(reason);this.name='D2EvidenceBlocked';}
}
function fail(reason){throw new D2EvidenceBlocked(reason);}
function keysExactly(x,keys){
  return x&&Object.getPrototypeOf(x)===Object.prototype &&
    JSON.stringify(Object.keys(x).sort())===JSON.stringify([...keys].sort());
}
function safeString(s){
  if(typeof s!=='string')fail('NON_STRING_CANONICAL_VALUE');
  for(let i=0;i<s.length;i++){
    let n=s.charCodeAt(i);
    if(n>=0xd800&&n<=0xdbff){
      i++;
      if(i>=s.length||s.charCodeAt(i)<0xdc00||s.charCodeAt(i)>0xdfff)
        fail('INVALID_UNICODE_SURROGATE');
    }else if(n>=0xdc00&&n<=0xdfff)fail('INVALID_UNICODE_SURROGATE');
  }
  return s;
}
function canonical(x){
  if(x===null||typeof x==='boolean')return JSON.stringify(x);
  if(typeof x==='string')return JSON.stringify(safeString(x));
  if(typeof x==='number'){
    if(!Number.isSafeInteger(x))fail('UNSAFE_OR_FRACTIONAL_NUMBER');
    return String(x);
  }
  if(Array.isArray(x))return '['+x.map(canonical).join(',')+']';
  if(!x||Object.getPrototypeOf(x)!==Object.prototype)fail('INVALID_CANONICAL_OBJECT');
  const keys=Object.keys(x).sort();
  for(const k of keys){
    if(!/^[A-Za-z_][A-Za-z0-9_]*$/.test(k))fail('INVALID_CANONICAL_KEY');
  }
  return '{'+keys.map(k=>canonical(k)+':'+canonical(x[k])).join(',')+'}';
}
function stamp(value){
  if(typeof value!=='string'||!UTC.test(value))fail('UTC_TIMESTAMP_REQUIRED');
  const t=Date.parse(value);
  if(!Number.isFinite(t)||new Date(t).toISOString()!==value.replace('Z','.000Z'))
    fail('NONCANONICAL_TIMESTAMP');
  return t;
}
function bytes(raw){
  if(!Buffer.isBuffer(raw)||raw.length<2||raw.length>16384)fail('ENVELOPE_BYTES_INVALID');
  let value;
  try{
    const td=new TextDecoder('utf-8',{fatal:true});
    value=JSON.parse(td.decode(raw));
  }catch(_){fail('ENVELOPE_JSON_INVALID');}
  // Canonical byte comparison rejects duplicate keys, whitespace tricks and
  // unsafe JSON number notation rather than accepting a last-key-wins parse.
  if(!raw.equals(Buffer.from(canonical(value),'utf8')))
    fail('NONCANONICAL_OR_DUPLICATE_JSON');
  return value;
}
function requireHash(h,reason){
  if(typeof h!=='string'||!HASH.test(h))fail(reason);
}
/*
 * trust and expected must come from a trusted operator-controlled source,
 * never the envelope or a caller-controlled manifest. No such root is
 * configured in this project. Even a valid signature is not provider proof.
 */
function verifyOne(rawEnvelope,trust,expected,nowMs){
  const env=bytes(rawEnvelope);
  if(!keysExactly(env,ENVELOPE_KEYS)||env.schema!==SCHEMA)
    fail('ENVELOPE_SCHEMA_INVALID');
  const p=env.payload;
  if(!keysExactly(p,PAYLOAD_KEYS))fail('PAYLOAD_SCHEMA_INVALID');
  if(!trust||!keysExactly(trust,['key_id','public_key_pem','fingerprint_sha256']))
    fail('TRUST_ROOT_REQUIRED');
  if(!expected||!keysExactly(expected,[
    'attempt_id','audience','count_request_sha256','create_request_sha256','evidence_sha256',
    'monthly_inputs_sha256','report_id','run_id','scope','snapshot_id'
  ]))fail('INDEPENDENT_EXPECTATIONS_REQUIRED');
  if(!IDENT.test(env.key_id)||env.key_id!==trust.key_id||
      p.issuer!==trust.key_id||!IDENT.test(p.issuer))fail('SIGNER_KEY_ID_MISMATCH');
  if(!ROLES.has(p.scope)||p.scope!==expected.scope)fail('EVIDENCE_SCOPE_MISMATCH');
  if(p.audience!=='market-report-d2-shadow-offline'||
      expected.audience!==p.audience)fail('EVIDENCE_AUDIENCE_INVALID');
  for(const key of Object.keys(expected)){
    if(p[key]!==expected[key])fail('EVIDENCE_BINDING_MISMATCH_'+key);
  }
  for(const key of ['count_request_sha256','create_request_sha256','evidence_sha256','monthly_inputs_sha256'])
    requireHash(p[key],'EVIDENCE_DIGEST_INVALID_'+key);
  if(typeof p.snapshot_id!=='string'||!/^snapshot-[0-9a-f]{64}$/.test(p.snapshot_id))
    fail('SNAPSHOT_ID_INVALID');
  if(!/^\d{4}-\d{2}-\d{2}_(08|12|16|21)-00$/.test(p.report_id)||
      !IDENT.test(p.run_id)||!IDENT.test(p.attempt_id))fail('RUN_ID_INVALID');
  const first=stamp(p.issued_at),last=stamp(p.expires_at);
  if(typeof nowMs!=='number'||!Number.isSafeInteger(nowMs)||
      last<=first||last-first>5*60000||nowMs<first||nowMs>last)
    fail('EVIDENCE_EXPIRED_OR_NOT_YET_VALID');
  if(typeof trust.public_key_pem!=='string'||
      typeof trust.fingerprint_sha256!=='string'||
      !HASH.test(trust.fingerprint_sha256))fail('TRUST_ROOT_INVALID');
  let key,fingerprint;
  try{
    key=crypto.createPublicKey(trust.public_key_pem);
    if(key.asymmetricKeyType!=='ed25519')fail('ED25519_KEY_REQUIRED');
    fingerprint=crypto.createHash('sha256').update(
      key.export({type:'spki',format:'der'})).digest('hex');
  }catch(e){if(e instanceof D2EvidenceBlocked)throw e;fail('TRUST_KEY_MALFORMED');}
  if(fingerprint!==trust.fingerprint_sha256)fail('TRUST_FINGERPRINT_MISMATCH');
  if(typeof env.signature_b64url!=='string'||
      !/^[A-Za-z0-9_-]{86}$/.test(env.signature_b64url))
    fail('SIGNATURE_ENCODING_INVALID');
  const sig=Buffer.from(env.signature_b64url,'base64url');
  if(sig.length!==64||sig.toString('base64url')!==env.signature_b64url)
    fail('SIGNATURE_NONCANONICAL');
  const signed=Buffer.concat([PREFIX,Buffer.from(canonical(p),'utf8')]);
  if(!crypto.verify(null,signed,key,sig))fail('SIGNATURE_MISMATCH');
  return Object.freeze({
    status:'OFFLINE_DETACHED_SIGNATURE_SHAPE_PASS',
    role:p.scope,signature_mathematically_valid:true,
    transport_authority_independently_verified:false,
    provider_authenticated:false,billing_authenticated:false,
    retry_allowed:false,api_send_allowed:false,publication_allowed:false
  });
}
function verifyPair(rawCount,rawBilling,trustRoots,expected,nowMs){
  if(!trustRoots||!keysExactly(trustRoots,['input_count','monthly_billing'])||
      trustRoots.input_count.key_id===trustRoots.monthly_billing.key_id)
    fail('DISTINCT_ROLE_TRUST_ROOTS_REQUIRED');
  if(!expected||!keysExactly(expected,['input_count','monthly_billing']))
    fail('DISTINCT_ROLE_EXPECTATIONS_REQUIRED');
  if(expected.input_count.scope!=='input_count'||
      expected.monthly_billing.scope!=='monthly_billing')
    fail('ROLE_EXPECTATIONS_INVALID');
  for(const field of ['report_id','run_id','attempt_id','snapshot_id',
                       'create_request_sha256','count_request_sha256','monthly_inputs_sha256','audience']){
    if(expected.input_count[field]!==expected.monthly_billing[field])
      fail('CROSS_ROLE_BINDING_MISMATCH_'+field);
  }
  const a=verifyOne(rawCount,trustRoots.input_count,expected.input_count,nowMs);
  const b=verifyOne(rawBilling,trustRoots.monthly_billing,expected.monthly_billing,nowMs);
  return Object.freeze({
    status:'OFFLINE_DUAL_SIGNATURES_VALID_WITHOUT_EXTERNAL_TRUST',
    signatures_checked:2,count_signature_valid:a.signature_mathematically_valid,
    billing_signature_valid:b.signature_mathematically_valid,
    independent_trust_roots_configured:false,
    actual_provider_evidence_verified:false,
    retry_allowed:false,api_send_allowed:false,publication_allowed:false
  });
}
module.exports={verifyOne,verifyPair,canonical,PREFIX,SCHEMA,D2EvidenceBlocked};
