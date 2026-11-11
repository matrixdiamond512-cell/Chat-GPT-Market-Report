data "google_storage_bucket" "approved_test_only" {
  name = var.test_only_bucket
}

locals {
  service_name = "mr-evidence-test-watchdog-0800"
  job_name     = "mr-watchdog-0800"
  audience     = "https://test-only.market-report.invalid/${var.project_id}/${local.service_name}"
  job_resource = "projects/${var.project_id}/locations/${var.region}/jobs/${local.job_name}"
  object_prefix_condition = join(" || ", [
    "resource.name.startsWith(\"projects/_/buckets/${var.test_only_bucket}/objects/test-only/08-00/ledger/\")",
    "resource.name.startsWith(\"projects/_/buckets/${var.test_only_bucket}/objects/test-only/08-00/evidence/\")"
  ])
}

resource "google_service_account" "watchdog_runtime" {
  project      = var.project_id
  account_id   = "mr-pr188-watchdog-runtime"
  display_name = "TEST ONLY PR188 independent Evidence watchdog"
}

resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = "mr-pr188-watchdog-scheduler"
  display_name = "TEST ONLY PR188 watchdog Scheduler caller"
}

resource "google_cloud_run_v2_service" "watchdog" {
  project             = var.project_id
  name                = local.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  deletion_protection = true
  custom_audiences    = [local.audience]

  template {
    service_account                  = google_service_account.watchdog_runtime.email
    timeout                          = "45s"
    max_instance_request_concurrency = 1

    scaling {
      max_instance_count = var.max_instances
    }

    containers {
      image = var.container_image
      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "TEST_ONLY_ENVIRONMENT"
        value = "TEST_ONLY"
      }
      env {
        name  = "SERVICE_MODE"
        value = "watchdog"
      }
      env {
        name  = "OIDC_AUDIENCE"
        value = local.audience
      }
      env {
        name  = "EXPECTED_PRINCIPAL"
        value = google_service_account.scheduler.email
      }
      env {
        name  = "EXPECTED_JOB_RESOURCE"
        value = local.job_resource
      }
      env {
        name  = "EXPECTED_REPORT_SLOT"
        value = "08:00"
      }
      env {
        name  = "TEST_ONLY_BUCKET"
        value = var.test_only_bucket
      }
      env {
        name  = "TEST_ONLY_PREFIX"
        value = var.test_only_prefix
      }
      env {
        name  = "EVIDENCE_SERVICE_NAME"
        value = "mr-pre-slot-test"
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "watchdog_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.watchdog.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "watchdog" {
  project          = var.project_id
  region           = var.region
  name             = local.job_name
  description      = "Read-only TEST ONLY watchdog for the 08:00 report Evidence."
  schedule         = "57 7 * * 1-5"
  time_zone        = "Asia/Tokyo"
  paused           = !var.enable_scheduler_jobs
  attempt_deadline = "60s"

  retry_config {
    retry_count          = 2
    max_retry_duration   = "120s"
    min_backoff_duration = "5s"
    max_backoff_duration = "30s"
    max_doublings        = 2
  }

  http_target {
    http_method = "POST"
    uri         = google_cloud_run_v2_service.watchdog.uri
    headers     = { "Content-Type" = "application/json" }

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = local.audience
    }
  }

  depends_on = [google_cloud_run_v2_service_iam_member.watchdog_invoker]
}

resource "google_storage_bucket_iam_member" "watchdog_evidence_reader" {
  bucket = data.google_storage_bucket.approved_test_only.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.watchdog_runtime.email}"

  condition {
    title       = "pr188_watchdog_read_08_evidence_only"
    description = "Read-only access to the 08:00 TEST ONLY ledger and Evidence prefixes."
    expression  = local.object_prefix_condition
  }
}

resource "google_project_iam_member" "watchdog_logs_reader" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.watchdog_runtime.email}"
}
