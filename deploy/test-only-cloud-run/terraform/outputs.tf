output "services" {
  description = "TEST ONLY Cloud Run service URIs."
  value       = { for key, service in google_cloud_run_v2_service.service : key => service.uri }
}
output "scheduler_jobs" {
  description = "TEST ONLY Cloud Scheduler resource names; paused unless enable_scheduler_jobs=true."
  value       = { for key, job in google_cloud_scheduler_job.job : key => job.id }
}
output "scheduler_jobs_enabled" {
  value = var.enable_scheduler_jobs
}
