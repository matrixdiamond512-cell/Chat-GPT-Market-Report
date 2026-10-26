#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to a dedicated isolated TEST_ONLY project}"
: "${TF_STATE_BUCKET:?Set TF_STATE_BUCKET to a globally unique, TEST_ONLY-only bucket name}"
LOCATION="${TF_STATE_LOCATION:-asia-northeast1}"

if [[ "${PROJECT_ID}" =~ (prod|production) ]]; then
  echo "Refusing a project ID that appears to be production." >&2
  exit 2
fi
if [[ "${TF_STATE_BUCKET}" =~ [A-Z_] || ${#TF_STATE_BUCKET} -lt 3 ]]; then
  echo "TF_STATE_BUCKET must be a valid lowercase GCS bucket name." >&2
  exit 2
fi

gcloud services enable storage.googleapis.com --project "${PROJECT_ID}"
if ! gcloud storage buckets describe "gs://${TF_STATE_BUCKET}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${TF_STATE_BUCKET}" \
    --project "${PROJECT_ID}" --location "${LOCATION}" \
    --uniform-bucket-level-access --public-access-prevention
fi
gcloud storage buckets update "gs://${TF_STATE_BUCKET}" \
  --uniform-bucket-level-access --public-access-prevention --versioning

echo "State bucket configured: gs://${TF_STATE_BUCKET}"
echo "Verify its project, IAM (operator only), public-access prevention, UBLA and versioning before Terraform init."
