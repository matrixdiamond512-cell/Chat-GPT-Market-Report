#!/usr/bin/env bash
# Issue #205 / PR #206 isolated Cloud Run TEST_ONLY one-shot.
# Starts with a read-only preflight. To make any cloud changes, an operator must
# explicitly set PR206_APPLY_TEST_ONLY=YES and pin PR206_EXPECTED_SHA.
# NEVER targets production, PR204 job, Scheduler, IAM bindings or formal Docs.
set -euo pipefail
PROJECT="market-report-test-only"
REGION="asia-northeast1"
REPOSITORY="market-report-test-only"
JOB="mr-close-acquisition-pr206-e2e"
SA="mr-pre-slot-test-runner@market-report-test-only.iam.gserviceaccount.com"
SHEET="1C0U7JXZT7DMDvDSL8Ah9uVfLhncnCOffIgKl3n8Hk-w"

fail() { printf 'BLOCKED: %s\n' "$*" >&2; exit 2; }
command -v gcloud >/dev/null 2>&1 || fail "gcloud is unavailable"
command -v git >/dev/null 2>&1 || fail "git is unavailable"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."
test -n "$(printenv PR206_EXPECTED_SHA || true)" || fail "set PR206_EXPECTED_SHA to reviewed full PR206 commit SHA"
HEAD="$(git rev-parse HEAD)"
test "$HEAD" = "$PR206_EXPECTED_SHA" || fail "HEAD does not match expected reviewed commit"
test "$(git branch --show-current)" = "codex/close-acquisition-p0-20261116" || fail "wrong branch"
test -z "$(git status --porcelain)" || fail "working tree is dirty"
test -n "$(printenv PR206_EVIDENCE_BUCKET || true)" || fail "set PR206_EVIDENCE_BUCKET to an existing TEST_ONLY-only bucket"
case "$PR206_EVIDENCE_BUCKET" in
  market-report-test-only-*) ;;
  *) fail "evidence bucket must start with market-report-test-only-" ;;
esac
# Also checks fixed Sheets allowlists and backs up existing TEST_ONLY job specs
# privately outside git. It never deploys or alters infrastructure.
PR206_EXPECTED_SHA="$HEAD" bash scripts/pr206_test_only_preflight.sh
gcloud iam service-accounts describe "$SA" --project="$PROJECT" --format="value(email)" >/dev/null \
  || fail "TEST_ONLY service account is not readable"
gcloud artifacts repositories describe "$REPOSITORY" --project="$PROJECT" --location="$REGION" --format="value(format)" \
  | grep -Fxq DOCKER || fail "expected existing Docker Artifact Registry repository is not available"
gcloud storage buckets describe "gs://$PR206_EVIDENCE_BUCKET" --format="value(name)" >/dev/null \
  || fail "dedicated TEST_ONLY evidence bucket is not available"
gcloud run jobs list --project="$PROJECT" --region="$REGION" --format="value(metadata.name)" \
  | grep -Fxq "$JOB" && fail "PR206 job already exists; never replace it without separate review"
printf 'PREFLIGHT_READY project=%s job=%s head=%s\n' "$PROJECT" "$JOB" "$HEAD"
if [ "$(printenv PR206_APPLY_TEST_ONLY || true)" != "YES" ]; then
  echo "NOT_RUN: image build, Job deploy/execute, Sheets persistence, GCS evidence, Scheduler."
  echo "To authorize only the isolated one-shot, set PR206_APPLY_TEST_ONLY=YES."
  exit 0
fi
# Post-cutoff manual test only: it cannot establish an on-time 07:50 schedule.
CURRENT_HHMM="$(TZ=Asia/Tokyo date +%H%M)"
test "$CURRENT_HHMM" -ge 0800 || fail "manual-late E2E may only run after 08:00 JST"
umask 077
OUT="$HOME/pr206-test-only-e2e/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"
printf '%s\n' "$HEAD" > "$OUT/code-sha.txt"
printf '%s\n' "$PR206_EVIDENCE_BUCKET" > "$OUT/evidence-bucket.txt"
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT
# Explicit isolated build context: do not ship .git, untracked data or secrets.
cp -R scripts config "$BUILD_DIR/"
cp Dockerfile.market-close-test-only "$BUILD_DIR/Dockerfile"
TAG="$REGION-docker.pkg.dev/$PROJECT/$REPOSITORY/close-acquisition-pr206-e2e:$HEAD"
echo "Building isolated PR206 code, no production image/job changes..."
gcloud builds submit "$BUILD_DIR" --tag="$TAG" --project="$PROJECT" --quiet | tee "$OUT/cloud-build.txt"
DIGEST="$(gcloud artifacts docker images describe "$TAG" --project="$PROJECT" --format='value(image_summary.digest)')"
[[ "$DIGEST" =~ ^sha256:[a-f0-9]{64}$ ]] || fail "cannot resolve immutable image digest"
IMMUTABLE="$REGION-docker.pkg.dev/$PROJECT/$REPOSITORY/close-acquisition-pr206-e2e@$DIGEST"
printf '%s\n' "$IMMUTABLE" > "$OUT/image-digest.txt"
# Recheck uniqueness after build to avoid an unreviewed replacement.
gcloud run jobs list --project="$PROJECT" --region="$REGION" --format="value(metadata.name)" \
  | grep -Fxq "$JOB" && fail "Job appeared during build; stop without overwrite"
gcloud run jobs create "$JOB" --image="$IMMUTABLE" --project="$PROJECT" --region="$REGION" \
  --service-account="$SA" --tasks=1 --parallelism=1 --max-retries=0 --task-timeout=900s \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT,MARKET_CLOSE_ENVIRONMENT=TEST_ONLY,MARKET_CLOSE_TEST_ONLY_EVIDENCE_BUCKET=$PR206_EVIDENCE_BUCKET,MARKET_CLOSE_TEST_ONLY_LATE_RUN=1" \
  --quiet | tee "$OUT/job-create.txt"
gcloud run jobs describe "$JOB" --project="$PROJECT" --region="$REGION" --format=json > "$OUT/job-after.json"
echo "Starting one late-manual TEST_ONLY execution; never represents 07:50 success."
gcloud run jobs execute "$JOB" --project="$PROJECT" --region="$REGION" --wait --quiet \
  --update-env-vars="MARKET_CLOSE_TEST_ONLY_LATE_RUN=1" 2>&1 | tee "$OUT/execution.txt"
gcloud run jobs executions list --job="$JOB" --project="$PROJECT" --region="$REGION" --format=json \
  > "$OUT/executions.json"
gcloud storage ls -l "gs://$PR206_EVIDENCE_BUCKET/close-acquisition/" > "$OUT/gcs-evidence-objects.txt"
echo "RUNTIME_ATTEMPT_FINISHED: inspect Sheets independently, GCS generation/hash and 28-item audit before E4/E5 PASS."
echo "PRIVATE_EVIDENCE_DIR: $OUT"
echo "NOT_RUN: Scheduler; production; PR merge; fixed Docs."
