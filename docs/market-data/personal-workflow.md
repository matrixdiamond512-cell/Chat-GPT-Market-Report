# Personal market-data workflow

The private market workflow has one data lineage: acquire a market snapshot, validate each instrument using its own market calendar/session, normalize it, and pass that same snapshot to both the Google Sheets writer and the private report renderer. Sheets persistence and report rendering remain separate technical steps so either can be retried safely; they are not treated as different user purposes.

`data/market/latest.json` is the input consumed by `scripts/write_market_data_to_sheets.py`. The private report draft is built from that same payload with:

```text
python scripts/build_personal_market_report.py --input data/market/latest.json --output <private-path>
```

To append the report body to the dedicated private test workbook, use `--write-test-sheet` with `MARKET_DATA_TEST_SPREADSHEET_ID`, `MARKET_DATA_SPREADSHEET_ID`, and `GOOGLE_SERVICE_ACCOUNT_JSON` configured. The writer refuses to proceed if the test ID equals the production ID, appends only to `Personal_Market_Report`, reads the row back, and uses a stable snapshot ID to prevent duplicates. It does not modify the production `終値一覧` tab or its 186-column layout.

The generated report creates the detailed analysis sections from the same acquired snapshot as its 28-item table. It uses source-attached daily changes only when the row is verified, and it records each market's own as-of date, retrieval time, source and validation basis instead of forcing all markets to one calendar date. News, fund flows, positioning, events or price targets are not invented when the snapshot lacks those observations; the report marks them unavailable and uses conditional scenarios grounded in the verified changes. Continuous-futures values remain references unless contract-specific settlement is confirmed; unavailable fields stay blank. The upstream market adapter remains responsible for source-specific quote, close, date, freshness and session validation.

Personal Sheets storage and private report creation are part of this same workflow. Public GitHub storage and public dashboard display are separate publication destinations and retain their own controls. A restriction on one automated source route does not prevent use of other validated routes or manual import paths.

## Historical detailed-report integration — 2026-10-12

The report renderer creates news, cross-asset flow, positioning, six-market outlook, scenario, invalidation and risk sections from the shared market snapshot. It does not carry over a legacy narrative whose timestamp differs from the quote records. When the corresponding evidence (dated news, flows, positioning, events) is absent, that section says so instead of reusing old prose. Rates and price observations are rendered from the same normalized snapshot, with item-specific `asOf`, retrieval time, source, session/anchor, unit, and validation basis. Historical snapshots carry an explicit warning.

The already saved historical row remains an archival record of its original body. New report versions are generated from one matched snapshot and do not copy that older narrative. The complete prior readback evidence and limitations are recorded in `docs/project-control/EVIDENCE_LEDGER.md`. No production close-list values or formats were changed.


## 2026-10-15 PR #94 strict historical as-of guard (code change, tests pending)

The delayed 2026-10-13 Tokyo archive assembled on 2026-10-15 is preserved unchanged. It is not a 2026-10-13 16:00 JST contemporaneous report. BTC/USD 2026-10-14 UTC and OANDA FX 2026-10-14 New York daily closes cannot appear in a report claiming the earlier Tokyo cutoff.

Added \`scripts/market_snapshot_asof.py\` and an optional \`--as-of 2026-10-13T16:00:00+09:00\` to the private report renderer. A separate strict view suppresses any observation lacking evidence available by cutoff. Later retrieval requires explicit pre-cutoff \`publishedAt\`, \`publicationEvidenceUrl\` and \`publicationEvidence\`; publication date alone or market date alone is not enough. Verified Japan valuation observations also require an explicit \`seriesBasis\`; calculated Nikkei deviation requires same-series history metadata; Prime metrics require a Prime-only scope. References never become production candidates. Post-cutoff news is suppressed, and rejected numerical values are removed rather than re-labeled while still visible. Output includes exclusions and a deterministic cutoff-specific snapshot ID.

This commit only adds the as-of projection and regression tests; no live-source re-acquisition, Sheets append, production write, source-rights attestation, GitHub Actions dispatch, workflow PASS claim, or main merge. The previous archive-wide 11/12/5 tally remains historical and MUST NOT be presented as the strict 16:00 view's verified/reference/unavailable tally. Exact historical as-of coverage depends on documented availability timestamps for each source. Tests are **NOT_RUN** until hosted CI or a local execution is read back. PR stays OPEN / Draft / unmerged.
