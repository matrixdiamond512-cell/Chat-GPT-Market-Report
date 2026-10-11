# Personal market-data workflow

The private market workflow has one data lineage: acquire a market snapshot, validate each instrument using its own market calendar/session, normalize it, and pass that same snapshot to both the Google Sheets writer and the private report renderer. Sheets persistence and report rendering remain separate technical steps so either can be retried safely; they are not treated as different user purposes.

`data/market/latest.json` is the input consumed by `scripts/write_market_data_to_sheets.py`. The private report draft is built from that same payload with:

```text
python scripts/build_personal_market_report.py --input data/market/latest.json --detailed-report data/latest-report.json --output <private-path>
```

To append the report body to the dedicated private test workbook, use `--write-test-sheet` with `MARKET_DATA_TEST_SPREADSHEET_ID`, `MARKET_DATA_SPREADSHEET_ID`, and `GOOGLE_SERVICE_ACCOUNT_JSON` configured. The writer refuses to proceed if the test ID equals the production ID, appends only to `Personal_Market_Report`, reads the row back, and uses a stable snapshot ID to prevent duplicates. It does not modify the production `終値一覧` tab or its 186-column layout.

The generated report retains the existing detailed narrative sections when `--detailed-report` is supplied, then adds the 28-item table from the same acquired snapshot plus a snapshot-derived interest-rate section. It records each market's own as-of date, retrieval time, source and validation basis instead of forcing all markets to one calendar date. The narrative's original report date is identified and its prose is not silently recalculated from new quotes. Continuous-futures values remain references unless contract-specific settlement is confirmed; unavailable fields stay blank. The upstream market adapter remains responsible for source-specific quote, close, date, freshness and session validation.

Personal Sheets storage and private report creation are part of this same workflow. Public GitHub storage and public dashboard display are separate publication destinations and retain their own controls. A restriction on one automated source route does not prevent use of other validated routes or manual import paths.

## Historical detailed-report integration — 2026-10-12

When `--detailed-report data/latest-report.json` is supplied, the report renderer keeps the existing news, cross-asset flow, positioning, six-market outlook, scenario, invalidation and risk sections in the same private report as the 28-item table from the shared market snapshot. It identifies the original narrative timestamp and states that the prose was preserved, not recalculated from later quotes. Rates in the added rate section come directly from the same normalized snapshot. Per-market `asOf`, retrieval time, source, session/anchor, unit, and validation basis remain item-specific. This does not refresh the narrative or market data; report freshness follows the snapshot, and historical snapshots carry an explicit warning.

A real saved historical report was read from existing private tabs and stored in the dedicated `Personal_Market_Report` test tab. The complete readback evidence and limitations are recorded in `docs/project-control/EVIDENCE_LEDGER.md`. No production close-list values or formats were changed.