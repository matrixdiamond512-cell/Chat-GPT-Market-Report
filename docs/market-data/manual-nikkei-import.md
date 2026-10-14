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

`dailyCloseHistory` is optional. When provided, it must contain at least 200 dated Japan-market sessions ending on `marketDate`; holidays are omitted. Set `dailyCloseHistorySourceName` and `dailyCloseHistorySourceUrl` when history comes from a different source. Deviations are calculated from the history series' own latest close and simple moving average; the importer does not replace it with a different official close. A mismatch against `nikkei225Close` is recorded in the series definition, and technical rows from a separate source remain `REFERENCE_ONLY` pending independent history verification. The importer rejects duplicate dates, weekend/future dates, invalid values, missing source attribution, and insufficient history. The 25- and 200-session deviations both include the history series' target-day close:

`(target close / arithmetic mean of last N closes - 1) × 100`

The index-based PER/PBR values are optional as a pair. Supply `nikkei225ValuationBasis: "index_based"`, both metrics, and `nikkei225Close`; the importer derives EPS as `nikkei225Close / nikkei225ForecastPER`. If the source separately reports comparable index-based EPS, include `nikkei225ReportedForecastEPS`; the importer checks equality at its published precision. If no comparable source EPS is published, the derived EPS stays explicitly labelled as calculated. Weighted-average constituent metrics are a different series and are rejected. With no daily history, official cash/VI plus the valuation pair produce five rows. With history, the two deviation rows are added; history from another source is never promoted to `VERIFIED_MANUAL` by source-value attestation alone.

Run locally from the repository root:

```powershell
python scripts/import_manual_nikkei_data.py --input nikkei-manual.json --output nikkei-personal-report-input.json
```

To also append the available rows to the dedicated private test tab `Manual_Nikkei_Review`, provide `MARKET_DATA_TEST_SPREADSHEET_ID` and `GOOGLE_SERVICE_ACCOUNT_JSON` in the local process environment and add `--write-test-sheet`. If `MARKET_DATA_SPREADSHEET_ID` is set, the importer refuses to use it as the test destination. Snapshot IDs make repeated imports idempotent; a changed value under an existing snapshot ID stops rather than overwrites.

After checking the source's displayed date and values, add `--attest-source-reviewed` alongside `--write-test-sheet`. Official same-source values and derived same-date EPS append to `Personal_Report_Ready` as `VERIFIED_MANUAL`; calculations based on a separate history source append as `REFERENCE_ONLY`. The normal JSON output and `Manual_Nikkei_Review` remain labelled `MANUAL_REVIEW`; without this explicit option no row is promoted.

Rows are labelled `MANUAL_REVIEW`; manual entry and arithmetic checks do not independently verify the displayed source value. Check the source date/value and all imported rows before treating them as verified. No public dashboard output is generated.
