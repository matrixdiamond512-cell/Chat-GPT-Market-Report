# Personal manual Nikkei import

Use this path when an official Nikkei value is available for personal analysis but automated collection is not enabled. The importer makes no network request. It writes only to the configured private test spreadsheet and never updates the production `終値一覧`.

Prepare UTF-8 JSON with these fields:

```json
{
  "marketDate": "YYYY-MM-DD",
  "sourceName": "Name shown on the official source",
  "sourceUrl": "https://...",
  "sourceCapturedAt": "YYYY-MM-DDThh:mm:ss+09:00",
  "nikkei225Close": 0,
  "nikkeiViClose": 0,
  "nikkei225ValuationBasis": "index_based",
  "nikkei225ForecastPER": 0,
  "nikkei225IndexPBR": 0,
  "nikkei225ReportedForecastEPS": 0,
  "dailyCloseHistory": [
    {"date": "YYYY-MM-DD", "close": 0}
  ]
}
```

`dailyCloseHistory` must contain at least 200 dated Japan-market weekdays, end on `marketDate`, and have a final close exactly equal to `nikkei225Close`. Include one row for every observed session; holidays are omitted. The importer rejects duplicate dates, weekend/future dates, invalid values, missing source attribution, and insufficient history. The 25- and 200-session deviations both include the target day's close:

`(target close / arithmetic mean of last N closes - 1) × 100`

The valuation fields are optional as a group. Supply all four valuation keys shown above only when the source explicitly reports **Nikkei 225 index-based** forecast PER, PBR, and forecast EPS for the same `marketDate`. Weighted-average constituent metrics are a different series and are rejected. The importer derives the EPS used in the report as `nikkei225Close / nikkei225ForecastPER`, then requires it to round to the source-reported EPS at the latter's published decimal precision. When the valuation group is absent, the importer still produces the four cash/VI/deviation rows; when present, it produces seven rows. A mismatch or partial valuation group is rejected.

Run locally from the repository root:

```powershell
python scripts/import_manual_nikkei_data.py --input nikkei-manual.json --output nikkei-personal-report-input.json
```

To also append the four or seven rows to the dedicated private test tab `Manual_Nikkei_Review`, provide `MARKET_DATA_TEST_SPREADSHEET_ID` and `GOOGLE_SERVICE_ACCOUNT_JSON` in the local process environment and add `--write-test-sheet`. If `MARKET_DATA_SPREADSHEET_ID` is set, the importer refuses to use it as the test destination. Snapshot IDs make repeated imports idempotent; a changed value under an existing snapshot ID stops rather than overwrites.

After checking the official source's displayed date and values yourself, add `--attest-source-reviewed` alongside `--write-test-sheet`. This appends the four or seven same-date rows to `Personal_Report_Ready` with the distinct status `VERIFIED_MANUAL`. The normal JSON output and `Manual_Nikkei_Review` remain labelled `MANUAL_REVIEW`; without this explicit option the values are never promoted.

Rows are labelled `MANUAL_REVIEW`; manual entry and arithmetic checks do not independently verify the displayed source value. Check the source date/value and all imported rows before treating them as verified. No public dashboard output is generated.

