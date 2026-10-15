# Objective Card — 2026-10-13 16:00 JST reconstruction

## Primary objective
Produce a reproducible, evidence-bounded historical reconstruction for 2026-10-13 16:00 JST; preserve the report quality gates; validate private test-Sheets roundtrip and a read-only production comparison; keep PRs Draft and do not merge or publish.

## Acceptance criteria
- Account for all 28 market fields with VERIFIED_AS_OF / REFERENCE_AS_OF / UNAVAILABLE_AS_OF and reasons.
- Exclude later information unless publication-before-cutoff is proven by identity- and hash-matched original evidence.
- Produce snapshot, evidence ledger, same-snapshot report, reproducibility/hash evidence, and 9-period/7-column timeline.
- Run requested P0 tests and current relevant Actions checks.
- Save one unique 9-cell row to the personal test sheet and read all cells back.
- Inspect the production close-list date row without changing cells, formatting, formulas, or audit history.
- Update the formal requirement, specification, and operations documents with implementation and open outcomes.

## Constraints / forbidden substitute
No main merge, production publish/write, fabricated values/news, weakening of gates, or replacement of current reports[0]. A later correct price is not proof that it was available by the cutoff.

## Current state
P0 implementation and 53 targeted unit tests pass in an isolated PR #94 source copy. The retained input archive does not contain strict as-of finalization/publication evidence for the target; the generated partial reconstruction therefore classifies 0 VERIFIED, 0 REFERENCE, and 28 UNAVAILABLE_AS_OF. Test-Sheets row 18 was saved and read back. Production row 27 (2026/10/13) was read before and after; target data and structure, including 23 conditional-format rules, were identical. A separate read-only `--dry-run` path was added and its pure comparison function passed the zero-write regression tests. PR #94 was updated at commit `abefccc185de90845e43aadecaf9fa49bf2e1983`; that HEAD has no GitHub check runs. The three formal Docs were updated and read back. Market evidence, a live invocation of the new CLI, current-head Actions, and PR #133 integration remain open.

## Next necessary action
Reconcile the market evidence gap and obtain a current-head Hosted Actions result. Keep PRs Draft and production untouched until every required acceptance is met.
