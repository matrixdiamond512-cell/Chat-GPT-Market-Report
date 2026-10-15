# Evidence ledger — dashboard market timeline

| Claim | Evidence | Level | Result | Limit | Run ID / timestamp |
| --- | --- | --- | --- | --- | --- |
| Four slot timelines satisfy the stated schema, phases, source identity, amendment labeling, and omission rules. | `node --test tests/test_market_timeline.js` (12 tests). | E2 | PASS (12/12). | Component/schema and static UI-contract evidence; not a live-source verification of market events. | local / 2026-10-16 JST |
| Existing report publication eligibility remains fail-closed. | `node --test tests/test_report_publication_policy.js` (8 eligibility states plus preservation checks). | E2 | PASS. | Does not prove a production publication attempt. | local / 2026-10-16 JST |
| JavaScript sources parse. | `node --check assets/js/market-timeline.js`; `node --check assets/js/top-dashboard.js`; `node --check scripts/reporting/build_market_timeline_archive.js`. | E1 | PASS. | Syntax only. | local / 2026-10-16 JST |
| Apps Script source parses as JavaScript. | `Get-Content apps-script/MarketReportWebSync.gs -Raw | node --check`. | E1 | PASS. | Node syntax check does not emulate Google Apps Script runtime. | local / 2026-10-16 JST |
| Feature diff has no whitespace errors with repository CRLF conventions accounted for. | `git -c core.whitespace=cr-at-eol diff --check`. | E0 | PASS. | Structural check only. | local / 2026-10-16 JST |
| Browser behavior, responsive layout, and real date/time selection are visually verified. | Attempted local browser preview at `127.0.0.1:8765`; browser connection timed out and shell loopback request was denied by environment. | E4 | NOT_RUN / BLOCKED. | Automated tests assert placement and responsive CSS; visual/mobile runtime confirmation remains open. | local / 2026-10-16 JST |
| PR records files and evidence without publishing. | Draft [PR #150](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pull/150) created from `codex/market-session-timeline` into `main`; GitHub reports `draft=true`, `merged=false`. | E5 | PASS. | No merge or deployment performed. | GitHub / 2026-10-16 JST |
| PR CI workflow ran. | GitHub workflow-run lookup for head commit `a822fd1ee86ab9ed63554b5ef551880358fc721e` returned no pull-request workflow runs. | E5 | NOT_RUN. | Workflow result is unavailable; no pass claimed. | GitHub / 2026-10-16 JST |
