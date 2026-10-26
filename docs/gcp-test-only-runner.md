# PR #183 — Google Cloud TEST_ONLY runner

## Scope and state

This is an isolated pre-slot acquisition/evidence runner. It is not a production scheduler, report writer, renderer, or publisher. It calls the existing `scripts/run_market_data_acquisition.py --slot 08:00 --mode full`, then reuses `execute_test_only_capture`, `build_slot_evidence`, the 15-minute freshness contract, the strict 08:00 cutoff, create-only storage and exact readback. It never calls Docs, GitHub main, Drive, or publication code. The container starts with a clean `data/market` directory to prevent reuse of a prior run's values.

No Google Cloud project or resource was created or deployed in this change. External runtime E2E is BLOCKED pending a human-provisioned TEST_ONLY project and credentials.

## Service choice

Cloud Run Service is used because Cloud Scheduler can make a synchronous authenticated HTTP request and the app can record the first handler timestamp, reject starts more than 60 seconds after the Scheduler time, and return the capture/readback result. Cloud Run Jobs are better suited to longer batch executions, but Scheduler starts Jobs through a control-plane API and execution is asynchronous; actual container start must then be polled and correlated. That additional polling path is unnecessary for this short, request-bounded capture and would complicate the <=60-second start gate. This choice does not guarantee Scheduler delivery latency: every request remains fail-closed.

Scheduler OIDC authenticates the HTTP request. Each of the three jobs uses its own caller service account, exact `X-CloudScheduler-JobName` allowlist entry, and Cloud Run invoker IAM binding. The Scheduler uses an explicit custom audience configured on the Run service, avoiding a self-referential service-URI setting. The app verifies the OIDC signature, audience and email, then creates a short-lived internal HMAC request and passes it through PR #183's existing signed trigger contract. Scheduler does not create the HMAC itself; the trusted, authenticated ingress adapter bridges the two contracts. The actual start is the first handler instruction, never the scheduled timestamp.

## Schedules and data flow

Three weekday jobs in `Asia/Tokyo` call the same private-evidence service:

| Scheduler time | Purpose |
| --- | --- |
| 07:47 JST | First TEST_ONLY acquisition/evidence attempt |
| 07:53 JST | Independent new attempt if no earlier success |
| 07:57 JST | Last pre-cutoff attempt; strict 08:00 cutoff still applies |

Each attempt has a deterministic identity from exact Scheduler job name and schedule time. GCS create-only ledger claims prevent duplicate retries; collisions block. The acquisition subprocess runs full mode in a clean disposable container filesystem. It freezes the resulting raw source bytes using existing evidence code, writes under `test-only/08-00`, reads the exact GCS generation back, verifies all existing source/context/snapshot hashes and freshness, and checks the cutoff again. If the cutoff is crossed after the write, only that exact object generation is deleted; failure to clean up leaves a quarantined TEST_ONLY object that expires under the bucket's 14-day lifecycle. No such evidence is publishable.

The bucket has uniform access, enforced public-access prevention and a 14-day lifecycle. Writes use GCS generation-match zero; readback pins the generation. The runner identity has Secret Accessor for only the HMAC secret and a project custom role bound to only the dedicated bucket with object create/get/delete (no object update permission). It has no Docs, GitHub, Drive, or publication credentials. Scheduler identities have only Cloud Run Invoker. The runner's one-instance/concurrency configuration plus durable per-attempt ledger prevents duplicate acquisition.

## Build / Cloud Shell setup

Use a new or explicitly TEST_ONLY existing project with billing enabled; never select the production project. Required human actions:
1. Select a project and region `asia-northeast1`; enable billing and verify no production Drive/GitHub credentials are present.
2. Install/authorize `gcloud` and Terraform >=1.6 in Google Cloud Shell. The operator needs Service Usage Admin, Cloud Run Admin, Cloud Scheduler Admin, Service Account Admin, Service Account User on the runtime and caller identities, Project IAM Admin for bindings, IAM Role Admin to create the project custom role, Logging Config Writer for the 14-day log bucket, Secret Manager Admin, Storage Admin, Artifact Registry Admin, and Cloud Build Editor. The Cloud Build service agent needs Artifact Registry Writer on the image repository. Prefer a temporary setup operator; runtime identities remain narrowly scoped.
3. Clone this PR branch in Cloud Shell. Run `scripts/gcp/build_test_image.sh` with `PROJECT_ID`. Pin the published image by digest (not mutable tag) into a private `terraform.tfvars`.
4. Run `scripts/gcp/deploy_test_only.sh plan`; inspect all resources and the target project. Only after explicit human review run `apply`.
5. Add a random HMAC secret of at least 32 bytes to the Secret Manager secret Terraform created. Do not put it in Git, shell history, Terraform variables/state, output, or this chat. Example using an ephemeral local file in Cloud Shell: `umask 077; head -c 48 /dev/urandom > /tmp/market-report-hmac; gcloud secrets versions add market-report-test-only-trigger-hmac --data-file=/tmp/market-report-hmac; shred -u /tmp/market-report-hmac`.
6. Confirm the service has no unauthenticated invoker, the bucket is private, APIs/IAM/job names match outputs, and the project has no production access. Confirm one Scheduler execution at a time and billing alert.
7. Terraform sets the isolated project's Cloud Logging `_Default` bucket retention to 14 days; this applies to every default-bucket log in that project, so do not use a project with unrelated workloads. At the first approved weekday, inspect Cloud Scheduler attempt logs, Cloud Run structured logs, GCS object generation and pinned readback. Record scheduled time, actual handler start, lag seconds, generatedAt, reportId/revision, sourceHash, snapshotHash, object generation, and readback result. Run each abnormal test using a separate TEST_ONLY fixture/endpoint in the isolated project; do not edit production identities.

`deploy_test_only.sh plan` is the default and creates no cloud resources. `apply` requires the operator to choose it explicitly. Terraform creates Secret Manager metadata only; secret payload remains an external human operation. It creates no Docs, Drive, GitHub or publication integration.

## Cost estimate (USD, indicative)

Assume 3 fixed Scheduler jobs, 23 weekday executions each/month (69 requests), Cloud Run 1 vCPU/1 GiB, 1-3 minutes/request, small JSON evidence, and no min instances:
- Cloud Scheduler: 3 jobs are within the current 3-job-per-billing-account free allowance; otherwise `$0.10/job/31 days` applies.
- Cloud Run: raw usage at current published rates is approximately `$0.08-$0.25/month` for 69-207 vCPU-minutes plus 1-3 GiB memory, before the shared free tier; normally within the listed monthly CPU/memory free allowances if unused elsewhere.
- Secret Manager: one active version and about 69 accesses/month are within the published six-version/10,000-access free limits if unused elsewhere.
- GCS: evidence and ledger volume should remain in MB; regional storage, operations, Artifact Registry image storage, Cloud Build, logs and internet egress depend on actual usage. Set a billing budget and alert; free tiers are shared by billing account and are not a spend cap.

Prices can change; check the [Cloud Run](https://cloud.google.com/run/pricing), [Cloud Scheduler](https://cloud.google.com/scheduler/pricing), [Secret Manager](https://cloud.google.com/secret-manager/pricing), and [Cloud Storage](https://cloud.google.com/storage/pricing) prices before applying.

## Verification boundaries / known limitations

- Unit tests and Terraform static validation do not prove Cloud Scheduler timing, IAM, market source reachability, Secret Manager, GCS generation readback, lifecycle deletion or cost.
- External E2E is NOT_RUN until the operator provisions the isolated project and records actual execution evidence. GCS's 14-day deletion is also NOT_RUN until a created object has aged through the lifecycle (or a controlled bucket test validates it).
- Three staggered jobs make three independent acquisition attempts, not a promise of run-at-08:00. A real handler start beyond 60 seconds, acquisition at/after cutoff, stale source, duplicate attempt, wrong caller, bad token, hash mismatch, write/readback mismatch, or after-cutoff readback fails closed.
- Cloud Run Service scale-to-zero may introduce cold start; the <=60-second gate observes it. If real start delay exceeds 60 seconds, do not weaken the gate. Evaluate minimum instances (with added idle cost) or a dedicated always-on runner as a separately approved design.
- Container internet egress is needed for the existing market sources. Their reachability/rate limits are not guaranteed by this code. TEST_ONLY retains source identities/status, and existing acquisition validation rejects unavailable or stale required values.
- The ingress currently captures market acquisition and immutable snapshot evidence only. It does not generate the full report body/Docs receipt/manifest or run the infographic renderer. Those remain downstream gates and out of the Cloud-only pre-slot capture scope.
