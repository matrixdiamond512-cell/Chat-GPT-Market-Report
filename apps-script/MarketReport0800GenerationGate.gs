/* Mandatory new-report 08:00 generation QA. No report write may precede this gate. */
var MR0800_CONTRACT_ID_ = 'market-report-0800-infographic-facts-v1';
var MR0800_GATE_NAME_ = 'PRE_SAVE_AND_PRE_RENDER_08_00_GENERATION_QA';
var MR0800_SECTIONS_ = ['title_datetime','overall_judgement','attention_points','market_theme','material_market_relation',
  'ny_timeline','ny_indices','major_market_data','ny_market_points','cross_asset_flow','positioning',
  'six_market_outlook','news_materials','scenario_analysis','handover','top_three_conditions','final_summary'];
var MR0800_STAGES_ = ['開始前','開場','中盤','終盤','東京時間／次時間帯への引継ぎ'];
var MR0800_INDEX_LABELS_ = ['NYダウ','NASDAQ総合','S&P500','Russell 2000'];
var MR0800_DATA_LABELS_ = ['日経225現物','TOPIX','日経225先物（大阪取引所）','USD/JPY','EUR/USD','COMEX金先物','WTI原油','VIX','日経VI','Fear & Greed Index','米10年債利回り','日本10年国債利回り','日経225予想PER','日経225予想EPS'];
var MR0800_MARKETS_ = ['金','WTI原油','日経225先物（大阪取引所）','USD/JPY','EUR/USD','BTCUSD'];
var MR0800_SCENARIOS_ = ['上振れ','メイン','代替','崩れる条件'];

function marketReport0800GenerationQa_(payload) {
  var errors = [];
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return marketReport0800QaResult_(['GENERATION_PAYLOAD_INVALID']);
  var body = String(payload.body_text || '');
  var bodyHash = marketReportSha256_(Utilities.newBlob(body, 'text/plain').getBytes());
  var idMatch = String(payload.report_datetime || '').match(/^(\d{4}-\d{2}-\d{2})T08:00(?::00)?(?:\+09:00|\+0900)$/);
  if (!body.trim()) errors.push('BODY_TEXT_MISSING');
  if (payload.body_hash !== bodyHash) errors.push('BODY_HASH_MISMATCH');
  if (!idMatch || payload.report_id !== idMatch[1] + '_08-00') errors.push('REPORT_ID_OR_SLOT_MISMATCH');
  if (payload.source_type !== 'GOOGLE_DOCS' || payload.synthetic_fixture === true) errors.push('NON_LIVE_OR_SYNTHETIC_SOURCE_CANNOT_BE_SAVED');
  var sections = payload.sections;
  if (!Array.isArray(sections) || JSON.stringify(sections.map(function(x){return x.section_id;})) !== JSON.stringify(MR0800_SECTIONS_)) errors.push('FIXED_08_SECTION_ORDER_MISMATCH');
  var rawFacts = Array.isArray(payload.structured_facts) ? payload.structured_facts : [];
  if (!rawFacts.length) errors.push('STRUCTURED_FACTS_MISSING');
  var facts = {}, referenced = {}, bySection = {};
  MR0800_SECTIONS_.forEach(function(id){bySection[id]=[];});
  rawFacts.forEach(function(fact){
    if (!fact || typeof fact !== 'object' || !fact.fact_id || facts[fact.fact_id]) { errors.push('FACT_ID_MISSING_OR_DUPLICATE'); return; }
    if (!fact.source_excerpt || body.indexOf(String(fact.source_excerpt)) < 0 || !fact.text || String(fact.source_excerpt).indexOf(String(fact.text)) < 0) errors.push('FACT_SOURCE_BINDING_INVALID:' + fact.fact_id);
    if (MR0800_SECTIONS_.indexOf(fact.section_id) < 0 || !fact.fields || typeof fact.fields !== 'object') errors.push('FACT_SECTION_OR_FIELDS_INVALID:' + fact.fact_id);
    facts[fact.fact_id] = fact;
  });
  (Array.isArray(sections) ? sections : []).forEach(function(section){
    if (!section || !Array.isArray(section.fact_ids) || !bySection[section.section_id]) { errors.push('SECTION_FACT_IDS_INVALID'); return; }
    section.fact_ids.forEach(function(id){
      var fact=facts[id]; if (!fact || fact.section_id !== section.section_id) {errors.push('SECTION_FACT_UNRESOLVED:' + id); return;}
      referenced[id]=true; bySection[section.section_id].push(fact);
    });
  });
  Object.keys(facts).forEach(function(id){if(!referenced[id]) errors.push('FACT_NOT_ASSIGNED_TO_SECTION:' + id);});
  function field(fact,key){
    var value=fact && fact.fields && fact.fields[key];
    if(typeof value !== 'string' || !value.trim()) {errors.push('REQUIRED_FIELD_MISSING:' + (fact && fact.fact_id) + ':' + key); return '';}
    if(String(fact.source_excerpt).indexOf(value)<0) errors.push('REQUIRED_FIELD_NOT_SOURCE_BOUND:' + fact.fact_id + ':' + key);
    return value;
  }
  var judgement=bySection.overall_judgement;
  if(judgement.length<2 || !judgement.some(function(f){return f.fields.role==='judgement';}) || !judgement.some(function(f){return f.fields.role==='reason';})) errors.push('OVERALL_JUDGEMENT_AND_REASON_REQUIRED');
  if(bySection.attention_points.length!==5 || bySection.attention_points.some(function(f,i){return f.fields.order!==i+1;})) errors.push('EXACTLY_FIVE_ATTENTION_POINTS_REQUIRED');
  var themes=bySection.market_theme;
  if(!themes.some(function(f){return f.fields.role==='central_theme';}) || !themes.some(function(f){return f.fields.role==='support';})) errors.push('MARKET_THEME_AND_SUPPORT_REQUIRED');
  bySection.material_market_relation.forEach(function(f){['material','affected_market','direction'].forEach(function(k){field(f,k);});});
  if(!bySection.material_market_relation.length) errors.push('MATERIAL_MARKET_RELATION_REQUIRED');
  if(JSON.stringify(bySection.ny_timeline.map(function(f){return f.fields.stage;}))!==JSON.stringify(MR0800_STAGES_)) errors.push('FIVE_ORDERED_NY_TIMELINE_STAGES_REQUIRED');
  function rowLabels(id){return bySection[id].map(function(f){return f.fields.row && f.fields.row[0];});}
  MR0800_INDEX_LABELS_.forEach(function(label){if(rowLabels('ny_indices').indexOf(label)<0)errors.push('NY_INDEX_ROW_MISSING:'+label);});
  MR0800_DATA_LABELS_.forEach(function(label){if(rowLabels('major_market_data').indexOf(label)<0)errors.push('MARKET_DATA_ROW_MISSING:'+label);});
  if(bySection.ny_market_points.length<2) errors.push('NY_MARKET_POINTS_INSUFFICIENT');
  bySection.cross_asset_flow.forEach(function(f){['origin_asset','destination_asset','direction','causal_link'].forEach(function(k){field(f,k);});});
  if(!bySection.cross_asset_flow.length) errors.push('CROSS_ASSET_FLOW_REQUIRED');
  if(!bySection.positioning.length) errors.push('POSITIONING_FACT_REQUIRED');
  bySection.positioning.forEach(function(f){if(typeof f.fields.category!=='string' || !f.fields.category.trim())errors.push('POSITIONING_CATEGORY_REQUIRED:'+f.fact_id);});
  bySection.six_market_outlook.forEach(function(f){['current_value','current_value_as_of','judgement','bullish_condition','bearish_condition'].forEach(function(k){field(f,k);});});
  if(JSON.stringify(bySection.six_market_outlook.map(function(f){return f.fields.market;}))!==JSON.stringify(MR0800_MARKETS_)) errors.push('SIX_MARKET_OUTLOOK_COVERAGE_OR_ORDER_INVALID');
  if(!bySection.news_materials.length) errors.push('AT_LEAST_ONE_NEWS_ITEM_REQUIRED');
  bySection.news_materials.forEach(function(f){['headline','time','affected_market','price_reaction'].forEach(function(k){field(f,k);});});
  if(JSON.stringify(bySection.scenario_analysis.map(function(f){return f.fields.scenario;}))!==JSON.stringify(MR0800_SCENARIOS_)) errors.push('FOUR_ORDERED_SCENARIO_FACTS_REQUIRED');
  if(!bySection.handover.length || bySection.handover.some(function(f,i){return f.fields.order!==i+1;})) errors.push('NEXT_SLOT_HANDOVER_REQUIRED');
  if(bySection.top_three_conditions.length!==3 || bySection.top_three_conditions.some(function(f,i){return f.fields.order!==i+1;})) errors.push('EXACTLY_THREE_ORDERED_TOP_CONDITIONS_REQUIRED');
  if(!bySection.final_summary.length) errors.push('FINAL_SUMMARY_REQUIRED');
  var numeric=Array.isArray(payload.numeric_registry)?payload.numeric_registry:[];
  if(!numeric.length) errors.push('NUMERIC_REGISTRY_REQUIRED');
  var numericIds={}; var numericFactIds={};
  numeric.forEach(function(entry){
    var fact=facts[entry.fact_id];
    var valid=entry && entry.numeric_id && !numericIds[entry.numeric_id] && fact && entry.source_excerpt===fact.source_excerpt
      && body.indexOf(String(entry.source_excerpt||''))>=0 && String(entry.value||'')
      && String(entry.source_excerpt||'').indexOf(String(entry.value||''))>=0 && String(entry.as_of||'')
      && String(entry.as_of_source_excerpt||'') && body.indexOf(String(entry.as_of_source_excerpt||''))>=0
      && String(entry.as_of_source_excerpt||'').indexOf(String(entry.as_of||''))>=0
      && (!entry.unit || String(entry.source_excerpt||'').indexOf(String(entry.unit))>=0);
    if(!valid) errors.push('NUMERIC_REGISTRY_IDENTITY_INVALID:' + (entry && entry.numeric_id || 'unknown'));
    if(entry && entry.numeric_id) numericIds[entry.numeric_id]=true;
    if(entry && entry.fact_id) numericFactIds[entry.fact_id]=true;
  });
  ['ny_indices','major_market_data'].forEach(function(sectionId){bySection[sectionId].forEach(function(f){
    if(!Array.isArray(f.fields.row) || f.fields.row.length<2 || !f.fields.row.slice(1).some(function(v){return String(v||'').trim();})) errors.push('NUMERIC_TABLE_ROW_VALUE_MISSING:'+f.fact_id);
    if(!numericFactIds[f.fact_id]) errors.push('NUMERIC_FACT_REGISTRY_LINK_MISSING:'+f.fact_id);
  });});
  bySection.six_market_outlook.forEach(function(f){
    var match=String(f.fields.current_value||'').match(/[-+]?\d[\d,.]*(?:%|[A-Za-z/]+)?/);
    if(!match) return;
    var linkedId=f.fields.current_value_numeric_id;
    var linked=numeric.some(function(entry){return entry.numeric_id===linkedId && entry.fact_id===f.fact_id
      && String(match[0]).replace(/%$/,'')===String(entry.value||'').replace(/%$/,'');});
    if(!linked) errors.push('SIX_MARKET_CURRENT_VALUE_NUMERIC_LINK_MISSING:'+f.fact_id);
  });
  var snapshot=payload.market_data_snapshot || {};
  var identity=payload.source_snapshot_identity || {};
  var expectedSnapshotId='docs-revision-sha256:'+marketReport0800Sha256_({
    source_document_id:identity.source_document_id||'',revision:identity.revision||'',body_hash:identity.body_hash||''
  });
  if(identity.method!=='SHA256_CANONICAL_SOURCE_ID_REVISION_BODY_HASH'
      || identity.source_document_id!==payload.source_document_id || identity.revision!==payload.revision
      || identity.body_hash!==bodyHash || payload.source_snapshot_id!==expectedSnapshotId
      || snapshot.snapshot_id!==payload.source_snapshot_id) errors.push('SOURCE_SNAPSHOT_IDENTITY_INVALID');
  var expectedSnapshotFields={snapshot_id:payload.source_snapshot_id,report_id:payload.report_id,report_as_of:payload.report_datetime,
    source_document_id:payload.source_document_id,source_document_revision:payload.revision,
    source_document_created_at:payload.source_created_at,source_document_updated_at:payload.source_updated_at,source_body_sha256:bodyHash};
  Object.keys(expectedSnapshotFields).forEach(function(key){if(snapshot[key]!==expectedSnapshotFields[key])errors.push('SNAPSHOT_SOURCE_BINDING_MISMATCH:'+key);});
  var sourceNumeric=Array.isArray(payload.source_numeric_registry)?payload.source_numeric_registry:[];
  var sourceNumericHash=marketReport0800Sha256_({numeric_registry:sourceNumeric});
  var prevalidation=payload.numeric_registry_prevalidation||{};
  if(sourceNumericHash!==payload.source_numeric_registry_sha256 || prevalidation.status!=='PASS'
      || prevalidation.body_hash!==bodyHash || prevalidation.source_numeric_registry_sha256!==sourceNumericHash
      || prevalidation.source_registry_count!==sourceNumeric.length) errors.push('UPSTREAM_NUMERIC_REGISTRY_PASS_EVIDENCE_INVALID');
  if(marketReport0800Canonical_(payload.numeric_registry||[])!==marketReport0800Canonical_(sourceNumeric)
      || marketReport0800Canonical_(snapshot.numeric_registry||[])!==marketReport0800Canonical_(sourceNumeric)
      || snapshot.source_numeric_registry_sha256!==sourceNumericHash
      || marketReport0800Canonical_(snapshot.numeric_registry_prevalidation||{})!==marketReport0800Canonical_(prevalidation)) errors.push('SNAPSHOT_NUMERIC_REGISTRY_BINDING_INVALID');
  var snapshotFacts=Array.isArray(snapshot.facts)?snapshot.facts:[];
  var snapshotFactsById={}; snapshotFacts.forEach(function(f){if(f && f.fact_id)snapshotFactsById[f.fact_id]=f;});
  if(Object.keys(snapshotFactsById).length!==Object.keys(facts).length) errors.push('SNAPSHOT_FACT_ID_SET_MISMATCH');
  Object.keys(facts).forEach(function(id){
    var sf=snapshotFactsById[id], f=facts[id];
    if(!sf || sf.section_id!==f.section_id || sf.text!==f.text || sf.source_excerpt!==f.source_excerpt) errors.push('SNAPSHOT_FACT_MISMATCH:'+id);
  });
  var snapshotForHash={}; Object.keys(snapshot).forEach(function(key){if(key!=='snapshot_sha256')snapshotForHash[key]=snapshot[key];});
  if(snapshot.snapshot_sha256!==marketReport0800Sha256_(snapshotForHash)) errors.push('SNAPSHOT_SHA256_MISMATCH');
  if(snapshot.snapshot_provenance!=='LIVE_CAPTURED' || !snapshot.snapshot_id || !/^[0-9a-f]{64}$/.test(String(snapshot.snapshot_sha256||''))) errors.push('LIVE_SNAPSHOT_IDENTITY_REQUIRED');
  return {contract_id:MR0800_CONTRACT_ID_,gate:MR0800_GATE_NAME_,status:errors.length?'FAIL':'PASS',report_id:payload.report_id,
    body_sha256:bodyHash,structured_source_sha256:marketReport0800Sha256_(
      {structured_facts:rawFacts,sections:sections||[]}),numeric_registry_sha256:marketReport0800Sha256_({numeric_registry:numeric}),
    snapshot_sha256:snapshot.snapshot_sha256||'',snapshot_provenance:snapshot.snapshot_provenance||'',
    fact_count:Object.keys(facts).length,numeric_count:numeric.length,
    validation_gates:{SOURCE_INTEGRITY:errors.length?'FAIL':'PASS',NUMERIC_INTEGRITY:errors.length?'FAIL':'PASS',
      SNAPSHOT_INTEGRITY:errors.length?'FAIL':'PASS',CONTENT_COMPLETENESS:errors.length?'FAIL':'PASS'},
    qa_result_sha256:'',errors:errors,side_effects:{google_docs_write:false,png_write:false,portal_write:false,production_json_write:false}};
}

function marketReport0800QaResult_(errors) {
  return {contract_id:MR0800_CONTRACT_ID_,gate:MR0800_GATE_NAME_,status:'FAIL',errors:errors,
    side_effects:{google_docs_write:false,png_write:false,portal_write:false,production_json_write:false}};
}

function marketReport0800Sha256_(value) {
  var canonical = marketReport0800Canonical_(value);
  var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, Utilities.newBlob(canonical,'application/json').getBytes());
  return bytes.map(function(b){var n=(b+256)%256;return ('0'+n.toString(16)).slice(-2);}).join('');
}

function marketReport0800ReceiptHashView_(receipt) {
  return {
    contract_id:receipt.contract_id,gate:receipt.gate,status:receipt.status,report_id:receipt.report_id,
    body_sha256:receipt.body_sha256,structured_source_sha256:receipt.structured_source_sha256,
    numeric_registry_sha256:receipt.numeric_registry_sha256,snapshot_sha256:receipt.snapshot_sha256,
    snapshot_provenance:receipt.snapshot_provenance,fact_count:receipt.fact_count,numeric_count:receipt.numeric_count,
    validation_gates:receipt.validation_gates,qa_result_sha256:''
  };
}

function marketReport0800Canonical_(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return '[' + value.map(marketReport0800Canonical_).join(',') + ']';
  return '{' + Object.keys(value).sort().map(function(k){return JSON.stringify(k)+':'+marketReport0800Canonical_(value[k]);}).join(',') + '}';
}

function requireMarketReport0800GenerationQa_(report) {
  if (!report || report.time !== '08:00') return {status:'NOT_APPLICABLE'};
  var receipt = report.infographicGenerationQa;
  var expectedId = String(report.date||'') + '_08-00';
  var bodyHash = marketReportSha256_(Utilities.newBlob(String(report.fullText||''),'text/plain').getBytes());
  var receiptForHash = receipt && marketReport0800ReceiptHashView_(receipt);
  var qaHashMatches = Boolean(receiptForHash && receipt.qa_result_sha256 === marketReport0800Sha256_(receiptForHash));
  if (!receipt || receipt.contract_id !== MR0800_CONTRACT_ID_ || receipt.gate !== MR0800_GATE_NAME_
      || receipt.status !== 'PASS' || receipt.report_id !== expectedId || receipt.body_sha256 !== bodyHash
      || receipt.snapshot_provenance !== 'LIVE_CAPTURED' || !/^[0-9a-f]{64}$/.test(String(receipt.structured_source_sha256||''))
      || !/^[0-9a-f]{64}$/.test(String(receipt.numeric_registry_sha256||''))
      || !/^[0-9a-f]{64}$/.test(String(receipt.snapshot_sha256||''))
      || !/^[0-9a-f]{64}$/.test(String(receipt.qa_result_sha256||''))
      || Number(receipt.fact_count||0)<1 || Number(receipt.numeric_count||0)<1 || !qaHashMatches) {
    throw new Error('08:00 pre-save QA receipt missing, failed, or bound to a different report; no write is permitted.');
  }
  return receipt;
}

function saveNew0800GoogleDocAfterQa_(payload) {
  var qa = marketReport0800GenerationQa_(payload);
  if (qa.status !== 'PASS') throw new Error('08:00 pre-save QA failed: ' + qa.errors.join(', '));
  qa.qa_result_sha256 = marketReport0800Sha256_(marketReport0800ReceiptHashView_(qa));
  var document = DocumentApp.create(String(payload.title));
  document.getBody().setText(String(payload.body_text));
  document.saveAndClose();
  var file = DriveApp.getFileById(document.getId());
  file.setDescription('MARKET_REPORT_0800_QA_V1:' + JSON.stringify(qa));
  return {report_id:payload.report_id,document_id:document.getId(),body_sha256:qa.body_sha256,qa:qa};
}

function create0800ReportFromQaJsonPrompt() {
  var ui = SpreadsheetApp.getUi();
  var response = ui.prompt('08:00レポートをQA後に保存',
    'body_text・structured_facts・numeric_registry・snapshotを含む生成JSONを貼り付けてください。QA FAILならDocsは作成されません。',
    ui.ButtonSet.OK_CANCEL);
  if (response.getSelectedButton() !== ui.Button.OK) return null;
  var payload;
  try { payload = JSON.parse(response.getResponseText()); }
  catch (error) { throw new Error('生成JSONを読み取れません: ' + error.message); }
  var result = saveNew0800GoogleDocAfterQa_(payload);
  ui.alert('08:00事前QA PASS。Google Docsを作成しました。\nreport_id: ' + result.report_id + '\nDocument ID: ' + result.document_id);
  return result;
}

function marketReport0800QaFromFile_(file) {
  var description = String(file.getDescription() || '');
  var prefix = 'MARKET_REPORT_0800_QA_V1:';
  if (description.indexOf(prefix) !== 0) return null;
  try { return JSON.parse(description.slice(prefix.length)); }
  catch (error) { throw new Error('08:00 QA document metadata is malformed.'); }
}
