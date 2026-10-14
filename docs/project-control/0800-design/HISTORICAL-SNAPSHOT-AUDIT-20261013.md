# 2026-10-13 four-slot original and snapshot audit

Audit run: `historical-snapshot-audit-20261014-main-4a9e70f`  
Source refs: GitHub `main` at `4a9e70f4cb3af0848259504740f53b53bb40a6b9`; PR branch before main integration `61456f7a610d04a583c98e5d2910e1c29aa62bc7`.

## Findings

The current `data/market/history/` files are not automatically the original slot snapshots. The generated time and acquisition log must agree with the intended window. The files and run logs were read from GitHub history without restoring any withdrawn report or changing canonical data.

| Slot | Earliest relevant evidence in Git history | Canonical body / identity link | Disposition |
|---|---|---|---|
| 08:00 | `fa5773a`, snapshot generated `2026-10-13T11:37:42+09:00`; acquisition log says the scheduled 06:30 run was 307.7 minutes late and fetched only during recovery. | No `reports/2026-10-13_08-00.json` at the acquisition commit or current main. The review source is a readback/reconstruction with no immutable report identity. | Late data is not an 08:00 original. Historical source/snapshot envelope remains unavailable. |
| 12:00 | `76cf749`, snapshot blob `8b093c6285f4154f249b99bd53f768fc67d3c7f2`, generated `2026-10-13T11:34:12+09:00`; its acquisition row is `verified`, fallback 0, run count 1, scheduled 11:34. The current history file was later replaced by an 18:34:55 recovery snapshot (`ce34315`). | No `reports/2026-10-13_12-00.json` exists at the original acquisition commit or current main. The local review input is explicitly `RECONSTRUCTED_FROM_12H_SOURCE_AND_VALIDATED_CONTEXT`, not an original report. | The on-window market snapshot itself is recoverable from Git history. It is not linked to an original report body/revision/hash/spec, so it cannot qualify as a formal report source. Do not replace it with the later current snapshot. |
| 16:00 | `f0de1bc`, initial slot-labelled snapshot generated `2026-10-13T18:19:41+09:00`; the current file was later replaced by a 23:28:05 recovery snapshot (`92055e1`). | Canonical report exists with revision `1791875571770` and bodyHash `5fdc2e936ad7b60d7c3ca4bb4c8963a729a27d43d6dd6d4b33492d542dde3e17`, but it has no matching `snapshot_id`/snapshot hash envelope. | Report identity is present; exact report-to-snapshot linkage is not. The after-slot snapshots do not repair that gap. |
| 21:00 | `8b6fd9f`, snapshot generated `2026-10-13T23:05:42+09:00`; the acquisition log is a 23:05 fetch, after the report slot. | No canonical `reports/2026-10-13_21-00.json` at the acquisition commit or current main. The review source has no immutable body identity. | Later market data is not an original 21:00 snapshot. Historical source/snapshot envelope remains unavailable. |

The acquisition and snapshot files still present at main `4a9e70f` do not complete a single immutable report transaction for any of the four slots. One authentic on-window snapshot is recoverable for 12:00, while its original report body and identity are not. For 16:00 the canonical report body identity exists but the retained snapshots do not bind to it. The 08:00 and 21:00 snapshots were acquired after their report times and no canonical bodies are present. Existing unverified/reconstructed preview inputs remain review-only.

The 2026-10-14 16:00 production E2E has a separate gap: its ChatGPT body and Google Docs readback differ, and the task history says GitHub canonical registration did not occur. A later `live_recovery` acquisition log or snapshot is not proof of the exact market snapshot used by that ChatGPT/Docs body and was not substituted into it.

## Recovery boundary

- Preserve the 12:00 original market snapshot by its Git commit/blob evidence; do not copy the later retry snapshot over it or infer a report body from it.
- Keep the 08:00, 12:00, 16:00, and 21:00 report previews marked unverified until the same source provides body, revision, body hash, snapshot identity, and spec linkage.
- Do not restore withdrawn reports from a rendered preview, ChatGPT history, later snapshot, or reconstructed text.
- New reports must persist one immutable identity/body/snapshot/spec envelope before Docs save or rendering, require Docs readback hash equality, and stop before canonical GitHub registration/publication on any mismatch.

No Google Drive write, canonical report restoration, publication, or main-branch write occurred during this audit.
