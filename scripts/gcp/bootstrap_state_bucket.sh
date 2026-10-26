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

EXPECTED_PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
if [[ ! "${EXPECTED_PROJECT_NUMBER}" =~ ^[0-9]+$ ]]; then
  echo "Could not resolve the TEST_ONLY project's numeric ID; refusing bucket changes." >&2
  exit 1
fi

DESCRIBE_ERROR="$(mktemp)"
trap 'rm -f "${DESCRIBE_ERROR}"' EXIT
BUCKET_EXISTS=false
if BUCKET_PROJECT_NUMBER="$(gcloud storage buckets describe "gs://${TF_STATE_BUCKET}" --format='value(projectNumber)' 2>"${DESCRIBE_ERROR}")"; then
  BUCKET_EXISTS=true
  if [[ ! "${BUCKET_PROJECT_NUMBER}" =~ ^[0-9]+$ ]]; then
    echo "Could not determine the existing bucket owner; refusing all bucket updates." >&2
    exit 1
  fi
  if [[ "${BUCKET_PROJECT_NUMBER}" != "${EXPECTED_PROJECT_NUMBER}" ]]; then
    echo "Refusing to modify gs://${TF_STATE_BUCKET}: owner project number ${BUCKET_PROJECT_NUMBER} does not match TEST_ONLY project ${PROJECT_ID} (${EXPECTED_PROJECT_NUMBER})." >&2
    exit 1
  fi
elif ! grep -Eqi '(^|[^0-9])404([^0-9]|$)|NOT_FOUND|not found|does not exist' "${DESCRIBE_ERROR}"; then
  echo "Could not safely determine whether the state bucket exists; refusing creation or updates." >&2
  exit 1
fi

gcloud services enable storage.googleapis.com --project "${PROJECT_ID}"
if [[ "${BUCKET_EXISTS}" != true ]]; then
  gcloud storage buckets create "gs://${TF_STATE_BUCKET}" \
    --project "${PROJECT_ID}" --location "${LOCATION}" \
    --uniform-bucket-level-access --public-access-prevention
  BUCKET_PROJECT_NUMBER="$(gcloud storage buckets describe "gs://${TF_STATE_BUCKET}" --format='value(projectNumber)')"
  if [[ "${BUCKET_PROJECT_NUMBER}" != "${EXPECTED_PROJECT_NUMBER}" ]]; then
    echo "New state bucket owner does not match the TEST_ONLY project; refusing further changes." >&2
    exit 1
  fi
fi
gcloud storage buckets update "gs://${TF_STATE_BUCKET}" \
  --uniform-bucket-level-access --public-access-prevention --versioning

echo "State bucket configured: gs://${TF_STATE_BUCKET}"
echo "Verify its project, IAM (operator only), public-access prevention, UBLA and versioning before Terraform init."
