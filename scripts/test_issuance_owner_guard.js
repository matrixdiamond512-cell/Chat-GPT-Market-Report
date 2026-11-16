'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('apps-script/MarketReportWebSync.gs', 'utf8');
const context = {};
vm.runInNewContext(source, context, { filename: 'MarketReportWebSync.gs' });
const allows = context.marketReportSlotOwnerAllows_;

const base = { schemaVersion: 1, slotOwners: {
  '08:00': 'apps_script_legacy',
  '12:00': 'apps_script_legacy',
  '16:00': 'apps_script_legacy',
  '21:00': 'apps_script_legacy'
}};
assert.equal(allows({time:'08:00'}, base, 'apps_script_legacy'), true);
assert.equal(allows({time:'08:00'}, base, 'g2_issuance_cli'), false);
assert.equal(allows({time:'12:00'}, base, 'apps_script_legacy'), true);
assert.equal(allows({time:'16:00'}, base, 'apps_script_legacy'), true);
assert.equal(allows({time:'21:00'}, base, 'apps_script_legacy'), true);
assert.equal(allows({time:'08:00'}, {schemaVersion:1,slotOwners:{}}, 'apps_script_legacy'), false);
console.log('08:00 publisher ownership guard PASS; 12:00/16:00/21:00 remain legacy-owned.');
