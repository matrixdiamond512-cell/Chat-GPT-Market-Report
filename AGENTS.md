# AGENTS.md — Market report delivery documentation

For changes to the market report delivery system, read `docs/system/DOCUMENT_CONTROL.md` first.

- Do not create separately named dated/versioned requirements, specifications, or manuals. Keep stable GitHub paths and stable Google Docs IDs.
- For any change, record a change request ID, modification date, sources/PR, affected documents, verification status and unresolved items.
- Update affected requirements, specifications, body-authoring instructions and operations manuals together. A change to a market portal display or publishing pipeline is part of the same system when it affects report delivery.
- Preserve prior histories. Use Git history, Google Docs revision history, and the designated archive folder instead of naming a new "latest" file.
- Do not report `verified`, `published` or `complete` without independent evidence for the stated stage. Do not reconstruct pre-slot evidence retrospectively.
- Current configured report slots are weekdays 08:00/12:00/16:00/21:00 JST, none on weekends; recheck the actual config and task execution history before changing.

## Codex cross-PC handoff — HANDOFF-20261020-01 (2026-10-20 JST)

- Before continuing on another computer or with another authorized developer, read `HANDOFF.md`, the root `README.md`, the current issues/PRs and Actions runs, **after** reading the canonical `docs/system/DOCUMENT_CONTROL.md`.
- A transfer of source code is not a transfer of prior Codex conversations, local uncommitted changes, credentials, Google Drive/App Script runtime access, or verified publication evidence. Each person must sign in using their own authorized accounts.
- Confirm current `main`, branch, commit, clean/dirty worktree, PR overlap and latest workflow outcomes before changing code. Create a task branch and record the change-request ID, source/PR, affected canonical docs, scope, test commands/results, and unresolved items.
- Do not use documentation updates as authorization to change production data, report slots, Apps Script triggers, Drive/Docs files, PNGs, receipts, Pages deployment, or API billing.
- CI PASS, fixture PASS, report text availability, Drive readback, receipt validity, portal live DOM, and notification arrival are different proofs. Report NOT_RUN/UNKNOWN honestly, and never fabricate pre-slot evidence after the slot.
- Do not push secrets, login material, service-account JSON, or unreviewed bulk market data. Avoid force-push and overwriting another computer's work.


## MRF-0800-20261029 — scheduled issuance integration review

- Keep TEST_ONLY acquisition evidence separate from production issuance. An external capture PASS does not prove G2 creation, Google Docs save/readback, canonical registration, or portal publication.
- For the proposed 08:00 issuance transaction, preserve one report identity/revision/body hash and one generation-pinned snapshot through Docs and portal readbacks. Keep the duplicate-slot claim and all existing freshness, cutoff, receipt, and publish gates fail-closed.
- The independent Draft PR is based on the latest main observed for that PR. No production Docs/Drive write, main change, or Pages deployment is authorized by this implementation task. Real external stages remain NOT_RUN until observed.


- MRF-0800-20261029 continuation: Drive source filenames and body titles are separate contracts. Before claiming portal connectivity, verify the existing importer's evidence source and workflow side effects. The saved-Docs publication workflow writes canonical data to main and dispatches Pages; never invoke it as a test without explicit release authorization.



- Run `sync_reports_from_drive.py --apply` for this work only against a separately marked `LOCAL_STAGING_ONLY` checkout and only after exact-generation TEST_ONLY evidence staging plus strict Docs identity/body-hash binding. The normal scheduled workflow remains unchanged; never dispatch its production write/deploy path as a test.
