terraform {
  required_version = ">= 1.6.0"
  backend "gcs" {
    prefix = "market-report-pre-slot-test/state"
  }
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "= 6.49.0"
    }
  }
}
