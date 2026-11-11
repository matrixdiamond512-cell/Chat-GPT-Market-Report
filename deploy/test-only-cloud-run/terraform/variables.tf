variable "project_id" {
  description = "Dedicated TEST ONLY Google Cloud project. Must be named with a -test-only suffix."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}-test-only$", var.project_id))
    error_message = "project_id must be a dedicated project whose ID ends in -test-only."
  }
}
variable "region" {
  description = "Cloud Run and Cloud Scheduler location."
  type        = string
  default     = "asia-northeast1"
  validation {
    condition     = var.region == "asia-northeast1"
    error_message = "This TEST ONLY deployment is pinned to the Tokyo region."
  }
}
variable "test_only_bucket" {
  description = "Existing approved TEST ONLY bucket. Terraform never creates or replaces it."
  type        = string
  validation {
    condition     = var.test_only_bucket == "market-report-test-only-mr-pre-slot-test-evidence"
    error_message = "Only the approved TEST ONLY bucket is allowed."
  }
}
variable "test_only_prefix" {
  description = "Isolated TEST ONLY object namespace."
  type        = string
  default     = "test-only/scheduler-e2e"
  validation {
    condition     = var.test_only_prefix == "test-only/scheduler-e2e"
    error_message = "Only the dedicated scheduler-e2e TEST ONLY prefix is allowed."
  }
}
variable "container_image" {
  description = "Previously built container image pinned by immutable SHA-256 digest."
  type        = string
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.container_image))
    error_message = "container_image must end in @sha256:<64 lowercase hex characters>."
  }
}
variable "enable_scheduler_jobs" {
  description = "Explicitly unpause all eight TEST ONLY Scheduler jobs after approval. Defaults to false."
  type        = bool
  default     = false
}
variable "max_instances" {
  description = "Maximum instances per Cloud Run service."
  type        = number
  default     = 2
  validation {
    condition     = var.max_instances >= 1 && var.max_instances <= 3
    error_message = "max_instances must be between 1 and 3."
  }
}
