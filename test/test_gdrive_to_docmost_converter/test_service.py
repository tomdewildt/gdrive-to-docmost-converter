import io
import zipfile

import pytest

from gdrive_to_docmost_converter import service as service_module
from gdrive_to_docmost_converter.drive import _GOOGLE_DRIVE_FOLDER_MIME_TYPE, DriveItem
from gdrive_to_docmost_converter.exceptions import ImportFailedError, ImportTimeoutError
from gdrive_to_docmost_converter.service import ConversionService

from .conftest import BuildDocument, FakeDocmostClient, FakeDriveClient


def _unzip_files(content: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


class TestConversionService:
    def test_convert_doc_exports_both_formats_and_imports_zip(
        self,
        service_with_fake_clients: ConversionService,
        build_document: BuildDocument,
        fake_drive_client: FakeDriveClient,
        fake_docmost_client: FakeDocmostClient,
    ) -> None:
        # Arrange
        build_document("doc-1", "My Doc")

        # Act
        service_with_fake_clients.convert_doc("space-1", "doc-1")

        # Assert
        assert fake_drive_client.calls == [
            ("get_item", {"item_id": "doc-1"}),
            ("export_markdown", {"doc_id": "doc-1"}),
            ("export_html", {"doc_id": "doc-1"}),
        ]
        method, arguments = fake_docmost_client.calls[0]
        assert method == "import_zip"
        assert arguments["filename"] == "my-doc.zip"
        assert arguments["space_id"] == "space-1"
        assert fake_docmost_client.calls[1] == ("get_import_job", {"import_job_id": "import-job-1"})

    def test_convert_doc_titles_page_and_stores_markdown_images(
        self,
        service_with_fake_clients: ConversionService,
        build_document: BuildDocument,
        fake_docmost_client: FakeDocmostClient,
        png: bytes,
    ) -> None:
        # Arrange
        build_document("doc-1", "My Doc")

        # Act
        service_with_fake_clients.convert_doc("space-1", "doc-1")

        # Assert
        files = _unzip_files(fake_docmost_client.calls[0][1]["content"])
        markdown = files["My Doc.md"].decode()
        assert markdown.startswith("# My Doc\n\nHello world.")
        assert "[image1]: my-doc/image1.png" in markdown
        assert files["my-doc/image1.png"] == png

    def test_convert_doc_adds_images_missing_from_markdown_from_html_export(
        self,
        service_with_fake_clients: ConversionService,
        build_document: BuildDocument,
        fake_docmost_client: FakeDocmostClient,
        drawing: bytes,
    ) -> None:
        # Arrange
        build_document("doc-1", "My Doc")

        # Act
        service_with_fake_clients.convert_doc("space-1", "doc-1")

        # Assert
        files = _unzip_files(fake_docmost_client.calls[0][1]["content"])
        assert "![](my-doc/html-image2.png)" in files["My Doc.md"].decode()
        assert files["my-doc/html-image2.png"] == drawing
        assert "my-doc/html-image1.png" not in files

    def test_convert_folder_wraps_drive_tree_in_parent_page(
        self,
        service_with_fake_clients: ConversionService,
        build_document: BuildDocument,
        fake_drive_client: FakeDriveClient,
        fake_docmost_client: FakeDocmostClient,
        png: bytes,
        drawing: bytes,
    ) -> None:
        # Arrange
        fake_drive_client.get_item_results["folder-1"] = DriveItem("folder-1", "Wiki", _GOOGLE_DRIVE_FOLDER_MIME_TYPE)
        fake_drive_client.get_folder_results["folder-1"] = [
            build_document("doc-1", "Overview"),
            DriveItem("folder-2", "Guides", _GOOGLE_DRIVE_FOLDER_MIME_TYPE),
        ]
        fake_drive_client.get_folder_results["folder-2"] = [build_document("doc-2", "Setup")]

        # Act
        service_with_fake_clients.convert_folder("space-1", "folder-1")

        # Assert
        files = _unzip_files(fake_docmost_client.calls[0][1]["content"])
        assert {name for name in files if name.endswith(".md")} == {
            "Wiki.md",
            "Wiki/Overview.md",
            "Wiki/Guides/Setup.md",
        }
        assert files["Wiki.md"] == b"# Wiki\n"
        assert files["Wiki/Guides/setup/image1.png"] == png
        assert files["Wiki/Guides/setup/html-image2.png"] == drawing

    def test_convert_folder_without_documents_skips_import(
        self,
        service_with_fake_clients: ConversionService,
        fake_drive_client: FakeDriveClient,
        fake_docmost_client: FakeDocmostClient,
    ) -> None:
        # Arrange
        fake_drive_client.get_item_results["folder-1"] = DriveItem("folder-1", "Empty", _GOOGLE_DRIVE_FOLDER_MIME_TYPE)

        # Act
        service_with_fake_clients.convert_folder("space-1", "folder-1")

        # Assert
        assert fake_docmost_client.calls == []

    def test_convert_doc_raises_when_import_fails(
        self,
        service_with_fake_clients: ConversionService,
        build_document: BuildDocument,
        fake_docmost_client: FakeDocmostClient,
    ) -> None:
        # Arrange
        build_document("doc-1", "My Doc")
        fake_docmost_client.get_import_job_result = {"status": "failed", "errorMessage": "boom"}

        # Act / Assert
        with pytest.raises(ImportFailedError, match="boom"):
            service_with_fake_clients.convert_doc("space-1", "doc-1")

    def test_convert_doc_raises_when_import_does_not_finish_in_time(
        self,
        service_with_fake_clients: ConversionService,
        build_document: BuildDocument,
        fake_docmost_client: FakeDocmostClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange
        build_document("doc-1", "My Doc")
        fake_docmost_client.get_import_job_result = {"status": "processing"}
        monkeypatch.setattr(service_module, "_DOCMOST_IMPORT_JOB_TIMEOUT_SECONDS", 0)

        # Act / Assert
        with pytest.raises(ImportTimeoutError):
            service_with_fake_clients.convert_doc("space-1", "doc-1")

    def test_convert_doc_makes_names_with_slashes_and_punctuation_zip_safe(
        self,
        service_with_fake_clients: ConversionService,
        build_document: BuildDocument,
        fake_docmost_client: FakeDocmostClient,
    ) -> None:
        # Arrange
        build_document("doc-1", "Q1/Q2 Plan!")

        # Act
        service_with_fake_clients.convert_doc("space-1", "doc-1")

        # Assert
        arguments = fake_docmost_client.calls[0][1]
        files = _unzip_files(arguments["content"])
        assert arguments["filename"] == "q1-q2-plan.zip"
        assert files["Q1-Q2 Plan!.md"].decode().startswith("# Q1/Q2 Plan!\n")
        assert "q1-q2-plan/image1.png" in files

    def test_convert_folder_skips_items_that_are_not_documents_or_folders(
        self,
        service_with_fake_clients: ConversionService,
        build_document: BuildDocument,
        fake_drive_client: FakeDriveClient,
        fake_docmost_client: FakeDocmostClient,
    ) -> None:
        # Arrange
        fake_drive_client.get_item_results["folder-1"] = DriveItem("folder-1", "Wiki", _GOOGLE_DRIVE_FOLDER_MIME_TYPE)
        fake_drive_client.get_folder_results["folder-1"] = [
            build_document("doc-1", "Overview"),
            DriveItem("sheet-1", "Budget", "application/vnd.google-apps.spreadsheet"),
        ]

        # Act
        service_with_fake_clients.convert_folder("space-1", "folder-1")

        # Assert
        files = _unzip_files(fake_docmost_client.calls[0][1]["content"])
        assert {name for name in files if name.endswith(".md")} == {"Wiki.md", "Wiki/Overview.md"}
        assert ("export_markdown", {"doc_id": "sheet-1"}) not in fake_drive_client.calls
