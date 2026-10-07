const fs = require('fs');
const vm = require('vm');
const crypto = require('crypto');

const web = fs.readFileSync('apps-script/MarketReportWebSync.gs', 'utf8');
const reportContextCode = fs.readFileSync('apps-script/MarketReportContext.gs', 'utf8');
const fixture = JSON.parse(fs.readFileSync('tests/fixtures/vision_attestation_contract.json', 'utf8'));
const signedByteArray = buffer => Array.from(buffer, value => value > 127 ? value - 256 : value);
const context = {
  Utilities: {
    DigestAlgorithm: { SHA_256: 'SHA-256' },
    computeHmacSha256Signature: (payload, secret) => signedByteArray(crypto.createHmac('sha256', secret).update(payload, 'utf8').digest()),
    newBlob: text => ({ getBytes: () => signedByteArray(Buffer.from(text, 'utf8')) }),
    computeDigest: (_, bytes) => signedByteArray(crypto.createHash('sha256').update(Buffer.from(bytes.map(value => value & 255))).digest())
  },
  MimeType: { GOOGLE_DOCS: 'application/vnd.google-apps.document' },
  DriveApp: { getFileById: id => ({
    isTrashed: () => false,
    getMimeType: () => 'application/vnd.google-apps.document',
    getName: () => 'マーケットレポート_2026-10-06_12-00',
    getId: () => id
  }) },
  DocumentApp: { openById: () => ({ getBody: () => ({ getText: () => '本文確認\n' }) }) }
};
const properties = { MARKET_REPORT_VISION_HMAC_KEY: 'short', MARKET_REPORT_TRUSTED_VISION_PROVIDER: 'trusted-fixture-provider' };
context.PropertiesService = { getScriptProperties: () => ({ getProperty: key => properties[key] || '' }) };

vm.createContext(context);
vm.runInContext(reportContextCode, context);
vm.runInContext(web, context);

const validReportContext = { report_date: '2026-10-06', report_time: '12:00', report_id: '2026-10-06_12-00', data_cutoff: '2026-10-06T11:55:00+09:00', previous_report_id: '2026-10-06_08-00', previous_business_day: '2026-10-05', revision: 1, mode: 'historical' };
const parsedDoc = context.marketReportDocInfoFromName_('マーケットレポート_2026-10-06_12-00', validReportContext);
if (!parsedDoc || parsedDoc.key !== '2026-10-06 12:00') throw new Error('Matching immutable context was rejected');
let contextMismatchRejected = false;
try { context.marketReportDocInfoFromName_('マーケットレポート_2026-10-06_16-00', validReportContext); } catch (_) { contextMismatchRejected = true; }
if (!contextMismatchRejected) throw new Error('Document/context slot mismatch was accepted');

let shortKeyRejected = false;
try { context.marketReportVisionTrustConfig_(); } catch (_) { shortKeyRejected = true; }
if (!shortKeyRejected) throw new Error('Short HMAC key was accepted');
properties.MARKET_REPORT_VISION_HMAC_KEY = fixture.test_secret;
properties.MARKET_REPORT_TRUSTED_VISION_PROVIDER = 'fixture-test-only';
// TEST 32: even a sufficiently long key cannot make fixture identity a production trust root.
let fixtureTrustConfigRejected = false;
try { context.marketReportVisionTrustConfig_(); }
catch (error) { fixtureTrustConfigRejected = /VISION_FIXTURE_PROVIDER_FORBIDDEN/.test(String(error.message)); }
if (!fixtureTrustConfigRejected) throw new Error('Production trust config accepted fixture-test-only');

properties.MARKET_REPORT_TRUSTED_VISION_PROVIDER = fixture.review.provider;
if (context.marketReportVisionTrustConfig_().provider !== fixture.review.provider) {
  throw new Error('Configured Vision provider identity was not read');
}

const payload = context.marketReportVisionAttestationPayload_(fixture.review);
if (payload !== fixture.payload) throw new Error('Apps Script and Python attestation payloads differ');
if (context.marketReportHmacSha256_(payload, fixture.test_secret) !== fixture.review.signature) {
  throw new Error('Apps Script and Python HMAC calculation differs');
}
// TEST 33: the test harness may verify the canonical fixture signature directly.
context.verifyMarketReportVisionReviewSignature_(fixture.review,
  { secret: fixture.test_secret, provider: fixture.review.provider });

const boundReport = {
  date: '2026-10-06', time: '12:00', title: fixture.review.title,
  bodyHash: fixture.review.source_sha256, sourceDocument: { id: fixture.review.source_document_id }
};
let productionVerifierRejectedFixture = false;
// TEST 34: production validation rejects the fixture identity even when passed directly.
try {
  const fixtureReview = Object.assign({}, fixture.review, { provider: 'fixture-test-only' });
  context.validateMarketReportVisionReview_(boundReport,
    { getId: () => fixtureReview.drive_image_file_id }, fixtureReview.image_sha256, fixtureReview,
    { secret: fixture.test_secret, provider: 'test-configured-provider' });
} catch (error) {
  productionVerifierRejectedFixture = /VISION_FIXTURE_PROVIDER_FORBIDDEN/.test(String(error.message));
}
if (!productionVerifierRejectedFixture) throw new Error('Production verifier accepted fixture identity');

// Existing contract fixture uses a non-production-looking test identity. The production gate
// must continue accepting a correctly signed non-fixture identity without weakening checks.
// TEST 35: existing non-fixture HMAC validation remains unchanged.
context.validateMarketReportVisionReview_(boundReport,
  { getId: () => fixture.review.drive_image_file_id }, fixture.review.image_sha256, fixture.review,
  { secret: fixture.test_secret, provider: fixture.review.provider });

let alteredImageRejected = false;
try {
  context.validateMarketReportVisionReview_(boundReport,
    { getId: () => 'different-drive-image' }, fixture.review.image_sha256, fixture.review,
    { secret: fixture.test_secret, provider: fixture.review.provider });
} catch (_) { alteredImageRejected = true; }
if (!alteredImageRejected) throw new Error('Signed review was accepted for a different Drive image');

const readbackText = '本文確認';
const readbackReport = {
  fullText: readbackText,
  bodyHash: context.marketReportSha256_(context.Utilities.newBlob(readbackText, 'text/plain').getBytes()),
  sourceDocument: { id: 'doc-fixture-1', name: 'マーケットレポート_2026-10-06_12-00' }
};
context.verifyMarketReportSourceDocReadback_(readbackReport);
context.DocumentApp.openById = () => ({ getBody: () => ({ getText: () => '本文改変\n' }) });
let changedDocRejected = false;
try { context.verifyMarketReportSourceDocReadback_(readbackReport); } catch (_) { changedDocRejected = true; }
if (!changedDocRejected) throw new Error('Changed Google Docs body passed the readback gate');

console.log('Apps Script infographic gate tests passed (fixture production rejection and test-only HMAC cases included).');
