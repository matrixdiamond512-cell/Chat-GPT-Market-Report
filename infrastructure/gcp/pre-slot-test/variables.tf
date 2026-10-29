variable "project_id" {
  description = "Existing, billing-enabled TEST_ONLY project. Never use the production project."
  type        = string
}

variable "region" {
  description = "Co-located Cloud Run, Scheduler, Artifact Registry, and GCS region."
  type        = string
  default     = "asia-northeast1"
}

variable "resource_prefix" {
  description = "Lowercase unique prefix for isolated TEST_ONLY resources."
  type        = string
  default     = "mr-pre-slot-test"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{5,25}$", var.resource_prefix))
    error_message = "Use 6-26 lowercase letters, digits, and hyphens."
  }
}

variable "runner_image" {
  description = "Immutable Artifact Registry image digest built from this PR branch."
  type        = string
}

variable "trigger_secret_id" {
  description = "Secret Manager secret ID; Terraform creates metadata only, never secret data."
  type        = string
  default     = "market-report-test-only-trigger-hmac"
}

variable "enable_test_scheduler" {
  description = "Enable only after base infrastructure review; creates the three TEST_ONLY 07:47/07:53/07:57 JST jobs."
  type        = bool
  default     = false
}
