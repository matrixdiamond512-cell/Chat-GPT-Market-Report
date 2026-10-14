# New-report pipeline test (local DRAFT only)

Source snapshot: [`source-report.json`](source-report.json), copied byte-for-byte from `reports/2026-10-14_16-00.json` in PR branch commit `a019887aac2c33a7d32fb7ba3ec013972d8863af` (SHA-256: `8d044ab59c6a0406e57af391dce707fe92f0fdf3b71f68738bb87123eb3eaae3`). It is retained under test evidence, not the canonical publication directory; the canonical test-only entry was removed after pipeline verification to keep the publication index stable.

The report title is `TEST ONLY`, with a new report identity, revision 1, typed snapshot, and exact body hash. G0/G1/G2, source-bound spec validation, prompt generation, approved-layout preflight, Edge rendering, and local panel manifest all passed. The image and panel manifest remain `DEBUG_PREVIEW`; numeric validation is `UNVERIFIED`; `publish_allowed` is false; no publication manifest was created. The test body deliberately contains no real scheduled events.

See [acceptance evidence](../../ACCEPTANCE-20261014.md).
