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
- Historical infographic replay: distinguish missing original capture from missing source evidence. A typed `SOURCE_RECONSTRUCTED` snapshot can preserve the evidence chain for a saved report without claiming `LIVE_CAPTURED`; keep real gaps blocked and record them independently. On Windows, set temporary test output under the writable workspace before unittest runs; the default OS temp location may be inaccessible and can produce misleading permission errors.
- 08:00 reference reproduction: missing source data must not trigger pagination or a different composition. Keep all 16 fixed zones on one sheet with explicit source-gap markers, and report layout, completeness, and readability gates separately; a 768px readability FAIL remains a real failure.
- A complete synthetic renderer fixture is useful for proving the 08:00 dispatch contract, but must carry `SYNTHETIC_FIXTURE` provenance and never production eligibility. In real-source replay, font-floor and overflow gates can conflict with the fixed reference geometry; show the overflow and preserve FAIL instead of reducing text to a false pass.

- 08:00 visual fidelity: fixed coordinates alone are not visual similarity. Validate each panel's information form and hierarchy (numbered markers, table columns, cause/effect arrows, scenario colors, emphasis) while treating source completeness separately. Compact only source-bound wording; if the display must omit meaning or clips text, fail the panel rather than shrinking it to an unreadable size.
- New 08:00 report creation must produce structured facts and numeric registry with the body, then run `scripts/generate_0800_infographic.py` before Docs save or rendering. The contract tool is a local preflight, not a live Google Docs adapter; do not claim external save-time enforcement unless a future caller actually invokes it.
