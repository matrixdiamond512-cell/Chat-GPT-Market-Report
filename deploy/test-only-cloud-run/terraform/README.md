# TEST ONLY Cloud Scheduler → Cloud Run

This Terraform is a **deployment candidate** for an isolated TEST ONLY project. It creates four slot-specific producer services, four independent watchdog services, eight invocation service accounts, two runtime service accounts, eight Cloud Scheduler jobs, conditional GCS IAM, Cloud Logging metrics, and notification-free Monitoring alert policies. It never creates or changes a production resource.

## Guardrails

- The project ID must end in `-test-only`; the location is fixed to `asia-northeast1`.
- The bucket must be the pre-approved `market-report-test-only-mr-pre-slot-test-evidence`. Terraform only reads its metadata and adds prefix-conditioned IAM members; it never creates the bucket.
- GCS access is limited to `test-only/scheduler-e2e/inputs/` and `test-only/scheduler-e2e/evidence/`. Producers can read inputs, read evidence and create evidence. They receive no object delete permission. Watchdogs can only read evidence and TEST ONLY logs.
- Scheduler invocation accounts are separate for each service, with `roles/run.invoker` on only their matching service.
- Run services are internal-ingress, require IAM authentication, have no minimum instances, and cap at two instances.
- Scheduled jobs are created **paused by default**. Setting `enable_scheduler_jobs=true` explicitly unpauses all eight. A controlled test must use a future, approved TEST ONLY slot and seeded TEST ONLY input. Do not backfill a real historical production slot.
- The pinned input must already exist. This configuration does not seed GCS data, publish an image, deploy, create IAM, or enable APIs until an operator runs Terraform. Those actions require separate explicit authorization.

## Build and plan

Build the image from the repository root and push it to an already-approved TEST ONLY Artifact Registry repository. Then use the immutable image digest, never a mutable tag.

```powershell
docker build -f deploy/test-only-cloud-run/Dockerfile -t REGION-docker.pkg.dev/PROJECT/REPOSITORY/evidence:BUILD .
docker push REGION-docker.pkg.dev/PROJECT/REPOSITORY/evidence:BUILD
terraform -chdir=deploy/test-only-cloud-run/terraform init
terraform -chdir=deploy/test-only-cloud-run/terraform plan -out=test-only.tfplan -var="project_id=DEDICATED-test-only" -var="test_only_bucket=market-report-test-only-mr-pre-slot-test-evidence" -var="container_image=REGION-docker.pkg.dev/PROJECT/REPOSITORY/evidence@sha256:DIGEST"
```

Review the plan for only the resources listed above. Apply while jobs remain paused. After verifying principals, audiences, service revisions, GCS prefix IAM and an approved future test slot/input, a separately authorized second apply can use `-var="enable_scheduler_jobs=true"`. Reconcile job state and the object generation before any retry after uncertain writes.

## API and IAM prerequisites

APIs managed by this configuration: Cloud Run, Cloud Scheduler, IAM, IAM Credentials, Cloud Logging, Cloud Monitoring and Cloud Storage. The applying principal needs project-level service-usage, Cloud Run, Scheduler, service-account, Logging/Monitoring and conditional bucket IAM administration rights. The Cloud Scheduler service agent must have its Google-managed service-agent role. The caller must have `iam.serviceAccounts.actAs` on each Scheduler identity. No key files are used. Do not grant project Editor/Owner to the runtime identities.

## Cost estimate (USD, 2026-11-11)

Assumption: 4 weekday report slots × 20 weekdays/month, one producer and one watchdog request per slot, up to 45 seconds per request, 1 vCPU / 0.5 GiB, eight Scheduler jobs, <=0.5 GiB container image, and a TEST ONLY evidence corpus <=1 GiB. Uses current published rates and excludes tax, currency conversion, billing-account usage already consuming free tier, API enabling side effects, and abnormal retry storms.

- Cloud Scheduler: 8 jobs, 3 free per billing account, 5 billable × $0.10/job/31 days = **$0.50/month**. If all three free jobs are already consumed, eight billable jobs total **$0.80/month**.
- Cloud Run request-based ceiling at the assumption: about 7,200 vCPU-seconds and 3,600 GiB-seconds/month; at Tokyo Tier 1 rates ($0.000024/vCPU-second and $0.0000025/GiB-second), about **$0.36/month** before the shared monthly free allotments (180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests). Expected cost is $0 when those shared allowances remain available; otherwise $0.36 is the estimate.
- Existing GCS bucket: 1 GiB retained standard data is about **$0.02/month** at the Tokyo rate; 1,000 standard Class A and 1,000 Class B operations are about **$0.0054**. Actual Evidence objects are expected to be much smaller; retained-object growth is unbounded unless separately governed.
- Artifact Registry: first 0.5 GiB per billing account is free; above that, published storage pricing is approximately $0.10/GiB-month. Assumed image fits in free allotment.
- Cloud Logging: first 50 GiB/project/month is free; default log retention and Cloud Monitoring standard metrics/alerts are assumed within included quota. No notification channels are configured.

Therefore the rough monthly service estimate is **$0.50–$0.75** under the stated profile, or **$0.80–$1.05** if the Scheduler and compute free allotments are already consumed. Actual charges depend on existing billing-account use and retries. Re-check the calculator before apply: https://cloud.google.com/products/calculator

## Verification boundary

Run unit/fixture tests and `terraform fmt -check`, `terraform init -backend=false`, `terraform validate` in CI. A successful plan or CI does not prove a deployed OIDC invocation or GCS write/readback. No service is deployed by this repository change. The current runtime evidence is limited to the separate successful WIF read-only GitHub Actions job; actual Cloud Scheduler → Cloud Run → GCS save/readback → independent Watchdog is still **BLOCKED_TEST_ENV_APPROVAL / NOT_RUN**.
