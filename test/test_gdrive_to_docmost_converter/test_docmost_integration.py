import uuid
from collections import Counter
from collections.abc import Iterator
from typing import Any

import pytest

from gdrive_to_docmost_converter.config import config
from gdrive_to_docmost_converter.docmost import DocmostClient
from gdrive_to_docmost_converter.drive import _GOOGLE_DRIVE_DOCUMENT_MIME_TYPE, DriveItem
from gdrive_to_docmost_converter.service import ConversionService

from .conftest import BuildZip, DocmostPages, FakeDriveClient, WaitForImportJob


def _flatten_page_content(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield node
    for child in node.get("content", []):
        yield from _flatten_page_content(child)


@pytest.mark.integration()
class TestHttpxDocmostClientIntegration:
    def test_get_space_id_resolves_slug_to_uuid(self, docmost_client: DocmostClient) -> None:
        # Act
        space_id = docmost_client.get_space_id(config.DOCMOST_SPACE_SLUG)

        # Assert
        assert space_id != config.DOCMOST_SPACE_SLUG
        assert len(space_id) == 36

    def test_import_zip_creates_page_tree_from_folders(
        self,
        docmost_client: DocmostClient,
        docmost_pages: DocmostPages,
        wait_for_import_job: WaitForImportJob,
        build_zip: BuildZip,
        png: bytes,
    ) -> None:
        # Arrange
        title = f"Parent {uuid.uuid4()}"
        zip_content = build_zip(
            {
                "parent.md": f"# {title}\n\nA paragraph with an image.\n\n![diagram](parent/image1.png)\n",
                "parent/child.md": "# Child\n\nA nested page.\n",
                "parent/image1.png": png,
            }
        )

        # Act
        import_job_id = docmost_client.import_zip(
            space_id=docmost_pages.space_id,
            filename="integration-test.zip",
            content=zip_content,
        )

        # Assert
        assert wait_for_import_job(import_job_id)["status"] == "success"
        parent = next(page for page in docmost_pages.root_pages() if page["title"] == title)
        assert [page["title"] for page in docmost_pages.child_pages(parent["id"])] == ["Child"]


@pytest.mark.integration()
class TestConversionServiceIntegration:
    def test_convert_doc_creates_native_docmost_content_from_real_google_export(
        self,
        service_with_real_docmost_client: ConversionService,
        fake_drive_client: FakeDriveClient,
        docmost_pages: DocmostPages,
        google_markdown_export: str,
        google_html_export_zip: bytes,
        expected_markdown: str,
    ) -> None:
        # Arrange
        title = f"Conversion {uuid.uuid4()}"
        fake_drive_client.get_item_results["doc-1"] = DriveItem("doc-1", title, _GOOGLE_DRIVE_DOCUMENT_MIME_TYPE)
        fake_drive_client.export_markdown_results["doc-1"] = google_markdown_export
        fake_drive_client.export_html_results["doc-1"] = google_html_export_zip

        # Act
        service_with_real_docmost_client.convert_doc(docmost_pages.space_id, "doc-1")

        # Assert
        page = next(page for page in docmost_pages.root_pages() if page["title"] == title)
        page_content = docmost_pages.content(page["id"])
        page_nodes = list(_flatten_page_content(page_content))
        node_types = Counter(node["type"] for node in page_nodes)
        mark_types = {mark["type"] for node in page_nodes for mark in node.get("marks", [])}
        page_text = "".join(node.get("text", "") for node in page_nodes)
        empty_lines = [
            node for node in page_content["content"] if node["type"] == "paragraph" and not node.get("content")
        ]

        assert page_content["content"][0]["type"] == "heading"
        assert node_types["image"] == 3
        assert {"taskList", "mathInline", "codeBlock", "table", "horizontalRule"} <= node_types.keys()
        assert [node["attrs"]["checked"] for node in page_nodes if node["type"] == "taskItem"] == [True, True, False]
        assert {"bold", "italic", "strike", "underline", "highlight", "textStyle", "subscript", "superscript"} <= (
            mark_types
        )
        assert len(empty_lines) == expected_markdown.count("<p></p>")
        assert not any(leak in page_text for leak in ("<", "{#", "[^", "~~", "**"))
