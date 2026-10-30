const fs=require('fs'),assert=require('assert');
const yaml=fs.readFileSync('.github/workflows/sync-latest-report-watchdog.yml','utf8');
const scheduledCheck=yaml.split('name: Verify scheduled slot after reconciliation')[1].split('name: Verify dashboard matches latest report')[0];
assert(scheduledCheck.includes('from report_identity import canonical_path, internal_report_key'), 'scheduled slot verifier must import shared report identity helpers');
assert(!yaml.includes('5,20 0 * * 6'), 'Saturday cron still active');
assert(!yaml.includes('No complete source exists for'), '21:00 missing publication silently accepted');
assert(yaml.includes("raise SystemExit(f'scheduled canonical report missing after reconciliation: {path}')"));
for(const cron of ['5,15,30 23 * * 0-4','5,15,30 3 * * 1-5','5,15,30,50 7 * * 1-5','5,15,30 12 * * 1-5'])assert(yaml.includes(cron),cron);
console.log('Watchdog schedule and missing 21:00 fail-closed PASS');
