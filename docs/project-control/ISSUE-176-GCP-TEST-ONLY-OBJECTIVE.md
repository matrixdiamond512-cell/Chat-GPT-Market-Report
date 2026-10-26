# Issue #176 — isolated Google Cloud TEST_ONLY runner

## PRIMARY OBJECTIVE

Provide a reproducible, deployable isolated TEST_ONLY runner that starts from authenticated Scheduler invocations, performs a real fresh 08:00 market acquisition, freezes the exact source into a private immutable evidence object, and proves exact readback before the 08:00 deadline.

## ACCEPTANCE CRITERIA

- Cloud Scheduler's 07:47/07:53/07:57 JST attempts call an authenticated Cloud Run Service using OIDC and distinct allowlisted caller identities.
- The first application handler timestamp is recorded as actual start; delay greater than 60 seconds fails closed.
- The runner calls existing full market acquisition and existing report-slot evidence construction, preserving the 15-minute freshness and strict 08:00 cutoff.
- Identity, snapshot/source hashes, evidence identity, generation and exact readback are recorded for one attempt.
- The private GCS sink is create-only for evidence, readback pins the exact generation, attempts are deduplicated, and TEST_ONLY objects expire after 14 days.
- The execution identity has no Docs, GitHub, Drive, or publication credentials. TEST_ONLY never invokes those integrations.
- Cloud Shell build/deploy scripts and Terraform can reproduce the resources in an existing isolated project.
- Offline positive and negative contract tests plus Terraform validation pass.
- External normal/abnormal E2E is reported separately and is not inferred from offline tests.

## CONSTRAINTS

PR #183 remains OPEN/Draft/unmerged; PR #97 is untouched and remains Draft. Do not modify main, deploy production, write to production Google Drive, relax freshness/start-delay/cutoff gates, or report fixtures as real market data. Cloud resource creation requires a separate human action in an isolated project. Do not use GitHub Actions timing as a substitute for actual runner-start measurement.

## FORBIDDEN SUBSTITUTE

A Terraform plan, unit test, mocked OIDC/GCS adapter, Docker build, or CI success is not external scheduler delivery, real market-source acquisition, GCS readback, or 14-day lifecycle evidence.

## OPEN OUTCOMES

- O-1: Runner/container/Terraform/Cloud Shell artifacts and CI contracts — implemented; hosted CI pending.
- O-2: Human selects isolated billed GCP project, permissions, image build and resource apply — BLOCKED pending external setup.
- O-3: External 07:47/07:53/07:57 normal and abnormal E2E with actual start-lag and GCS evidence — NOT_RUN pending O-2.
- O-4: Observe a GCS object through 14-day lifecycle deletion — NOT_RUN.
- O-5: Terraform sets the isolated TEST_ONLY project's `_Default` Cloud Logging bucket to 14 days; observed deletion remains NOT_RUN pending external setup.
- O-6: Any production connection/deployment — OUT OF SCOPE.
