#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to an existing isolated TEST_ONLY project}"
REGION="${REGION:-asia-northeast1}"
REPOSITORY="${AR_REPOSITORY:-market-report-test-only}"
IMAGE_TAG="${IMAGE_TAG:-pre-slot-$(git rev-parse --short HEAD)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/runner:${IMAGE_TAG}"

gcloud services enable artifactregistry.googleapis.com cloudbuild.googleapis.com --project "${PROJECT_ID}"
gcloud artifacts repositories describe "${REPOSITORY}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "${REPOSITORY}" --repository-format=docker --location "${REGION}" --project "${PROJECT_ID}" --description="Isolated market report TEST_ONLY runner"
gcloud builds submit --project "${PROJECT_ID}" --region "${REGION}" --tag "${IMAGE}" \
  --file infrastructure/gcp/pre-slot-test/Dockerfile .
DIGEST="$(gcloud artifacts docker images describe "${IMAGE}" --project "${PROJECT_ID}" --format='value(image_summary.digest)')"
printf 'Built image: %s@%s\n' "${IMAGE%:*}" "${DIGEST}"
printf 'Set runner_image to the digest URL above in terraform.tfvars.\n'
