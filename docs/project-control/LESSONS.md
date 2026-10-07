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
