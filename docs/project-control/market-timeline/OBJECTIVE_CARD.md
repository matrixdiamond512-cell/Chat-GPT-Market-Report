# Dashboard market timeline

PRIMARY OBJECTIVE: Show source-bound, slot-specific actual market events and verified market reactions for 08:00, 12:00, 16:00, and 21:00 in a separate dashboard panel, without presenting later amendments as issued-at-the-time reports or weakening existing publication gates.

ACTIVE PROFILE: dashboard + data-tool.

ACCEPTANCE CRITERIA: Four slot-specific phase sets; event time and fact; verified market reaction with observed time; cautious market meaning; next watch; source; linked to report date/time/revision/body hash/evidence; date/time selection sync; historical 2026-10-15 amendments visibly retrospective; missing and time-unknown evidence explicit; mobile readable; existing controls and publication policy unchanged.

CONSTRAINTS: Preserve current workspace changes and production data. No main merge or Pages publication. Do not fabricate facts or timestamps. Preserve snapshot/bodyHash/receipt/publication eligibility gates.

OPEN OUTCOMES:
- O-001 Inspect dashboard/report source contract and 2026-10-15 archived amendments. COMPLETE (source identity and archived amendments reviewed).
- O-002 Implement source-bound timeline data and rendering for four slots. COMPLETE IN WORKTREE.
- O-003 Test slot selection, report identity, historical amendment labeling, empty state, and mobile layout. PARTIAL: current localhost browser smoke verified 10/15 four-slot switching, retrospective archive slot synchronization, 21:00 exact-body mismatch guard, and 10/14 + 10/13 historical empty timeline. Prior 390x844 mobile check remains applicable because CSS did not change. All 10/15 content quality outcomes remain INCOMPLETE; Pages production rendering is not tested.
- O-004 Create a draft PR with changed files and evidence; do not merge or deploy. COMPLETE (Draft PR #150 created; not merged/deployed).

NEXT NECESSARY ACTION: Commit and push the current content-evidence amendment and slot-sync fix to PR #150, then inspect CI for that exact head. Do not merge or deploy.

## Sync and evidence audit continuation — 2026-10-16 (ADD)

PRIMARY OBJECTIVE: Correct the stale-latest false-green status, make source ingestion preserve independently parsed timeline data, and record the actual state of numeric infographic verification and ChatGPT body delivery while keeping all publication gates intact.

ACCEPTANCE: Later archived/blocked canonical slots mark the dashboard degraded and stale without changing latest-report eligibility; exact source retries include BLOCKED_SNAPSHOT_MISSING but still require exact Docs readback and contemporaneous evidence; new imported reports carry timeline fields bound to date/slot/revision/body hash/Docs revision/evidence; 10/15 retrospective amendments remain labeled as later amendments; active CI runs the relevant Python and timeline tests; no main merge or Pages deployment.

IMPLEMENTED: Stale held-source detection and recovery; blocked-source retry; 12:00 amendment-heading parsing correction; Python timeline extraction in the canonical Docs importer; retained publication health gates; accurate no-change workflow diagnostic. Local `data/dashboard.json` now exposes observed stale state while `data/latest-report.json` still points at the latest eligible report.

OPEN OUTCOMES:
- O-005 Google Drive/Actions/Pages production end-to-end sync after the Draft PR is reviewed and merged: NOT_RUN. Current main remains stale because the October 15 source reports are archived or evidence-blocked.
- O-006 Actual numeric equality of October 15 infographics and report bodies: UNKNOWN / NOT_VERIFIED; the four source records declare `infographic_status=NOT_VERIFIED` and no corresponding verified manifest/image evidence was observed.
- O-007 Automated ChatGPT full-body generation/delivery and failure alerting: NOT_IMPLEMENTED in the inspected scheduled path; it builds ChatGPT input files and uses a manual paste-to-Sidebar flow. One-time OpenAI workflows exist, but no run/result was observed in the accessible action history.
- O-008 Draft PR active CI, browser/mobile visual verification, final source-to-Pages readback: OPEN.

CONSTRAINTS: Draft PR only. Do not merge, deploy Pages, write Google Drive/Docs, configure secrets, or fabricate missing historical evidence.

NEXT NECESSARY ACTION: Push the reviewed code and stale-state correction to Draft PR #150, inspect its active CI results, and leave browser/mobile and external service acceptance open where the environment cannot observe them.
