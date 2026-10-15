# PR #94 + PR #133 Integration Evidence

Updated: 2026-10-15 JST

## Objective

Validate both requested features together on a Draft branch based on the latest main commit. No main update, report publication, or production Sheets write was performed.

## Branch inputs

- Latest main at integration: `f7a61763bf88df455a21445cfdebe41be62e1531`
- PR #94 current head: `d72cd59a805bdbc12c7700b79dbea7bf64462797` (open, Draft)
- PR #133 current head: `c6d54d3cd1946482b7da3f0e4f426cd25a426733` (open, Draft)
- Integration branch: `codex/pr94-pr133-integrated-draft-20261015-review`
- Integration commit: `bfcdc4af078db329ed8964f62e68afc17f9fa6f3` plus this evidence/test update

## Conflict review and resolutions

GitHub reports `mergeable_state=dirty` for both PRs. The tree differences show three shared project-control files, and the following main/feature collisions:

- PR #94: `scripts/run_market_data_acquisition.py` and `scripts/run_market_data_window.py`.
- PR #133: `data/dashboard.json` and `tests/test_market_report_sync_contract.py`.

The integration uses latest main's market-window scheduler, dashboard data, and synchronization contract test. It ports the cutoff-valid time-series recorder into latest main's acquisition producer. It includes PR #133's narrative validator, report timeline builder, Apps Script timeline producer, and a separate dashboard projection regression test. The common project-control documents remain from main; this isolated integration ledger records the combined result.

## Evidence

| Claim | Evidence | State / level | Limit |
|---|---|---|---|
| PR #94 dry-run contract | 26 read-only tests pass, including JST conversion, duplicate-date failure, independent MATCH/VALUE_CONFLICT diagnostics, and mocks that fail if any Sheets write, row insert, audit or formatting call occurs | E1 / PASS | Live CLI not run; credentials unavailable |
| Integrated PR #94 Python scope | `py_compile` and five requested unittest suites pass: 64 tests | E1 / PASS | Hosted Actions remains NOT_RUN |
| PR #133 timeline producer | Node VM regression builds all 08:00/12:00/16:00/21:00 tables, excludes later-slot evidence, and passes the existing Apps Script prepublish timeline gate | E1 / PASS | No live Google Docs or GitHub publish |
| Dashboard projection | Separate test verifies canonical report immutability, idempotent market-data projection, and dashboard/report consistency | E1 / PASS | No remote dashboard write |
| 28-item cutoff evidence | 0 VERIFIED_AS_OF / 15 REFERENCE_AS_OF / 13 UNAVAILABLE_AS_OF | E0 / PASS | Later retrospective official data lacks evidence of availability before cutoff |
| Production Sheets | Writes 0; row insertions 0; audit additions 0; formatting changes 0 | E2 / PASS | Mock behavior plus prior read-only comparison |
| Test Sheets | Earlier isolated test saved one row and read all A:I values back exactly; ID `personal-report-ea69e338d9683914d3e5de34` appears once | E2 / PASS | Not repeated in this integration review |
| Latest report timeline | Main's `reports/2026-10-15_16-00.json` has no seven-column timeline. The producer now generates one from archived time-stamped observations. Existing report was not rewritten. | E0 / PARTIAL | The current artifact remains noncompliant until evidence-backed regeneration is possible |

## Hosted Actions

The latest PR #94 head has no workflow runs, check-runs or commit statuses. PR #133 also has no new run for the producer change. GitHub reports both PRs `dirty`, and GitHub documents that `pull_request` workflows do not run while a PR has merge conflicts. The safe test workflow added on the feature branches is not on the default branch, so its `workflow_dispatch` trigger is unavailable. The GitHub connector exposes no workflow-dispatch action, and the earlier computer-use approval timed out. No execution URL exists; a Hosted PASS is not claimed.

## Evidence re-evaluation

- Snapshot `asof-7c05cd9ed95a609865f57e9a`: 0 verified, 15 reference, 13 unavailable.
- All 15 reference points were captured at 2026-10-13 00:08:30 JST (2026-10-12 15:08:30 UTC). They are intraday/delayed references, not final closes; the FX and continuous futures observations represent that captured window.
- The four U.S. cash indices were observed at about 11:08 ET on October 12. NYSE's 09:30–16:00 ET core session had not closed by the capture, and October 13 16:00 JST was 03:00 ET on October 13, two hours before the October 12 close.
- Nikkei's retrospective page now shows October 13 open/high/low/close and PER/PBR, but the historical page provides no publication timestamp. Its historical-data page shows an update date of 2026-10-15. TSE daily report guidance says reports are posted on the next business day. These are later corroboration, not as-of evidence.
- Timestamped news source collection is not connected. No timeline claims are fabricated from undated headlines.

## No external publication

PRs #94 and #133 remain OPEN / Draft / unmerged. The integration branch is separate from main. No published report, production sheet, dashboard or canonical report was modified.

## Open outcomes

- Obtain a safe Hosted Actions run for the latest PR #94 head; do not run the live data-update workflow.
- Connect a timestamped news acquisition source with publisher, publication time, URL and captured source bytes/hash.
- Generate a compliant latest seven-column report after the future time-series collector has produced cutoff-valid observations.
- Live CLI dry-run cannot run until credentials are available. No production writes are authorized or needed for validation.
