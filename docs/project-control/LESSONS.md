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


- MRF-INGESTION-20261030-01: A successful importer process can store a non-public archive while failing publication eligibility. Log the performed stage, not the workflow's broad name. Keep receipt creation, canonical projection, Pages deployment, and public DOM readback as separate claims.


- MRF-INGESTION-20261030-01: Pin an evidence link to a commit that actually contains the referenced artifact. A later existence check cannot make an earlier 404 link valid; repair the link and record the correction without changing the acceptance state.


## MRF-0800-IMPORTER-COMBO-20261030-01 — test wiring is part of acceptance (ACTIVE, 2026-10-30 JST)

LESSON: Adding a regression test file and listing its path in a workflow filter do not prove it ran. Add the test command to the job and include the relevant source/helper paths in the trigger filter; inspect the exact-head job log for the test name and summary.

SOURCE PROBLEM: PR #189 added `tests/test_ingestion_outcome.py`, but its sync recovery workflow did not invoke that file. ROOT CAUSE: workflow path selection and test execution were treated as the same step. REPAIR: the integrated PR #188 workflow now watches the importer/helper/test paths and runs the test module; exact-head CI log reports 4 tests, OK. EXPECTED EFFECT: new contract tests become executable evidence on matching changes. STATUS: ACTIVE.

- MRF-0800-STAGING-BOUNDARY-20261030-01: Environment-name checks must use bounded tokens, not substrings, and path isolation must reject ancestor and descendant overlap. Check resolved destinations before creating directories so a symlink cannot cause an outside-root side effect.

- MR-ISSUANCE-CONNECT-20261104-02: A hosted suite can pass its older pipeline cases while newly added exact-importer tests remain unexecuted if the workflow stops at the first failure. Add the composed test to the real CI command list, inspect step-level logs, and keep the final SHA's exact run IDs. Package imports must be tested in both script and `scripts.*` module invocation contexts.
- MR-ISSUANCE-CONNECT-20261104-02: A green Pages workflow cannot prove publication. Bind the workflow run to the canonical commit SHA, then GET the public report JSON and compare report ID, revision, full text and body hash. Treat post-main Pages failure as partial completion, not PUBLISHED.
- MR-ISSUANCE-CONNECT-20261104-02: Component tests around PortalPublisher missed that run_issuance stripped the original pinned evidence envelope and the importer passed the pre-import G2 shape to the existing receipt verifier. Include one composed test using the real local importer and verifier with fake external boundaries; validate both input shape and downstream receipt source identity.


## MR-G2-TASK-HANDOFF-20261111-01 — 2026-11-11 JST

Source: user integration instructions and PR #188; prior head `b8ba8817f78294d9314f4fe20413b4b5b3dc4cbd`.
Affected canonical paths: requirements.md, specification.md, operations.md, DOCUMENT_CONTROL.md; project-control objective, decisions, lessons and evidence ledger. Google Docs fixed IDs remain unchanged; their current revisions and runtime access were not available, so synchronization/readback is NOT_RUN. Body-authoring changes are specified below for the fixed body-authoring manual, pending authorized access.

- Scope: task-output intake boundary plus an isolated chain; no production release. `task_output_handoff.freeze_task_output` reuses `TrustedG2BundleProducer.freeze_and_store`. Caller authentication must occur in an authorized host, outside task JSON. `VerifiedTaskInvocation` is a typed host contract, not an authentication implementation or a GCS provenance attestation.
- Body-authoring handoff contract: schemaVersion=1, report (date/time/report_id/revision), full_text with terminal newline, body_sha256, evidence_ref (object/generation/evidence_id/snapshot_id), frozen_at and scenario_review. Preserve full text and review quote offsets exactly. No Docs-derived substitute, inferred review, historical Evidence reconstruction or deadline extension is allowed.
- Independently configured evidence_reader reads the pinned generation; request-supplied Evidence bytes are ignored. The existing producer validates its exact bytes/hash/time/report/revision and persists G2 create-only. Return g2_ref object/generation/SHA-256, report/revision, Evidence reference and diagnostic invocation identity. Publication and notification remain NOT_RUN.
- Actual task-to-host authentication, callback/output access, installed Apps Script deployment/triggers and Google Docs permissions are UNKNOWN. The official scheduled-task documentation describes schedules/chat context and supported app events, but does not establish this account's task-to-GCS interface: https://learn.chatgpt.com/docs/automations . Therefore live task handoff is BLOCKED_G2_TASK_HANDOFF. No undocumented API or invented task webhook is used.
- Evidence must precede 08:00; review/freeze must remain within 08:00–08:40. The existing issuance CLI continues to enforce ownership and protected production gates. All four configured slots remain apps_script_legacy; weekday 08:00/12:00/16:00/21:00 and no weekend slots are unchanged.
- Isolation: task input -> exact Evidence -> immutable G2 -> fake Docs -> fake canonical/Receipt/Pages -> exact HTMLParser text; UI CI additionally feeds this generated canonical into the real report renderer and Playwright public-mode DOM validator. External stores/adapters remain simulated; this is not TEST ONLY live-service or production proof.
- Local verification: Python 3.13, ten targeted suites (task handoff, pipeline, portal, importer handoff, preflight, G2 handoff/producer, Evidence and WIF read/create-only), 168 tests, 167 PASS / 1 SKIP. Hosted final-head CI and browser DOM remain pending at this record's creation; older head successes are not reused.
- Read-only Environment API: report-publication exists and has a required reviewer, but prevent_self_review=false. Custom branch policy is enabled; exact branch inventory and admin bypass remain unverified. Protected preflight is not ready. Production WIF/IAM/GCS audit principal/Docs write scopes/GitHub write scopes are UNKNOWN; authenticated preflight and production E2E NOT_RUN. No configuration was changed.
