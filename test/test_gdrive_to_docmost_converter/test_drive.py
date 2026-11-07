import pytest

from gdrive_to_docmost_converter.drive import (
    _GOOGLE_DRIVE_DOCUMENT_MIME_TYPE,
    _GOOGLE_DRIVE_FOLDER_MIME_TYPE,
    DriveItem,
    GoogleDriveClient,
    extract_google_drive_file_id,
)

from .conftest import BuildDriveFile, FakeGoogleDriveService


class TestExtractGoogleDriveFileId:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("https://docs.google.com/document/d/1AbC-dEf_123/edit?tab=t.0", "1AbC-dEf_123"),
            ("https://drive.google.com/drive/folders/1AbC-dEf_123?usp=sharing", "1AbC-dEf_123"),
            ("https://drive.google.com/open?id=1AbC-dEf_123", "1AbC-dEf_123"),
            ("1AbC-dEf_123", "1AbC-dEf_123"),
        ],
        ids=["document-url", "folder-url", "open-url", "bare-id"],
    )
    def test_extract_google_drive_file_id_returns_id_for_urls_and_bare_ids(self, value: str, expected: str) -> None:
        # Act
        file_id = extract_google_drive_file_id(value)

        # Assert
        assert file_id == expected


class TestGoogleDriveClient:
    def test_get_item_maps_drive_file(
        self,
        fake_google_drive_service: FakeGoogleDriveService,
        google_drive_client: GoogleDriveClient,
        build_drive_file: BuildDriveFile,
    ) -> None:
        # Arrange
        fake_google_drive_service.files_resource.get_results["doc-1"] = build_drive_file(
            "doc-1", _GOOGLE_DRIVE_DOCUMENT_MIME_TYPE
        )

        # Act
        item = google_drive_client.get_item("doc-1")

        # Assert
        assert item == DriveItem("doc-1", "Name doc-1", _GOOGLE_DRIVE_DOCUMENT_MIME_TYPE)

    def test_get_folder_follows_pages_and_keeps_only_documents_and_folders(
        self,
        fake_google_drive_service: FakeGoogleDriveService,
        google_drive_client: GoogleDriveClient,
        build_drive_file: BuildDriveFile,
    ) -> None:
        # Arrange
        files_resource = fake_google_drive_service.files_resource
        files_resource.list_pages[None] = {
            "files": [
                build_drive_file("doc-1", _GOOGLE_DRIVE_DOCUMENT_MIME_TYPE),
                build_drive_file("sheet-1", "application/vnd.google-apps.spreadsheet"),
            ],
            "nextPageToken": "page-2",
        }
        files_resource.list_pages["page-2"] = {"files": [build_drive_file("folder-1", _GOOGLE_DRIVE_FOLDER_MIME_TYPE)]}

        # Act
        items = google_drive_client.get_folder("parent-1")

        # Assert
        assert [item.id for item in items] == ["doc-1", "folder-1"]
        assert [call[1]["pageToken"] for call in files_resource.calls] == [None, "page-2"]
        assert files_resource.calls[0][1]["q"] == "'parent-1' in parents and trashed = false"

    def test_export_markdown_requests_markdown_and_decodes_it(
        self,
        fake_google_drive_service: FakeGoogleDriveService,
        google_drive_client: GoogleDriveClient,
    ) -> None:
        # Arrange
        files_resource = fake_google_drive_service.files_resource
        files_resource.export_results["text/markdown"] = "# Café\n".encode()

        # Act
        markdown = google_drive_client.export_markdown("doc-1")

        # Assert
        assert markdown == "# Café\n"
        assert files_resource.calls == [("export", {"fileId": "doc-1", "mimeType": "text/markdown"})]

    def test_export_html_requests_zip_export(
        self,
        fake_google_drive_service: FakeGoogleDriveService,
        google_drive_client: GoogleDriveClient,
    ) -> None:
        # Arrange
        files_resource = fake_google_drive_service.files_resource
        files_resource.export_results["application/zip"] = b"zip-bytes"

        # Act
        html_export_zip = google_drive_client.export_html("doc-1")

        # Assert
        assert html_export_zip == b"zip-bytes"
        assert files_resource.calls == [("export", {"fileId": "doc-1", "mimeType": "application/zip"})]
