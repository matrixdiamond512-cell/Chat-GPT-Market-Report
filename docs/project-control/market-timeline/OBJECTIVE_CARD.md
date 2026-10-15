# Dashboard market timeline

PRIMARY OBJECTIVE: Show source-bound, slot-specific actual market events and verified market reactions for 08:00, 12:00, 16:00, and 21:00 in a separate dashboard panel, without presenting later amendments as issued-at-the-time reports or weakening existing publication gates.

ACTIVE PROFILE: dashboard + data-tool.

ACCEPTANCE CRITERIA: Four slot-specific phase sets; event time and fact; verified market reaction with observed time; cautious market meaning; next watch; source; linked to report date/time/revision/body hash/evidence; date/time selection sync; historical 2026-10-15 amendments visibly retrospective; missing and time-unknown evidence explicit; mobile readable; existing controls and publication policy unchanged.

CONSTRAINTS: Preserve current workspace changes and production data. No main merge or Pages publication. Do not fabricate facts or timestamps. Preserve snapshot/bodyHash/receipt/publication eligibility gates.

OPEN OUTCOMES:
- O-001 Inspect dashboard/report source contract and 2026-10-15 archived amendments. COMPLETE (source identity and archived amendments reviewed).
- O-002 Implement source-bound timeline data and rendering for four slots. COMPLETE IN WORKTREE.
- O-003 Test slot selection, report identity, historical amendment labeling, empty state, and mobile layout. PARTIAL (12 automated acceptance checks + publication-policy regression pass; browser visual verification unavailable because local loopback access is blocked in this environment).
- O-004 Create a draft PR with changed files and evidence; do not merge or deploy. COMPLETE (Draft PR #150 created; not merged/deployed).

NEXT NECESSARY ACTION: Have the Draft PR receive its required browser/mobile visual verification and CI run before review. Do not merge or deploy.
