# Personal market-data workflow

The private market workflow has one data lineage: acquire a market snapshot, validate each instrument using its own market calendar/session, normalize it, and pass that same snapshot to both the Google Sheets writer and the private report renderer. Sheets persistence and report rendering remain separate technical steps so either can be retried safely; they are not treated as different user purposes.

`data/market/latest.json` is the input consumed by `scripts/write_market_data_to_sheets.py`. The private report draft is built from that same payload with:

```text
python scripts/build_personal_market_report.py --input data/market/latest.json --output <private-path>
```

To append the report body to the dedicated private test workbook, use `--write-test-sheet` with `MARKET_DATA_TEST_SPREADSHEET_ID`, `MARKET_DATA_SPREADSHEET_ID`, and `GOOGLE_SERVICE_ACCOUNT_JSON` configured. The writer refuses to proceed if the test ID equals the production ID, appends only to `Personal_Market_Report`, reads the row back, and uses a stable snapshot ID to prevent duplicates. It does not modify the production `終値一覧` tab or its 186-column layout.

The generated table always has the 28 report fields. It shows verified values, labels fallback/continuous-futures values as references when settlement is not confirmed, and leaves unavailable values blank. It carries each market's own as-of date and source rather than forcing all markets to one calendar date. The upstream market adapter remains responsible for source-specific quote, close, date, freshness and session validation.

Personal Sheets storage and private report creation are part of this same workflow. Public GitHub storage and public dashboard display are separate publication destinations and retain their own controls. A restriction on one automated source route does not prevent use of other validated routes or manual import paths.

