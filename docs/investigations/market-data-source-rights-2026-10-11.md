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

The Nikkei official Historical Data and Daily Summary publish daily Nikkei 225 aggregate P/E and P/B, with both market-cap and index-weight bases. The official pages offer two distinct aggregate bases: market-cap basis and index-weight basis. Existing report/Sheets headers must be checked against their historical semantics before selecting either series; do not silently switch bases or substitute per-constituent values. The official guide defines index-weight EPS through the Nikkei 225 close and its P/E calculation, but the public archive displays P/E rounded to two decimals and does not directly publish EPS. Dividing by displayed P/E therefore gives an approximation and must not be labeled exact official EPS.

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