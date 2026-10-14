# PR #97 acceptance evidence — 2026-10-14

**Disposition: historical 4-slot previews are not formally accepted; fresh-report pipeline passes locally; visual design remains pending.** The October 13 images are `DEBUG_PREVIEW` artifacts for visual review only. They carry source/snapshot warnings and do not restore withdrawn reports.

## Four generated PNGs

| Slot | PNG | Dimensions | Receipt | Visual review |
|---|---|---:|---|---|
| 08:00 | [preview PNG](review-20261014-design-final/2026-10-13_08-00/png/preview-2026-10-13_08-00.png) | 1536 × 2539 | `PASS`; numeric validation `UNVERIFIED`; `DEBUG_PREVIEW` | Six primary market rows are kept together; panel 8 now carries risk/volatility series; still much taller than reference |
| 12:00 | [preview PNG](review-20261014-design-final/2026-10-13_12-00/png/preview-2026-10-13_12-00.png) | 1536 × 2001 | `PASS`; numeric validation `UNVERIFIED`; `DEBUG_PREVIEW` | Missing panel 6 shrinks to its unavailable marker; several other large gaps remain |
| 16:00 | [preview PNG](review-20261014-design-final/2026-10-13_16-00/png/preview-2026-10-13_16-00.png) | 1536 × 2408 | `PASS`; numeric validation `UNVERIFIED`; `DEBUG_PREVIEW` | Six primary markets and risk data are separated; still much taller than reference |
| 21:00 | [preview PNG](review-20261014-design-final/2026-10-13_21-00/png/preview-2026-10-13_21-00.png) | 1536 × 3137 | `PASS`; numeric validation `UNVERIFIED`; `DEBUG_PREVIEW` | Highest density and height; some narrow market tables remain hard to scan at page scale |

![Reference and four-slot contact sheet](review-20261014-design-final/comparison-contact-sheet.png)

The generated panels retain the approved 16-panel order, place the event schedule in panel 15, use high-contrast colored bands, keep six primary market tiles together, group volatility/sentiment series in panel 8, and distinguish the two cross-asset flow directions. Missing panel 6 content now collapses to its unavailable marker. Visual acceptance remains **PENDING**: compared with the 1536 × 1024 approved reference, these outputs remain substantially taller; the reference uses larger pictograms and more evenly filled illustrated cards. Panel 4 does not reproduce the reference's three illustrated risk conditions, and small table text is less readable at a fitted-page scale. Browser PASS does not resolve these design differences.

## Historical source and snapshot investigation

The four October 13 reports are not formally reproducible from the evidence recovered:

| Slot | Source evidence | Snapshot/spec disposition |
|---|---|---|
| 08:00 | Google Doc exists and its current text resembles a Git source version. Its initial revision returned no body; the local lock has no original body hash, revision, snapshot ID, or report ID. Git history marks the report withdrawn. | `MARKET_DATA_SNAPSHOT_NOT_FOUND`; required body/identity/spec evidence missing. Later market-history acquisition is not a substitute. |
| 12:00 | Google Doc exists, but the earliest revision returned no body. Git contains an explicitly sourced reconstruction after the slot and the report was later withdrawn. | Snapshot and original identity absent. The reconstruction is not accepted as original. |
| 16:00 | Google Doc exists; the retained report text does not establish an immutable original body/revision-to-snapshot link. | Snapshot ID, typed historical snapshot, and source-bound spec absent. Current text alone is insufficient. |
| 21:00 | Google Doc exists, but the initial revision returned no body and usable original body/revision/hash proof was not recovered. Git history marks the report withdrawn. | `MARKET_DATA_SNAPSHOT_NOT_FOUND`; identity/spec absent. Later history cannot restore the prior market state. |

All retrieved historic market-history records were acquired after their report slots. No later prices were backfilled into the October 13 reports, and withdrawn source documents were not restored. Required recovery is the original pre-render acquisition payload/snapshot plus its immutable report identity, body hash, spec, and revision linkage from the original generator/archive or provider history. If that evidence no longer exists, those historical outputs remain unrecoverable as formal source reports.

## Fresh-report formal-generation trial

A new October 14 16:00 DRAFT was generated from a new acquisition payload. Its TEST ONLY source was copied into [isolated test evidence](review-20261014-design-final/new-report-test/source-report.json) and removed from the canonical `reports/` directory so publication-index rebuilds cannot ingest a test report. All six required symbols were verified at acquisition; no required values were missing and no fallback was used. Sixteen secondary-symbol acquisition errors were recorded. The typed snapshot, revision-1 identity, and body hash were bound at report creation, and G0/G1/G2 passed.

The first `validate_spec` run exposed three generator/validator contract mismatches: number cards treated change and percent as current prices, narrative numbers lacked precise source-line provenance, and numbered panel headings did not match required-section aliases. These were fixed without relaxing the source lock or snapshot-value checks. Market price/change/change-percent fields now bind separately to the typed snapshot; other body numbers bind to exact source-section line hashes; numbered headings are normalized before the existing required-section comparison. Regression cases reject changed source-line hashes and check each market field. The same new report then passed `validate-infographic-spec` with 30 structured panels and 49 unique numeric values and generated a source-bound prompt.

The approved-layout DRAFT render also passed with a current Git source at commit `a019887aac2c33a7d32fb7ba3ec013972d8863af`. Its local `panel-manifest.json`, `numeric-registry.json`, `source-lock.json`, `preflight.json`, render contract, and [test PNG](review-20261014-design-final/new-report-test/png/preview-2026-10-14_16-00.png) are included. The renderer reported no overflow, no out-of-panel content, and no card overlaps. It remains `DEBUG_PREVIEW`; numeric validation is `UNVERIFIED`, `publish_allowed=false`, and the publication manifest is `NOT_CREATED`. Event rows in this pipeline-only body deliberately contain no market-event data, so this proves report/spec/render connection but not real event ingestion. G3/G4, Drive/Portal readback, and external publication were not run.

## Verification

- Python `unittest discover -s tests -q`: **PASS, 240 tests** before latest-main integration; after integrating main `931dd9b53a04b85a32ee59a8ca61bf4a3fb51188`, `unittest discover -s tests`: **PASS, 250 tests**. Publication consistency, all 164 indexed reports, canonical parity, and `build_reports.py` no-rewrite stability also **PASS** after isolating the TEST ONLY source from canonical history.
- Independent publication-path, Apps Script infographic gate, and 16:00 source recovery fail-closed regression tests: **PASS**.
- Four Edge render receipts: **PASS** for browser layout/render diagnostics; no rendered overflow or card overlaps in the stored receipts. The receipts label numeric validation `UNVERIFIED` and artifact type `DEBUG_PREVIEW`.
- Source/snapshot audit for historical reports: **BLOCKED** by missing original snapshot/identity evidence as detailed above.
- Fresh-report G0/G1/G2, report/body and market validation, spec validation, source lock, prompt generation, and approved-layout DRAFT renderer: **PASS**. Local panel manifest created; publication manifest **NOT_CREATED** by design.
- Human visual comparison against approved reference: **NOT ACCEPTED**; differences remain.
- Formal manifest integration, Drive/Portal readback, physical-device review: **NOT_RUN**.
- Existing publication-stop and validation gates were not relaxed. PR remains Draft/Open; no merge, production publication, or Google Drive save was performed.
- Latest main `931dd9b53a04b85a32ee59a8ca61bf4a3fb51188` is integrated into this PR branch at merge commit `b4422cac20987b2eb2dfc970995478afb01ff62a`. Conflict resolution keeps the strict complete-dashboard copy and all FR-15–FR-19 identity/history protections; the Saturday/Sunday no-new-publication rule remains enforced. PR-branch push does not run the main-only publication/deployment workflows.
- The TEST ONLY source JSON is now isolated under the test-evidence directory. A post-move `build_reports.py` stability run discovered 164 canonical files and made no worktree changes; the report was not left in publishable canonical history.

## Next necessary work

1. Further reduce visual height, improve compact table readability, and make risk conditions closer to the approved three-item illustration; review the new four-slot PNGs at display scale.
2. Exercise event ingestion in a fresh report with event data bound to verified primary sources; the current pipeline test intentionally has no real event entries.
3. Recover original pre-slot source snapshots and immutable report identity evidence from source archives if available. Keep unrecoverable slots explicitly blocked.
4. Treat Drive/Portal readback and publication manifest as separate external work after explicit authorization; do not publish this PR branch.
