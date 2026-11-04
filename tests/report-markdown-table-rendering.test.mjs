import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const coreSource = fs.readFileSync(path.join(root, "assets/js/report-core-v3.js"), "utf8");
const markdownSource = fs.readFileSync(path.join(root, "assets/js/report-markdown-fulltext-fix.js"), "utf8");
const nov3 = JSON.parse(fs.readFileSync(path.join(root, "data/dashboard-drive-archive-2026-11-03.json"), "utf8"));
const archive = nov3.reports.find(report => report.date === "2026-11-03" && report.time === "21:00");
assert.ok(archive, "the 21:00 view-only archive fixture exists");

function renderer() {
  const window = { MarketReportPublicationPolicy: { isEligible: () => false } };
  const context = vm.createContext({ window, console, URL, URLSearchParams, Date });
  const coreWithoutInit = coreSource.replace(/init\(\);\s*$/, "");
  assert.notEqual(coreWithoutInit, coreSource, "renderer test hook insertion point");
  vm.runInContext(coreWithoutInit, context, { filename: "report-core-v3.js" });
  vm.runInContext(markdownSource, context, { filename: "report-markdown-fulltext-fix.js" });
  vm.runInContext("window.__reportRenderTest = { renderMarketTable, renderRichText, parseDocument };", context);
  return window.__reportRenderTest;
}

test("actual Nov 3 21:00 Markdown tables render as readable tables with all source rows", () => {
  const api = renderer();
  const lines = archive.fullText.split("\n");
  const rendered = api.renderRichText(lines);
  assert.equal((rendered.match(/<table\b/g) || []).length, 2);
  assert.equal((rendered.match(/<tbody>/g) || []).length, 2);
  assert.equal((rendered.match(/<tr>/g) || []).length, 21, "all 19 body rows plus two table header rows");
  assert.equal((rendered.match(/<th scope="col"/g) || []).length, 8, "both tables keep their four columns");
  assert.doesNotMatch(rendered, /\|\s*:?-{3,}/, "Markdown separator lines are not shown as prose");
  assert.match(rendered, /NYダウ/);
  assert.match(rendered, /14:00～15:30/);
});

test("reference-only major-market prose is not fabricated into a price row", () => {
  const api = renderer();
  const parsed = api.parseDocument(archive.fullText, archive.title);
  const section = parsed.sections.find(item => /主要市場データ/.test(item.title));
  assert.ok(section, "major market section exists");
  const rendered = api.renderMarketTable(archive, section.lines, section.title);
  assert.doesNotMatch(rendered, /<table\b/);
  assert.match(rendered, /上表のとおり/);
  assert.doesNotMatch(rendered, /<th scope="row">上表のとおり/);
});

test("five-column Markdown tables and cell escaping preserve content safely", () => {
  const api = renderer();
  const rendered = api.renderRichText([
    "| 指標 | 値 | 前日比 | 騰落率 | 方向 |",
    "|:---|---:|:---:|---:|---|",
    "| <script>alert(1)</script> | 5 | +1 | 2% | 上昇 |"
  ]);
  assert.match(rendered, /class="market-table markdown-table market-table-five"/);
  assert.match(rendered, /style="text-align:right"/);
  assert.match(rendered, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.doesNotMatch(rendered, /<script>/);
  assert.equal((rendered.match(/<td /g) || []).length, 5);
});
