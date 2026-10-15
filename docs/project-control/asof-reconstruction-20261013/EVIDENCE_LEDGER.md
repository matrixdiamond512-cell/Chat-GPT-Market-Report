# Evidence Ledger — 2026-10-13 16:00 JST reconstruction

Last updated: 2026-10-15. Evidence scope is limited to the isolated PR #94 source copy and the external read/write results listed below.

| Claim | Evidence | Level / state | Limit |
|---|---|---|---|
| P0 source compiles | `python -m py_compile scripts/market_snapshot_asof.py scripts/build_personal_market_report.py scripts/sync_market_close_sheet.py` | E0 / PASS | Isolated copy; hosted checks on current remote HEAD are unavailable |
| Requested test suites pass | `python -m unittest tests.test_market_snapshot_asof tests.test_personal_market_report tests.test_personal_market_snapshot tests.test_sync_market_close_sheet -q` (54 tests) | E1 / PASS | Isolated copy; rerun on 2026-10-15 after adding intraday-reference coverage |
| Historical cutoff | 2026-10-13T16:00:00+09:00 = 2026-10-13T07:00:00Z | E0 / PASS | No claim that the report was generated at the historical time |
| 28 fields classified | Snapshot `asof-7c05cd9ed95a609865f57e9a`; 0 VERIFIED_AS_OF / 15 REFERENCE_AS_OF / 13 UNAVAILABLE_AS_OF | E0 / PASS | 15 are pre-cutoff intraday references, not closes; the archive contains no strict finalization evidence. Missing values mean absent from this archive/run, not that markets had no data |
| Snapshot hash | `8b6baf8378f3fd8032072137fdf3010adec20a5c8a059bc0009147dc8a7ffd5b` | E0 / PASS | SHA-256 of the generated JSON file bytes |
| Evidence-ledger hash | `61ddf818133c82f4e1f7db6b50fef36f821e90d0b568ff5f0e94404d57925274` | E0 / PASS | SHA-256 of the generated JSON file bytes |
| Report hash | `f03e16e08076946bb62882ed2495f59f60cf3a7c59be6aa61fc687e31da611a4` | E0 / PASS | SHA-256 of generated Markdown file bytes; generation time embedded |
| Timeline shape | 9 JST periods and 7 common columns | E0 / PASS | Every period states that contemporaneous event/price evidence is absent; no price path is inferred |
| Private Sheets save/readback | `Market Data API Test` / `Personal_Market_Report`, corrected row 19, ID `personal-report-ea69e338d9683914d3e5de34`; all A:I read back exactly, including full body and hash | E2 / PASS | Test ID `1vqraQzVpIHWLFSxP5X5NWoTYquT6B27l-A7UuyYauNY`, distinct from production ID; ID occurs once. Earlier row 18 remains preserved as the superseded 0/0/28 artifact |
| Production read-only inspection | `終値一覧`, row 27, date `2026/10/13`; matching-row scan returned one row. Nonempty target-row fields: A, U, V, BO, BP, BQ, BR, CX, CY | E2 / PASS | No production write/update tool was called. Full dry-run implementation and a structural before/after comparison remain open |
| Dedicated dry-run path | `sync_market_close_sheet.py --dry-run` dispatches to a separate read-only function and bypasses upsert, formatting, readback-write, and audit-log paths. Dry-run artifact: 0 MATCH / 0 VALUE_CONFLICT / 2 DEFINITION_PENDING / 13 UNAVAILABLE_AS_OF / 0 FORMULA_PROTECTED / 13 NO_ELIGIBLE_WRITE | E1 / PASS | Pure comparison function tested locally. Live sheet was independently inspected through read-only Sheets connector; CLI was not invoked because local service-account credentials are unavailable |
| Production before/after | Re-read row 27, full A:GF headers, A2:A940 date column, formulas and metadata. All compared values matched; 1 target-date row; 186 columns and 23 conditional-format rules | E2 / PASS | No writes were made to production; date-cell display and formula-rendered serial differ by rendering mode but underlying data remained unchanged |
| Draft PR state | PR #94 HEAD `78ee1ba2e8b120ca9ebf8761e2b9f8361511d3e2`, OPEN / Draft / unmerged; PR #133 HEAD `e8b8b8684129171029fc9976424838ff96e29bf1`, OPEN / Draft / unmerged | E5 / PASS | PR #94 latest HEAD has 0 check runs and 0 PR workflow runs; PR #133 still has 3 latest validation failures |

| Formal Docs correction | Requirement, specification, and operations documents appended under required-revision guards; all three read back with corrected counts, row-19 ID, and PR #94 HEAD | E2 / PASS | Append-only correction preserves earlier entries as history |

## Failures / not run
- `pytest` is unavailable in the bundled interpreter; standard-library `unittest` was used as specified by the task.
- A broader exploratory run of 42 tests included four unrelated source-validation errors because the isolated review copy lacks the corresponding source configuration. It is not part of the requested P0 suites; no PASS claim is made for that broader run.
- The first attempted Sheets row serialization used the Windows cp932 stdout and failed before any external write; the successful UTF-8 retry wrote exactly one test-sheet row, then read back all nine cells.
- No current GitHub Actions run for the tested P0 code has been observed yet.
- No complete market-source/history evidence was recovered for the 2026-10-13 16:00 JST cutoff; all 28 outputs remain unavailable in this run.
- New `--dry-run` CLI was not live-invoked: local service-account credentials are unavailable. The external production comparison used the connected Sheets read-only API and the same target row.
- The report is a partial history reconstruction, not an as-of-complete market narrative.

## Production safety
Production spreadsheet ID: `1n2ACInX4pmK0TdijC8xaur2RIiNZyVa6GFTZAyofcuE`. Read only. Production write calls: 0; row insertions: 0; audit updates: 0; formatting updates: 0.

