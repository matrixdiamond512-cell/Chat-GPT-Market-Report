#!/usr/bin/env bash
# PR206 TEST_ONLY Cloud Run read-only preflight. No builds, GCP writes or Job executions.
set -euo pipefail

PROJECT="market-report-test-only"
REGION="${PR206_REGION:-asia-northeast1}"
EXPECTED_SHEET="1C0U7JXZT7DMDvDSL8Ah9uVfLhncnCOffIgKl3n8Hk-w"
BRANCH="codex/close-acquisition-p0-20261116"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ROOT="${PR206_PREFLIGHT_OUTPUT_DIR:-$HOME/pr206-test-only-preflight}"
OUTPUT="$ROOT/$STAMP"
umask 077
mkdir -p "$OUTPUT"
fail() { printf 'BLOCKED: %s\n' "$*" >&2; exit 2; }

command -v gcloud >/dev/null 2>&1 || fail "gcloud CLI unavailable; no cloud changes performed"
command -v git >/dev/null 2>&1 || fail "git unavailable"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
LOCAL_BRANCH="$(git branch --show-current)"
[[ "$LOCAL_BRANCH" == "$BRANCH" ]] || fail "wrong branch: $LOCAL_BRANCH; expected $BRANCH"
LOCAL_HEAD="$(git rev-parse HEAD)"
if [[ -n "${PR206_EXPECTED_SHA:-}" && "$LOCAL_HEAD" != "$PR206_EXPECTED_SHA" ]]; then
  fail "HEAD is $LOCAL_HEAD, not expected $PR206_EXPECTED_SHA"
fi
[[ -z "$(git status --porcelain)" ]] || fail "worktree is not clean; do not build from mixed/dirty source"
grep -qF "TEST_ONLY_SPREADSHEET_ID = \"$EXPECTED_SHEET\"" scripts/cloud_run_market_close_job.py \
  || fail "PR206 allowlisted spreadsheet mismatch"
grep -qF "TEST_ONLY_SPREADSHEET_ID = \"$EXPECTED_SHEET\"" scripts/sync_market_close_sheet.py \
  || fail "close sync sheet allowlist mismatch"
grep -qF 'ALLOWED_PROJECT = "market-report-test-only"' scripts/cloud_run_market_close_job.py \
  || fail "project allowlist mismatch"
test -f Dockerfile.market-close-test-only || fail "missing TEST_ONLY Dockerfile"

ACTIVE="$(gcloud auth list --filter='status:ACTIVE' --format='value(account)' 2>/dev/null || true)"
[[ -n "$ACTIVE" ]] || fail "no active gcloud identity"
printf 'AUTH active identity: present (address omitted)\n'
printf 'PROJECT allowlist: %s\n' "$PROJECT"
printf 'REGION: %s\n' "$REGION"
printf 'PR206 branch: %s\n' "$LOCAL_BRANCH"
printf 'PR206 HEAD: %s\n' "$LOCAL_HEAD"
printf 'PR206 isolated sheet: %s\n' "$EXPECTED_SHEET"

# Only read-only gcloud operations. Never change active gcloud project.
gcloud projects describe "$PROJECT" --format='json(projectId,projectNumber,lifecycleState)' > "$OUTPUT/project.json" \
  || fail "cannot read isolated project"
gcloud run jobs list --project="$PROJECT" --region="$REGION" --format=json > "$OUTPUT/cloud-run-jobs.json" \
  || fail "cannot list isolated jobs"
gcloud artifacts repositories list --project="$PROJECT" --location="$REGION" --format=json > "$OUTPUT/artifact-repositories.json" \
  || printf 'WARN: artifact repository inventory not readable\n'
gcloud scheduler jobs list --project="$PROJECT" --location="$REGION" --format=json > "$OUTPUT/scheduler-jobs.json" \
  || printf 'WARN: scheduler inventory not readable\n'
gcloud storage buckets list --project="$PROJECT" --format=json > "$OUTPUT/buckets.json" \
  || printf 'WARN: bucket inventory not readable\n'

# Private backups outside git; never print specs or service account env values.
gcloud run jobs list --project="$PROJECT" --region="$REGION" \
  --format='value(metadata.name)' | while IFS= read -r job; do
    case "$job" in
      mr-close-sheet-*|mr-pre-slot-*)
        gcloud run jobs describe "$job" --project="$PROJECT" --region="$REGION" --format=json \
          > "$OUTPUT/job-$job.json" || fail "failed to back up Job $job"
        printf 'BACKED_UP_JOB %s\n' "$job"
        ;;
    esac
  done
printf '%s\n' "$LOCAL_HEAD" > "$OUTPUT/pr206-head.txt"
printf '%s\n' "$PROJECT" > "$OUTPUT/project-id.txt"
printf '%s\n' "$EXPECTED_SHEET" > "$OUTPUT/sheet-id.txt"
printf '%s\n' "$STAMP" > "$OUTPUT/preflight-utc.txt"
(
  cd "$OUTPUT"
  for filename in ./*.json; do
    [[ -f "$filename" ]] && sha256sum "$filename"
  done
) > "$OUTPUT/backup-sha256.txt"

echo "PREFLIGHT_READ_ONLY_OK"
echo "Private local backup directory: $OUTPUT"
echo "NOT_RUN: image build / Job update / Job execution / Scheduler."
echo "Never overwrite existing mr-close-sheet-pr204-e2e."
