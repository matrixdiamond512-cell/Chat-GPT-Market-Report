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

## Cloud Shell setup, TEST_ONLY execution and readback

### Responsibility boundary

- **Codex/CI can do now:** edit this PR branch; build and start the Docker image in GitHub Actions; run offline contract tests; run Terraform fmt/init-without-backend/validate; inspect the Terraform source for IAM and storage invariants. This does not create cloud resources or prove a real plan.
- **Human must do in Google Cloud:** create and select a dedicated TEST_ONLY project, attach billing and a budget alert, authorize Cloud Shell, bootstrap the state bucket, review the real plan, and separately approve any apply. Human also adds the secret value and observes the scheduled execution. Codex has no connected GCP account/Cloud Shell credential in this task.
- Never use the production project. No apply, production deployment, Docs/GitHub/Drive writes, or main changes are performed by this PR task.

### Architecture and state

Cloud Scheduler → authenticated Cloud Run **Service** → existing acquisition/evidence path → private GCS. A synchronous authenticated Service lets the handler record its actual first-instruction start time and return a result; a Cloud Run Job would need asynchronous execution polling/correlation before it could prove the <=60-second start gate. Neither choice guarantees Scheduler latency, so late starts still fail closed. GitHub Actions cron is not a timing substitute.

Terraform remote state uses a separate GCS bucket in the dedicated TEST_ONLY project, with uniform bucket-level access, public access prevention, and object versioning. The state bucket is bootstrapped separately before Terraform init and is not the evidence bucket. The evidence bucket itself does not enable Object Versioning: GCS generation numbers still support exact-generation readback for a live object, while avoiding archived generations that could outlast the 14-day cleanup policy. Its soft-delete retention is set to zero and lifecycle deletion is configured at 14 days; lifecycle execution is asynchronous, so actual deletion still needs a separate runtime observation. Grant state access only to the human/operator identity; the Cloud Run and Scheduler identities receive no state access. Do not put secret payloads in tfvars or Terraform: Terraform creates Secret Manager metadata only. .gitignore excludes tfvars, plans, state and .terraform/.

### Ordered setup and first scheduled readback

Replace the example values with the dedicated TEST_ONLY project and unique bucket name. Do not copy secret values into commands or logs.

1. **Human — project and billing.** In Google Cloud Console create/select a dedicated project whose ID is not production; attach billing; create a budget alert; confirm the project contains no unrelated workloads. The 14-day _Default log retention setting is project-wide.
2. **Human — Cloud Shell identity and checkout.**
   ~~~~sh
   gcloud auth login
   export PROJECT_ID='your-dedicated-test-only-project'
   export REGION='asia-northeast1'
   export TF_STATE_BUCKET='your-globally-unique-test-only-tfstate-bucket'
   gcloud config set project "$PROJECT_ID"
   test "$(gcloud config get-value project)" = "$PROJECT_ID"
   git clone --branch codex/issue-176-0800-upstream-recovery https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report.git
   cd Chat-GPT-Market-Report
   ~~~~
   **Codex can prepare the branch and CI; only a human with project access can authenticate Cloud Shell.**
3. **Human — bootstrap remote Terraform state.**
   ~~~~sh
   scripts/gcp/bootstrap_state_bucket.sh
   gcloud storage buckets describe "gs://$TF_STATE_BUCKET" --format='yaml(name,location,iamConfiguration,versioning)'
   ~~~~
   Check public access prevention, uniform access, versioning, and bucket IAM (intended operator/state administrators only). Do not grant the runner or Scheduler access to this bucket. The separate evidence bucket is not versioned, but every write captures and reads back its live generation.
4. **Human — build and pin the image.** Ensure the operator has Cloud Build and Artifact Registry permissions in this TEST_ONLY project.
   ~~~~sh
   export IMAGE_TAG="pre-slot-$(git rev-parse --short HEAD)"
   PROJECT_ID="$PROJECT_ID" REGION="$REGION" IMAGE_TAG="$IMAGE_TAG" scripts/gcp/build_test_image.sh
   export RUNNER_IMAGE='asia-northeast1-docker.pkg.dev/PROJECT/market-report-test-only/runner@sha256:REPLACE_WITH_PRINTED_DIGEST'
   ~~~~
   The script submits the repository root (.) as build context. cloudbuild.yaml selects the existing Dockerfile. It never relies on unsupported gcloud builds submit --file.
5. **Human — generate and review a real plan; no apply yet.**
   ~~~~sh
   export TF_STATE_BUCKET
   PROJECT_ID="$PROJECT_ID" RUNNER_IMAGE="$RUNNER_IMAGE" TF_STATE_BUCKET="$TF_STATE_BUCKET" scripts/gcp/deploy_test_only.sh plan
   terraform -chdir=infrastructure/gcp/pre-slot-test show -no-color tfplan
   ~~~~
   Confirm the plan targets only the dedicated TEST_ONLY project and documented Scheduler, Cloud Run, Secret Manager metadata, private evidence bucket, IAM, APIs and 14-day logging retention. Reject any unrelated/prod target or broad write permission. The script accepts only plan; it cannot apply. A real plan requires the human-provisioned project, credentials, state bucket and provider access, so CI does not fabricate one.
6. **Human — separate apply approval.** Applying requires a later, explicit approval after the exact plan is reviewed. Only the authorized human operator may then run:
   ~~~~sh
   terraform -chdir=infrastructure/gcp/pre-slot-test apply tfplan
   ~~~~
   This is a documented future step, not executed by Codex. Re-run and review a fresh plan if the saved plan is stale.
7. **Human — add the TEST_ONLY HMAC secret after resource creation.**
   ~~~~sh
   umask 077
   head -c 48 /dev/urandom > /tmp/market-report-hmac
   gcloud secrets versions add market-report-test-only-trigger-hmac --data-file=/tmp/market-report-hmac
   shred -u /tmp/market-report-hmac
   ~~~~
   Do not put the value in Git, shell history, Terraform variables/state, CI output, or this chat. Restrict secret access to the runner service account as defined in Terraform.
8. **Human — inspect the deployed configuration before waiting for a weekday run.**
   ~~~~sh
   gcloud run services describe mr-pre-slot-test --region "$REGION" --project "$PROJECT_ID" --format='yaml(status.url,metadata.annotations,spec.template.spec.serviceAccountName)'
   gcloud scheduler jobs list --location "$REGION" --project "$PROJECT_ID"
   gcloud storage buckets describe "gs://$PROJECT_ID-mr-pre-slot-test-evidence" --project "$PROJECT_ID" --format='yaml(iamConfiguration,versioning,lifecycle)'
   ~~~~
   Verify no unauthenticated allUsers invoker, each scheduler caller matches the Cloud Run invoker binding and OIDC audience, evidence bucket public prevention/UBLA, 14-day lifecycle and soft-delete=0 are correct, and runner has no Docs/GitHub/main/Drive/publication or Terraform-state permissions.
9. **Human — observe a real scheduled TEST_ONLY attempt.** Wait for a weekday 07:47, 07:53, or 07:57 JST job; do not use a later/other-slot snapshot as substitute. Record Scheduler scheduled time and Cloud Run actualStartAt, startLagSeconds, report ID, source/snapshot hashes, evidence bucket/object/generation and exact readback status from the same response/log event. A start delay over 60 seconds, stale source, cutoff breach, duplicate, or mismatch must remain blocked.
   ~~~~sh
   gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="mr-pre-slot-test"' --project "$PROJECT_ID" --freshness=2d --limit=30 --format=json
   ~~~~
10. **Human — independently re-read the exact object generation.** Copy bucket, object, generation and evidenceSha256 from the same successful runner result; install the pinned GCP runtime dependencies if absent.
    ~~~~sh
    python -m pip install -r scripts/gcp/requirements.txt
    python scripts/gcp/verify_test_only_object.py \
      --bucket 'TEST_ONLY_BUCKET' \
      --object 'test-only/08-00/evidence/ATTEMPT_ID/EVIDENCE_ID.json' \
      --generation 'GENERATION_FROM_RUN' \
      --sha256 'EVIDENCE_SHA256_FROM_RUN'
    ~~~~
    Expected result is PASS_EXACT_GENERATION_READBACK with the same SHA-256. A mismatch is FAIL and must not be retried by overwriting; keep the object quarantined until lifecycle cleanup.
11. **Codex — review, if requested.** Share only nonsecret plan output, sanitized logs and the readback result. Codex can correlate them against this PR and report observed scope; it cannot claim an external E2E until those records exist.

### Required operator permissions

The temporary setup operator needs project-level Service Usage Admin, Cloud Run Admin, Cloud Scheduler Admin, Service Account Admin/User, Project IAM Admin and IAM Role Admin, Logging Config Writer, Secret Manager Admin, Storage Admin, Artifact Registry Admin and Cloud Build Editor. Narrow these to the TEST_ONLY project and bucket wherever supported. Cloud Build's service agent needs Artifact Registry Writer for the test repository. At runtime, Scheduler identities receive Cloud Run Invoker only; the runner receives access to the one secret and the evidence bucket's custom create/get/delete role. No runtime Docs, GitHub, Drive, publisher or state permissions are granted.

## Cost estimate (USD, indicative)

Assume 3 fixed Scheduler jobs, 23 weekday executions each/month (69 requests), Cloud Run 1 vCPU/1 GiB, 1-3 minutes/request, small JSON evidence, and no min instances:
- Cloud Scheduler: 3 jobs are within the current 3-job-per-billing-account free allowance; otherwise `$0.10/job/31 days` applies.
- Cloud Run: raw usage at current published rates is approximately `$0.08-$0.25/month` for 69-207 vCPU-minutes plus 1-3 GiB memory, before the shared free tier; normally within the listed monthly CPU/memory free allowances if unused elsewhere.
- Secret Manager: one active version and about 69 accesses/month are within the published six-version/10,000-access free limits if unused elsewhere.
- GCS: evidence and ledger volume should remain in MB; regional storage, operations, Artifact Registry image storage, Cloud Build, logs and internet egress depend on actual usage. Set a billing budget and alert; free tiers are shared by billing account and are not a spend cap.

Prices can change; check the [Cloud Run](https://cloud.google.com/run/pricing), [Cloud Scheduler](https://cloud.google.com/scheduler/pricing), [Secret Manager](https://cloud.google.com/secret-manager/pricing), and [Cloud Storage](https://cloud.google.com/storage/pricing) prices before applying.

## Verification boundaries / known limitations

- Unit tests and Terraform static validation do not prove Cloud Scheduler timing, IAM, market source reachability, Secret Manager, GCS generation readback, lifecycle deletion or cost.
- External E2E is NOT_RUN until the operator provisions the isolated project and records actual execution evidence. GCS lifecycle deletion is also NOT_RUN until a created object has aged through the 14-day lifecycle (or a controlled bucket test validates it); lifecycle execution is asynchronous.
- Three staggered jobs make three independent acquisition attempts, not a promise of run-at-08:00. A real handler start beyond 60 seconds, acquisition at/after cutoff, stale source, duplicate attempt, wrong caller, bad token, hash mismatch, write/readback mismatch, or after-cutoff readback fails closed.
- Cloud Run Service scale-to-zero may introduce cold start; the <=60-second gate observes it. If real start delay exceeds 60 seconds, do not weaken the gate. Evaluate minimum instances (with added idle cost) or a dedicated always-on runner as a separately approved design.
- Container internet egress is needed for the existing market sources. Their reachability/rate limits are not guaranteed by this code. TEST_ONLY retains source identities/status, and existing acquisition validation rejects unavailable or stale required values.
- The ingress currently captures market acquisition and immutable snapshot evidence only. It does not generate the full report body/Docs receipt/manifest or run the infographic renderer. Those remain downstream gates and out of the Cloud-only pre-slot capture scope.
