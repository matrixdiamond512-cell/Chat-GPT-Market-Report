#!/usr/bin/env bash
# P1 isolated Shadow: deploy patched Cloud Run and Workflow, leaving BOTH jobs PAUSED.
# No Scheduler resume, no report publication, no GCS application writes.
set -Eeuo pipefail
P="market-report-p1-shadow"
R="asia-northeast1"
S="p1-report-shadow-ingress"
J="slot-0800-t13"
K="p1-one-shot-verification-stop"
WF="p1-one-shot-verification"
SHA="dad4c972dfbd263d44bca1d0976510b394f3beb4"
DIR="$HOME/p1-pr184-one-shot"
REG="asia-northeast1-docker.pkg.dev/$P/p1-report-shadow-images"
TAG="$REG/$S:p1-fix-${SHA:0:12}"
RT="p1-shadow-runtime@$P.iam.gserviceaccount.com"
WFA="p1-one-shot-supervisor@$P.iam.gserviceaccount.com"
for exe in gcloud git jq mktemp cp; do command -v "$exe" >/dev/null; done
[[ -d "$DIR/.git" ]] || { echo "ERROR: expected checkout $DIR missing"; exit 2; }
cd "$DIR"
[[ -z "$(git status --porcelain)" ]] || { echo "ABORT: local Git tree dirty"; exit 2; }
git fetch origin codex/p1-one-shot-auto-verify-20261027 --quiet
git checkout --detach "$SHA" --quiet
[[ "$(git rev-parse HEAD)" == "$SHA" ]] || { echo "ABORT: source commit mismatch"; exit 2; }
echo "Pinned source: $SHA"
assert_paused() {
  local job state
  for job in "$J" "$K"; do
    state="$(gcloud scheduler jobs describe "$job" --project="$P" --location="$R" --format='value(state)')"
    echo "$job=$state"
    [[ "$state" == PAUSED ]] || { echo "ABORT: $job is not PAUSED"; exit 1; }
  done
}
assert_paused
echo '=== Verify existing Cloud Run safety settings ==='
gcloud run services describe "$S" --project="$P" --region="$R" --format=json >/tmp/p1-fix-run-before.json
jq -e --arg sa "$RT" '
  ([.status.conditions[]? | select(.type=="Ready") | .status] | first)=="True"
  and .spec.template.spec.serviceAccountName==$sa
  and ([.spec.template.spec.containers[0].env[]? |
       select(.name=="SHADOW_STORAGE_ENABLED") | .value] | first)=="false"
  and (.metadata.annotations["run.googleapis.com/invoker-iam-disabled"] // "false")=="false"
' /tmp/p1-fix-run-before.json >/dev/null
echo '=== Deploy new safety Workflow, then run paused-only smoke ==='
gcloud workflows deploy "$WF" --project="$P" --location="$R" \
  --source=cloud/workflows/p1-one-shot-auto-verify.yaml \
  --service-account="$WFA" --quiet --format='value(revisionId)'
ARGS="$(jq -nc --arg p "$P" \
  --arg j "projects/$P/locations/$R/jobs/$J" \
  --arg k "projects/$P/locations/$R/jobs/$K" \
  --arg s "$S" --arg id "$J" \
  '{project_id:$p,target_job:$j,watchdog_job:$k,cloud_run_service:$s,expected_job_id:$id}')"
gcloud workflows run "$WF" --project="$P" --location="$R" \
  --data="$ARGS" --format=json >/tmp/p1-fix-workflow-smoke.json
jq -e '
  .state=="SUCCEEDED"
  and (.result | fromjson |
       .targetSchedulerState=="PAUSED"
       and .watchdogSchedulerState=="PAUSED"
       and .checks.targetPauseReadback=="PASS"
       and .checks.watchdogPauseReadback=="PASS")
' /tmp/p1-fix-workflow-smoke.json >/dev/null
assert_paused
echo '=== Remote Cloud Build (minimal Docker build context) ==='
CTX="$(mktemp -d)"
trap 'rm -rf "$CTX"' EXIT
mkdir -p "$CTX/config" "$CTX/scripts"
cp Dockerfile requirements-p1-cloudrun.txt "$CTX/"
cp config/report_schedule.json "$CTX/config/"
for f in resolve_market_report_slot report_continuity_shadow report_continuity_gcs report_continuity_ingress run_report_continuity_service p1_trial_fixture_provider; do
  cp "scripts/$f.py" "$CTX/scripts/"
done
gcloud builds submit "$CTX" --project="$P" --region="$R" \
  --tag="$TAG" --timeout=1200s --quiet
IMAGE="$(gcloud artifacts docker images describe "$TAG" \
  --project="$P" --format='value(image_summary.fully_qualified_digest)')"
[[ "$IMAGE" == "$REG/$S@sha256:"* ]] || { echo 'ABORT: invalid image digest'; exit 1; }
echo "Image digest: $IMAGE"
assert_paused
echo '=== Update Cloud Run image, do not alter environment/identity ==='
gcloud run services update "$S" --project="$P" --region="$R" --image="$IMAGE" --quiet
gcloud run services describe "$S" --project="$P" --region="$R" --format=json >/tmp/p1-fix-run-after.json
jq -e --arg img "$IMAGE" --arg sa "$RT" '
  ([.status.conditions[]? | select(.type=="Ready") | .status] | first)=="True"
  and .spec.template.spec.containers[0].image==$img
  and .spec.template.spec.serviceAccountName==$sa
  and ([.spec.template.spec.containers[0].env[]? |
       select(.name=="SHADOW_STORAGE_ENABLED") | .value] | first)=="false"
  and (.metadata.annotations["run.googleapis.com/invoker-iam-disabled"] // "false")=="false"
' /tmp/p1-fix-run-after.json >/dev/null
diff -u <(jq -S '.spec.template.spec.containers[0].env' /tmp/p1-fix-run-before.json) \
        <(jq -S '.spec.template.spec.containers[0].env' /tmp/p1-fix-run-after.json)
assert_paused
echo 'SUCCESS: patched Workflow and Cloud Run deployed; BOTH Schedulers remain PAUSED'
echo 'NOT ARMED: the next 07:47 trial requires a separate, controlled action.'
echo "CODE=$SHA IMAGE=$IMAGE"
