import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync("assets/js/morning-report-qa-gate.js", "utf8");

function createHarness() {
  const warnings = [];
  const body = {
    hidden: false,
    style: {},
    firstChild: null,
    querySelectorAll: () => [table],
    insertBefore(node) { warnings.push(node); this.firstChild = node; }
  };
  let tableRemoved = false;
  const section = { querySelector: () => ({ textContent: "主要市場データ" }) };
  const table = {
    textContent: "現在値・確認値",
    closest: () => section,
    querySelectorAll: () => [],
    remove() { tableRemoved = true; }
  };
  const document = {
    documentElement: { dataset: {} },
    querySelector(selector) { return selector === ".report-body" ? body : null; },
    querySelectorAll: () => [table],
    getElementById(id) { return warnings.find((warning) => warning.id === id) || null; },
    createElement: () => ({ setAttribute(name, value) { this[name] = value; }, remove() {} })
  };
  const messages = [];
  const window = { addEventListener() {} };
  vm.runInNewContext(source, {
    document, window, Date,
    console: { info() {}, warn(...args) { messages.push(args); }, error(...args) { messages.push(args); } },
    fetch: async () => { throw new Error("unused"); }
  });
  return { qa: window.MorningReportQA, body, warnings, messages, get tableRemoved() { return tableRemoved; }, document };
}

test("failed enforced 08:00 data stays readable but its market table is hidden and clearly flagged", () => {
  const h = createHarness();
  const report = {
    date: "2026-10-06", time: "08:00", report_status: "PUBLISHED",
    sourceFile: "reports/2026-10-06_08-00.json",
    fullText: "本文は原文のまま",
    markets: [{ name: "USD/JPY", value: "150.00" }]
  };
  const result = h.qa.runRenderedQA(report);
  assert.equal(result.ready, false);
  assert.equal(h.document.documentElement.dataset.morningReportQa, "fail");
  assert.equal(h.body.hidden, false, "authored body remains readable");
  assert.equal(report.fullText, "本文は原文のまま", "source body is not rewritten");
  assert.equal(report.report_status, "PUBLISHED", "source publication status is not rewritten");
  assert.equal(h.tableRemoved, true, "unverified rendered market table is withheld");
  assert.equal(h.warnings.length, 1);
  assert.match(h.warnings[0].textContent, /発行ステータスは変更していません/);
  assert.match(h.warnings[0].textContent, /市場データ検証に未達/);
  assert.equal(h.warnings[0].role, "alert");
  assert.equal(h.messages[0][1].file, "reports/2026-10-06_08-00.json");
  assert.equal(h.messages[0][1].date, "2026-10-06");
});

test("historical archive remains viewable without claiming formal 08:00 QA", () => {
  const h = createHarness();
  const result = h.qa.runRenderedQA({ date: "2026-10-12", time: "08:00", archiveStatus: "HISTORICAL_ARCHIVE" });
  assert.equal(result.archive, true);
  assert.equal(h.document.documentElement.dataset.morningReportQa, "historical-archive");
  assert.equal(h.warnings.length, 0);
  assert.equal(h.tableRemoved, false);
});
