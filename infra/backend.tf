terraform {
  backend "gcs" {
    bucket = "gdrive-to-docmost-converter-terraform-bucket"
  }
}
