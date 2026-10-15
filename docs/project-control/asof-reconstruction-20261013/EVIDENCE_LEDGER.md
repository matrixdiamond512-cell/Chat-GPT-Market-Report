# Evidence Ledger — 2026-10-13 16:00 JST reconstruction

Last updated: 2026-10-15. Evidence scope is limited to the isolated PR #94 source copy and the external read/write results listed below.

| Claim | Evidence | Level / state | Limit |
|---|---|---|---|
| P0 source compiles | `python -m py_compile scripts/market_snapshot_asof.py scripts/build_personal_market_report.py` | E0 / PASS | Isolated copy; not yet current remote HEAD |
| As-of tests pass | `python -m unittest tests.test_market_snapshot_asof -v` (12 tests) | E1 / PASS | Isolated copy |
| Personal report/snapshot tests pass | `python -m unittest tests.test_personal_market_report tests.test_personal_market_snapshot -v` (20 tests) | E1 / PASS | Isolated copy |
| Historical cutoff | 2026-10-13T16:00:00+09:00 = 2026-10-13T07:00:00Z | E0 / PASS | No claim that the report was generated at the historical time |
| 28 fields classified | Snapshot `asof-8fb93c8c729be84e0fab17be`; 0 VERIFIED_AS_OF / 0 REFERENCE_AS_OF / 28 UNAVAILABLE_AS_OF | E0 / PASS | The input archive was a partial 2026-10-12 intraday snapshot; this means evidence absent from this archive/run, not that markets had no data |
| Snapshot hash | `4ab78099014ab6e06e36f8429adfafcf0a8654f103365640c67e14b49fc33b14` | E0 / PASS | Hash of generated reconstruction artifact |
| Evidence-ledger hash | `a905e6230e0082964582d44b39051e8c4d26e9d142cf3d481864f2d6853b1534` | E0 / PASS | Stable ledger hash excludes generation metadata |
| Report hash | `f68dd85562367e4b45e5474023605eca0972f60a047c870e9f34be95055aa95c` | E0 / PASS | Same-snapshot report; generation time is embedded |
| Timeline shape | 9 JST periods and 7 common columns | E0 / PASS | Every period states that contemporaneous event/price evidence is absent; no price path is inferred |
| Private Sheets save/readback | `Market Data API Test` / `Personal_Market_Report`, row 18, ID `personal-report-0dc334dce7e5713688e0d954`; A:I read back including full body and hash | E2 / PASS | Test ID `1vqraQzVpIHWLFSxP5X5NWoTYquT6B27l-A7UuyYauNY`, distinct from production ID; duplicate scan before write found no same ID |
| Production read-only inspection | `終値一覧`, row 27, date `2026/10/13`; matching-row scan returned one row. Nonempty target-row fields: A, U, V, BO, BP, BQ, BR, CX, CY | E2 / PASS | No production write/update tool was called. Full dry-run implementation and a structural before/after comparison remain open |
| Draft PR state | PR #94 was OPEN / Draft / unmerged at initial inspection; PR #133 also OPEN / Draft / unmerged | E5 / UNKNOWN after pending update | Must re-read both PRs and Actions after any branch update |

## Failures / not run
- `pytest` is unavailable in the bundled interpreter; standard-library `unittest` was used as specified by the task.
- A broader exploratory run of 42 tests included four unrelated source-validation errors because the isolated review copy lacks the corresponding source configuration. It is not part of the requested P0 suites; no PASS claim is made for that broader run.
- The first attempted Sheets row serialization used the Windows cp932 stdout and failed before any external write; the successful UTF-8 retry wrote exactly one test-sheet row, then read back all nine cells.
- No current GitHub Actions run for the tested P0 code has been observed yet.
- The report is a partial history reconstruction, not an as-of-complete market narrative.

## Production safety
Production spreadsheet ID: `1n2ACInX4pmK0TdijC8xaur2RIiNZyVa6GFTZAyofcuE`. Read only. Production write calls: 0; row insertions: 0; audit updates: 0; formatting updates: 0.
