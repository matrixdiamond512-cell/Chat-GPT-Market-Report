const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const MarketTimeline = require("../../assets/js/market-timeline.js");

const REQUIRED_SLOTS = ["08:00", "12:00", "16:00", "21:00"];
const ALLOWED_SOURCE_STATES = new Set(["SOURCE_ARCHIVED", "BLOCKED_SNAPSHOT_MISSING"]);

function buildArchive(date, repositoryRoot = path.resolve(__dirname, "../..")) {
  const reports = REQUIRED_SLOTS.map((time) => {
    const reportId = MarketTimeline.reportId(date, time);
    const sourcePath = `reports/${reportId}.json`;
    const source = JSON.parse(fs.readFileSync(path.join(repositoryRoot, sourcePath), "utf8"));
    if (source.date !== date || source.time !== time) throw new Error(`${reportId}: source slot mismatch`);
    if (!ALLOWED_SOURCE_STATES.has(source.report_status)) throw new Error(`${reportId}: refusing non-archived source status ${source.report_status}`);
    const actualHash = crypto.createHash("sha256").update(source.fullText || "", "utf8").digest("hex");
    if (!source.bodyHash || actualHash !== source.bodyHash) throw new Error(`${reportId}: saved body hash mismatch`);

    const timeline = MarketTimeline.parseTimelineText(source);
    if (!timeline || timeline.evidenceStatus !== "AFTER_ISSUANCE_AMENDMENT" || timeline.amendmentDate !== "2026/10/16") {
      throw new Error(`${reportId}: required 2026/10/16 retrospective amendment was not identified`);
    }
    if (timeline.events.length === 0) throw new Error(`${reportId}: no labeled actual events could be extracted`);
    if (timeline.events.some((event) => !event.event || !event.reaction || !event.meaning || !event.sources.length)) {
      throw new Error(`${reportId}: an event is missing required evidence fields`);
    }

    return {
      ...timeline,
      sourcePath,
      sourceBodyHash: source.bodyHash,
      reportRevision: source.revision,
      publicationStatus: source.report_status,
      sourceDocumentId: source.sourceDocument?.id || null,
      sourceTitle: source.title
    };
  });

  return {
    schemaVersion: "market-timeline-archive/v1",
    date,
    archiveStatus: "RETROSPECTIVE_AMENDMENTS_ONLY",
    generatedAt: "2026-10-16",
    note: "These sidecars are extracted from saved 2026/10/16 amendments. They do not change original report bodies, snapshot evidence, receipts, or publication status.",
    reports
  };
}

if (require.main === module) {
  const date = process.argv[2];
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date || "")) throw new Error("Usage: node build_market_timeline_archive.js YYYY-MM-DD");
  const repositoryRoot = path.resolve(__dirname, "../..");
  const outputDirectory = path.join(repositoryRoot, "data", "market-timelines");
  fs.mkdirSync(outputDirectory, { recursive: true });
  const outputPath = path.join(outputDirectory, `${date}.json`);
  fs.writeFileSync(outputPath, `${JSON.stringify(buildArchive(date, repositoryRoot), null, 2)}\n`, "utf8");
  process.stdout.write(`Wrote ${path.relative(repositoryRoot, outputPath)}\n`);
}

module.exports = { buildArchive };
