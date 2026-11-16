variable "project_id" {
  description = "Dedicated TEST ONLY Google Cloud project. Must end in -test-only."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}-test-only$", var.project_id))
    error_message = "project_id must end in -test-only."
  }
}

variable "region" {
  description = "Cloud Run and Cloud Scheduler location."
  type        = string
  default     = "asia-northeast1"
  validation {
    condition     = var.region == "asia-northeast1"
    error_message = "This TEST ONLY deployment is pinned to Tokyo."
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
  description = "Legacy runtime configuration guard; live reader uses fixed 08:00 prefixes."
  type        = string
  default     = "test-only/scheduler-e2e"
  validation {
    condition     = var.test_only_prefix == "test-only/scheduler-e2e"
    error_message = "Unexpected TEST ONLY runtime prefix."
  }
}

variable "container_image" {
  description = "Container image containing the updated watchdog adapter, pinned by immutable digest."
  type        = string
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.container_image))
    error_message = "container_image must end in @sha256:<64 lowercase hex characters>."
  }
}

variable "enable_scheduler_jobs" {
  description = "Unpause only the single 08:00 TEST ONLY watchdog job. Defaults to false."
  type        = bool
  default     = false
}

variable "max_instances" {
  description = "Maximum watchdog Cloud Run instances."
  type        = number
  default     = 1
  validation {
    condition     = var.max_instances == 1
    error_message = "The isolated watchdog is limited to one instance."
  }
}
