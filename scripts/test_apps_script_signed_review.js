const fs = require('fs');
const vm = require('vm');
const crypto = require('crypto');

const [reviewPath, expectedPayloadPath] = process.argv.slice(2);
if (!reviewPath || !expectedPayloadPath) throw new Error('review and expected payload files are required');
const review = JSON.parse(fs.readFileSync(reviewPath, 'utf8'));
const expectedPayload = fs.readFileSync(expectedPayloadPath, 'utf8');
const web = fs.readFileSync('apps-script/MarketReportWebSync.gs', 'utf8');
const reportContextCode = fs.readFileSync('apps-script/MarketReportContext.gs', 'utf8');
const signedByteArray = buffer => Array.from(buffer, value => value > 127 ? value - 256 : value);
const context = {
  Utilities: {
    DigestAlgorithm: { SHA_256: 'SHA-256' },
    computeHmacSha256Signature: (payload, secret) => signedByteArray(crypto.createHmac('sha256', secret).update(payload, 'utf8').digest()),
    newBlob: text => ({ getBytes: () => signedByteArray(Buffer.from(text, 'utf8')) }),
    computeDigest: (_, bytes) => signedByteArray(crypto.createHash('sha256').update(Buffer.from(bytes.map(value => value & 255))).digest())
  },
  MimeType: { GOOGLE_DOCS: 'application/vnd.google-apps.document' },
  PropertiesService: { getScriptProperties: () => ({ getProperty: key => process.env[key] || '' }) }
};
vm.createContext(context);
vm.runInContext(reportContextCode, context);
vm.runInContext(web, context);
const payload = context.marketReportVisionAttestationPayload_(review);
if (payload !== expectedPayload) {
  let index = 0;
  while (index < payload.length && payload[index] === expectedPayload[index]) index++;
  throw new Error('Python and Apps Script canonical payloads differ at ' + index +
    ' (lengths ' + payload.length + '/' + expectedPayload.length + '): actual=' +
    JSON.stringify(payload.slice(index, index + 50)) + ' expected=' +
    JSON.stringify(expectedPayload.slice(index, index + 50)));
}
const reportId = review.report_id;
const match = /^(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})$/.exec(reportId);
if (!match) throw new Error('invalid report identity');
const report = { date: match[1], time: match[2] + ':' + match[3], title: review.title,
  bodyHash: review.source_sha256, sourceDocument: { id: review.source_document_id } };
const trust = { secret: process.env.MARKET_REPORT_VISION_HMAC_KEY,
  provider: process.env.MARKET_REPORT_TRUSTED_VISION_PROVIDER };
context.validateMarketReportVisionReview_(report, { getId: () => review.drive_image_file_id },
  review.image_sha256, review, trust);
let tamperRejected = false;
try {
  context.validateMarketReportVisionReview_(report, { getId: () => 'different-drive-image' },
    review.image_sha256, review, trust);
} catch (_) { tamperRejected = true; }
if (!tamperRejected) throw new Error('altered Drive image identity was accepted');
console.log('Dynamic Apps Script signed review verification passed.');
