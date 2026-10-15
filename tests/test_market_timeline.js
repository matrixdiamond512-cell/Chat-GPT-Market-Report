const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const test = require("node:test");
const MarketTimeline = require("../assets/js/market-timeline.js");
const PublicationPolicy = require("../assets/js/report-publication-policy.js");
const { buildArchive } = require("../scripts/reporting/build_market_timeline_archive.js");

const root = path.resolve(__dirname, "..");
const archivePath = path.join(root, "data/market-timelines/2026-10-15.json");
const archive = JSON.parse(fs.readFileSync(archivePath, "utf8"));
const expectedPhases = {
  "08:00": ["NY開場前", "寄り付き", "序盤", "中盤", "終盤・引け", "東京への引き継ぎ"],
  "12:00": ["寄り付き前", "寄り付き", "前場序盤", "中盤", "前引け"],
  "16:00": ["午前の振り返り", "後場開始", "後場中盤", "大引け", "欧州への引き継ぎ"],
  "21:00": ["欧州開場前", "寄り付き", "序盤", "中盤", "NYへの引き継ぎ"]
};
const sourceFor = (timeline) => JSON.parse(fs.readFileSync(path.join(root, timeline.sourcePath), "utf8"));

test("01: all four required slots and slot-specific phases are defined", () => {
  assert.deepEqual(Object.keys(MarketTimeline.SLOT_DEFINITIONS), Object.keys(expectedPhases));
  for (const [slot, phases] of Object.entries(expectedPhases)) {
    assert.deepEqual(MarketTimeline.SLOT_DEFINITIONS[slot].phases, phases);
  }
});

test("02: retrospective archive contains all four 2026-10-15 slots", () => {
  assert.equal(archive.schemaVersion, "market-timeline-archive/v1");
  assert.deepEqual(archive.reports.map((item) => item.reportTime), Object.keys(expectedPhases));
});

test("03: each event separates fact, reaction, meaning, next watch, and source", () => {
  for (const timeline of archive.reports) {
    assert.ok(timeline.events.length > 0);
    for (const event of timeline.events) {
      assert.ok(event.event);
      assert.ok(event.reaction);
      assert.ok(event.meaning);
      assert.ok(event.nextWatch);
      assert.ok(event.sources.length);
      assert.ok(Object.hasOwn(event, "occurredAt"));
      assert.ok(Object.hasOwn(event, "reactionObservedAt"));
    }
  }
});

test("04: four slot timelines include every required phase", () => {
  for (const timeline of archive.reports) {
    const observed = new Set(timeline.events.map((event) => event.phase));
    for (const phase of expectedPhases[timeline.reportTime]) assert.ok(observed.has(phase), `${timeline.reportTime} missing ${phase}`);
  }
});

test("05: archived amendment identity is bound to date, slot, revision, body hash, and source document", () => {
  for (const timeline of archive.reports) {
    const source = sourceFor(timeline);
    assert.equal(timeline.reportId, `${source.date}_${source.time.replace(":", "-")}`);
    assert.equal(timeline.reportDate, source.date);
    assert.equal(timeline.reportTime, source.time);
    assert.equal(String(timeline.reportRevision), String(source.revision));
    assert.equal(timeline.sourceBodyHash, source.bodyHash);
    assert.equal(timeline.sourceDocumentId, source.sourceDocument.id);
  }
});

test("06: saved source bodies still hash to their original bodyHash", () => {
  for (const timeline of archive.reports) {
    const source = sourceFor(timeline);
    const hash = crypto.createHash("sha256").update(source.fullText, "utf8").digest("hex");
    assert.equal(hash, source.bodyHash);
  }
});

test("07: unrecorded event times remain explicitly unknown", () => {
  const timeline = archive.reports.find((item) => item.reportTime === "08:00");
  const untimed = timeline.events.find((event) => event.timePrecision === "time-not-recorded");
  assert.ok(untimed);
  assert.equal(untimed.occurredAt, null);
  assert.match(untimed.timeLabel, /時刻付き個別観測なし|正確な高値時刻/);
});

test("08: unpublished scheduled events are not shown as occurred events", () => {
  const timeline = archive.reports.find((item) => item.reportTime === "21:00");
  assert.ok(timeline.events.every((event) => !/発表予定|未発表/.test(`${event.event} ${event.reaction}`)));
});

test("09: all 2026-10-15 timelines are labeled as later amendments", () => {
  for (const timeline of archive.reports) {
    assert.equal(timeline.evidenceStatus, "AFTER_ISSUANCE_AMENDMENT");
    assert.equal(timeline.amendmentDate, "2026/10/16");
  }
});

test("10: source report statuses remain archived or blocked and are not public-eligible", () => {
  for (const timeline of archive.reports) {
    const source = sourceFor(timeline);
    assert.equal(source.report_status, timeline.publicationStatus);
    assert.ok(["SOURCE_ARCHIVED", "BLOCKED_SNAPSHOT_MISSING"].includes(source.report_status));
    assert.equal(PublicationPolicy.isEligible(source), false);
  }
});

test("11: archive generation is deterministic and rejects source-body or slot mismatches", async () => {
  assert.deepEqual(buildArchive("2026-10-15", root), archive);
  const timeline = archive.reports[0];
  const source = sourceFor(timeline);
  assert.equal((await MarketTimeline.verifyArchivedTimeline(timeline, source)).valid, true);
  assert.equal((await MarketTimeline.verifyArchivedTimeline(timeline, { ...source, fullText: `${source.fullText}tampered` })).valid, false);
  assert.equal((await MarketTimeline.verifyArchivedTimeline(timeline, { ...source, time: "12:00" })).valid, false);
  assert.equal((await MarketTimeline.verifyArchivedTimeline(timeline, { ...source, revision: 3 })).valid, false);
});

test("12: panel is below six-market summary, upcoming-events table remains, and narrow-screen rules exist", () => {
  const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
  const summary = html.indexOf("class=\"market-summary panel\"");
  const timeline = html.indexOf("id=\"marketTimelinePanel\"");
  const environment = html.indexOf("id=\"market-environment\"");
  assert.ok(summary >= 0 && summary < timeline && timeline < environment);
  assert.match(html, /今後の重要イベント（簡易）/);
  assert.match(html, /id=\"eventRows\"/);
  const dashboard = fs.readFileSync(path.join(root, "assets/js/top-dashboard.js"), "utf8");
  assert.match(dashboard, /出来事の発生時刻/);
  assert.match(dashboard, /反応の観測時刻/);
  const css = fs.readFileSync(path.join(root, "assets/css/top-dashboard.css"), "utf8");
  assert.match(css, /@media\s*\(max-width:\s*640px\)/);
  assert.match(css, /\.market-timeline-event dl\s*\{\s*grid-template-columns:\s*1fr/s);
});
