# Evidence ledger — DELIVERY-RECOVERY-20261029-01

Updated: 2026-10-29 JST

| Claim | Evidence | Level | Result / limit |
|---|---|---:|---|
| Old Cloud Run revision 00007-kmg rejected the 07:47 P1 request | User-provided incident record: OIDC and job name PASS; schedule FAIL; `SCHEDULE_NOT_ALLOWED` | E3 | Established from supplied evidence; no live re-execution |
| Revision 00008-b9d succeeds at 07:47 | No run/readback found | E4 | UNKNOWN; P1 remains a shadow test, not production proof |
| P1 test and stop-monitor schedulers are stopped | User-provided operation record; not reactivated | E4 | Current live state not newly re-read through GCP API |
| Oct 28 Docs exist for all four slots | Drive native Docs reads: 08 ID `1laY8WojdqX5kUNJj35PIXlNnikXqH_F7NntuNPuhOYA`; 12 ID `1D0KQ9O4NtPm5ZPEch2ROOTl-_kHxRzT8U1jhhzayrEg`; 16 ID `16va0K8CBeLPHwZKzK2ytCVbB42xWfOQWJq_AVwUKpIE`; 21 ID `1DQlp6RhzgzSNfda7Bwq6WqWsk9EFxaDKQFKT2B6v5WU` | E2 | Files and body titles/sections read; does not prove pre-slot evidence or formal publication |
| Oct 28 importer rejected every slot and made no canonical report | Actions run [40714284584](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/40714284584): all four `SOURCE_VALIDATION_BLOCKED`, `missing sections/conclusion`, `new_slots=[]`, `promotion_slots=[]`, `NO_NEW_REPORTS` | E4 | Workflow run evidence; safe no-op, not report delivery |
| Parser defect is reproducible from source format | Main parser regex recognizes period/Japanese list punctuation but not `｜`; all four Docs use `01｜...` numbered section lines | E0 | Structural defect confirmed; PR #187 proposes adding this separator while retaining gates |
| October 28 infographics exist | October infographic folder ID `1Ma24qcksen9Ufqz1wIUYqSTdYFfpok2w` listing had no Oct 28 assets | E2 | NOT FOUND in listing; no image readback |
| Official canonical, receipt, and Pages represent all Oct 28 reports | Reports path 404, no Oct 28 receipts; run built historical index only | E2/E4 | FAIL for Oct 28 publication outcome |
| ChatGPT schedule state | Final task-list readback: legacy `平日マーケットレポート・本文優先配信` weekly, next ~6h; new `マーケットレポート12:00` weekly, next ~10h; new `マーケットレポート16:00` weekly, next ~14h. Registration responses gave weekday-only and requested times. The 21:00 conversation said legacy would become 08:00-only, but no 21:00 task appeared in the list and response ended `この回答を読み込めませんでした`. | E4 | 08/12/16 task entries observed, but exact saved recurrence and legacy prompt not independently verified; 21:00 absent; four-slot schedule NOT restored |
| Focused numbered-heading regression tests | CI run [40728029673](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/40728029673), job `numbered-heading-regression`; test step completed successfully on PR merge ref `abd37846b1bc4a5325f56c25e87bb958c3a6b029` (head `dd93ad7a0ce63e2e665a80540542578b5d3e79e6`) | E1 | PASS for focused parser regression cases only; no runtime delivery proof |
| Existing synchronization/publication contract regression | CI run [40728029672](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/40728029672), `publication-contract`; regression and publication/history verification steps succeeded on the same PR merge ref | E1/E2 | PASS for existing automated test fixtures/contracts (including reconciliation, schedule delivery, publication eligibility, report contracts, index consistency); no live API/Drive/Pages run |
| Four-slot live E2E | No actual slot execution after changes yet | E4/E5 | NOT_RUN |

## Next necessary action
Create/read back the missing 21:00 task; verify exact saved recurrence for 08/12/16/21 and no duplicate slots; verify/update the 08:00 prompt and required 28×5 table; then execute regression tests and observe the next eligible slot. Keep each external stage and failure separate. Do not retroactively publish Oct 28.
