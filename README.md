# Google Drive To Docmost Converter

[![Build](https://img.shields.io/github/actions/workflow/status/tomdewildt/gdrive-to-docmost-converter/ci.yml?branch=master)](https://github.com/tomdewildt/gdrive-to-docmost-converter/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/tomdewildt/gdrive-to-docmost-converter)](https://github.com/tomdewildt/gdrive-to-docmost-converter/blob/master/LICENSE)

Convert [Google Docs](https://docs.google.com/) from [Google Drive](https://drive.google.com/) to [Docmost](https://docmost.com/) pages, including images and nested folders, using the [Google Drive API](https://developers.google.com/workspace/drive/api) and the Docmost import API.

# How To Run

Prerequisites:

- mise version `2025.1.0` or later
- uv version `0.6.0` or later
- python version `3.13.0` or later
- docker version `27.0.0` or later
- terraform version `1.5.0` or later
- gcloud cli version `500.0.0` or later

### Development

1. Run `mise run init` to initialize the environment.
2. Copy `.env.example` to `.env` and configure the settings. Set either `CONV_DOCMOST_API_KEY` or `CONV_DOCMOST_EMAIL` and `CONV_DOCMOST_PASSWORD`, the space slug (the part after `/s/` in the space URL), and the path to the client secret JSON.
3. Run `mise run start -- doc <id-or-url>` to convert a single document. The first run opens a browser window to authorize access to Google Drive and caches the token at the configured token path.
4. Run `mise run start -- folder <id-or-url>` to convert a folder and its subfolders.
5. Run `mise run test` to run all tests, or `mise run test:unit` and `mise run test:integration` to run the unit and integration tests separately. The integration tests run against the docmost server.

Run `mise run docmost:start` to start the docmost server and `mise run docmost:stop` to stop it.

### Google Drive Client Setup

One-time setup of the Google Cloud project that grants access to Google Drive.

1. Run `gcloud auth application-default login` to authenticate terraform with Google Cloud.
2. Copy `infra/terraform.tfvars.example` to `infra/terraform.tfvars` and configure the settings.
3. Run `mise run infra:bootstrap` to create the Google Cloud project and the terraform state bucket.
4. Run `mise run infra:provision` to enable the Google Drive API.
5. Open the credentials URL from the terraform output, configure the OAuth consent screen, create an OAuth client of type desktop app, and download the client secret JSON.

# References

[Google Drive API Docs](https://developers.google.com/workspace/drive/api)

[Docmost Docs](https://docmost.com/docs/)

[Terraform Docs](https://developer.hashicorp.com/terraform/docs)

[Terraform Google Provider Docs](https://registry.terraform.io/providers/hashicorp/google/latest/docs)

[HTTPX Docs](https://www.python-httpx.org/)

[Pydantic Settings Docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

[BeautifulSoup Docs](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)

[Loguru Docs](https://loguru.readthedocs.io/)

[Docker Compose Docs](https://docs.docker.com/compose/)
