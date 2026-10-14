# Objective Card — publication synchronization recovery

Run ID: `production-recovery-20261014-0704`

PRIMARY OBJECTIVE: Repair the four confirmed GitHub Actions publication/index failures without weakening source verification or losing valid history; prepare a reviewed PR and verify production behavior where an actual scheduled run is observable.

ACCEPTANCE CRITERIA:
- Same-revision replay is idempotent while body hash/source identity stay identical; content conflicts and stale revisions remain blocked.
- Latest, canonical history, report index, and dashboard use one documented dashboard-copy contract and one report-key contract; independent `partial` status is preserved.
- The July 27 display fixture is preserved under test fixtures and excluded from public report history; all other valid report slots remain unchanged.
- Rebuilds are repeatable, fullText remains required for real published reports, and regression tests cover positive and negative cases.
- Relevant Actions pass on a PR; live scheduled Apps Script-to-Pages behavior is reported only if observed.

CONSTRAINTS: Do not repeat Google authorization; do not alter Apps Script triggers or Drive originals; preserve body hash/revision/source-ID gates; never publish rejected originals; do not delete valid history; use a branch and PR; do not disclose secrets; keep unrelated local dirty work untouched.

ACTIVE PROFILE: generic-app + data-tool. Scope: `scripts/build_reports.py`, `scripts/sync_latest_report_publication.py`, `scripts/reconcile_latest_report_market_data.py`, `scripts/verify_publication_consistency.py`, `scripts/build_report_index.py`, `scripts/verify_scheduled_report_delivery.py`, relevant workflows, fixture migration, regression tests, and affected existing operator documentation.

BASELINE: GitHub `main` `3ec46ff65b76af29ebd211239cf155a9a7e05e29` (verified latest at 2026-10-14 07:13 JST). Production report latest is 2026-10-13 16:00; source hash `5fdc2e936ad7b60d7c3ca4bb4c8963a729a27d43d6dd6d4b33492d542dde3e17`.

OPEN OUTCOMES: Apply repairs; preserve/compare all report IDs; run regressions and relevant workflows; prepare PR; independently verify whether the next scheduled production run happens. Apps Script live E2E remains `PENDING_LIVE_RUN` until observed. GitHub Actions OAuth secrets remain a separate configuration item; do not repeat Apps Script approval.

NEXT NECESSARY ACTION: Implement shared report identity and canonical publication rules in the isolated feature branch, then test against the pinned baseline and current history.
