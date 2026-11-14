output "watchdog_service_uri" {
  description = "TEST ONLY watchdog Cloud Run service URI; IAM authentication is required."
  value       = google_cloud_run_v2_service.watchdog.uri
}

output "watchdog_scheduler_job" {
  description = "TEST ONLY 08:00 Cloud Scheduler job resource name."
  value       = google_cloud_scheduler_job.watchdog.id
}

output "watchdog_scheduler_enabled" {
  value = var.enable_scheduler_jobs
}
