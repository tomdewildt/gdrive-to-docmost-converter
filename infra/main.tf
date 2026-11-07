resource "google_project" "project" {
  org_id          = var.google_organization_id
  billing_account = var.google_billing_account_id
  project_id      = var.google_project_name
  name            = var.google_project_name

  deletion_policy = "DELETE"
}

resource "google_storage_bucket" "state" {
  project                     = google_project.project.project_id
  name                        = "${var.google_project_name}-terraform-bucket"
  location                    = var.google_project_region
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }
}

resource "google_project_service" "drive" {
  project = google_project.project.project_id
  service = "drive.googleapis.com"

  disable_on_destroy = false
}
