const assert = require("node:assert/strict");
const policy = require("../assets/js/report-publication-policy.js");

const statuses = [
  ["PUBLISHED", true],
  ["DOC_READBACK_PASS", true],
  ["SOURCE_ARCHIVED", false],
  ["BLOCKED", false],
  ["FAILED", false],
  ["UNKNOWN", false],
  ["", true],
  [undefined, true]
];
for (const [status, expected] of statuses) {
  assert.equal(policy.isEligible({ date: "2026-10-14", time: "21:00", report_status: status }), expected, String(status));
}

const history = [
  { date: "2026-10-13", time: "16:00", report_status: "PUBLISHED", fullText: "verified history" },
  { date: "2026-10-14", time: "21:00", report_status: "SOURCE_ARCHIVED", fullText: "must remain private" },
  { date: "2026-10-12", time: "12:00", fullText: "legacy statusless history" }
];
const dashboard = [
  { date: "2026-10-14", time: "21:00", report_status: "SOURCE_ARCHIVED", fullText: "must remain private" },
  { date: "2026-10-13", time: "16:00", report_status: "PUBLISHED", theme: "dashboard projection" },
  { date: "2026-10-11", time: "08:00", report_status: "BLOCKED", fullText: "blocked dashboard source" }
];
const merged = policy.merge(history, dashboard);
assert.deepEqual(merged.map(({date,time}) => `${date} ${time}`), [
  "2026-10-13 16:00",
  "2026-10-12 12:00"
]);
assert.equal(merged[0].fullText, "verified history");
assert.equal(merged[0].theme, "dashboard projection");
assert.ok(!merged.some(report => report.fullText === "must remain private"));
assert.ok(!merged.some(report => report.report_status === "BLOCKED"));

console.log("Dashboard publication policy checks passed (8 eligibility states, blocked/archived merge, legacy history, and projection preservation).");
