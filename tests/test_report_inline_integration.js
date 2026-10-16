const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const index = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const reportPage = fs.readFileSync(path.join(root, 'report.html'), 'utf8');
const dashboard = fs.readFileSync(path.join(root, 'assets/js/top-dashboard.js'), 'utf8');
const reportCore = fs.readFileSync(path.join(root, 'assets/js/report-core-v3.js'), 'utf8');
const reportCss = fs.readFileSync(path.join(root, 'assets/css/report-fulltext.css'), 'utf8');
const integration = fs.readFileSync(path.join(root, 'assets/js/report-inline-integration.js'), 'utf8');

assert.match(index, /id="reportDocumentFrame"/);
assert.match(index, /href="#report-detail"/);
assert.match(index, /report-inline-integration\.js/);
assert.match(dashboard, /MarketDashboardSelectedReport = report/);
assert.match(dashboard, /market-dashboard-report-selected/);
assert.match(reportPage, /params\.get\("embedded"\) === "1"/);
assert.match(reportPage, /destination\.hash = "report-detail"/);
assert.match(reportCore, /notifyEmbeddedReport_\("ready", selectedReport\)/);
assert.match(reportCss, /html\.report-embedded \.page>\.controls/);

const body = '同じ本文。価格 65,520 円。';
const current = {date:'2026-10-19', time:'08:00', report_id:'r1', revision:7, bodyHash:'a'.repeat(64), snapshot_id:'s1', fullText:body};
const frameListeners = {};
const sentReports = [];
const frame = {hidden:false, style:{}, dataset:{}, src:'',
  addEventListener(name, callback) { (frameListeners[name] ||= []).push(callback); },
  contentWindow:{MarketReportLastRendered:current, postMessage(message) { sentReports.push(message); }}
};
const status = {textContent:''};
const listeners = {};
const window = {
  MarketDashboardSelectedReport: current,
  addEventListener(name, callback) { (listeners[name] ||= []).push(callback); }
};
const document = {
  baseURI:'https://example.test/portal/index.html',
  getElementById(id) { return id === 'reportDocumentFrame' ? frame : status; }
};
vm.runInNewContext(integration, {window, document, location:{origin:'https://example.test'}, URL});

const url = new URL(frame.src, document.baseURI);
assert.equal(url.pathname, '/portal/report.html');
assert.equal(url.searchParams.get('embedded'), '1');
assert.equal(url.searchParams.get('date'), current.date);
assert.equal(url.searchParams.get('time'), current.time);
assert.equal(frame.hidden, true, 'body is withheld until the embedded render is identity-checked');
frameListeners.load[0]();
assert.equal(sentReports[0].type, 'market-dashboard-selected-report');
assert.equal(sentReports[0].report, current, 'the dashboard report object is the renderer input');

const message = (data, overrides={}) => listeners.message[0]({
  origin:'https://example.test', source:frame.contentWindow, data, ...overrides
});
message({type:'market-report-inline-rendered', status:'ready', date:current.date, time:current.time, height:1600});
assert.equal(frame.hidden, false);
assert.equal(frame.dataset.verifiedKey, '2026-10-19 08:00');
assert.equal(frame.style.height, '1600px');
assert.match(status.textContent, /同一本文・identityを確認/);

const next = {...current, time:'12:00', report_id:'r2', revision:8, bodyHash:'b'.repeat(64), snapshot_id:'s2'};
listeners['market-dashboard-report-selected'][0]({detail:{report:next}});
assert.equal(frame.hidden, true);
assert.equal(new URL(frame.src, document.baseURI).searchParams.get('time'), '12:00');
frameListeners.load[0]();
assert.equal(sentReports.at(-1).report, next);
frame.contentWindow.MarketReportLastRendered = {...next, fullText:'異なる本文。'};
message({type:'market-report-inline-rendered', status:'ready', date:next.date, time:next.time, height:1700});
assert.equal(frame.hidden, true, 'a text or identity mismatch must block the inline report');
assert.match(status.textContent, /表示を停止しました/);

process.stdout.write('report inline integration contract: PASS\n');

