# Market data source rights and acquisition route review

Review date: 2026-10-11
Scope: CME Nikkei 225 yen/USD futures, Nikkei 225 aggregate valuation, and TSE Prime market aggregate measures.
PR: #94, branch `codex/market-data-completeness-recovery`

## Usage scopes

- Private Google Sheets used by the account holder for personal analysis may fit a source's personal-use allowance, subject to that source's exact terms and API plan. This does not establish permission to upload the source data to GitHub.
- Committing values, histories, or generated CSV/JSON to this public GitHub repository is a separate storage and distribution use. The collect-only workflow therefore does not commit snapshots, build public dashboard files, or upload artifacts.
- Showing these values on the public dashboard or in a public report is third-party display/redistribution. Do not enable it without the relevant data owner's approval or an appropriate redistribution license.
- The collect-only workflow prints route status, source identifier, observation date, and error code, but no quote values.

## Findings by market

### CME Nikkei 225 futures (yen and USD)

CME's official Nikkei contract sheet lists USD futures in four quarterly months (March, June, September, December). Standard yen futures list 12 quarterly months plus three serial months; yen E-mini lists quarterly contracts. The standard USD contract expires at 4:15 p.m. Central Time on the business day before the second Friday; standard yen expires Thursday before the second Friday. Holiday rules can move the date. Thus a generic "next third Friday" calculation is not a safe contract selector. The exchange's live contract calendar / authorized quote feed should supply the listed contracts and last trade dates. A continuous series also needs a documented liquidity/roll rule; expiry calculation alone does not identify the liquid front contract.

CME's website market-data explanation permits personal, non-commercial viewing but prohibits scripted/data-mined collection and publication without permission. Do not automate the quote page. No CME Information License Agreement or permitted vendor feed is configured in the task. CME route status remains `BLOCKED_ENTITLEMENT`; do not substitute Yahoo chart scraping, CME webpage scraping, or an OSE quote.

Sources:
- CME Nikkei product contract sheet: https://www.cmegroup.com/trading/equity-index/files/nikkei-225-futures-and-options-fc.pdf
- CME market-data terms: https://www.cmegroup.com/trading/market-data-explanation-disclaimer.html
- CME licensed data products: https://www.cmegroup.com/market-data/license-data.html

### Nikkei 225 PER, PBR, EPS

The Nikkei official Historical Data and Daily Summary publish daily Nikkei 225 aggregate P/E and P/B, with both weighted-average and index-based series. The official pages offer two distinct aggregate bases: weighted-average and index-based series. Existing report/Sheets headers must be checked against their historical semantics before selecting either series; do not silently switch bases or substitute per-constituent values. The official guide defines index-weight EPS through the Nikkei 225 close and its P/E calculation, but the public archive displays P/E rounded to two decimals and does not directly publish EPS. Dividing by displayed P/E therefore gives an approximation and must not be labeled exact official EPS.

Nikkei says the public pages are available for personal use but copying/reproduction beyond personal use and dissemination to third parties require permission/license. This can be considered only for a private personal-analysis output after terms are confirmed; it does not authorize GitHub persistence or public dashboard display. The official archive is the preferred candidate for private Sheets. A live adapter must verify that the requested Japan session date appears in the exact row and retain the basis/definition in metadata.

Sources:
- Historical Data / daily valuation measures: https://indexes.nikkei.co.jp/en/nkave/archives/data?list=per
- Daily Summary: https://indexes.nikkei.co.jp/nkave/archives/summary?dt=20261009&idx=nk225
- Provision and use scope: https://indexes.nikkei.co.jp/nkave/data/index.en.html
- Index license/display process: https://indexes.nikkei.co.jp/nkave/license/display_usage.en.html

### TSE Prime turnover, volume, advances, declines, and advance/decline ratio

JPX's Equities Market Summary is the official source that presents market-segment trading volume/value and advancing/declining counts. JPX's user guide states that daily report content is made available the first business day after the trading day and distinguishes market-section totals from issue-level rows. However, the market-summary terms restrict use to personal viewing and prohibit processing, accumulation, reuse, reproduction, and redistribution outside the viewing device. The daily report is a plausible official source for validation and historical analysis, but its availability on the web is not itself authorization for automated extraction or downstream storage.

J-Quants API is an official individual-investor API, with a free tier that is delayed and personal use only. Its Stock Prices data are by issue; its docs do not establish that a free account provides the official Prime aggregate breadth/time series needed here. Summing issue-level values is a separate derived methodology and must not be described as the official JPX aggregate. The paid JPX data products expose official machine-readable datasets under usage scopes/contracts, including redistribution tiers; no such entitlement is configured. No values are to be inferred from price-only records, nor may a historical gap be filled from a different market segment.

Sources:
- JPX Equities Market Summary and its data-use restrictions: https://www.jpx.co.jp/english/markets/equities/summary/index.html
- JPX Daily Report and publication timing/contents: https://www.jpx.co.jp/english/markets/statistics-equities/daily/01.html
- J-Quants API (individual use): https://www.jpx.co.jp/english/markets/other-data-services/j-quants-api/index.html
- J-Quants API plans (personal use and free-plan delay): https://jpx-jquants.com/dashboard/menu/
- JPX paid reference-data use scopes and contract requirement: https://www.jpx.co.jp/english/markets/paid-info-equities/reference/

## Existing automated sources reviewed

Yahoo's current terms prohibit automated collection without express prior permission. CME's quote pages also prohibit scripts/data mining. Existing code may still have routes referencing these providers, but code presence is not source authorization; these routes must not be counted as approved public redistribution paths. FRED/official government statistical series can be evaluated individually for the specific series and workflow; they are not substitutes for the restricted sources above.

- Yahoo Terms of Service: https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html?ncid=mbr_idnedulnk00000001
- CME market data terms above

## Implementation and validation status

- PR #94 adds a `validate-only` dispatch choice to the existing independent market-data workflow. In this mode the run performs acquisition and JSON validation only. It skips dashboard/CSV export building, Git commits/pushes, all Sheets sync steps and artifacts. It omits the quote-value summary and reports only status/source/date/error metadata.
- This code-level isolation is E0 until a hosted run verifies it. The workflow has not been dispatched because the current source configuration still contains automated Yahoo/Stooq/JPX/CME paths whose applicable data entitlements are unconfirmed, and the remaining ten required report routes are not connected.
- Current connected-route count remains 18/28 (64.3%). The missing ten are the two CME futures fields, Nikkei PER/PBR/EPS, and five Prime aggregate fields (turnover, volume, advances, declines, and 25-day ratio).
- No Sheets writes or historical backfills were performed by this review. Existing date rows and cells were not edited.
- Next step: provision/confirm entitlements and endpoint/account scope, then implement the private Sheets adapter for Nikkei/J-Quants if allowed and a CME authorized feed adapter. Keep public storage/display disabled until redistribution approval is established.


## Workflow guard added after entitlement response

The account-holder response to the access-rights question was “未契約・未確認” for CME, JPX and J-Quants. Therefore a network run against the current mixed-provider configuration is not yet authorized by confirmed source terms. The validate-only dispatch now has a source_automation_rights_confirmed checkbox defaulting to false; the workflow stops before its first market-data request unless the operator confirms permission for every provider the configured run can contact. This is an explicit operator attestation, not proof of rights. It does not expose quote values, and the existing output/commit/Sheets/artifact gates still apply. No GitHub Actions data run has been dispatched.

The check intentionally blocks the current run rather than silently treating public visibility as permission for automated collection. The 18 existing routes include providers with automated-collection restrictions or unconfirmed terms, and the ten missing routes still lack an authorized provider. A provider-specific allowlist and live Action run can follow once usage scope is established.

### Free Tokyo Metropolitan open-data substitute checked

Tokyo Metropolitan Government's Open Data API catalog provides a TSE Prime row for the Statistical Yearbook dataset under CC BY, with a direct CSV link. The reviewed dataset is the 2023 yearbook and its table is annual/aggregated; it cannot fill daily market-turnover, volume, advances/declines, or daily history cells. It is a lawful public substitute for the annual statistic it actually represents, not a proxy for the daily report fields. The official JPX real-time data page lists market-section total trading value/volume and rising/declining counts, but describes market data as paid and requires an information-provision/license agreement for direct/API access; its end-of-day data vendors also require their applicable license process.

- Tokyo Open Data API catalog (CC BY; 2023 Statistical Yearbook): https://spec.api.metro.tokyo.lg.jp/spec/t000003d2000001026-cd1457d223b130eeef3252b9da0c4f37-0?lang=en
- Source CSV: https://www.toukei.metro.tokyo.lg.jp/tnenkan/2023/tn23qv150701.csv
- JPX market data terms/routes: https://www.jpx.co.jp/english/markets/paid-info-equities/realtime/


## Follow-up source review requested on 2026-10-11

This follow-up reviewed the specified Yahoo Finance, Nikkei Profile, Invest Forest, JPX Daily Report, JPX Equities Market Summary, and Stock Market Data sources. “Visible without payment” is recorded separately from permission for automated access, retention, and onward display.

### Yahoo Finance CME contracts

The Yahoo quote pages resolve the requested symbols to individual CME-listed deferred contracts, not stable continuous-series aliases: the observed NIY=F and NKD=F pages currently label December 2026 contracts and show a December 11, 2026 settlement date. NIY is JPY-denominated and NKD is USD-denominated. This confirms the symbols exist and expose delayed quotes, but Yahoo's current terms expressly require prior permission for automated collection. The symbols therefore remain manual-view references only and are not enabled in the Actions collector. Contract selection still must use the actual CME listed-contract schedule and an explicit liquidity/roll rule; the fixed expiry approximation alone is insufficient.

- Yahoo NIY=F: https://finance.yahoo.com/quote/NIY%3DF/
- Yahoo NKD=F: https://finance.yahoo.com/quote/NKD%3DF/
- Yahoo Terms of Service, automated collection restriction: https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html?ncid=mbr_idnedulnk00000001

### Nikkei Profile valuation history and EPS

The official Nikkei Profile historical PER and PBR pages exist as separate daily archive views. The user guide says daily investment indicators such as PER update at about 19:00 JST on securities business days and identifies downloadable CSV/PDF material. It also prohibits distributing site CSV/PDF/printouts to third parties; this does not authorize public GitHub persistence or public dashboard display. The official page should be treated as a private-use candidate for manual download into the account holder's private analysis only until Nikkei confirms that unattended recurring retrieval by GitHub Actions and private Sheets storage are within the permitted scope. No automated adapter was enabled because the requested rights answer remains “未契約・未確認.”

The official series are not interchangeable: the 2026-10-09 page exposes PER 17.37 (weighted-average) and 22.87 (index basis), and PBR 1.90 (weighted-average) and 2.83 (index basis). Existing output semantics must determine which pair maps to the existing report fields. The archive rounds PER to two decimals and does not provide an exact EPS field in that series; the implementation must not publish close divided by the rounded PER as an exact official EPS.

For comparison only, the public Invest Forest PER chart displays a dated table with 2026-10-09 close 69,030.92, PER 17.37, PBR 1.90, and EPS 3,974.15. Recalculation corrects the earlier arithmetic: close / displayed EPS = 17.3699835, which rounds to 17.37, and close / displayed PER = 3,974.1462, which rounds to EPS 3,974.15. The displayed figures are consistent at their shown precision; the earlier note claiming a mismatch (17.3575 and EPS 3,971.29) was erroneous and is withdrawn. The located programmatic-extraction restriction is in a premium-service terms page; it does not by itself establish the terms applicable to this free PER page. No separate free-page automated-access license or public data API was identified. Keep Actions collection disabled pending the operator's written clarification for one daily automated request and private personal Google Sheets retention. This clarification would not cover GitHub storage or public dashboard/report redistribution, which require separate permissions.

- Nikkei PER archive: https://indexes.nikkei.co.jp/nkave/archives/data?list=per
- Nikkei PBR archive: https://indexes.nikkei.co.jp/nkave/archives/data?list=pbr
- Nikkei user guide (update schedule and third-party circulation): https://indexes.nikkei.co.jp/nkave/archives/file/users_guide_jp.pdf
- Invest Forest PER/PBR/EPS page: https://nikkeiyosoku.com/nikkeiper/
- Invest Forest programmatic-extraction restriction: https://pay.nikkeiyosoku.com/kiyaku/

### Tokyo Stock Exchange Daily Report and market-segment aggregates

JPX's Daily Report guide says the report is posted on the next business day and retained in the archive for the latest 12 months. It describes “概算・精算表” as product- and market-segment-level volume/value totals, and “相場表” as issue-level OHLC/volume. These are distinct data scopes. The public daily page exposes the report columns “概算・精算表 / 株式相場表 / 債券相場表”; the reviewed files/examples are PDFs. The page does not document daily CSV/Excel delivery for the report. JPX separately provides Excel and CSV on some other monthly or data-catalog products; these must not be presented as formats for this specific Daily Report. JPX site terms require permission for secondary use and redistribution, so neither PDF parsing nor daily page scraping is enabled for recurring collection. Manual viewing can identify source values but is not treated as a reusable data license.

JPX's Equities Market Summary is a separate official segment aggregate: its page shows Prime/Standard/Growth trading volume, trading value and advancing/declining/unchanged/unavailable counts, refreshes around 12:00 and 18:15 on weekdays, and exposes only the past five business days. Its disclaimer prohibits accumulation, editing, processing, and third-party provision without permission. It cannot be used as an automated free route or for the required 25-session historical numerator/denominator without that permission.

- Daily Report guide: https://www.jpx.co.jp/markets/statistics-equities/daily/01.html
- Daily Report listing: https://www.jpx.co.jp/markets/statistics-equities/daily/
- Equities Market Summary and display terms: https://www.jpx.co.jp/english/markets/equities/summary/index.html
- JPX Quick market-data disclaimer and update times: https://www.jpx.co.jp/quick-disclaimer/
- JPX site terms: https://www.jpx.co.jp/term-of-use/index.html

### Stock Market Data breadth pages

The requested site publishes Prime-market 5/25/75-session ratios and says they are calculated from JPX-published Prime advances/declines. Its visible historical ratio table covers only the recent rows, not a permissively licensed CSV/API of Prime daily raw counts. Its usage rules say it does not provide data and disallow copying/reproduction absent prior written permission. Thus it cannot be scraped to populate the raw advance/decline columns or used to reconstruct the user's ratio. The only acceptable calculation is the user's specified formula from Prime-only daily advancer/decliner counts over the latest 25 Japan trading sessions; market-wide or Nikkei-225 breadth is not a substitute.

- Prime breadth page: https://stock-marketdata.com/advance-decline-tse-prime-market
- Site terms: https://stock-marketdata.com/riyoukiyaku.html

### Free official J-Quants alternative and remaining limits

JPX's individual-investor J-Quants API free plan is an explicit programmatic-access path with stock OHLC, listed-issue information, and two years of history delayed by 12 weeks. This is a plausible private-analysis route for delayed historical backfill only, subject to account registration, its current plan terms, and a properly protected API credential. It is not live current-market verification. Its quote and security-master data are issue-level; calculating Prime segment totals or breadth from them would be a separately derived aggregate requiring a date-specific Prime universe, treatment of no-trade/unchanged issues, and comparison against JPX published totals. It must be labelled derived, not official JPX aggregate. The task has no configured J-Quants account credential, and the user response says access is not confirmed, so no J-Quants request was made.

- J-Quants plan and delay: https://jpx-jquants.com/dashboard/menu/
- J-Quants API overview: https://jpx-jquants.com/?lang=ja%2F


## Existing connected report routes: source-specific use scope

This matrix covers the 18 required report-item routes currently connected in `config/market_data_sources.json`. A code path is not an access license. “Private Sheets” is a personal-analysis store; “GitHub” includes committing data or leaving quote values in public Actions logs; “public display” includes the dashboard and public report. Permission in one column does not grant the other two.

| Provider / configured fields | Automated request | Private Google Sheets | Public GitHub storage / Actions logs | Public dashboard / report |
| --- | --- | --- | --- | --- |
| Yahoo Finance (`dow`, `nasdaq`, `sp500`, `russell2000`, `nikkei225_cash`, `gold`, `wti`, `usdjpy`, `eurusd`, `btcusd`, `vix`, `nikkei225_dev25`, `nikkei225_dev200`) | Yahoo Terms expressly require prior permission for automated collection. No permission is configured. | Not established by public visibility; permission needed before recurring collection. | Not authorized by the access terms; do not commit or log quote values. | No display/redistribution right established. |
| Stooq (`gold` spot fallback, `wti`, `usdjpy`, `eurusd`, `btcusd`) | No machine-readable license/terms establishing this collector's recurring automated access was located in the reviewed official pages. Status is UNKNOWN, not permission. | UNKNOWN pending provider terms. | UNKNOWN; do not persist publicly. | UNKNOWN; do not display. |
| JPX/OSE quote page (`nikkei225_futures_ose`) | Public delayed quote page is not an authorized API; applicable secondary-use terms and permissions remain unconfirmed. | UNKNOWN pending an approved feed/permission. | Not authorized by the current evidence. | Not authorized by the current evidence. |
| Nikkei Indexes (`nikkei225_futures_ose` reference-only, `nikkei_vi`) | Nikkei retains index rights and describes separate display/non-display licensing. No automated-access permission is configured. | Personal viewing is distinct from recurring retrieval and retention; automation scope remains UNKNOWN. | Not authorized by the current evidence. | Requires the appropriate index display approval/license. |
| Cboe (`vix` EOD source) | Cboe data policies govern access and storage; no Cboe feed entitlement is configured for this project. | Internal/personal use is not established by merely viewing the page or CSV. | No redistribution permission established. | No public redistribution permission established. |
| CNN (`fear_greed`) | Existing adapter uses a site-internal graph-data endpoint; no documented public API or automated-access grant was found. | UNKNOWN; do not infer permission from the page's public display. | No public persistence permission established. | No public display permission established. |
| U.S. Treasury (`us10y` primary) | The official XML feed documents programmatic GET retrieval. This is the only source-specific route in the current config that has an official machine-readable endpoint documented for this collector. | Candidate for the private sheet route, with date/source attribution retained. | Public retention/output rights were not independently established in this review; current collect-only mode does not persist it. | Confirm applicable Treasury terms and attribution before enabling output. |
| FRED / Board of Governors (`us10y` fallback) | The route now uses the documented `fred/series/observations` API and requires a registered `FRED_API_KEY`; the former graph-CSV endpoint was removed from this source definition. The DGS10 page identifies the Board of Governors as source and marks the series “Public Domain: Citation Requested”, while its graph banner also says data are copyrighted. FRED's API terms say series owners' restrictions still control and require source attribution. Preserve this ambiguity as a rights check, not a blanket restriction or public-use clearance. | FRED's API terms permit use of third-party-owned series for own personal use without contacting the source owner first; DGS10 is Board-sourced and tagged Public Domain, but its page also displays a copyright notice. Private Sheets can be considered for personal analysis with attribution after the user registers/accepts API terms; no live credential is configured. | Not cleared for this project's public commit/log use. | Not cleared for public report display by this review; required FRED attribution/notice and source-owner scope must be resolved. |
| Local `rates-bonds.json` (`jp10y`) | No provider request occurs in this adapter; it reuses a same-date confirmed local record. The record's underlying LSEG terms are not represented in its schema. | UNKNOWN until the upstream LSEG entitlement and scope are recorded. | The public repository copy is a separate storage/distribution use and is not cleared by this adapter. | Not cleared until LSEG source rights and report display scope are verified. |
| CoinMarketCap (`crypto_fear_greed`, optional / not required) | Existing code path is not an established licensed production API route. The personal API terms limit storage to caching and restrict third-party availability. | Long-term sheet history is not established as permitted; this optional metric is not part of the 18 required items. | Not authorized by the reviewed personal terms. | Not authorized by the reviewed personal terms. |

Primary terms reviewed for the new matrix:
- Yahoo Terms of Service (automated collection requires express prior permission): https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html
- CME Market Data Terms (applies to the two open CME futures routes): https://www.cmegroup.com/trading/market-data-explanation-disclaimer.html
- Cboe Market Data Services document library and policies: https://www.cboe.com/data/market-data-services/document-library
- FRED legal notices / service and API terms: https://fred.stlouisfed.org/legal/
- FRED DGS10 series page (source attribution and copyright notice): https://fred.stlouisfed.org/series/DGS10
- FRED observations API documentation (JSON response formats and registered key): https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- FRED API terms (API key and third-party series restrictions): https://fred.stlouisfed.org/docs/api/terms_of_use.html
- CoinMarketCap personal API terms: https://pro.coinmarketcap.com/user-agreement-personal/
- Nikkei Indexes profile and license / index-data sections: https://indexes.nikkei.co.jp/en/nkave/index/profile?cid=3&idx=nk225vi
- U.S. Treasury XML feed documentation: https://home.treasury.gov/treasury-daily-interest-rate-xml-feed

### Run #46: incomplete diagnostic payload

The preserved evidence identifies `nikkei225_cash` as unavailable with a stale-data validation result and reports two fallback items. After the run's job-log endpoint began returning 404, neither the fallback item IDs nor their per-source error codes could be re-read from GitHub. No artifacts were listed for run #46. They remain UNKNOWN; do not assign a provider failure cause to either item. The acquisition code shows fallback is used when no current candidate passes validation or same-market source comparison detects excessive divergence, but that code path alone does not prove which condition occurred for those two symbols.

The collect-only workflow summary is being expanded to emit each item's fallback flag and source/error-code pairs while omitting quote values. This will make the next rights-authorized validation diagnostic without publishing numeric data. The PR's repository/dashboard writer continues to require separate downstream-use approval; automated-collection confirmation alone is not that approval.

### Method for the ten open fields

1. CME Yen Nikkei futures: individual NIY=F deferred contract quote; automated use blocked by Yahoo terms. Realistic automated alternative: authorized CME/vendor feed; otherwise manual observation.
2. CME USD Nikkei futures: individual NKD=F deferred contract quote; same block and alternative as above.
3. Nikkei PER: official Nikkei daily PER archive, preserve weighted-average vs index-basis series; automated retrieval awaits Nikkei written scope confirmation.
4. Nikkei PBR: official Nikkei daily PBR archive, preserve weighted-average vs index-basis series; same gate.
5. Nikkei expected EPS: no exact free official EPS series was established. If Invest Forest provides written permission for the free page, its dated EPS field is a candidate; the displayed 2026-10-09 close/PER/EPS values are consistent at shown precision, but a production adapter must independently enforce same-session and definition checks.
6. Prime trading value: JPX Daily Report market-segment “概算” total is the closest public source, next-business-day PDF; automated reuse blocked by JPX terms. Equities Market Summary has the current aggregate but the same downstream-processing restriction.
7. Prime trading volume: same route and restriction as #6.
8. Prime advancers: JPX Equities Market Summary Prime row provides the visible daily aggregate; automated storage/processing blocked. Historical raw series requires JPX permission or a validated licensed/API source.
9. Prime decliners: same route and restriction as #8.
10. Prime 25-session ratio: calculate 100 × sum(Prime-only advancers for the latest 25 Japan sessions) / sum(Prime-only decliners for those same sessions). No authorized free raw-count series was established; third-party published ratios cannot replace the input series.

### Implementation and run status after this review

No acquisition adapter or source definition was added for these ten fields: every examined current quote/data page either expressly restricts automated collection/processing, requires an unconfirmed account/entitlement, or only exposes delayed/derived values. Adding a scraper under a “free” label would violate the source-rights constraint. The existing rights-confirmation checkbox remains false by default. GitHub Actions live collection and date validation were not run because the existing mixed-source workflow would contact sources whose automated rights are unconfirmed, and this GitHub connector has no workflow_dispatch operation. The user explicitly asked to keep the PR Draft; it remains OPEN/DRAFT. Google Sheets write/readback and historical backfill are unchanged and NOT_RUN.


## Clarification follow-up: free Invest Forest page vs premium terms (2026-10-11)

The user clarified that the cited automatic-extraction restriction is from a premium-member agreement and may not determine the terms for the free public PER chart. The free page was directly inspected at https://nikkeiyosoku.com/nikkeiper/ and displays a dated daily table, including 2026-10-09 close 69,030.92, PER 17.37, PBR 1.90 and EPS 3,974.15; its displayed history covers roughly two months. The free page is therefore a useful data candidate for all three Nikkei valuation fields, subject to permission and methodology validation.

The previous calculation in this document was wrong. Using the displayed figures: 69,030.92 / 3,974.15 = 17.3699835 (rounds to 17.37); 69,030.92 / 17.37 = 3,974.1462 (rounds to 3,974.15). The page's displayed PER and EPS are consistent to their displayed precision. This corrects and withdraws the prior claim that the values failed that check. It does not prove the provider's underlying definitions or source inputs.

The accessible premium terms expressly cover their paid service and prohibit programmatic extraction, accumulation/use of data, and publication of obtained data. That text alone does not settle what terms govern the free public chart. No separate free-page license permitting unattended daily requests was found. Therefore the current status is RIGHTS_SCOPE_UNCONFIRMED, not “free-page automation prohibited.” Do not dispatch an automated request against the page until the operator clarifies permission.

The permission request should be limited and explicit: (a) one automated request per Japan trading day from GitHub Actions for personal market analysis, (b) storage in a private Google Sheet, and (c) no values committed to GitHub and no public display/redistribution. Ask whether the free page's own terms and any upstream data-owner terms allow this collection, retention, and intended internal use. An affirmative answer for (a)-(b) would not grant (c).

Nikkei Profile independently publishes daily historical PER and PBR with weighted-average and index-based series; its official data page says uses beyond personal use/quotation require permission and its contact page specifically routes index data processing/non-display uses to licensing. This remains a separate permission candidate. Its public archive rounds PER/PBR and does not provide exact EPS in the same series, so Invest Forest's EPS cannot be replaced with an exact calculation from rounded Nikkei PER.

Sources:
- Free Invest Forest dated PER/PBR/EPS table: https://nikkeiyosoku.com/nikkeiper/
- Invest Forest premium terms (scope is the premium service): https://nikkeiyosoku.com/order_kiyaku/
- Invest Forest inquiry form: https://nikkeiyosoku.com/inquiry/
- Nikkei public data-use scope: https://indexes.nikkei.co.jp/nkave/data/
- Nikkei non-display/data-processing inquiry: https://indexes.nikkei.co.jp/nkave/contact/

## Existing-route verification follow-up: official U.S. Treasury source (2026-10-11)

For an existing connected field that is outside the ten still-missing items, the U.S. Treasury documents a daily interest-rate XML feed intended for GET retrieval, including the daily par yield curve and a monthly query parameter. The 10-year value is the `BC_10YEAR` element and the observation date is `NEW_DATE`. This is a distinct series/method from FRED DGS10 and is recorded as a source-specific alternate for the existing US10Y report field, not as a replacement claim that the series are identical. The isolated Actions validator contacts only this documented Treasury feed, checks numeric presence, configured range/freshness and non-future date, and prints metadata without a quote value. It does not write repository data, create an artifact, update Sheets, or contact FRED/Yahoo/JPX/Nikkei. The remaining configured providers are still behind the rights gate.

Sources:
- Treasury Daily Interest Rate XML Feed (endpoint, query format, publication data): https://home.treasury.gov/treasury-daily-interest-rate-xml-feed
- Treasury Daily Rates and CSV/XML formats: https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve
- Treasury XML feed format change notice (field schema): https://home.treasury.gov/developer-notice-xml-changes

The route is connected in code but has not yet been executed on GitHub Actions. It does not raise the report-item route count above 18/28. Private Google Sheets storage and public GitHub/dashboard retention are separate downstream-use scopes; neither is exercised by this collect-only validator.

## FRED fallback adapter correction (2026-10-11)

The existing DGS10 fallback was using FRED's graph CSV endpoint without a registered API key. It is now configured for FRED's documented `fred/series/observations` JSON endpoint and reads the series and date from the returned observation objects. It requires a registered `FRED_API_KEY`; missing credentials fail before network access. API errors are reduced to their error code and a generic message so a key in the query URL cannot escape through an exception. The Actions acquisition step passes only the `FRED_API_KEY` secret to the fetch process; this does not grant permission for public data persistence or dashboard display.

The FRED API terms require a registered key and say third-party series rights remain with the series owner. DGS10 identifies the Board of Governors, carries a “Public Domain: Citation Requested” tag, and also has a generic copyright warning banner. The route is therefore a documented free API path, but downstream permission is scoped conservatively: private personal Sheets use can be considered with attribution under the API terms; public GitHub storage and dashboard display remain gated and uncleared. The DGS10-specific discrepancy should be confirmed with the source before public reuse. A separate `fred-us10y` validate-only Actions target now contacts only this source and requires the source-rights attestation; it skips values, exports, public persistence, and Sheets. No key was available in this task, so live FRED acquisition remains NOT_RUN.

Sources:
- FRED series observations API (JSON format): https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- FRED API terms (registered key and source-owner rights): https://fred.stlouisfed.org/docs/api/terms_of_use.html
- DGS10 metadata, source and rights labels: https://fred.stlouisfed.org/series/DGS10



## Existing 17 routes: source conditions and isolated evaluation scope (2026-10-12)

This review excludes the already validated U.S. Treasury route and the ten not-yet-connected report fields. It distinguishes a source's ability to return data from permission to automate collection and permission to store or republish it.

- **Yahoo Finance (index, futures, FX, crypto, commodities, and moving-average routes):** Yahoo's current Terms of Service require express prior permission before automated collection. No permission was confirmed, so the Yahoo routes were not contacted.
- **Stooq fallbacks (gold, WTI, USD/JPY, EUR/USD, BTC/USD):** no authoritative Stooq grant for this project's automated requests or intended downstream uses was confirmed. These remain disabled as fallback routes pending source terms confirmation.
- **JPX / OSE and Nikkei Profile (OSE futures, Nikkei VI):** JPX's site terms prohibit unlicensed secondary use/re-distribution and require permission for relevant market data; Nikkei Profile use beyond its stated personal-use scope is also not cleared. Neither source was contacted.
- **Cboe VIX:** the delayed-quotes page expressly prohibits automated extraction. Cboe also offers downloadable historical data, but the reviewed public page did not establish a blanket right for this project's recurring automated collection and public dashboard use. No Cboe route was contacted.
- **CNN Fear & Greed:** the configured graph-data URL is not documented as a public API, and no automation permission was found. It remains uncontacted.
- **FRED DGS10 fallback:** this is a documented API but requires a registered key and preserves series-owner rights. No live request was made; public GitHub/dashboard downstream rights are not cleared. Treasury remains the proven primary US10Y route.
- **Japan 10-year yield:** the configured adapter reads the repository's existing `data/rates-bonds.json`; its external lineage and current automated-use permission were not established in this review. It was not separately probed.
- **CoinMarketCap Crypto Fear & Greed:** the official `/v3/fear-and-greed/historical` endpoint is available through the keyless public API and returns dated daily values at 00:00 UTC. CMC documents the keyless service for scripts/prototypes/evaluation, while its pricing guidance says production use should use an authenticated Basic-or-higher key. This supports only a one-off metadata-only evaluation in this task. It does not authorize GitHub value commits, ongoing production collection, or public display/re-distribution. The dedicated Actions target does not write a sheet, artifact, or repository data, and its validator emits no numeric values. No live Actions request has yet been submitted.
- The separate product/data-use permissions remain distinct: a free API or public page does not itself clear public GitHub retention or public dashboard display. No public data output is enabled by the isolated target.

Primary terms/docs reviewed:
- Yahoo Terms: https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html
- JPX Terms: https://www.jpx.co.jp/term-of-use/index.html
- Cboe VIX delayed quote notice: https://ww2.cboe.com/delayed_quotes/vix/
- CMC Crypto Fear & Greed historical API: https://coinmarketcap.com/api/documentation/pro-api-reference/global-metrics
- CMC keyless API scope: https://coinmarketcap.com/api/documentation/pro-api-reference/keyless-public-api
- CMC pricing and production guidance: https://coinmarketcap.com/api/pricing/


## 2026-10-12 — 公式代替API/CSVの追加調査と限定ライブ検証

- 財務省「国債金利情報」は現行CSVと1974年以降の履歴CSVを提供。10年値は個別債の終値ではなく、15:00 JST時点の流通市場価格に基づく10年コンスタント・マチュリティの半年複利金利で、翌営業日09:30以降に更新。財務省サイトはPDL 1.0を適用し、出典表示を条件に再利用・公衆送信・改変を認める。個人Sheets、公開GitHub保存、公開表示はいずれも出典表示等に従う。データ定義の差を避けるため、現行JP10Yルートへの自動切替はせず reference-only とする。
- 日本銀行時系列統計APIは誰でもJSON/CSVで取得可能。USD/JPYのFM08 / FXERD04「東京市場ドル・円スポット17時時点」は日次公表系列。データは概ね毎営業日08:50頃に利用可能。API利用サービスの公開時は日銀への事前通知とクレジット表示を求めている。今回は公開値・シートを作らない単一ソース診断であり、東京17時値を連続スポット価格や終値としては扱わず reference-only にする。
- 新しい公式経路は本番collectorでの優先・fallback対象外。Actions検証は値を出力せず、source ID、取得日、検証コードだけを記録する。テスト用/本番シート・GitHub市場データ保存・dashboard更新は行わない。
- 別指標や権利条件上採用しなかった候補: ECB daily reference ratesはEUR/USD・JPY/EURから計算可能だが、16:00 CETのinformation-only reference rateで、連続FX closeではない; FRED DJIA/NASDAQCOM/SP500は日次終値だが第三者指数著作権が明記され、公開用途は権利者確認が別途必要; EIA daily WTIはCushing spot priceで、WTI futuresの代替とは数えない; Coinbase market-data termsは再配布を禁じ、個人/研究用途に限定し、AI用途制限も含むためこのエージェント経由での取得対象にしない; Cboe website termsはコンテンツ1部の個人非商用閲覧/ダウンロードを認める一方で電子検索システムへの保存・公開等を制限し、定期Actions自動取得の許諾は確認できなかったため未接続のままとする。
- 残る米指数・CME先物・金・原油先物・BTC・VIX・Nikkei cash/VI/deviations・CNN F&G・JPX Prime aggregatesは既存外部条件または指標定義の壁が残る。代替系列が現物/先物、daily close/reference、指数/ETF、異なるFear & Greedのいずれかに変わる場合は同じ列に混ぜない。

