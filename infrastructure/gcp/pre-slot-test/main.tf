provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  slots = {
    "0747" = "47 7 * * 1-5"
    "0753" = "53 7 * * 1-5"
    "0757" = "57 7 * * 1-5"
  }
  required_apis = toset([
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudscheduler.googleapis.com",
    "logging.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
  ])
  runner_audience = "https://${var.resource_prefix}-${var.project_id}.test-only.invalid"
  job_names = {
    for key, _ in local.slots :
    "projects/${var.project_id}/locations/${var.region}/jobs/${var.resource_prefix}-${key}" => google_service_account.scheduler[key].email
  }
}

resource "google_project_service" "required" {
  for_each           = local.required_apis
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_logging_project_bucket_config" "test_only_default" {
  project        = var.project_id
  location       = "global"
  bucket_id      = "_Default"
  retention_days = 14
  description    = "14-day diagnostics retention for the isolated market report TEST_ONLY project"
}

resource "google_storage_bucket" "evidence" {
  project                     = var.project_id
  name                        = "${var.project_id}-${var.resource_prefix}-evidence"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  # Evidence objects expire at 14 days; disabling soft delete avoids retaining
  # deleted TEST_ONLY bytes for an additional default recovery window.
  soft_delete_policy {
    retention_duration_seconds = 0
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 14
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_service_account" "runner" {
  project      = var.project_id
  account_id   = "${var.resource_prefix}-runner"
  display_name = "Market report isolated TEST_ONLY runner"
}

resource "google_service_account" "scheduler" {
  for_each     = local.slots
  project      = var.project_id
  account_id   = "${var.resource_prefix}-${each.key}"
  display_name = "TEST_ONLY Scheduler caller ${each.key}"
}

resource "google_secret_manager_secret" "trigger" {
  project   = var.project_id
  secret_id = var.trigger_secret_id
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "runner_access" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.trigger.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runner.email}"
}

resource "google_project_iam_custom_role" "test_only_evidence_writer" {
  project     = var.project_id
  role_id     = "marketReportTestOnlyEvidenceWriter"
  title       = "Market report TEST_ONLY evidence create/read/delete"
  description = "Create-only TEST_ONLY evidence, exact generation readback, and exact-generation late cleanup."
  stage       = "GA"
  permissions = [
    "storage.objects.create",
    "storage.objects.get",
    "storage.objects.delete",
  ]
}

resource "google_storage_bucket_iam_member" "runner_objects" {
  bucket = google_storage_bucket.evidence.name
  role   = google_project_iam_custom_role.test_only_evidence_writer.name
  member = "serviceAccount:${google_service_account.runner.email}"
}

resource "google_cloud_run_v2_service" "runner" {
  project             = var.project_id
  name                = var.resource_prefix
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  custom_audiences    = [local.runner_audience]

  # Cloud Run API reports service-level default zeros even though this service
  # only configures revision-level max_instance_count below. Do not rewrite
  # implicit service-level scaling during Scheduler-only changes.
  # Any intended service-level scaling change needs a separate reviewed change.
  lifecycle {
    ignore_changes = [scaling]
  }

  template {
    service_account                  = google_service_account.runner.email
    timeout                          = "300s"
    max_instance_request_concurrency = 1
    scaling {
      max_instance_count = 1
    }

    containers {
      image = var.runner_image
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
      env {
        name  = "RUNNER_AUDIENCE"
        value = local.runner_audience
      }
      env {
        name  = "TEST_ONLY_GCS_BUCKET"
        value = google_storage_bucket.evidence.name
      }
      env {
        name  = "TEST_ONLY_OBJECT_PREFIX"
        value = "test-only/08-00"
      }
      env {
        name  = "ALLOWED_SCHEDULER_CALLERS_JSON"
        value = jsonencode(local.job_names)
      }
      env {
        name  = "TRIGGER_SECRET_RESOURCE"
        value = "${google_secret_manager_secret.trigger.id}/versions/latest"
      }
    }

    labels = {
      environment = "test-only"
      system      = "market-report"
    }
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.runner_access,
    google_storage_bucket_iam_member.runner_objects,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "scheduler_invoker" {
  for_each = google_service_account.scheduler
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.runner.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${each.value.email}"
}

resource "google_cloud_scheduler_job" "pre_slot" {
  for_each    = var.enable_test_scheduler ? local.slots : {}
  project     = var.project_id
  region      = var.region
  name        = "${var.resource_prefix}-${each.key}"
  description = "TEST_ONLY 08:00 evidence capture preflight at JST ${each.key}"
  schedule    = each.value
  time_zone   = "Asia/Tokyo"

  attempt_deadline = "300s"

  # Cloud Scheduler normalizes a zero API value to the default 5.
  # With retry_count=1 and both backoff bounds at 5s, this does not
  # increase retry count or spacing; matching API state avoids drift.
  retry_config {
    retry_count          = 1
    max_retry_duration   = "60s"
    min_backoff_duration = "5s"
    max_backoff_duration = "5s"
    max_doublings        = 5
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.runner.uri}/capture"
    body        = base64encode("{}")
    headers     = { "Content-Type" = "application/json" }

    oidc_token {
      service_account_email = google_service_account.scheduler[each.key].email
      audience              = local.runner_audience
    }
  }

  depends_on = [google_project_service.required, google_cloud_run_v2_service_iam_member.scheduler_invoker]
}

output "service_uri" {
  value       = google_cloud_run_v2_service.runner.uri
  description = "IAM-authenticated TEST_ONLY Cloud Run endpoint."
}

output "evidence_bucket" {
  value       = google_storage_bucket.evidence.name
  description = "Private, uniform-access bucket with 14-day object expiry."
}

output "scheduler_job_names" {
  value       = [for job in google_cloud_scheduler_job.pre_slot : job.name]
  description = "Only the three TEST_ONLY pre-slot jobs."
}
