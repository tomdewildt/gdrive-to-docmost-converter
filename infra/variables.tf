variable "google_organization_id" {
  description = "The Google Cloud organization id"
  type        = string
}

variable "google_billing_account_id" {
  description = "The Google Cloud billing account id"
  type        = string
}

variable "google_project_name" {
  description = "The Google Cloud project name"
  type        = string
}

variable "google_project_region" {
  description = "The Google Cloud project region"
  type        = string
  default     = "europe-west4"
}

variable "google_project_zone" {
  description = "The Google Cloud project zone"
  type        = string
  default     = "europe-west4-a"
}

