# Free official market data alternatives and current evidence

Review date: 2026-10-12  
PR: #94, branch `codex/market-data-completeness-recovery`  
Scope: the 28 required report fields (18 existing fields plus 10 fields without a connected route).

## Use scopes

- **Personal private Google Sheets:** one account holder's private analysis. A source plan must permit API retrieval and retention for this use.
- **Public GitHub storage:** committing prices, histories, or generated market snapshots makes source data publicly downloadable. This is a separate redistribution/storage use.
- **Public report/dashboard:** showing source values to other people is public display/redistribution. An API key or free web page alone does not grant this right.
- Candidate/reference observations stay out of the normal dashboard collector unless their definition, retention, and display rights are all verified. Live validator logs contain dates/status but not market values or secret values.

## 28-field source and acceptance matrix

| # | Required field | Existing path / official free alternative checked | Live acquisition / validation | Sheets | Current decision / open requirement |
|---:|---|---|---|---|---|
| 1 | NY Dow | Existing Yahoo route. FRED DJIA history exists but carries index-owner restrictions. S&P DJI direct index API is subscription-based. | Existing route NOT_RUN; no rights-cleared alternative tested. | NOT_RUN | Connected in config; no confirmed public-retention/display license. |
| 2 | NASDAQ Composite | Existing Yahoo route. Nasdaq's official COMP page publishes a latest close; automation directs users to its secured web service/data products. | Existing route NOT_RUN; no authorized automated feed tested. | NOT_RUN | Connected in config; web display does not establish automated download permission. |
| 3 | S&P 500 | Existing Yahoo route. FRED series exists but S&P DJI index rights remain; S&P DJI EOD API requires a Data Services account/subscription. | Existing route NOT_RUN; no rights-cleared alternative tested. | NOT_RUN | Connected in config; need index data/display entitlement for public output. |
| 4 | Russell 2000 | Existing Yahoo route. FTSE Russell owns/licences the index; no free automated series with suitable retention/display rights confirmed. | Existing route NOT_RUN. | NOT_RUN | Connected in config; no compliant free replacement confirmed. |
| 5 | Nikkei 225 cash | Existing Yahoo route. Official Nikkei history/API paths require the appropriate data-use scope. FMP index history was considered but not used: its terms prohibit copying/downloading without prior written approval, and public display requires a separate agreement. | Existing route NOT_RUN. | NOT_RUN | Connected in config; exact Nikkei close remains without a confirmed automated, publishable free feed. |
| 6 | Gold | Existing Yahoo GC futures and Stooq XAU/USD fallback represent different instruments. LBMA benchmark access is distributed under licensing; no suitable free GC futures feed confirmed. | Existing routes NOT_RUN. | NOT_RUN | Connected in config; do not replace futures with spot gold. |
| 7 | WTI crude | Existing CL continuous-futures routes. EIA's public RWTC series is daily Cushing WTI spot, not NYMEX front-month futures; EIA also cautions that some web materials are third-party protected. | EIA value not requested; it is not an equivalent item. | NOT_RUN | Connected in config; do not substitute spot for futures. |
| 8 | OSE Nikkei 225 futures | Existing JPX delayed quote/profile routes. J-Quants Free does not include futures; JPX index/futures data are in paid plans/products. | Existing route NOT_RUN. | NOT_RUN | Connected in config; no free authorized automated OSE quote path confirmed. |
| 9 | USD/JPY | Existing Yahoo/Stooq routes have unresolved automated-use scope. Official BOJ FM08/FXERD04 publishes a Tokyo 17:00 daily reference observation. | PASS in Actions run #119: date 2026-10-07 17:00 JST, source/date/finiteness/direction checks OK. Reference-only; not a continuous FX close. | NOT_RUN | Supplemental official reference route; not counted as a report-compatible close until the report definition is aligned. |
| 10 | EUR/USD | Existing Yahoo/Stooq routes have unresolved automated-use scope. ECB publishes daily USD-per-EUR reference values, normally around 16:00 CET, for information. | PASS in Actions run #119: date 2026-10-09, source/date/finiteness/direction checks OK. Reference-only. | NOT_RUN | Supplemental official reference route; not a continuous FX close. |
| 11 | BTC/USD | Existing Yahoo/Stooq routes have unresolved scope. Kraken public OHLC offers an individual exchange's daily UTC candle; its terms distinguish personal use from other use. | PASS in Actions run #119: completed candle 2026-10-10 UTC, source/date/finiteness/direction checks OK. Reference-only. | NOT_RUN | Single-venue close, not a global composite; private use and any public display/storage need the applicable Kraken permission. |
| 12 | VIX | Existing Cboe historical CSV/Yahoo routes. Cboe publishes VIX history and delayed quote pages, but a periodic automated archive/storage right was not confirmed. FRED is not a clean rights-cleared substitute. | Existing routes NOT_RUN. | NOT_RUN | Connected in config; no verified free automated retention/display route. |
| 13 | Nikkei VI | Existing Nikkei Profile route. Same official index data licensing boundary applies. | Existing route NOT_RUN. | NOT_RUN | Connected in config; no confirmed free automated public-use route. |
| 14 | CNN Fear & Greed | Existing CNN graph-data endpoint; no official public automated API/reuse grant confirmed. | Existing route NOT_RUN. | NOT_RUN | Connected in config; no substitute. |
| 15 | Japan 10-year yield | Existing local rates snapshot. Official MOF daily 10-year constant-maturity CSV is based on secondary-market prices at 15:00 JST and published next business day from about 09:30; MOF PDL 1.0 permits reuse with attribution. | PASS in Actions run #119: market date 2026-10-08, source/date/finiteness/direction checks OK. Reference-only because timestamp and existing report series alignment have not been accepted. | NOT_RUN | Supplemental official route; adding visible attribution and slot-specific stale-date rules is required before public collector use. |
| 16 | U.S. 10-year yield | Official U.S. Treasury daily par-yield curve XML, 10-year field. FRED DGS10 remains a secondary fallback with its own key and series-use terms. | Official Treasury route had a successful hosted validation and real test-sheet readback in run #80 (one item); not rerun in #119 because the user asked to avoid repeating it. | PASS, dedicated test sheet only, run #80 | One test-sheet item is saved/read back; production sheet and public dashboard were not written in this work. |
| 17 | Nikkei 225 25-day deviation | Existing Yahoo daily-history calculation route. Needs 25 authorized Nikkei cash closes under the same calendar/close definition. | Existing route NOT_RUN. | NOT_RUN | Connected in config; no authorized free history route confirmed. |
| 18 | Nikkei 225 200-day deviation | Existing Yahoo daily-history calculation route. Needs at least 200 valid, date-aligned Nikkei cash closes under the same definition. | Existing route NOT_RUN. | NOT_RUN | Connected in config; no authorized free history route confirmed. |
| 19 | CME Nikkei yen futures | CME official delayed market-data access is available through licensed products/distributors; no free public automated retention grant found. Yahoo contracts are individual delayed expiries, not an authorized CME API. | Unconnected / NOT_RUN. | NOT_RUN | No accepted free automated path. |
| 20 | CME Nikkei USD futures | Same CME market-data entitlement boundary as the yen contract; keep contract/expiry distinct. | Unconnected / NOT_RUN. | NOT_RUN | No accepted free automated path. |
| 21 | Nikkei 225 PER | Nikkei Profile provides daily aggregate PER history/CSV, but automated retrieval and redistribution for this task are not confirmed. | Unconnected / NOT_RUN. | NOT_RUN | Need Nikkei authorization for the intended storage/display scope and confirm the existing PER basis. |
| 22 | Nikkei 225 PBR | Official history provides multiple bases (weighted average vs index basis); the displayed rounded values cannot be mixed. | Unconnected / NOT_RUN. | NOT_RUN | Need rights and exact basis mapping. |
| 23 | Nikkei 225 EPS | No exact free official daily EPS feed confirmed. Inferring EPS from a rounded PER and close is not an exact source value; any same-definition calculation must be cross-checked against a published forecast EPS. | Unconnected / NOT_RUN. | NOT_RUN | Need a licensed same-definition close/PER/EPS source or formally permitted published series. |
| 24 | TSE Prime turnover value | JPX daily market report/statistics are the official aggregate candidate. The report is a PDF in the reviewed download path; the free J-Quants plan supplies constituent stock OHLC, not this aggregate. | Unconnected / NOT_RUN. | NOT_RUN | No free automated aggregate feed with reuse rights confirmed; do not silently compute/label constituent sum as JPX aggregate. |
| 25 | TSE Prime trading volume | Same JPX aggregate statistics route; individual stock volume is not the aggregate source requested. | Unconnected / NOT_RUN. | NOT_RUN | No accepted free automated aggregate feed. |
| 26 | TSE Prime advancers | JPX aggregate count is distinct from a vendor's market-wide breadth series or a partial constituent universe. | Unconnected / NOT_RUN. | NOT_RUN | No accepted free automated aggregate feed. |
| 27 | TSE Prime decliners | Same market-segment aggregate constraint as advancers. | Unconnected / NOT_RUN. | NOT_RUN | No accepted free automated aggregate feed. |
| 28 | TSE Prime 25-day breadth ratio | Must be calculated from 25 Japanese business days of Prime-only advancer/decliner counts. Do not substitute another market's ratio or a precomputed mixed-market series. | Unconnected / NOT_RUN. | NOT_RUN | No accepted daily Prime count history source; the outstanding historical 8 turnover/volume cells remain unfilled. |

## Free-source checks and limits

- FMP advertises a $0 Basic plan with 250 calls/day and end-of-day history. Its published Terms of Service allow only an individual’s own personal, non-business, non-commercial use; they prohibit copying or downloading data without prior written approval, and a separate agreement is required for multi-user display. Therefore no FMP data was requested, written to Sheets, committed, or displayed. A credentialed Actions dispatch was not added.
- The official EIA API is free but requires registration; its bulk download needs no API key and is updated twice daily. EIA's reuse policy generally permits distribution of EIA information with attribution, subject to protected third-party materials. The RWTC series is Cushing WTI spot (not the report's CL continuous future), so it cannot raise the WTI futures connection count.
- JPX states the J-Quants Free plan offers two years of daily stock OHLC with a 12-week delay; index OHLC is not included in Free, and other market-specific index/derivative datasets require paid tiers. This does not provide same-day index prices or the official Prime aggregate statistics required here.
- Nasdaq's COMP page publishes a value/date, but the official index-data page directs automated retrieval to a secured web service and data delivery products. S&P DJI's official historical API requires a Data Services account and authenticated subscription. A free public page is not an automated-use license.
- CNN Fear & Greed and CoinMarketCap Crypto Fear & Greed remain separate indicators. No CMC endpoint was used to populate CNN Fear & Greed.

## Actions and counts

- Current PR head at validation: `bf7f25143214bce30682613c90d8cf023908bc51`; PR #94 remained OPEN/DRAFT/unmerged.
- Actions run #119 (`38159134573`) succeeded on that head. The official MOF, BOJ, ECB, and Kraken source-only probes all reported verified; public logs omitted values. These are four reference observations, not four accepted report-field substitutions.
- The selected adapter regression suite passed 8/8. The Treasury, normal update, test-sheet, and Treasury-sheet jobs were skipped in #119. No Sheets save occurred in #119.
- **Existing configured report paths:** 18/28 (64.3%). **Unconnected report fields:** 10/28.
- **Live exact report-item acquisition proven:** 1/28 (US 10-year Treasury route, prior run #80); four additional current reference observations are explicitly excluded from the exact report-item count.
- **Dedicated test-sheet save/readback proven:** 1/28 (US 10-year Treasury, run #80). **Production sheet writes in run #119:** 0.
- Existing JPX Prime historical repair remains 5/13 known blanks filled; eight turnover/volume cells remain blank. No cells or sheet formatting were changed.
- A proposed workflow edit that would send the repository's FMP API secret to FMP was rejected by the automatic approval reviewer because the account plan and permission for credentialed automated use/retention had not been established. The rejected workflow edit was not applied; no FMP API request or secret disclosure occurred. This path remains pending written FMP permission and an explicit authorized test scope.
- PR #94 remains OPEN/DRAFT and unmerged. Do not promote references or merge until the exact report definitions, rights scope, and all required source/storage checks pass.


## TradingView official MCP assessment (2026-10-12)

- Official MCP endpoint: `https://mcp.tradingview.com/mcp`; OAuth 2.1, paid Essential-or-higher plan. Official docs describe quote/price history, fundamentals, screeners, and economic series. Beta data may be delayed and request limits may apply.
- The available read-only MCP returned a numeric daily bar for 17 of the 28 requested fields in this one-time manual inspection. These observations are not accepted as PR acquisition routes and were not written to this repository, Sheets, Actions artifacts, or dashboards. The report's raw values are intentionally absent from this public record.
- Numeric bars were manually available for the Dow, Nasdaq Composite, S&P 500, Russell 2000, Nikkei 225 cash index, COMEX gold continuous futures, NYMEX WTI continuous futures, OSE Nikkei futures, CME yen- and USD-denominated Nikkei futures, USD/JPY, EUR/USD, Bitstamp BTC/USD, CBOE VIX, TOCOM Nikkei VI-labelled index, and TradingView JP/US 10-year yield series. Exact timestamp/close convention or source identity is not established for FX daily bars, several derivatives, rates, and the Nikkei VI-labelled route; BTC/USD is a single-exchange Bitstamp spot series. These are candidate observations only.
- CNN Fear & Greed had no matching index symbol. A crypto token named FEAR is not CNN's index and was not substituted.
- `get_financials(TVC:NI225)` returned null for index EPS, P/E, and P/B. It provides issuer-level fundamentals; no Nikkei 225 aggregate valuation series was established. The official valuation columns are stock-level.
- Daily OHLC history is available for the Nikkei index, and the technicals tool exposes SMA200 but not SMA25 or either requested deviation rate. No derived deviation was computed or connected.
- The Japan stock screener exposes per-stock traded value and volume. Its available column catalog has no Prime-wide daily advance/decline count or breadth ratio. A screened or summed constituent set is not accepted as the official Prime market aggregate.
- TradingView's Japanese Terms of Use distinguish display-only personal/internal use from non-display machine processing and redistribution. A private Google Sheet viewed only by this user is a personal-display candidate and should be assessed separately from public GitHub storage or a public dashboard. The terms do not clearly resolve automated historical retention or an Actions-to-Sheets write; because they prohibit non-display machine processing, this automated path remains uncertain and disabled pending clarification from TradingView. Public GitHub storage and public raw-data display are separate redistribution uses and remain disabled. The narrow allowance for an attributed chart snapshot does not authorize raw-value redistribution.
- No source code or existing adapter was changed; no scheduled run, Sheets save/readback, GitHub market-data persistence, or public display was enabled. PR #94 remains OPEN/DRAFT/unmerged.

## TradingView MCP practical candidate pass (2026-10-12 JST)

- The user's updated direction is to use MCP-read values as private dashboard/Sheets candidates, while treating an unattended GitHub Actions collector and public distribution as separate scopes.
- A fresh official MCP 1D OHLCV batch returned numeric bars for all 17 candidate fields. The three initial quote-symbol misses were corrected by search (CBOEFTSE:RUT, TOCOM:NVI); historical daily bars for those symbols were available. This is not 17 accepted report-close validations: the MCP notice says the newest bar may still be forming, and close/session conventions differ.
- The candidate batch covers Dow, Nasdaq Composite, S&P 500, Russell 2000, Nikkei 225 cash, COMEX GC1!, NYMEX CL1!, OSE NK2251!, CME NIY1!/NKD1!, USDJPY, EURUSD, Bitstamp BTCUSD, CBOE VIX, TOCOM NVI, JP10Y and US10Y. The 17 values, source symbols, bar anchors, dates, units, and session tags were written only to a new TradingView_MCP_Candidates tab in the private test spreadsheet; no market values were committed to this public repository.
- Readback of A1:M18 confirmed 17 rows and the 13-column schema. A separate cell-metadata read confirmed numeric values remain numeric and the header formatting/frozen row is present. The existing test input/history/rules tabs were not targeted. This is a private candidate save/readback result; it does not alter the prior count of 1/28 exact report-compatible PR items.
- Added scripts/import_tradingview_mcp_candidates.py: manual MCP JSON → fixed symbol/unit/session contract → normalized candidate JSON → append-only private test tab. It requires exactly 17 fields and rejects mismatched instrument identity, units, sessions, non-1D bars, invalid/nonfinite values, timezone-free timestamps, duplicate fields, and future dates. It records market-specific dates and UTC bar anchors separately. It never calls TradingView, touches Actions, writes production Sheets, changes public market snapshots, or promotes a candidate to verified.
- Added regression tests and a private import guide. PR workflow runs the focused tests when these files change. The test outcomes are pending this PR update's Actions run.
- Current counts stay distinct: existing PR report paths 18/28; one-time MCP candidate bars 17/28; exact report-compatible live acquisition still 1/28 (Treasury); private candidate rows saved/read back 17/17; accepted close/session validations for these 17 candidates 0/17. No production writes and no public dashboard update.
- Market-date normalization is intentionally not inferred from a shared calendar date. Every row preserves the provider's UTC bar anchor and a field-specific date label; FX, futures, BTC, and yields still need close/session confirmation before report use. The BTC candidate used the prior completed UTC daily bar because the latest returned bar was still forming.
- PR #94 remains OPEN/DRAFT/unmerged. This manual bridge is the next practical candidate path; scheduled Actions and public display remain separate future outcomes.

## PR test result update (2026-10-12)

- Local bundled Python checks passed: 10/10 importer unit tests and bytecode compilation. GitHub Actions run #143 on the current PR head passed the dedicated candidate importer test/compile job. Its separate official MOF/BOJ/ECB/Kraken reference probes also passed, but they remain reference-only and are not counted as report-compatible TradingView fields.
- The date guard uses each field's market timezone, not one common UTC calendar date; one regression explicitly covers Tokyo local date while UTC is still on the prior date. Exact market close/settlement validation is still 0/17 for the candidates.
- The run skipped the market snapshot update and both Sheets jobs. The previously confirmed private candidate-tab write/readback remains 17/17; no second live write was attempted. Existing report route count and exact PR live count do not change.

## Source-date label correction and latest Actions result

- The private candidate tab labels its per-market field as Source Market Date, not as a report-verified close date. Japan 10-year yield source date is 2026-10-09 when its UTC bar anchor is converted to Asia/Tokyo; U.S. 10-year source date is 2026-10-08 in America/New_York. The UTC anchor is retained separately.
- Only the test tab's header K1 and Japan-yield date cell K17 changed; the 17 numeric values and all pre-existing test tabs were preserved.
- GitHub Actions run #148 (38161816314) passed importer compile and its focused 10-test suite, plus the separate official-reference validation job. The snapshot update and Sheets jobs were skipped. Close/session acceptance remains 0/17.


## TradingView close qualification (2026-10-12)

The 17 manually captured TradingView MCP daily candidates were reviewed using market-specific close rules. Promotion is field-specific: indexes require a same-date official index value at the publisher's stated precision; CME/OSE futures require a named contract and official settlement; FX uses a selected 17:00 America/New_York daily close; BITSTAMP BTC/USD uses a UTC daily candle ending at 00:00 UTC. The private candidate sheet records values, reference sources, dates, and per-field outcomes.

- VERIFIED: 4/17 — Nasdaq Composite matches Nasdaq Global Index Watch at its published precision for 2026-10-09; USD/JPY and EUR/USD daily bars match the final hourly close at the selected New York 17:00 boundary and are dated by the close date; BITSTAMP BTC/USD daily candle matches the last hourly close at the UTC boundary while keeping the UTC candle date. This establishes report-close semantics for the selected series, not equivalence to the separate BOJ/ECB fixings.
- Not verified: 13/17. The Nikkei 225 candidate differs from the official Nikkei daily summary; Nikkei VI differs from the official VI profile. Dow mismatches the published U.S. close reference, and that comparison is secondary rather than an official index feed. S&P 500 and Russell 2000 match secondary published closes but their official sponsor historical values were not independently read. Cboe's official VIX history is distributed as CSV, which the current web reader could not parse. Treasury candidates remain unverified against the same official yield series/date.
- Futures remain unverified. OSE, COMEX, NYMEX and CME values are continuous 1! series. They cannot establish a named-contract settlement. CME lists quarterly contracts, NIY also has serial months, and the customary Nikkei roll occurs on the Monday before the second Friday expiration; for the October 9, 2026 observation, December 2026 is the relevant quarterly lead after September expiration. A named-contract settlement comparison is still required.
- Added a conservative verifier that only promotes an official Nasdaq exact-close comparison, a 17:00 NY FX boundary cross-check, a same-exchange UTC BTC boundary cross-check, or a named-contract official settlement match. Continuous futures are explicitly rejected. Automation and public data publication remain disabled.
- Test-only sheet readback confirms all 17 candidate rows remain present and uniquely keyed; 4 statuses are VERIFIED, 2 are CONFLICT, 1 has a secondary-reference mismatch, and the remaining 10 lack qualifying evidence. No production spreadsheet, dashboard data, or close list was written.
- GitHub Actions run #155 (38163586492) passed the verifier compile/tests and the existing official reference validation. Run #157 is pending after the BTC boundary rule update; no automatic market collection or Sheets writes are included. PR #94 remains OPEN/DRAFT/unmerged.

Primary references: [Nasdaq Global Index Watch](https://indexes.nasdaqomx.com/Index/Overview/comp), [Nikkei 225 daily summary](https://indexes.nikkei.co.jp/nkave/archives/summary?dt=20261009&idx=nk225), [Nikkei VI profile](https://indexes.nikkei.co.jp/nkave/index/profile?idx=nk225vi), [CME roll dates](https://www.cmegroup.com/trading/equity-index/rolldates.html), [CME Nikkei yen contract settlements/specifications](https://www.cmegroup.com/ja/markets/equities/international-indices/nikkei-225-yen.settlements.html), [Bitstamp public OHLC API](https://www.bitstamp.net/api/), and [Cboe VIX historical data](https://www.cboe.com/tradable_products/vix/vix_historical_data).


### Official S&P 500 close added

Follow-up official-source review found the S&P 500 level and timestamp on S&P Dow Jones Indices' page, showing the 2026-10-09 cash close at its published precision. The TradingView candidate matches at two decimals and is now VERIFIED. The current candidate qualification is therefore 5/17: Nasdaq Composite, S&P 500, USD/JPY at 17:00 New York, EUR/USD at 17:00 New York, and BITSTAMP BTC/USD at the UTC daily boundary. The other 12 remain unresolved: two official Nikkei conflicts, one Dow secondary-reference mismatch, one secondary-only Russell 2000 match, five continuous futures without named settlements, VIX without parsed official history, and two yields without matching official series proof.



### Timestamp-boundary verifier regression sweep

The close verifier now rejects an index bar unless its bar timestamp is 09:30 America/New_York, an FX daily bar unless the start and end are exactly 17:00 America/New_York, and a Bitcoin daily bar unless the candle starts and ends at 00:00 UTC. Its regression suite also rejects an official-source mismatch, wrong FX timezone boundary, and continuous futures presented without named-contract settlement evidence. GitHub Actions run #169 (38164034694) passed compilation, candidate/close-verifier suites, and existing official reference validation. Snapshot update and both Sheets jobs were skipped. Candidate count remains 5/17 VERIFIED; production sheet and public snapshot were not changed.


## TradingView category-page review and 2026-10-09 close checks (2026-10-12)

The supplied Japan economy, U.S. stocks/futures, cryptocurrency, futures, and bond market pages are useful discovery surfaces, but their live tables do not by themselves establish a report-grade historical close. Index breadth on a general market page is not the TSE Prime-only advance/decline universe; current government-yield tables are not a historical, same-time CMT series; and continuous futures pages do not expose a guarantee that the displayed bar close is the exchange settlement. Candidate validation therefore stayed contract-, venue-, date-, timezone-, and definition-specific.

- Dow: DJ:DJI is the matching TradingView provider symbol; 2026-10-09 matched the AP secondary cash-close report at published two-decimal precision. TVC:DJI mismatched. The official S&P DJI daily XLS link was found but not readable, so keep the secondary evidence label.
- Russell 2000: CBOEFTSE:RUT matched AP on 2026-10-09 at two decimals. LSEG's downloadable index-value path is available, but the exact official daily file was not read; this remains a secondary-source check.
- VIX: CBOE:VIX matched Yahoo Finance and ChartExchange daily history on 2026-10-09. Cboe confirms its official download contains daily closes, but its download redirect could not be read in this run. Do not claim direct Cboe-file validation.
- Nikkei 225 cash: TVC:NI225 conflicts with the Nikkei official close on 2026-10-09. The Vantage alternative resolves to a CFD, not cash index.
- Nikkei VI: TOCOM:NVI identifies as “NIKKEI 225 VI TRADE INDEX,” a distinct futures-traded VI instrument; it is not Nikkei's OSE-options-derived Nikkei Stock Average Volatility Index. It conflicts with the official index and cannot be substituted.
- Futures: Continuous-vs-named OHLC daily-bar matches were found for COMEX GC1!/GCZ2026 (Dec-2026), NYMEX CL1!/CLX2026 (Nov-2026 front contract; Dec CLZ2026 differs), OSE NK2251!/NK225Z2026 (Dec-2026), CME NIY1!/NIYZ2026 (Dec-2026), and CME NKD1!/NKDZ2026 (Dec-2026). These comparisons help establish contract identity but are not official settlement comparisons. CME/JPX daily settlement rows have not been parsed/read back; all five stay pending. CME lists quarterly equity-index cycles and NIY serial months; use the exchange's contract listing/roll schedule to determine the instrument, never infer settlement from a continuous close.
- Yields: Treasury 10-year CMT is defined from indicative bid quotes near 15:30 ET and is dated 2026-10-09; TradingView TVC:US10Y is a separate LSEG series/date boundary, so precision rounding alone cannot establish equivalence. MOF's latest then-published JGB curve was dated 2026-10-08; no same-date Oct 9 comparison was available.
- FX and BTC are market-boundary checks inside TradingView: FX daily bars align to their final hourly bar at 17:00 New York; BITSTAMP BTC/USD aligns at 00:00 UTC. Separate BOJ, ECB and Kraken Actions validators passed date/source validation in run #175, but candidate numeric values were not compared against these independent series. They remain VERIFIED only under the TradingView feed-specific close convention, not independent-source validation.

Primary/secondary evidence links: [Nikkei 225 official daily summary](https://indexes.nikkei.co.jp/nkave/archives/summary?dt=20261009&idx=nk225), [Nikkei VI profile](https://indexes.nikkei.co.jp/en/nkave/index/profile?cid=7&idx=nk225vi), [AP daily market close](https://apnews.com/article/wall-street-stocks-dow-nasdaq-dafbd0c4037ee10e2a9e305f3cfa8e70), [Cboe VIX historical data](https://www.cboe.com/tradable-products/vix/vix-historical-data), [Treasury daily yield curve](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value_month=202610&type=daily_treasury_yield_curve), [MOF JGB rates](https://www.mof.go.jp/jgbs/reference/interest_rate/index.htm), [CME Gold settlements](https://www.cmegroup.com/markets/metals/precious/gold.settlements.html), [CME WTI settlements](https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.settlements.html), and [JPX/OSE daily derivatives reports](https://www.jpx.co.jp/markets/statistics-derivatives/daily/index.html).

Final candidate review state in the private test tab: VERIFIED 8/17, CONFLICT 2/17, PENDING 7/17. The five futures remain pending until official named-contract settlements are confirmed. Production spreadsheet and public dashboard were not changed.


### JPX/OSE daily settlement-file clarification (2026-10-12)

JPX's official “Settlement Prices for Futures and Options” page confirms a combined CSV file for OSE and TOCOM listed products, with the latest publication timestamp shown as 2026-10-09 on the inspected page. The planned publication is around 16:45 JST each business day, but JPX warns that release may be delayed or canceled; holiday-trading data is not included. This is the correct official source family for checking the OSE Nikkei named-contract settlement. The reader exposed the explanatory PDF link but not the dynamic CSV download or its row contents, so NK225Z2026 settlement for 2026-10-09 is still unverified and remains PENDING. JPX describes these figures as investment-reference information; the page does not itself grant a clear machine-retention or redistribution license. No automated collector was enabled.


## TradingView Japan market breadth (2026-10-12)

TradingView's Japan market page exposes advancing/declining breadth. Its published definition says country-level breadth counts all listed stocks in the country: positive change is advancing; zero or negative change is declining. This differs from an exchange-segment-only Prime metric. The user's screenshot's 2.46K/1.41K labels are rounded display figures, not exact counts. [TradingView Japan market page](https://jp.tradingview.com/markets/japan/) · [Market-breadth methodology](https://www.tradingview.com/support/solutions/43000794825-market-breadth-advancing-and-declining/)

A read-only official TradingView MCP screener call returned exact totalCount values for Japan stocks (2,471 advancing; 1,432 declining) at approximately 2026-10-12 04:11 JST. The result did not include the underlying market-date, so it is not verified as a daily close. A screener attempt to restrict to “Tokyo Stock Exchange Prime Market Index” was rejected: that index is not supported in the MCP's index filter. Accordingly, these figures are supplemental Japan-wide breadth only. They do not fill the TSE Prime advancing/declining count fields, and no automation, report mapping, or sheet write was enabled.


## Official-source implementation follow-up — 2026-10-12

### Nikkei official index series

The 3-year daily CSV route remains technically connected for Nikkei 225 and Nikkei VI, with 25/200 deviations derived from the official Nikkei 225 close series. Nikkei's current license page clarifies that automatic machine processing for internal use requires contacting Nikkei and receiving permission under a license agreement. Thus the official series is a verified source definition but is not currently an authorized Actions automation path. The implementation now exposes a guarded, one-off private test-Sheets roundtrip; it requires source-automation and private-sheet confirmations, uses its own three test tabs, performs numeric/date readback and duplicate prevention, and cannot target the production close list. No Nikkei runtime values were acquired in run #206.

### TSE Daily Report

The official Daily Report guide says the report is posted on the first business day after a trading day. Estimated/Settled contains market-section statistics: Estimated is the current trading day, while Settled is for four business days earlier. The page lists daily report, stock quotation and bond quotation files. The browser-visible version uses a dynamic date selector and did not expose a stable direct file URL or enough metadata to establish CSV/Excel/PDF format for the specific report file. Prime market value/volume may be present in this official report family, but no parser, row-level Prime evidence, or automated-retention permission is established here. Daily report figures must be labeled Estimated or Settled; they are not silently interchangeable.

### Named futures settlement access

CME's official settlement overview defines daily settlements as values from the product's settlement period/close. It directs users to CME DataMine for access to daily/final settlement data and does not expose a documented free public bulk API on the overview. The existing continuous or named TradingView OHLC bars therefore remain references, not CME official settlements. An automated contract-specific settlement adapter is not claimed until a permitted machine-readable distribution is identified.

### CNN Fear & Greed

The commonly used CNN graphdata endpoint is an undocumented site endpoint found in independent client code and is subject to bot responses; it is not documented as a public API by CNN. It remains disabled for automated use. This is the CNN equity Fear & Greed series and cannot be replaced with the distinct CoinMarketCap Crypto Fear & Greed metric.

Primary source references: [Nikkei internal-use machine processing terms](https://indexes.nikkei.co.jp/nkave/license/non-display_usage.en.html), [JPX Daily Report](https://www.jpx.co.jp/markets/statistics-equities/daily/index.html), [JPX Daily Report guide](https://www.jpx.co.jp/english/markets/statistics-equities/daily/01.html), and [CME Daily Settlements](https://www.cmegroup.com/market-data/daily-settlements.html). The third-party CNN client is discovery evidence only: https://github.com/whit3rabbit/fear-greed-data/blob/main/scripts/fetch_cnn.py.

### Runtime boundary

Actions run #206 (38167365312) passed code guards and existing provider checks at PR commit 25cf3d94d8e9cc4a71fae88e5968fbe36ef34371; it did not invoke the Nikkei-only job or Sheets write jobs. PR remains OPEN/Draft/unmerged. No production sheet or public dashboard value was changed.
