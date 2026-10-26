#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-plan}" != "plan" || "$#" -gt 1 ]]; then
  echo "usage: $0 [plan]  # apply is intentionally not supported by this script" >&2
  exit 2
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="${HERE}/infrastructure/gcp/pre-slot-test"
: "${PROJECT_ID:?Set PROJECT_ID to an existing isolated TEST_ONLY project}"
: "${RUNNER_IMAGE:?Set RUNNER_IMAGE to the Artifact Registry image digest}"
: "${TF_STATE_BUCKET:?Set TF_STATE_BUCKET to the private versioned TEST_ONLY state bucket}"

case "${PROJECT_ID,,}" in *prod*|*production*) echo "Refusing a production-looking project ID." >&2; exit 2;; esac
if [[ "${RUNNER_IMAGE}" != *@sha256:* ]]; then
  echo "RUNNER_IMAGE must be pinned by immutable sha256 digest." >&2
  exit 2
fi

cat > "${TF_DIR}/terraform.tfvars" <<EOF
project_id   = "${PROJECT_ID}"
runner_image = "${RUNNER_IMAGE}"
EOF
chmod 600 "${TF_DIR}/terraform.tfvars"

terraform -chdir="${TF_DIR}" init \
  -backend-config="bucket=${TF_STATE_BUCKET}" \
  -backend-config="prefix=market-report-pre-slot-test/state"
terraform -chdir="${TF_DIR}" fmt -check
terraform -chdir="${TF_DIR}" validate
terraform -chdir="${TF_DIR}" plan -out=tfplan
terraform -chdir="${TF_DIR}" show -no-color tfplan

echo "PLAN ONLY: no cloud resources were created or changed."
echo "After separate human approval and plan review only, an authorized operator may run:"
echo "  terraform -chdir=infrastructure/gcp/pre-slot-test apply tfplan"
