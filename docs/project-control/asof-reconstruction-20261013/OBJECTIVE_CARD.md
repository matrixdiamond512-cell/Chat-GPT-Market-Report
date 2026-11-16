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
P0 implementation and final artifacts are on PR #94 HEAD `78ee1ba2e8b120ca9ebf8761e2b9f8361511d3e2`; the final requested suites compile and pass (54 unittest cases). The retained input archive contains 15 pre-cutoff intraday quote references, but no strict as-of finalization evidence, so the reconstruction classifies 0 VERIFIED_AS_OF / 15 REFERENCE_AS_OF / 13 UNAVAILABLE_AS_OF. These references are explicitly not closes and are production-ineligible. Corrected test-Sheets row 19 (A:I) was saved and read back; older row 18 is preserved. Production row 27 (2026/10/13) was read before and after; target data and structure, including 23 conditional-format rules, were identical. Dedicated `--dry-run` dispatch and zero-write tests pass, while the CLI itself was not live-invoked because local service-account credentials are unavailable. Production was inspected through the read-only Sheets connector only. The three formal Docs were appended with this correction and read back. PR #133 remains unchanged. Both PRs remain Draft/unmerged. Hosted Actions check-runs and PR workflow-runs for PR #94 HEAD are both 0; PR #133 has 3 failing latest validation checks.

## Next necessary action
Reconcile the market evidence gap and obtain a current-head Hosted Actions result when a supported runner is available. Keep PRs Draft and production untouched until every required acceptance is met.

