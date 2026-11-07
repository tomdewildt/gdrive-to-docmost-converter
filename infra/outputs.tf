# The OAuth consent screen and desktop client cannot be managed via the API, this points to where they must be created
# by hand.
output "google_credentials_url" {
  description = "Console page to configure the OAuth consent screen and desktop client"
  value       = "https://console.cloud.google.com/apis/credentials?project=${google_project.project.project_id}"
}
