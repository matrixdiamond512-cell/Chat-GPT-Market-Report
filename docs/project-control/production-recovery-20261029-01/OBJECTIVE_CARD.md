# Objective card — DELIVERY-RECOVERY-20261029-01

Updated: 2026-10-29 JST

## Primary objective
Restore the existing weekday market-report pipeline so real reports are generated at 08:00, 12:00, 16:00, and 21:00 JST and reach Google Drive, the GitHub source/index/receipt, GitHub Pages, and users without duplicate or invented evidence.

## Acceptance
For each slot independently: actual weekday trigger at the specified JST time; full body rendered in its designated ChatGPT conversation; pre-slot evidence when official publication is claimed; verified Google Docs save and full-text readback in the correct monthly folder; same-slot PNG saved and read back in the infographic folder; canonical/index/receipt agree; Pages deploy and public body/image/title match; duplicate reportId absent; notification verified where observable.

## Constraints
- No weekend issue; keep all four times; honor JST/DST conversion.
- Never backfill pre-slot evidence or fabricate prices, events, save/publication results.
- Preserve historic bodies, formulas, images, reports, and receipts; no duplicate reportId.
- Keep 08:00 at 28 items × 5 columns; maintain all six markets and slot-specific event chronology.
- Preserve separate body and infographic publication states and current strict publication gate.
- Do not restart the paused P1 verification schedulers.
- No unrelated EA/dashboard work.

## Current result
NOT RESTORED. The Oct 28 Docs were saved at each slot, but the importing workflow rejected all four and produced no canonical report or receipt. No Oct 28 PNGs were found. PR #187 repairs one parser defect only. The active ChatGPT task now shows weekly repetition after a weekday edit, but exact 08:00 was not verified and the other three schedules remain unresolved. No run-to-Pages E2E has been shown.

## Open outcomes
1. Establish and read back four exact JST weekday triggers, including safe DST behavior.
2. Align scheduled-task report prompts with the strict semantic section contract and 08:00 data table.
3. Execute regression tests for slots, timezone/DST, OIDC, evidence timing, Docs/PNG write/readback, idempotency, receipts, Pages, and recovery errors.
4. Observe four real report executions through all applicable external stages and notification.
5. Reconcile fixed-path formal docs and evidence with the confirmed result; do not call recovery complete before all mandatory outcomes pass.
