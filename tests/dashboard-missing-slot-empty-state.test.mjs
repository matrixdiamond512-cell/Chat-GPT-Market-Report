import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const root = new URL('../', import.meta.url);
const read = path => fs.readFileSync(new URL(path, root), 'utf8');
const gaps = JSON.parse(read('data/report-content-gaps.json')).missingSlots;
const main = read('assets/js/top-dashboard.js').replace(/init\(\);\s*$/, '');

function harness(search = '') {
  const nodes = {};
  const flags = new Set();
  const shell = {
    classList: {
      toggle(name, on) { if (on) flags.add(name); else flags.delete(name); },
      contains(name) { return flags.has(name); }
    }
  };
  const document = {
    title: '',
    getElementById(id) {
      if (!nodes[id]) nodes[id] = {
        innerHTML: '', textContent: '', hidden: id === 'dashboardMissingSlot',
        querySelectorAll() { return []; }
      };
      return nodes[id];
    },
    querySelector(selector) { return selector === '.page-shell' ? shell : null; }
  };
  const window = {
    location: { search, href: 'https://example.test/index.html' + search },
    history: { replaceState(_state, _unused, url) { window.location.href = String(url); } },
    MarketReportPublicationPolicy: { isEligible: () => true }
  };
  const fetch = async () => ({
    ok: true, json: async () => ({ status: 'SOURCE_NOT_FOUND_IN_REPOSITORY', missingSlots: gaps })
  });
  const context = vm.createContext({ window, document, URLSearchParams, URL, Date, console, fetch });
  vm.runInContext(main + '\nwindow.hooks={selectReport,setDashboardMissingState,init,selected:()=>selectedReport,missing:()=>requestedMissingSlot};', context);
  const known = [
    { date: '2026-11-16', time: '16:00' },
    { date: '2026-10-20', time: '12:00' },
    { date: '2026-10-22', time: '08:00' },
    // An old recovery notice exists, but the original 12:00 body does not.
    { date: '2026-10-22', time: '12:00', originalReportStatus: 'ORIGINAL_NOT_FOUND', archiveType: 'RECONSTRUCTED_SOURCE' },
    { date: '2026-11-04', time: '12:00' },
    { date: '2026-11-06', time: '16:00' }
  ];
  vm.runInContext('reports=' + JSON.stringify(known), context);
  vm.runInContext('knownMissingReportSlots=new Set(' + JSON.stringify(gaps) + ')', context);
  return { window, document, shell, nodes, hooks: window.hooks, known, context };
}

test('exactly five known original-body gaps remain declared, not synthesized', () => {
  assert.equal(gaps.length, 5);
  assert.equal(new Set(gaps).size, 5);
});

for (const slot of gaps) {
  test('dashboard explicitly clears previous view for missing ' + slot, () => {
    const [date, time] = slot.split(' ');
    const h = harness();
    // Simulate text remaining from a previously selected, real report.
    h.document.getElementById('marketCards').innerHTML = 'PREVIOUS_REPORT_VALUE';
    h.hooks.selectReport(date, time);
    assert.equal(h.hooks.selected(), null);
    assert.equal(h.hooks.missing().date, date);
    assert.equal(h.hooks.missing().time, time);
    assert.equal(h.shell.classList.contains('dashboard-missing-slot'), true);
    assert.equal(h.nodes.dashboardMissingSlot.hidden, false);
    assert.match(h.nodes.dashboardMissingSlot.textContent, /対象データなし/);
    assert.match(h.nodes.dashboardMissingSlot.textContent, /前のレポート.*表示しません/);
    assert.match(h.nodes.reportStatus.textContent, /対象データなし/);
    assert.equal(h.nodes.dateInput.value, date);
    assert.match(h.nodes.timeTabs.innerHTML, new RegExp('data-time="' + time + '"'));
    assert.doesNotMatch(h.nodes.timeTabs.innerHTML, /disabled/);
    const address = new URL(h.window.location.href);
    assert.equal(address.searchParams.get('date'), date);
    assert.equal(address.searchParams.get('time'), time);
    assert.equal(h.nodes.marketCards.innerHTML, 'PREVIOUS_REPORT_VALUE');
    // The container-level visibility fence hides every stale panel, even if
    // later overlay scripts have left historical text in its DOM subtree.
    assert.match(read('assets/css/top-dashboard.css'), /\.page-shell\.dashboard-missing-slot\s*>\s*:not\(\.control-bar\):not\(#dashboardMissingSlot\)/);
  });
}

test('missing-state notice and panel visibility are restored separately on real selection', () => {
  const h = harness();
  h.hooks.selectReport('2026-11-06', '12:00');
  assert.equal(h.shell.classList.contains('dashboard-missing-slot'), true);
  h.hooks.setDashboardMissingState(null);
  assert.equal(h.shell.classList.contains('dashboard-missing-slot'), false);
  assert.equal(h.nodes.dashboardMissingSlot.hidden, true);
  assert.equal(h.nodes.dashboardMissingSlot.textContent, '');
});

test('explicit missing deep link survives initial dashboard bootstrap without redirect', async () => {
  const h = harness('?date=2026-11-04&time=08%3A00');
  vm.runInContext(
    'loadDashboardReports=async()=>({reports:' + JSON.stringify(h.known) + ',meta:{}});' +
    'loadDashboardEventCalendar=async()=>({events:[]});' +
    'loadStockAnalysisData=async()=>null;',
    h.context
  );
  await h.hooks.init();
  assert.equal(h.hooks.selected(), null);
  assert.equal(h.shell.classList.contains('dashboard-missing-slot'), true);
  assert.match(h.nodes.reportStatus.textContent, /対象データなし/);
  assert.match(h.window.location.href, /date=2026-11-04/);
});
