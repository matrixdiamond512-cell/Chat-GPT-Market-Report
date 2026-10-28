# P1 one-shot Scheduler auto-verification runbook

Status: PREPARATION_ONLY. No workflow, Scheduler job, service account, IAM binding, API, deployment, or Storage object was created or changed by this change.

## Objective and one-shot sequence

Use the existing project, existing slot-0800-t13 Scheduler job, existing Cloud Run ingress, and existing bucket. The primary job remains PAUSED until the approved initial setup is complete.

1. On an approved weekday, the operator resumes the already configured primary slot-0800-t13 job once. Do not use 'gcloud scheduler jobs run'; that is a manual/off-schedule trigger and cannot prove the normal 07:47 Cron time.
2. Cloud Scheduler performs its ordinary 07:47 JST call with its fixed request body and OIDC token.
3. The independent p1-one-shot-verification-stop safety job starts the p1-one-shot-verification Cloud Workflow at 07:50 JST.
4. The workflow first pauses the primary Scheduler job, retries the pause/read pair up to three times, and reads the job back. It pauses its own safety job only after the primary readback is PAUSED; otherwise it leaves the watchdog enabled and reports a blocked stop.
5. After both pause/readback checks, the workflow reads the 07:45–07:52 JST Cloud Run log window and evaluates the request's HTTP status, OIDC stage, exact job allowlist result, scheduled-time result, Scheduler last-attempt status/time, log availability, and both PAUSED readbacks.
6. The workflow returns the structured result and writes the same JSON record to Cloud Logging. No Storage write is used.

This separates the control-plane safety path from the report acquisition handler. A report processor failure does not prevent the independent workflow from pausing the primary Scheduler job.

## Result contract

- PASS: HTTP 200; OIDC, job name and 07:47 JST schedule checks pass for today's expected run; Scheduler attempt is current and successful; logs were read; both Scheduler jobs read back PAUSED.
- FAIL: an attempt was observed and the HTTP, OIDC, job, time, or Scheduler result explicitly failed. The stop readbacks are reported separately.
- BLOCKED: the primary job or watchdog could not be read back as PAUSED. The watchdog remains enabled if the primary pause was not confirmed.
- INCOMPLETE: the primary was stopped, but a required attempt/log/stage was missing or unreadable, so a pass cannot be established.

The previous manual trigger result (400 SCHEDULE_NOT_ALLOWED) is a known time-validation failure and must never count as the normal scheduled run.

## Initial setup — only after separate approval

Cloud changes are intentionally not part of implementation or CI. Before applying, confirm that PR #182 and this stacked PR are the intended source and that the existing job is still paused. Do not create a project, bucket, budget, or duplicate the reported JPY 800 budget alert.

Required new items:

- API: workflows.googleapis.com (enable only after approval; Cloud Scheduler, Cloud Logging, Cloud Run and Storage were already listed enabled in the owner's readback).
- Workflow: p1-one-shot-verification, in asia-northeast1, using the checked-in definition at ../cloud/workflows/p1-one-shot-auto-verify.yaml.
- Safety job: p1-one-shot-verification-stop, schedule 50 7 * * 1-5, timezone Asia/Tokyo; OAuth 2.0 to the Workflows Executions API. Configure three bounded retries, maximum retry duration 10 minutes, and a 30-second HTTP attempt deadline. Its fixed body passes the existing project, primary job resource name, safety job resource name, expected short job ID and Cloud Run service name.
- Dedicated service accounts: p1-one-shot-supervisor for Workflows and p1-one-shot-trigger for the safety Scheduler job.

Least-privilege IAM plan:

- Workflow runtime identity: custom role with only cloudscheduler.jobs.pause and cloudscheduler.jobs.get, conditionally scoped to the two named Scheduler jobs where supported; logging.logEntries.list to read the Cloud Run request/application logs; and logging.logEntries.create to emit the structured result.
- Scheduler caller identity: workflows.executions.create on this one Workflow (for example, a resource-level roles/workflows.invoker binding).
- Setup operator: temporary deployment permissions only as needed to enable the API, create the two service accounts and resources, and grant the listed bindings. Do not grant project Owner or Editor to either runtime identity.
- No added Cloud Run IAM binding, Cloud Run deploy, GCS write permission, bucket change, or Storage write is needed for this safety workflow.

For the approved initial setup, deploy the Workflow, create the safety job in PAUSED state, read back its target/schedule/auth/retry settings and IAM, then resume the safety job. Resume the existing primary job once only after the safety path is confirmed. No later Cloud Shell action is expected on the normal PASS/FAIL path; inspect the workflow execution result or its structured Cloud Logging record.

Do not manually run or resume the target after the automated result. If the result is BLOCKED, do not allow another weekday primary run; restore the approved stop permissions/control path before any retry.

## Rollback

Pause the primary job and the safety job and read both states back. Leave the existing Cloud Run service, bucket, evidence and budget unchanged. If the new workflow and job are removed after a separately approved cleanup, retain their execution/log records according to the existing Cloud Logging retention policy. Never delete or overwrite evidence to make the verification appear successful.

## Verification limits

CI tests the offline status contract, log-stage events, fixed-body two-date ingress behavior, fractional Scheduler timestamp normalization, and the ordering of the checked-in safety workflow. It cannot prove Cloud Workflows API acceptance, IAM conditions, Cloud Scheduler delivery timing, Cloud Logging query permissions, or deployed image/runtime behavior. Those remain an approved external trial.


## 2026-10-28 JST real one-shot outcome (P1 SHADOW ONLY)

The approved 2026-10-28 07:47/07:50 trial was armed and executed, then
both Scheduler jobs were paused by the independent watchdog Workflow.
**This trial did NOT pass the full P1 ingress acceptance test.**

- Scheduler `slot-0800-t13` logged `AttemptStarted` and `AttemptFinished`
  around 07:47:10 JST; the finish event reported `INVALID_ARGUMENT`,
  `Original HTTP response code number = 400`.
- Cloud Run `p1-report-shadow-ingress` logged one `P1_INGRESS_RESULT`
  with `reason=SCHEDULE_NOT_ALLOWED`, `oidcResult=PASS`,
  `jobNameResult=PASS`, `scheduleTimeResult=FAIL`.
- The configured POST method, `Content-Type: application/json`, and the
  fixed 41-byte trigger body matched the contract.
- Watchdog job started at 07:50, invoked Workflow successfully, and both
  Scheduler jobs were read back `PAUSED`; Workflow `result=INCOMPLETE`
  because no successful schedule-bound Cloud Run ingress log existed.
- The primary job can show `lastAttemptTime=null`, `status.code=-1`
  after pausing **even though Cloud Scheduler's durable logs confirm the
  07:47 attempt**. Do not infer a missing run from that readback.
- The exact value of the incoming `X-CloudScheduler-ScheduleTime` header
  was not recorded, so the specific subreason for the 400 is not known.

### Fixes prepared in GitHub — not yet applied to GCP

1. The ingress accepts RFC3339 schedule times with nonzero UTC offsets
   (convert to UTC before calculating the 08:00 report slot), still rejecting
   malformed/future/off-minute/unauthorized schedule data.
2. Failed schedule validation now writes only enumerated
   `scheduleRejectCode` and `scheduleHeaderPresent` to Cloud Logging,
   **never** the raw header, OIDC token, or principal identity.
3. The safety Workflow reads Cloud Scheduler's `AttemptFinished` entries,
   scoped by job ID and expected 07:47 time, rather than requiring
   `lastAttemptTime` and `status.code` which may be reset by pause.
   It still requires one exact ingress log, HTTP 200, all stage PASS
   and both PAUSED readbacks; duplicate/failed attempts are rejected.
4. The read-only audit script also relies on `AttemptFinished` logs.

This source change and offline CI alone do not prove the live defect is fixed.
**Do not rearm the recurring Cron or rerun the whole setup** without a new
controlled single-day trial plan, cloud-side deployment/verification of
the patched image and Workflow, and a working safety stop. Keep both
Scheduler jobs PAUSED until that separate approved trial. No production
report, Google Drive publication, canonical/latest, or GCS evidence writes
may be enabled as part of this retry.
