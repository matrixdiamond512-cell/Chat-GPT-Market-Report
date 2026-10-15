# PR #94 + PR #133 Integration Evidence

Updated: 2026-10-15 JST

## Objective

Validate the two features together on a branch based on the current main commit without changing main or publishing a report.

## Branch inputs

- Main base: da1f28672aefa9d916e9e0888b79a7be42011fd6
- PR #94 head: d72cd59a805bdbc12c7700b79dbea7bf64462797 (Draft, open)
- PR #133 head: 4e1889cbfd61d714731be52b72ca21b91b255f17 (Draft, open)
- Integration branch: codex/pr94-pr133-integration-draft-20261015

## Conflict review and resolutions

- The branches have real GitHub merge conflicts (both PRs report mergeable_state=dirty).
- The PR diffs share three project-control files. This branch keeps main's copies and records the integration evidence here.
- PR #94's newer time-series recorder was transplanted into the latest-main acquisition producer. The latest-main market-window scheduler was kept because it contains subsequent schedule/cutoff changes.
- PR #133's dashboard JSON and synchronization-contract test conflict with newer main versions. This branch keeps main's files; the independent market-data projection code and timeline validation/producer changes are included.
- No dashboard rows or canonical report files were overwritten by the integration overlay.

## Evidence

| Claim | Evidence | State / level | Limit |
|---|---|---|---|
| PR #94 read-only close dry-run | 26 tests pass, including duplicate rows, JST target date, separate diagnostics/write eligibility, and write/insert/audit/format mocks | E1 / PASS | No live CLI credentials; no production execution |
| PR #94+time-series targeted Python suites | 64 tests and four-file py_compile pass in isolated review copy | E1 / PASS | Hosted Actions has not run |
| PR #133 timeline producer | Node VM test builds evidence-derived seven-column table; unchanged Apps Script timeline gate accepts it | E1 / PASS | No live Google Docs or GitHub publication |
| 28-item cutoff evidence | 0 VERIFIED_AS_OF / 15 REFERENCE_AS_OF / 13 UNAVAILABLE_AS_OF | E0 / PASS | Later official pages corroborate some market facts but do not prove publication before the 2026-10-13 16:00 JST cutoff |
| Production writes | Sheets writes 0; row insertions 0; audit additions 0; format changes 0 | E2 / PASS | Dry-run API behavior is separately proven with mocks |
| Hosted CI for latest PR #94 HEAD | No workflow runs or check-runs returned for the latest commit | E5 / NOT_RUN | GitHub database ref updates did not dispatch Actions; available GitHub connector has no workflow_dispatch operation; safe UI approval timed out |

## Market-evidence decision

The 15 reference values were captured at 2026-10-13 00:08:30 JST (2026-10-12 15:08:30 UTC), during the U.S. equity session. They are intraday/delayed references, not final closes. The October 12 U.S. equity close was after the report cutoff (2026-10-13 16:00 JST). Official Nikkei retrospective pages and the JPX daily report provide later corroboration but no exact publication time before cutoff. TSE daily reports are published on the next business day. No item is promoted to VERIFIED_AS_OF.

## Time-series report generation

The acquisition producer appends cutoff-valid, source-stamped snapshots to date/slot archives. The report producer reads only snapshots generated and observed by its cutoff, derives an explicit seven-column timeline, and labels empty intervals as unobserved. Timestamped news remains unavailable in the acquisition path and is recorded as not collected. The 2026-10-13 historical narrative is not backfilled from later data.

## Remaining outcomes

- Hosted PASS for the latest PR #94 HEAD remains unproven.
- Timestamped news-source collection is not implemented.
- The existing historical reports retain their current contents; no retroactive narrative or publication was performed.
- Test-sheet save/readback from the earlier isolated validation remains E2 / PASS; it was not repeated during this integration-only review.
- Both PRs remain Draft and unmerged; main is unchanged.
