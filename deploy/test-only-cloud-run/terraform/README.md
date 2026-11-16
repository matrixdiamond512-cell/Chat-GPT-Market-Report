# TEST ONLY 08:00 independent Evidence watchdog

This configuration creates exactly one authenticated Cloud Run watchdog, one weekday 07:57 JST Scheduler job, two dedicated service accounts, and read-only GCS/Cloud Logging access. It does not create a producer, write or seed Evidence, create a bucket, send notifications, or touch production resources.

## Guardrails

- The project ID must end in `-test-only`; the region is fixed to `asia-northeast1`.
- The only bucket allowed is the pre-existing private bucket `market-report-test-only-mr-pre-slot-test-evidence`.
- The watchdog reads the exact 08:00 ledger prefix for the report ID, then follows each verified ledger attempt ID into that attempt's Evidence prefix. It pins every object generation, validates the JSON contract and cutoff, and checks the content SHA-256 encoded in the Evidence object name.
- Runtime GCS read access is IAM-conditioned to `test-only/08-00/ledger/` and `test-only/08-00/evidence/`. No create, update, delete, Docs, GitHub, Pages, or notification permission is granted.
- Cloud Run requires IAM authentication. Only the dedicated Scheduler caller receives `roles/run.invoker` on this service.
- The only job is `mr-watchdog-0800`, weekdays at 07:57 JST. It is paused by default. No past date is replayed.
- Notification fields are log-only; no Monitoring notification channel is created.

## Prepare and review

Build the image from the reviewed PR head and push it to the already-approved TEST ONLY Artifact Registry repository. Pin its immutable digest in the Terraform input. Review the plan before applying; the plan must contain exactly one Cloud Run service, one Scheduler job, two service accounts, one invoker binding, and two read-only IAM grants. Do not use the existing producer image unless its digest is proven to contain the reviewed watchdog code.

Plan with `terraform -chdir=deploy/test-only-cloud-run/terraform plan -out=test-only.tfplan -var="project_id=market-report-test-only" -var="test_only_bucket=market-report-test-only-mr-pre-slot-test-evidence" -var="container_image=REGION-docker.pkg.dev/PROJECT/REPOSITORY/watchdog@sha256:DIGEST"`.

Apply once with the Scheduler paused. After reviewing service identity, immutable image, audience, invoker, bucket condition and log access, a separately approved apply can set `enable_scheduler_jobs=true`. Reconcile existing job state and evidence generation before any retry.

## Verification boundary

The CI workflow runs adapter contract tests and Terraform formatting/validation without cloud credentials. CI does not prove deployment, Scheduler OIDC, live GCS access, or a watchdog execution. A real E2E pass requires a future 08:00 pre-slot acquisition, the independent 07:57 OIDC invocation, and readback of its Cloud Run response/logs. `READY_FOR_DRAFT` is Evidence readiness only, not report publication.
