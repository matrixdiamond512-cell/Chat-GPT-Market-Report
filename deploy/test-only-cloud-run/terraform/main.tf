data "google_storage_bucket" "approved_test_only" {
  name = var.test_only_bucket
}
locals {
  slots = {
    "0800" = { slot = "08:00", producer_hour = "7", watchdog_hour = "7", producer_minute = "47", watchdog_minute = "57" }
    "1200" = { slot = "12:00", producer_hour = "11", watchdog_hour = "11", producer_minute = "47", watchdog_minute = "57" }
    "1600" = { slot = "16:00", producer_hour = "15", watchdog_hour = "15", producer_minute = "47", watchdog_minute = "57" }
    "2100" = { slot = "21:00", producer_hour = "20", watchdog_hour = "20", producer_minute = "47", watchdog_minute = "57" }
  }
  invocations = merge(
    { for key, slot in local.slots : "producer-${key}" => {
      mode = "producer", slot_key = key, slot = slot.slot,
      minute = slot.producer_minute, hour = slot.producer_hour,
      job_name = "mr-evidence-${key}", service_name = "mr-evidence-test-producer-${key}"
    } },
    { for key, slot in local.slots : "watchdog-${key}" => {
      mode = "watchdog", slot_key = key, slot = slot.slot,
      minute = slot.watchdog_minute, hour = slot.watchdog_hour,
      job_name = "mr-watchdog-${key}", service_name = "mr-evidence-test-watchdog-${key}"
    } }
  )
  writer_input_condition = "resource.name.startsWith(\"projects/_/buckets/${var.test_only_bucket}/objects/${var.test_only_prefix}/inputs/\")"
  writer_evidence_condition = "resource.name.startsWith(\"projects/_/buckets/${var.test_only_bucket}/objects/${var.test_only_prefix}/evidence/\")"
}
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "storage.googleapis.com"
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
resource "google_service_account" "runtime" {
  for_each     = toset(["producer", "watchdog"])
  project      = var.project_id
  account_id   = "mr-evidence-${each.key}"
  display_name = "TEST ONLY market report ${each.key} runtime"
  depends_on   = [google_project_service.apis]
}
resource "google_service_account" "scheduler" {
  for_each     = local.invocations
  project      = var.project_id
  account_id   = "mr-sched-${each.key}"
  display_name = "TEST ONLY Scheduler caller ${each.key}"
  depends_on   = [google_project_service.apis]
}
resource "google_cloud_run_v2_service" "service" {
  for_each            = local.invocations
  project             = var.project_id
  name                = each.value.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  deletion_protection = true
  custom_audiences    = ["https://test-only.market-report.invalid/${var.project_id}/${each.value.service_name}"]
  template {
    service_account                  = google_service_account.runtime[each.value.mode].email
    timeout                          = "45s"
    max_instance_request_concurrency = 1
    scaling {
      max_instance_count = var.max_instances
    }
    containers {
      image = var.container_image
      ports { container_port = 8080 }
      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }
      env {
        name  = "TEST_ONLY_ENVIRONMENT"
        value = "TEST_ONLY"
      }
      env { name = "SERVICE_MODE", value = each.value.mode }
      env { name = "OIDC_AUDIENCE", value = "https://test-only.market-report.invalid/${var.project_id}/${each.value.service_name}" }
      env { name = "EXPECTED_PRINCIPAL", value = google_service_account.scheduler[each.key].email }
      env { name = "EXPECTED_JOB_RESOURCE", value = "projects/${var.project_id}/locations/${var.region}/jobs/${each.value.job_name}" }
      env { name = "EXPECTED_REPORT_SLOT", value = each.value.slot }
      env { name = "TEST_ONLY_BUCKET", value = var.test_only_bucket }
      env { name = "TEST_ONLY_PREFIX", value = var.test_only_prefix }
      env { name = "EVIDENCE_SERVICE_NAME", value = "mr-evidence-test-producer-${each.value.slot_key}" }
    }
  }
  depends_on = [
    google_project_service.apis,
    google_service_account.runtime,
    google_service_account.scheduler
  ]
}
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  for_each = local.invocations
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.service[each.key].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler[each.key].email}"
}
resource "google_cloud_scheduler_job" "job" {
  for_each         = local.invocations
  project          = var.project_id
  region           = var.region
  name             = each.value.job_name
  description      = "TEST ONLY ${each.value.mode} for report slot ${each.value.slot}; notifications disabled."
  schedule         = "${each.value.minute} ${each.value.hour} * * 1-5"
  time_zone        = "Asia/Tokyo"
  paused           = !var.enable_scheduler_jobs
  attempt_deadline = "60s"
  retry_config {
    retry_count          = 2
    max_retry_duration   = "300s"
    min_backoff_duration = "5s"
    max_backoff_duration = "30s"
    max_doublings        = 2
  }
  http_target {
    http_method = "POST"
    uri         = google_cloud_run_v2_service.service[each.key].uri
    headers     = { "Content-Type" = "application/json" }
    oidc_token {
      service_account_email = google_service_account.scheduler[each.key].email
      audience              = "https://test-only.market-report.invalid/${var.project_id}/${each.value.service_name}"
    }
  }
  depends_on = [google_cloud_run_v2_service_iam_member.invoker]
}
resource "google_storage_bucket_iam_member" "producer_input_reader" {
  bucket = data.google_storage_bucket.approved_test_only.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime["producer"].email}"
  condition {
    title       = "test_only_scheduler_input_read"
    description = "Read-only access to TEST ONLY scheduler inputs."
    expression  = local.writer_input_condition
  }
}
resource "google_storage_bucket_iam_member" "producer_evidence_reader" {
  bucket = data.google_storage_bucket.approved_test_only.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime["producer"].email}"
  condition {
    title       = "test_only_scheduler_evidence_read"
    description = "Read-only readback within the TEST ONLY evidence prefix."
    expression  = local.writer_evidence_condition
  }
}
resource "google_storage_bucket_iam_member" "producer_evidence_creator" {
  bucket = data.google_storage_bucket.approved_test_only.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.runtime["producer"].email}"
  condition {
    title       = "test_only_scheduler_evidence_create"
    description = "Create-only writes within the TEST ONLY evidence prefix."
    expression  = local.writer_evidence_condition
  }
}
resource "google_storage_bucket_iam_member" "watchdog_evidence_reader" {
  bucket = data.google_storage_bucket.approved_test_only.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime["watchdog"].email}"
  condition {
    title       = "test_only_watchdog_evidence_read"
    description = "Independent read-only access to TEST ONLY Evidence."
    expression  = local.writer_evidence_condition
  }
}
resource "google_project_iam_member" "watchdog_logs_reader" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.runtime["watchdog"].email}"
}
resource "google_logging_metric" "failures" {
  project = var.project_id
  name    = "test_only_evidence_failures"
  filter  = "resource.type=\"cloud_run_revision\" AND jsonPayload.event=~\"evidence_request_(blocked|failed|rejected)\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
  depends_on = [google_project_service.apis]
}
resource "google_logging_metric" "watchdog_alerts" {
  project = var.project_id
  name    = "test_only_watchdog_alerts"
  filter  = "resource.type=\"cloud_run_revision\" AND jsonPayload.event=\"evidence_watchdog\" AND jsonPayload.state=~\"WARNING_.*|BLOCKED_.*|EVIDENCE_STATE_UNKNOWN\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
  depends_on = [google_project_service.apis]
}
resource "google_monitoring_alert_policy" "failures" {
  project      = var.project_id
  display_name = "TEST ONLY Evidence execution failure"
  combiner     = "OR"
  conditions {
    display_name = "An authenticated TEST ONLY request failed"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.failures.name}\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      trigger { count = 1 }
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }
}
resource "google_monitoring_alert_policy" "watchdog" {
  project      = var.project_id
  display_name = "TEST ONLY Evidence watchdog warning"
  combiner     = "OR"
  conditions {
    display_name = "Watchdog reported a missing, invalid, or unknown state"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.watchdog_alerts.name}\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      trigger { count = 1 }
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }
}
