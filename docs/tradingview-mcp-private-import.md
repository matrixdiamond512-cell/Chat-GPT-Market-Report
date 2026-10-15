# TradingView MCP manual candidate import

This bridge makes one-time, user-requested TradingView MCP observations usable in the private market-data test spreadsheet. It does not make TradingView a GitHub Actions data source.

## Data flow

1. Request 1D OHLCV bars from the connected official TradingView MCP for the 17 supported fields.
2. For each field, put the numeric bar close, exact TradingView symbol, unit, market type, session key, interval, source bar anchor (UTC), and that market's own source date in an input JSON file.
3. Run `scripts/import_tradingview_mcp_candidates.py` to validate the 17-field batch and normalize its metadata.
4. To test persistence, run with `--write-test-sheet`. The tool requires `MARKET_DATA_TEST_SPREADSHEET_ID` and `GOOGLE_SERVICE_ACCOUNT_JSON`, rejects an ID that matches `MARKET_DATA_SPREADSHEET_ID`, and appends only to the `TradingView_MCP_Candidates` tab. It never clears the tab or touches the production sheet.
5. Readback checks the row identity and every cell. Stable snapshot IDs make a repeat import append zero duplicate rows.

Example:

```powershell
python scripts/import_tradingview_mcp_candidates.py `
  --input .codex-temp-market/tradingview-mcp-input.json `
  --output .codex-temp-market/tradingview-mcp-normalized.json `
  --write-test-sheet
```

## Validation boundary

The adapter requires all 17 IDs exactly once; rejects unexpected symbols, units, market types, sessions, non-daily bars, nonfinite values, timezone-free timestamps, and future dates; and preserves each market's own date and exact UTC bar anchor. It labels every output `CANDIDATE_CLOSE_AND_SESSION_REVIEW_REQUIRED`. Passing the schema checks does not establish that a 1D bar close matches the report's cash close, settlement, reference time, or exchange session. The candidate must not be promoted to a verified report value until that per-market check is completed.

Current scope is manual MCP read → normalization → private test-sheet append/readback. The script makes no network calls to TradingView, does not run in Actions, and does not update public GitHub data, production Sheets, reports, or dashboard JSON. A separate explicit implementation is needed before any public display or unattended schedule is considered.

## Supported candidates

US cash indices (Dow, Nasdaq Composite, S&P 500, Russell 2000), Nikkei 225 cash, COMEX gold and NYMEX WTI continuous futures, OSE Nikkei 225 front futures, CME yen- and dollar-denominated Nikkei futures, USD/JPY, EUR/USD, Bitstamp BTC/USD, CBOE VIX, TOCOM:NVI, and TradingView JP/US 10-year yield series.

The output records market type, symbol, currency/unit, session key, retrieval time, bar anchor, and market date separately. In particular, a CME/COMEX/NYMEX continuous contract is not an identified dated delivery month, an FX 1D candle is not automatically a universal close, BTC is a single venue, and TradingView yield series are source-specific. These fields remain candidates until their report-specific definitions are confirmed.
