# Applicable lessons

- Never use runner start time or latest report to infer transaction identity. Date and slot are supplied once.
- any(generator) short-circuits mutation: process every item, aggregate changed afterward.
- Immutable snapshots must deep-freeze nested values, not merely freeze the outer object.
- Whole-body comparison must not hide a terminal punctuation mismatch.
- Report-level snapshots must remain separate from independent live dashboard data.

- Phase E: Durable checkpoints and effects are separate facts. Missing effects under a completed checkpoint require review, not silent recreation. Apply this check before any retry side effect.
- Phase E: UNKNOWN recovery must restore a successful prior state even when the remaining run has no new checkpoint. Persist validated publication observations before attempting Receipt creation.
- Phase E: Simulation markers and disabled production adapters bound the evidence claim. Synthetic SHA/DOM/PNG binding can establish E3 recovery behavior, not E5 real publication.
- Infographic validation: require exact section headings and bind each number to a typed market row, timestamp, unit and source section; caller-supplied PASS flags cannot stand in for provider-backed Vision or live readback.

- Archive manifests must be shared between dashboard and full report; metadata format drift must be normalized in a display-only adapter without changing publication eligibility. Test every saved source slot and forbid inference of actual capital flows from conditional prose.
# MR-STABILITY-REPAIR-20261117-03 / 2026-11-17 JST

LESSON: measure run_created to job_started before attributing schedule delay to runners or concurrency.
SOURCE PROBLEM: delayed morning runs started jobs only 2–3 seconds after run creation.
ROOT CAUSE: upstream delay remains UNKNOWN; slot-specific concurrency alone does not prove punctual scheduling.
APPLIES WHEN: future-slot acceptance and schedule incident analysis.
EXPECTED EFFECT: preserve cutoff rejection and avoid claiming unobserved scheduler recovery.
STATUS: ACTIVE.
