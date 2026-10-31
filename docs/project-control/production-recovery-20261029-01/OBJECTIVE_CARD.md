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
NOT RESTORED. Read-only Drive folder listings at 2026-10-29 02:17 JST found four October 28 report Docs and no October 29 Docs; the infographic month folder had no October 28 or 29 PNG. The October 28 importer run rejected all four sources and created no canonical report/receipt. PR #187 fixes the fullwidth-pipe numbered-heading parser defect. Manual replay of the saved-body contract also found the 12:00 source has a final explicit `結論：…` paragraph but no numbered conclusion heading; the PR now recognizes only explicit conclusion/final-judgment/summary labels and preserves same-line conclusion text as the section body, while unmarked prose remains rejected. The 08:00 source's previous-close section is a bullet list with no 28×5 table; the separate `qa-morning-report.yml` workflow checks table QA after `reports.json` changes and fails closed at Portal selection. Latest UI readback before the browser timeout showed the legacy 08:00 task and new 12:00/16:00 tasks, but no 21:00 task; exact recurrence/prompts remain unverified. Cloud Shell disconnected, P1 Scheduler current state UNKNOWN, and neither paused scheduler was resumed. No October 29 slot has run yet (readback at 02:17 JST). No live Docs/PNG/GitHub receipt/Pages/notification pipeline has been demonstrated.
## Open outcomes
1. Establish and read back four exact JST weekday triggers, including safe DST behavior.
2. Align scheduled-task report prompts with the strict semantic section contract and 08:00 data table.
3. Execute regression tests for slots, timezone/DST, OIDC, evidence timing, Docs/PNG write/readback, idempotency, receipts, Pages, and recovery errors.
4. Observe four real report executions through all applicable external stages and notification.
5. Reconcile fixed-path formal docs and evidence with the confirmed result; do not call recovery complete before all mandatory outcomes pass.
