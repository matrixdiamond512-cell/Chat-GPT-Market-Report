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


- MRF-0800-20261029: Three successful TEST_ONLY acquisition/snapshot readbacks prove only the acquisition and evidence-store stages. They do not establish G2 source capture, Google Docs persistence, canonical registration, or public portal delivery. Keep every later stage separately evidenced.


- MRF-0800-20261029: An exact Docs body and verified snapshot still do not reach the portal when the importer reads evidence from a different storage path. Trace the actual runtime handoff and workflow side effects before claiming end-to-end connectivity.


- MRF-0800-BRIDGE-20261030-01: Adjacent helper tests can pass while the importer wrapper between them remains untested. Compose the real local wrapper around fake external adapters, assert both exact-binding PASS and mismatch HOLD, and preserve TEST_ONLY provenance throughout.
