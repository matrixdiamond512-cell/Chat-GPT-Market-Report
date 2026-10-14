/*
 * Producer-owned, signed provenance boundary for market-report publication.
 * Draft-only until the actual ChatGPT report producer writes signed records.
 * Publisher NEVER manufactures these records from Docs/latest/market history.
 *
 * Records: producer-proof/YYYY-MM-DD_HH-MM.json
 * Signature: lowercase HMAC-SHA256 over recursively key-sorted JSON of
 * the entire record, except signature. Secret MUST be supplied by the
 * independently provisioned producer and configured out of repository.
 */
var MARKET_REPORT_PRODUCER_PROOF = {
  prefix: 'producer-proof/',
  signingKeyProperty: 'MARKET_REPORT_PRODUCER_HMAC_KEY',
  schemaVersion: 1
};

function marketReportProofFail_(reason) {
  throw new Error('PRODUCER_PROOF_BLOCKED: ' + reason);
}

function marketReportProofCanonical_(value) {
  if (Array.isArray(value)) {
    return '[' + value.map(marketReportProofCanonical_).join(',') + ']';
  }
  if (value && typeof value === 'object') {
    return '{' + Object.keys(value).sort().map(function(key) {
      return JSON.stringify(key) + ':' + marketReportProofCanonical_(value[key]);
    }).join(',') + '}';
  }
  if (value === null || typeof value === 'string' || typeof value === 'boolean' ||
      (typeof value === 'number' && Number.isFinite(value))) {
    return JSON.stringify(value);
  }
  marketReportProofFail_('invalid JSON value');
}

function marketReportProofSha_(value) {
  return marketReportSha256_(Utilities.newBlob(
    marketReportProofCanonical_(value), 'application/json').getBytes());
}

function marketReportProofHex_(bytes) {
  return Array.prototype.map.call(bytes, function(byte) {
    return ('0' + (byte & 255).toString(16)).slice(-2);
  }).join('');
}

function marketReportProofEqual_(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  var difference = 0;
  for (var i = 0; i < a.length; i++) difference |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return difference === 0;
}

function marketReportProofTime_(value, label) {
  if (typeof value !== 'string' || !/T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value)) {
    marketReportProofFail_(label + ' must be timezone-aware ISO8601');
  }
  var parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) marketReportProofFail_(label + ' invalid');
  return parsed;
}

function marketReportProofValidate_(record, report, sha) {
  if (!record || Array.isArray(record) || typeof record !== 'object' || !sha) {
    marketReportProofFail_('producer record missing or not fetched from GitHub');
  }
  var key = String(report.date || '') + '_' + String(report.time || '').replace(':', '-');
  if (!/^\d{4}-\d{2}-\d{2}_(08|12|16|21)-00$/.test(key) ||
      record.schema_version !== 1 || record.report_id !== key) {
    marketReportProofFail_('schema or report identity mismatch');
  }
  if (!Number.isInteger(record.revision) || record.revision < 1 ||
      !record.producer_run_id || !record.chat_evidence_id ||
      !/^[0-9a-f]{64}$/.test(String(record.body_sha256 || '')) ||
      record.body_sha256 !== record.chat_body_sha256 ||
      record.source_document_id !== String(report.sourceDocument && report.sourceDocument.id || '')) {
    marketReportProofFail_('producer identity, chat assertion or Docs identity missing');
  }
  var context = record.context;
  var snapshot = record.snapshot;
  if (!context || !snapshot || typeof context !== 'object' || typeof snapshot !== 'object') {
    marketReportProofFail_('context and snapshot required');
  }
  if (context.report_id !== key || context.report_date !== report.date ||
      context.report_time !== report.time || context.revision !== record.revision ||
      !['new', 'historical', 'recovery'].includes(context.mode) ||
      !/^\d{4}-\d{2}-\d{2}$/.test(String(context.previous_business_day || '')) ||
      context.previous_business_day >= context.report_date ||
      record.context_id !== 'context-' + marketReportProofSha_(context)) {
    marketReportProofFail_('context invalid or content digest mismatch');
  }
  var slotMs = marketReportProofTime_(report.date + 'T' + report.time + ':00+09:00', 'report slot');
  var cutoffMs = marketReportProofTime_(context.data_cutoff, 'data_cutoff');
  var capturedMs = marketReportProofTime_(snapshot.captured_at, 'captured_at');
  var producedMs = marketReportProofTime_(record.producer_created_at, 'producer_created_at');
  if (cutoffMs > slotMs || capturedMs > slotMs ||
      producedMs < capturedMs || producedMs > Date.now() + 60000) {
    marketReportProofFail_('source boundary moved after report slot or producer time invalid');
  }
  if (snapshot.report_id !== key || snapshot.revision !== record.revision ||
      snapshot.schema_version !== 1 || snapshot.data_cutoff !== context.data_cutoff ||
      !Array.isArray(snapshot.markets) || snapshot.markets.length < 6) {
    marketReportProofFail_('snapshot identity, cutoff or market series missing');
  }
  var marketKeys = {};
  snapshot.markets.forEach(function(market) {
    if (!market || !market.instrument || marketKeys[market.instrument] ||
        !['VALID', 'STALE', 'UNAVAILABLE', 'N/A'].includes(market.status)) {
      marketReportProofFail_('snapshot market invalid or duplicate');
    }
    marketKeys[market.instrument] = true;
    if (market.status === 'VALID' || market.status === 'STALE') {
      if (typeof market.priceValue !== 'number' || !Number.isFinite(market.priceValue) ||
          !Array.isArray(market.source) || !market.source.length ||
          marketReportProofTime_(market.asOf, 'market.asOf') > cutoffMs) {
        marketReportProofFail_('observed market series has invalid source/value/time');
      }
    } else if (market.priceValue !== null) {
      marketReportProofFail_('unavailable market cannot have a price');
    }
  });
  var identity = {};
  Object.keys(snapshot).forEach(function(k) {
    if (k !== 'snapshot_id') identity[k] = snapshot[k];
  });
  if (snapshot.snapshot_id !== 'snapshot-' + marketReportProofSha_(identity)) {
    marketReportProofFail_('snapshot content digest mismatch');
  }

  // A hash recomputed from Docs is NOT the expected producer hash; compare to
  // the independently signed value.
  var actualHash = marketReportSha256_(Utilities.newBlob(report.fullText, 'text/plain').getBytes());
  if (actualHash !== record.body_sha256) marketReportProofFail_('Docs/fullText does not match producer source');

  var unsigned = {};
  Object.keys(record).forEach(function(k) { if (k !== 'signature') unsigned[k] = record[k]; });
  var secret = PropertiesService.getScriptProperties()
    .getProperty(MARKET_REPORT_PRODUCER_PROOF.signingKeyProperty);
  if (!secret || Utilities.newBlob(secret, 'text/plain').getBytes().length < 32) {
    marketReportProofFail_('trusted producer verification key is not configured');
  }
  var expected = marketReportProofHex_(Utilities.computeHmacSha256Signature(
    marketReportProofCanonical_(unsigned), secret));
  if (!/^[0-9a-f]{64}$/.test(String(record.signature || '')) ||
      !marketReportProofEqual_(expected, record.signature)) {
    marketReportProofFail_('producer signature invalid');
  }
  // Mutate only after the entire proof is verified.
  report.revision = record.revision;
  report.bodyHash = record.body_sha256;
  report.snapshot_id = snapshot.snapshot_id;
  report.context_id = record.context_id;
  report.producer_run_id = record.producer_run_id;
  report.producer_proof_sha = sha;
  return record;
}

function marketReportVerifyProducerProof_(report) {
  if (typeof getGitHubJsonFile_ !== 'function' ||
      typeof marketReportSha256_ !== 'function') {
    marketReportProofFail_('trusted provenance/readback dependencies missing');
  }
  var key = String(report.date || '') + '_' + String(report.time || '').replace(':', '-');
  // No fallback to latest data, body-derived records or old report receipts.
  var source = getGitHubJsonFile_(MARKET_REPORT_PRODUCER_PROOF.prefix + key + '.json');
  return marketReportProofValidate_(source && source.data, report, source && source.sha);
}
