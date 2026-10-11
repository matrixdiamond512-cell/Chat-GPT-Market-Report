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
