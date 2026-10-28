#!/usr/bin/env bash
# P1 shadow: arm only the 2026-10-29 JST trial (not the weekday recurring cron).
# Run only on 2026-10-29 before 07:00 JST. This script NEVER manually runs a job.
set -Eeuo pipefail

P="market-report-p1-shadow"
R="asia-northeast1"
S="p1-report-shadow-ingress"
WF="p1-one-shot-verification"
J="slot-0800-t13"
K="p1-one-shot-verification-stop"
EXPECTED_IMAGE="asia-northeast1-docker.pkg.dev/$P/p1-report-shadow-images/$S@sha256:48269b72737c3aa1a27a45025708c7fad8dcea0b8e7f168edc83c9187cdcd8d2"
CHECK_DATE="2026-10-29"
J_CRON="47 7 29 10 *"
K_CRON="50 7 29 10 *"

check_time() {
  local d t
  d="$(TZ=Asia/Tokyo date +%F)"
  t="$(TZ=Asia/Tokyo date +%H%M)"
  [[ "$d" == "$CHECK_DATE" && "$t" < "0700" ]] || {
    echo "ABORT: only 2026-10-29 before 07:00 JST is approved for arming"
    return 1
  }
}
read_job() {
  gcloud scheduler jobs describe "$1" --project="$P" --location="$R" --format=json
}
check_paused() {
  local job state
  for job in "$J" "$K"; do
    state="$(gcloud scheduler jobs describe "$job" --project="$P" --location="$R" --format='value(state)')"
    echo "$job: $state"
    [[ "$state" == "PAUSED" ]] || {
      echo "ABORT: job must already be PAUSED: $job"
      return 1
    }
  done
}
check_time
check_paused

echo '=== Confirm patched Cloud Run and Workflow (no mutations) ==='
gcloud run services describe "$S" --project="$P" --region="$R" --format=json >/tmp/p1-1029-run.json
jq -e --arg image "$EXPECTED_IMAGE" --arg sa "p1-shadow-runtime@$P.iam.gserviceaccount.com" '
  ([.status.conditions[]? | select(.type=="Ready") | .status] | first)=="True"
  and .spec.template.spec.containers[0].image==$image
  and .spec.template.spec.serviceAccountName==$sa
  and ([.spec.template.spec.containers[0].env[]? |
      select(.name=="SHADOW_STORAGE_ENABLED") | .value] | first)=="false"
  and (.metadata.annotations["run.googleapis.com/invoker-iam-disabled"] // "false")=="false"
' /tmp/p1-1029-run.json >/dev/null || {
  echo "ABORT: patched Cloud Run image or safety settings do not match"
  exit 1
}

gcloud workflows describe "$WF" --project="$P" --location="$R" --format=json >/tmp/p1-1029-workflow.json
jq -e --arg sa "p1-one-shot-supervisor@$P.iam.gserviceaccount.com" '
   .revisionId=="000007-d46" and .state=="ACTIVE"
   and (.serviceAccount | endswith("/serviceAccounts/"+$sa))
' /tmp/p1-1029-workflow.json >/dev/null || {
  echo "ABORT: patched watchdog Workflow revision or runtime identity mismatch"
  exit 1
}

echo '=== Save and validate both PAUSED Scheduler configurations ==='
read_job "$J" >/tmp/p1-1029-primary-before.json
read_job "$K" >/tmp/p1-1029-watchdog-before.json
jq -e --arg sa "p1-0800-t13-invoker@$P.iam.gserviceaccount.com" '
  .state=="PAUSED" and .schedule=="47 7 * * 1-5"
  and .timeZone=="Asia/Tokyo"
  and .httpTarget.httpMethod=="POST"
  and .httpTarget.oidcToken.serviceAccountEmail==$sa
  and (.httpTarget.body | @base64d)=="{\"schemaVersion\":1,\"trigger\":\"P1_SHADOW\"}"
' /tmp/p1-1029-primary-before.json >/dev/null || {
  echo "ABORT: primary Scheduler differs from verified baseline"
  exit 1
}
jq -e --arg sa "p1-one-shot-trigger@$P.iam.gserviceaccount.com" '
  .state=="PAUSED" and .schedule=="50 7 * * 1-5"
  and .timeZone=="Asia/Tokyo"
  and .httpTarget.httpMethod=="POST"
  and .httpTarget.oauthToken.serviceAccountEmail==$sa
  and (.httpTarget.uri | endswith("/workflows/p1-one-shot-verification/executions"))
' /tmp/p1-1029-watchdog-before.json >/dev/null || {
  echo "ABORT: watchdog Scheduler differs from verified baseline"
  exit 1
}

echo '=== Date-scope both cron jobs to October 29 (annual at most) ==='
# Annual rather than weekday cron prevents tomorrow's unintended re-invocation
# even if the automatic pause fails. Both jobs are PAUSED during updates.
gcloud scheduler jobs update http "$J" --project="$P" --location="$R" \
  --schedule="$J_CRON" --quiet >/dev/null
gcloud scheduler jobs update http "$K" --project="$P" --location="$R" \
  --schedule="$K_CRON" --quiet >/dev/null
read_job "$J" >/tmp/p1-1029-primary-after.json
read_job "$K" >/tmp/p1-1029-watchdog-after.json

jq -e --arg cron "$J_CRON" '.state=="PAUSED" and .schedule==$cron' /tmp/p1-1029-primary-after.json >/dev/null
jq -e --arg cron "$K_CRON" '.state=="PAUSED" and .schedule==$cron' /tmp/p1-1029-watchdog-after.json >/dev/null
for item in primary watchdog; do
  diff -u \
    <(jq -S '{timeZone,httpTarget,retryConfig,attemptDeadline}' "/tmp/p1-1029-${item}-before.json") \
    <(jq -S '{timeZone,httpTarget,retryConfig,attemptDeadline}' "/tmp/p1-1029-${item}-after.json")
done

check_time
check_paused

# If any resume/readback fails, immediately return both jobs to PAUSED.
fail_safe() {
  local rc="$?"
  if (( rc != 0 )); then
    echo "ERROR: arming failed; pausing BOTH Scheduler jobs"
    gcloud scheduler jobs pause "$J" --project="$P" --location="$R" --quiet || true
    gcloud scheduler jobs pause "$K" --project="$P" --location="$R" --quiet || true
  fi
}
trap fail_safe EXIT
echo '=== Arm safety watchdog FIRST, then primary ==='
gcloud scheduler jobs resume "$K" --project="$P" --location="$R" --quiet
[[ "$(gcloud scheduler jobs describe "$K" --project="$P" --location="$R" --format='value(state)')" == "ENABLED" ]]
gcloud scheduler jobs resume "$J" --project="$P" --location="$R" --quiet
[[ "$(gcloud scheduler jobs describe "$J" --project="$P" --location="$R" --format='value(state)')" == "ENABLED" ]]
trap - EXIT

echo 'ARMED: P1 isolated trial for 2026-10-29 07:47/07:50 JST (NOT YET VERIFIED)'
echo 'Cron limited to October 29; expected automatic PAUSED for both jobs by 07:55 JST.'
echo 'No production publication or SHADOW_STORAGE_ENABLED change.'
