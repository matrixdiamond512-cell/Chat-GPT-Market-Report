# Foundation implementation — 2026-10-04

PRIMARY OBJECTIVE: Resolve SC-01–03 in the five formal Drive v1.8 documents, then implement immutable ReportContext → MarketDataSnapshot → ReportObject → G0–G8 validation foundations and the explicitly authorized P0 regression fixes.

ACTIVE PROFILE: dashboard + data-tool. Base commit: 600a533. Branch: codex/report-foundation-a-b-d-c.

ACCEPTANCE: Explicit dates, immutable retry identity, unknown-cron rejection, weekend new-report rejection; frozen report-bound snapshots; typed numeric markets and legacy read adapter; connected gates with PNG/manifest refusal, full-text Drive verification, rollback/projection/DOM checks; required A/B/D/C fixtures and existing regression checks; five formal Drive readbacks; unchanged production artifact hashes.

CONSTRAINTS: Preserve acquisition, readiness, history, source registry and legacy reads. No push/deploy or production JSON/report Docs/PNG/Receipt mutation. Formal specification updates are expressly authorized. 2026-10-02_21-00 remains UNRESOLVED / UNVERIFIED / NEEDS_REVIEW.

OUT OF SCOPE: E–H Publisher/Projection/Portal/Scheduler reorganization; production persist writer behavior change; canonical identity reconciliation.

FORBIDDEN SUBSTITUTE: Unit checks or new gate API do not prove that the existing live publishing pipelines enforce these gates. Report remaining deployment bypass separately.

OPEN OUTCOMES: None within the authorized A/B/D/C foundation task. Deferred: live Publisher/Projection/Portal/Scheduler enforcement, unresolved 2026-10-02_21-00 identity, existing unsafe canonical writer, historical structure/PNG gaps. These are not silently withdrawn.

NEXT ACTION: Stop after accepted af61a0a and final report. Start Phase E only on the user's next instruction; preserve all deferred outcomes and explicit production restrictions.
