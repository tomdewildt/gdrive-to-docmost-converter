terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

provider "google" {
  region = var.google_project_region
  zone   = var.google_project_zone
  default_labels = {
    "managed-by" = "terraform"
  }
}
