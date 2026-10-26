#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-plan}"
case "${ACTION}" in plan|apply) ;; *) echo "usage: $0 [plan|apply]" >&2; exit 2;; esac

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="${HERE}/infrastructure/gcp/pre-slot-test"
: "${PROJECT_ID:?Set PROJECT_ID to an existing isolated TEST_ONLY project}"
: "${RUNNER_IMAGE:?Set RUNNER_IMAGE to the Artifact Registry image digest}"

cat > "${TF_DIR}/terraform.tfvars" <<EOF
project_id   = "${PROJECT_ID}"
runner_image = "${RUNNER_IMAGE}"
EOF
chmod 600 "${TF_DIR}/terraform.tfvars"

terraform -chdir="${TF_DIR}" init
terraform -chdir="${TF_DIR}" fmt -check
terraform -chdir="${TF_DIR}" validate
terraform -chdir="${TF_DIR}" plan -out=tfplan
if [[ "${ACTION}" == "apply" ]]; then
  echo "Apply creates only TEST_ONLY resources in ${PROJECT_ID}; review plan and confirm in your own Cloud Shell."
  terraform -chdir="${TF_DIR}" apply tfplan
else
  echo "Plan only. No Google Cloud resources were created."
fi
