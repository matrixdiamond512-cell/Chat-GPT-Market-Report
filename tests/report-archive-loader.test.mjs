import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const source = fs.readFileSync(path.join(root, "assets/js/report-core-v3.js"), "utf8");
const manifest = JSON.parse(fs.readFileSync(path.join(root, "data/report-archive-manifest.json"), "utf8"));
const archives = new Map(manifest.files.map(entry =>
  [entry.path, JSON.parse(fs.readFileSync(path.join(root, entry.path), "utf8"))]));
const recoveryPayload = JSON.parse(fs.readFileSync(path.join(root, "data/report-recovery-2026-10.json"), "utf8"));
const formal = [];

function slotKey(r) { return r.date + " " + r.time; }
async function boot({ search = "", fail = [], payloadOverrides = {} } = {}) {
  const nodes = new Map();
  const node = (id) => {
    if (!nodes.has(id)) nodes.set(id, {
      id, value: "", min: "", max: "", textContent: "", innerHTML: "", className: "",
      disabled: false, title: "", attributes: {}, classList: { add() {} }, querySelectorAll() { return []; },
      setAttribute(k, v) { this.attributes[k] = v; }
    });
    return nodes.get(id);
  };
  const calls = [];
  const warnings = [];
  const document = { getElementById: node };
  const window = {
    MarketReportPublicationPolicy: { isEligible: r => r?.formal === true },
    dispatchEvent() {},
    __hooks: null,
    location: { search, href: "https://example.test/report.html" + search },
    history: { replaceState() {} }
  };
  const fetch = async (url) => {
    const p = String(url).split("?")[0];
    calls.push(p);
    if (fail.includes(p)) throw new Error(p + " network failure");
    let value;
    if (Object.hasOwn(payloadOverrides, p)) value = payloadOverrides[p];
    else if (p === "reports.json") value = formal;
    else if (p === "data/report-archive-manifest.json") value = manifest;
    else if (p === "data/report-recovery-2026-10.json") value = recoveryPayload;
    else if (archives.has(p)) value = archives.get(p);
    else throw new Error("unmapped request: " + p);
    return { ok: true, status: 200, json: async () => structuredClone(value) };
  };
  const console = { info(){}, warn(...args){ warnings.push(args.join(" ")); }, error(){} };
  const context = vm.createContext({
    window, document, fetch, console, URL, URLSearchParams, CustomEvent: class {},
    location: window.location, history: window.history, Date
  });
  let testable = source.replace(/window\.MarketReportRendererVersion = ([^;]+);\s*init\(\);\s*$/, (whole, version) =>
    `window.MarketReportRendererVersion = ${version};
      render = () => { renderControls(selectedReport); window.MarketReportLastRendered = selectedReport; };
      renderMissingReport = (date, time) => { selectedReport = null; window.MarketReportMissing = { date, time }; window.MarketReportLastRendered = null; document.getElementById("app").textContent = "対象データなし：この日時のレポート本文は登録されていません。"; };
      window.__hooks = { reports: () => reports, select: (d,t) => selectReport(d,t), selected: () => selectedReport };
      window.__loadPromise = init();`);
  assert.notEqual(testable, source, "test hook insertion point");
  vm.runInContext(testable, context, { filename: "report-core-v3.js" });
  await window.__loadPromise;
  return { window, nodes, calls, warnings };
}

function archiveSlot(date, time) {
  return archives.get(`data/dashboard-drive-archive-${date}.json`).reports.find(r => r.date === date && r.time === time);
}

test("manifest archive slots preserve exact bodies; missing 11/03 21:00 never falls back", async () => {
  const { window, nodes } = await boot();
  const slots = [
    ["2026-11-02","08:00"],["2026-11-02","12:00"],["2026-11-02","16:00"],["2026-11-02","21:00"],
    ...archives.get("data/dashboard-drive-archive-2026-11-03.json").reports.map(r => [r.date,r.time]),
    ["2026-10-30","21:00"]
  ];
  for (const [date,time] of slots) {
    window.__hooks.select(date,time);
    assert.equal(window.MarketReportLastRendered.fullText, archiveSlot(date,time).fullText, slotKey({date,time}));
  }
  const nov3Archive = structuredClone(archives.get("data/dashboard-drive-archive-2026-11-03.json"));
  nov3Archive.reports = nov3Archive.reports.filter(r => r.time !== "21:00");
  const missingSlot = await boot({payloadOverrides:{"data/dashboard-drive-archive-2026-11-03.json":nov3Archive}});
  const nov3Times = missingSlot.window.__hooks.reports().filter(r => r.date === "2026-11-03").map(r => r.time).sort();
  assert.equal(nov3Times.join(","), "08:00,12:00,16:00", "only saved Nov 3 slots are available");
  missingSlot.window.__hooks.select("2026-11-03","21:00");
  assert.equal(missingSlot.window.__hooks.selected(), null, "missing slot clears the selection");
  assert.equal(missingSlot.window.MarketReportLastRendered, null, "missing slot clears any previous body");
  assert.match(missingSlot.nodes.get("app").textContent, /本文は登録されていません/);
});

test("unverified archives stay display-only and 11/02 12:00 source is not mutated", async () => {
  const { window } = await boot({search:"?date=2026-11-02&time=12:00"});
  const selected = window.MarketReportLastRendered;
  assert.equal(selected.verifiedAtSlot, false);
  assert.equal(selected.originalReportStatus, "DRIVE_DOC_READBACK_NOT_SLOT_VERIFIED");
  assert.equal(selected.archiveStatus, "HISTORICAL_ARCHIVE");
  assert.equal(selected.fullText, archiveSlot("2026-11-02","12:00").fullText);
  assert.equal(archiveSlot("2026-11-02","12:00").verifiedAtSlot, true);
  assert.notEqual(selected.originalReportStatus, "PUBLISHED");
});

test("date controls move Oct 30 to Nov 2, then allow selecting a real Nov 3 slot", async () => {
  const nov3Archive = structuredClone(archives.get("data/dashboard-drive-archive-2026-11-03.json"));
  nov3Archive.reports = nov3Archive.reports.filter(r => r.time !== "21:00");
  const { window, nodes } = await boot({search:"?date=2026-10-30&time=21:00",payloadOverrides:{"data/dashboard-drive-archive-2026-11-03.json":nov3Archive}});
  assert.equal(window.MarketReportLastRendered.date, "2026-10-30");
  nodes.get("nextDate").onclick();
  assert.equal(window.MarketReportLastRendered.date, "2026-11-02");
  assert.equal(window.MarketReportLastRendered.time, "21:00");
  nodes.get("datePicker").value = "2026-11-03";
  nodes.get("datePicker").onchange();
  assert.equal(window.__hooks.selected(), null);
  assert.equal(window.MarketReportLastRendered, null);
  window.__hooks.select("2026-11-03","16:00");
  assert.equal(window.MarketReportLastRendered.fullText, archiveSlot("2026-11-03","16:00").fullText);
});
test("formal data failure does not discard valid saved records and warns", async () => {
  const { window, nodes } = await boot({fail:["reports.json"],search:"?date=2026-11-03&time=08:00"});
  assert.equal(window.MarketReportLastRendered.fullText, archiveSlot("2026-11-03","08:00").fullText);
  assert.match(nodes.get("reportStatus").textContent, /一部データ未取得/);
});

test("formal publication wins duplicate slot", async () => {
  const formalReport = { ...archiveSlot("2026-10-30","21:00"), formal:true, fullText:"FORMAL BODY", title:"Formal" };
  const payloadOverrides = {"reports.json":[formalReport]};
  const { window } = await boot({payloadOverrides, search:"?date=2026-10-30&time=21:00"});
  assert.equal(window.MarketReportLastRendered.fullText, "FORMAL BODY");
});

test("published or malformed records fail archive validation", async () => {
  const badPayload = structuredClone(archives.get("data/dashboard-drive-archive-2026-11-03.json"));
  const record = badPayload.reports.find(r => r.time==="16:00");
  record.originalReportStatus = "PUBLISHED";
  const { window } = await boot({payloadOverrides:{"data/dashboard-drive-archive-2026-11-03.json":badPayload}});
  assert.equal(window.__hooks.reports().some(r=>r.date==="2026-11-03" && r.time==="16:00"), false);
});

test("all sources down produces visible error; partial archive failure still allows available data", async () => {
  const all = ["reports.json","data/report-recovery-2026-10.json","data/report-archive-manifest.json"];
  const failed = await boot({fail:all});
  assert.match(failed.nodes.get("app").innerHTML, /再読み込みしてください/);
  const partial = await boot({fail:["data/dashboard-drive-archive-2026-11-02.json"],search:"?date=2026-10-30&time=21:00"});
  assert.equal(partial.window.MarketReportLastRendered.fullText, archiveSlot("2026-10-30","21:00").fullText);
  assert.match(partial.nodes.get("reportStatus").textContent,/一部データ未取得/);
});
