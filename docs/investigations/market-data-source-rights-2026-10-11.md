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

For comparison only, Invest Forest publicly displays 2026-10-09 close 69,030.92, PER 17.37, PBR 1.90 and EPS 3,974.15. The same close divided by that displayed EPS gives PER 17.3575 (17.36 rounded), while close divided by displayed PER 17.37 gives EPS 3,971.29, about 2.86 below the displayed EPS. This fails a direct same-date/definition consistency check at the displayed precision. The provider's public premium terms expressly prohibit program-based automatic extraction. Do not use its page as an Actions API; the displayed EPS may be shown as an unresolved cross-check only, not silently treated as validated official output.

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

### Method for the ten open fields

1. CME Yen Nikkei futures: individual NIY=F deferred contract quote; automated use blocked by Yahoo terms. Realistic automated alternative: authorized CME/vendor feed; otherwise manual observation.
2. CME USD Nikkei futures: individual NKD=F deferred contract quote; same block and alternative as above.
3. Nikkei PER: official Nikkei daily PER archive, preserve weighted-average vs index-basis series; automated retrieval awaits Nikkei written scope confirmation.
4. Nikkei PBR: official Nikkei daily PBR archive, preserve weighted-average vs index-basis series; same gate.
5. Nikkei expected EPS: derive only from same-session Nikkei close and unrounded PER of the same official basis, then compare with provider EPS; current third-party displayed figures fail displayed-precision parity and automated collection is prohibited/uncleared. No exact free official EPS series was established.
6. Prime trading value: JPX Daily Report market-segment “概算” total is the closest public source, next-business-day PDF; automated reuse blocked by JPX terms. Equities Market Summary has the current aggregate but the same downstream-processing restriction.
7. Prime trading volume: same route and restriction as #6.
8. Prime advancers: JPX Equities Market Summary Prime row provides the visible daily aggregate; automated storage/processing blocked. Historical raw series requires JPX permission or a validated licensed/API source.
9. Prime decliners: same route and restriction as #8.
10. Prime 25-session ratio: calculate 100 × sum(Prime-only advancers for the latest 25 Japan sessions) / sum(Prime-only decliners for those same sessions). No authorized free raw-count series was established; third-party published ratios cannot replace the input series.

### Implementation and run status after this review

No acquisition adapter or source definition was added for these ten fields: every examined current quote/data page either expressly restricts automated collection/processing, requires an unconfirmed account/entitlement, or only exposes delayed/derived values. Adding a scraper under a “free” label would violate the source-rights constraint. The existing rights-confirmation checkbox remains false by default. GitHub Actions live collection and date validation were not run because the existing mixed-source workflow would contact sources whose automated rights are unconfirmed, and this GitHub connector has no workflow_dispatch operation. The user explicitly asked to keep the PR Draft; it remains OPEN/DRAFT. Google Sheets write/readback and historical backfill are unchanged and NOT_RUN.
