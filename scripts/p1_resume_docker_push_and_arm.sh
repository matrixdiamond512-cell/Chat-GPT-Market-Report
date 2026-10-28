#!/usr/bin/env bash
# Resume P1 one-shot ONLY after safety Scheduler/Workflow smoke has passed.
# Pinned Cloud Run code: 65f9ec608d4d4eb88ad7c7bed5f87d1108c27a3a
set -Eeuo pipefail
P=market-report-p1-shadow
R=asia-northeast1
S=p1-report-shadow-ingress
J=slot-0800-t13
K=p1-one-shot-verification-stop
SHA=65f9ec608d4d4eb88ad7c7bed5f87d1108c27a3a
TAG="asia-northeast1-docker.pkg.dev/$P/p1-report-shadow-images/$S:pr184-${SHA:0:12}"
cd "$HOME/p1-pr184-one-shot"
[[ "$(git rev-parse HEAD)" == "$SHA" && -z "$(git status --porcelain)" ]] || { echo 'ERROR: pinned code mismatch'; exit 1; }
for job in "$J" "$K"; do
  state="$(gcloud scheduler jobs describe "$job" --project="$P" --location="$R" --format='value(state)')"
  echo "$job: $state"
  [[ "$state" == PAUSED ]] || { echo 'ABORT: scheduler is not paused'; exit 1; }
done
[[ "$(TZ=Asia/Tokyo date +%F)" == 2026-10-27 ]] || { echo 'ABORT: 2026-10-28 trial setup date has passed'; exit 1; }
echo '=== Use existing Docker image ==='
docker image inspect "$TAG" >/dev/null || { echo 'ERROR: Docker image not present; do not re-run whole setup'; exit 1; }
echo '=== Retry temporary Artifact Registry connection failures ==='
PUSHED=false
for attempt in 1 2 3 4; do
  if docker push "$TAG"; then PUSHED=true; break; fi
  echo "Artifact Registry push attempt $attempt failed"
  sleep $((attempt * 5))
done
[[ "$PUSHED" == true ]] || { echo 'ERROR: push failed; both jobs remain PAUSED'; exit 1; }
IMAGE="$(docker image inspect "$TAG" --format '{{index .RepoDigests 0}}')"
[[ "$IMAGE" == "asia-northeast1-docker.pkg.dev/$P/p1-report-shadow-images/$S@sha256:"* ]] || { echo 'ERROR: missing immutable image digest'; exit 1; }
echo "Verified image: $IMAGE"
echo '=== Verify Cloud Run security baseline ==='
gcloud run services describe "$S" --project="$P" --region="$R" --format=json > /tmp/p1-run-resume-before.json
jq -e --arg sa "p1-shadow-runtime@$P.iam.gserviceaccount.com" '
 ([.status.conditions[]? | select(.type=="Ready") | .status] | first)=="True"
 and .spec.template.spec.serviceAccountName==$sa
 and ([.spec.template.spec.containers[0].env[]? | select(.name=="SHADOW_STORAGE_ENABLED") | .value] | first)=="false"
 and (.metadata.annotations["run.googleapis.com/invoker-iam-disabled"] // "false")=="false"
' /tmp/p1-run-resume-before.json >/dev/null

gcloud run services update "$S" --project="$P" --region="$R" --image="$IMAGE" --quiet

gcloud run services describe "$S" --project="$P" --region="$R" --format=json > /tmp/p1-run-resume-after.json
jq -e --arg img "$IMAGE" --arg sa "p1-shadow-runtime@$P.iam.gserviceaccount.com" '
 ([.status.conditions[]? | select(.type=="Ready") | .status] | first)=="True"
 and .spec.template.spec.containers[0].image==$img
 and .spec.template.spec.serviceAccountName==$sa
 and ([.spec.template.spec.containers[0].env[]? | select(.name=="SHADOW_STORAGE_ENABLED") | .value] | first)=="false"
 and (.metadata.annotations["run.googleapis.com/invoker-iam-disabled"] // "false")=="false"
' /tmp/p1-run-resume-after.json >/dev/null
diff -u <(jq -S '.spec.template.spec.containers[0].env' /tmp/p1-run-resume-before.json) <(jq -S '.spec.template.spec.containers[0].env' /tmp/p1-run-resume-after.json)
echo '=== Verify safety Scheduler binding ==='
gcloud scheduler jobs describe "$K" --project="$P" --location="$R" --format=json | jq -e --arg sa "p1-one-shot-trigger@$P.iam.gserviceaccount.com" '
 .state=="PAUSED" and .schedule=="50 7 * * 1-5" and .timeZone=="Asia/Tokyo"
 and .httpTarget.oauthToken.serviceAccountEmail==$sa
' >/dev/null
[[ "$(gcloud scheduler jobs describe "$J" --project="$P" --location="$R" --format='value(state)')" == PAUSED ]]

trap 'rc=$?; if ((rc != 0)); then echo "ABORT: stopping both Scheduler jobs"; gcloud scheduler jobs pause "$J" --project="$P" --location="$R" --quiet || true; gcloud scheduler jobs pause "$K" --project="$P" --location="$R" --quiet || true; fi' EXIT

echo '=== Arm watchdog BEFORE primary ==='
gcloud scheduler jobs resume "$K" --project="$P" --location="$R" --quiet
[[ "$(gcloud scheduler jobs describe "$K" --project="$P" --location="$R" --format='value(state)')" == ENABLED ]]
gcloud scheduler jobs resume "$J" --project="$P" --location="$R" --quiet
[[ "$(gcloud scheduler jobs describe "$J" --project="$P" --location="$R" --format='value(state)')" == ENABLED ]]
trap - EXIT

echo 'SUCCESS: P1 one-shot ARMED for 2026-10-28 07:47/07:50 JST (NOT YET VERIFIED)'
echo "Cloud Run image: $IMAGE"
