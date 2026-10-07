'use strict';

const fs = require('fs');
const vm = require('vm');

const source = fs.readFileSync('assets/js/report-core-v3.js', 'utf8').replace(/\r\n?/g, '\n');
const start = source.indexOf('function splitCanonicalTitleFromSource_');
const end = source.indexOf('\n\nfunction splitChangeRate', start);
if (start < 0 || end < 0) throw new Error('Canonical document parsing functions could not be located');
const sandbox = {module: {exports: {}}, headingInfo: () => null};
vm.createContext(sandbox);
vm.runInContext(source.slice(start, end) + '\nmodule.exports = {splitCanonicalTitleFromSource_, parseDocument};', sandbox);
const {splitCanonicalTitleFromSource_, parseDocument} = sandbox.module.exports;

const title = 'マーケットレポート｜2026/10/07（水）12:00';
const body = '情報基準：2026/10/07 12:00 JST。本文を保持します。';

// TEST 01: canonical newline remains a separator and is removed only once.
const normal = parseDocument(title + '\n' + body, title);
if (normal.title !== title || normal.preface.join('\n') !== body) {
  throw new Error('Normal title/newline/body parsing failed');
}

// TEST 02-04: malformed leading concatenation is recovered using report.title.
const malformed = parseDocument(title + body, title);
if (malformed.title !== title) throw new Error('Canonical report.title did not win over source-derived title');
if (malformed.preface.join('\n') !== body) throw new Error('Malformed title remainder was lost from the body');
if (malformed.title.length > 160) throw new Error('Malformed source expanded the rendered title');

// TEST 05: a later title-like phrase is ordinary body text and must not be split.
const embedded = body + '\n本文内の例：' + title + ' はそのまま表示します。';
const embeddedResult = parseDocument(title + embedded, title);
if (embeddedResult.preface.join('\n') !== embedded) throw new Error('Title-like text inside the body was split or lost');

// A different prefix is preserved as body; the trusted canonical title stays authoritative.
const mismatchedPrefix = parseDocument('別の文章\n' + body, title);
if (mismatchedPrefix.title !== title || mismatchedPrefix.preface.join('\n') !== '別の文章\n' + body) {
  throw new Error('Nonmatching source prefix was rewritten');
}
const titleOnly = splitCanonicalTitleFromSource_(title, title);
if (titleOnly.title !== title || titleOnly.bodySource !== '') throw new Error('Title-only source was not handled exactly');

console.log('Market Report title-boundary tests passed (normal, malformed, canonical priority, remainder, and embedded title).');
