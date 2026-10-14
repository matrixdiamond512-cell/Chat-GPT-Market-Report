# PR #97 acceptance evidence — 2026-10-14

**Disposition: NOT ACCEPTED for formal generation or visual design.** The 4 PNGs below are local `DEBUG_PREVIEW` artifacts for visual review only. They carry the data-provenance warning and must not be treated as restored reports, approved designs, or publication-ready material.

## Four generated PNGs

| Slot | PNG | Dimensions | Receipt | Visual review |
|---|---|---:|---|---|
| 08:00 | [preview PNG](review-20261014-design-final/2026-10-13_08-00/png/preview-2026-10-13_08-00.png) | 1536 × 2333 | `PASS`; numeric validation `UNVERIFIED`; `DEBUG_PREVIEW` | Content remains comparatively sparse in several panels; much taller than reference |
| 12:00 | [preview PNG](review-20261014-design-final/2026-10-13_12-00/png/preview-2026-10-13_12-00.png) | 1536 × 2015 | `PASS`; numeric validation `UNVERIFIED`; `DEBUG_PREVIEW` | Denser tables; large unused vertical space remains in panels 1, 2, 6, and 8 |
| 16:00 | [preview PNG](review-20261014-design-final/2026-10-13_16-00/png/preview-2026-10-13_16-00.png) | 1536 × 2408 | `PASS`; numeric validation `UNVERIFIED`; `DEBUG_PREVIEW` | Balanced information across rows, but much taller than reference and warning panel uses a different treatment |
| 21:00 | [preview PNG](review-20261014-design-final/2026-10-13_21-00/png/preview-2026-10-13_21-00.png) | 1536 × 3137 | `PASS`; numeric validation `UNVERIFIED`; `DEBUG_PREVIEW` | Highest density and height; some narrow market tables are difficult to scan at page scale |

![Reference and four-slot contact sheet](review-20261014-design-final/comparison-contact-sheet.png)

The generated panels retain the approved 16-panel order, use the event schedule at panel 15, improve contrast with colored panel bands, use six compact market tiles, and distinguish the two cross-asset flow directions. The theme now reads more clearly as a structured report. Visual acceptance remains **PENDING**: versus the 1536 × 1024 approved reference, every output is substantially taller; the reference packs more information into compact illustrated cards, uses larger pictograms/arrows, and fills panel space more evenly. Several generated panels have conspicuous blank areas, panel 4 does not reproduce the reference's three illustrated risk conditions, and the compact text/table styling is less legible and less pictorial. Technical browser checks do not resolve these design differences.

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

A new local-only October 14 16:00 draft was constructed using a new acquisition payload. At acquisition, all six required market symbols were returned as verified, with no required fields missing and no fallback values; 16 secondary-symbol acquisition errors were recorded. A typed snapshot and internally consistent new report identity/body hash were created. No canonical report file, Google Doc, Drive file, or production state was written.

Formal generation then **failed closed** at `validate_spec` with `MISSING_REQUIRED_SECTION`, `NUMERIC_DRIFT`, and `NUMBER_PROVENANCE_MISSING`. Inspection identified generator/validator contract mismatches: numeric cards annotate change and percentage values as if they were the market's `priceValue`, while the validator requires each annotated value to equal `priceValue`; the 16-panel numbered heading/title forms also do not satisfy the validator's required-section title aliases. These findings were retained as failures; no validation gate was bypassed. Formal projection, render-to-manifest, and G3/G4 publication/readback therefore remain **BLOCKED / NOT_RUN**. Required repair is to align the generator's number-field provenance and approved-panel heading mapping with the existing validation contract, add regression cases, and repeat the entire fresh-report trial.

## Verification

- Python `unittest discover -s tests -q`: **PASS, 237 tests** on 2026-10-14.
- Four Edge render receipts: **PASS** for browser layout/render diagnostics; no rendered overflow or card overlaps in the stored receipts. The receipts label numeric validation `UNVERIFIED` and artifact type `DEBUG_PREVIEW`.
- Source/snapshot audit for historical reports: **BLOCKED** by missing original snapshot/identity evidence as detailed above.
- Fresh-report spec validation: **FAIL/CLOSED** with the three errors above.
- Human visual comparison against approved reference: **NOT ACCEPTED**; differences remain.
- Formal manifest integration, Drive/Portal readback, physical-device review: **NOT_RUN**.
- Existing publication-stop and validation gates were not relaxed. PR remains Draft/Open; no merge, production publication, or Google Drive save was performed.

## Next necessary work

1. Repair and regression-test the fresh-report generator/validator contract without relaxing existing data, snapshot, or publication gates.
2. Re-run a new-report test through validated spec, approved projection, image verification, and local manifest linkage.
3. Reduce page height, remove empty panel space, strengthen pictograms/arrows, and make the event/risk treatments closer to the approved reference; review all four outputs again at display scale.
4. Recover original pre-slot source snapshots and immutable report identity evidence from source archives if available. Keep unrecoverable slots explicitly blocked.
