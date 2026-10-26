#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to an existing isolated TEST_ONLY project}"
REGION="${REGION:-asia-northeast1}"
REPOSITORY="${AR_REPOSITORY:-market-report-test-only}"
IMAGE_TAG="${IMAGE_TAG:-pre-slot-$(git rev-parse --short HEAD)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/runner:${IMAGE_TAG}"
CONFIG="infrastructure/gcp/pre-slot-test/cloudbuild.yaml"

if [[ ! -f "${CONFIG}" || ! -f "infrastructure/gcp/pre-slot-test/Dockerfile" ]]; then
  echo "Run this script from the repository root; Cloud Build config or Dockerfile is missing." >&2
  exit 2
fi

gcloud services enable artifactregistry.googleapis.com cloudbuild.googleapis.com --project "${PROJECT_ID}"
gcloud artifacts repositories describe "${REPOSITORY}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "${REPOSITORY}" --repository-format=docker --location "${REGION}" --project "${PROJECT_ID}" --description="Isolated market report TEST_ONLY runner"

# The final "." is intentionally the repository-root build context. The config
# selects the existing Dockerfile; gcloud builds submit has no --file option.
gcloud builds submit --project "${PROJECT_ID}" --region "${REGION}" \
  --config "${CONFIG}" --substitutions="_IMAGE=${IMAGE}" .
DIGEST="$(gcloud artifacts docker images describe "${IMAGE}" --project "${PROJECT_ID}" --format='value(image_summary.digest)')"
if [[ -z "${DIGEST}" ]]; then
  echo "Artifact Registry did not return an immutable image digest." >&2
  exit 1
fi
printf 'Built image: %s@%s\n' "${IMAGE%:*}" "${DIGEST}"
printf 'Export RUNNER_IMAGE=%s@%s (digest-pinned)\n' "${IMAGE%:*}" "${DIGEST}"
