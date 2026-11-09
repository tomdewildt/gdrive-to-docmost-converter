import base64
import io
import time
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from gdrive_to_docmost_converter.config import config
from gdrive_to_docmost_converter.docmost import DocmostClient, HttpxDocmostClient, create_docmost_client
from gdrive_to_docmost_converter.drive import (
    _GOOGLE_DRIVE_DOCUMENT_MIME_TYPE,
    DriveClient,
    DriveItem,
    GoogleDriveClient,
)
from gdrive_to_docmost_converter.service import ConversionService

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


BuildZip = Callable[[dict[str, str | bytes]], bytes]
BuildDocument = Callable[[str, str], DriveItem]
BuildDriveFile = Callable[[str, str], dict[str, str]]
BuildHtmlDocument = Callable[..., str]
BuildHtmlSpan = Callable[..., str]
WaitForImportJob = Callable[[str], dict[str, Any]]
HttpHandler = Callable[[httpx.Request], httpx.Response]
BuildDocmostClient = Callable[..., HttpxDocmostClient]


class FakeDriveClient(DriveClient):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.get_item_results: dict[str, DriveItem] = {}
        self.get_folder_results: dict[str, list[DriveItem]] = {}
        self.export_markdown_results: dict[str, str] = {}
        self.export_html_results: dict[str, bytes] = {}

    def get_item(self, item_id: str) -> DriveItem:
        self.calls.append(("get_item", {"item_id": item_id}))
        return self.get_item_results[item_id]

    def get_folder(self, folder_id: str) -> list[DriveItem]:
        self.calls.append(("get_folder", {"folder_id": folder_id}))
        return self.get_folder_results.get(folder_id, [])

    def export_html(self, doc_id: str) -> bytes:
        self.calls.append(("export_html", {"doc_id": doc_id}))
        return self.export_html_results[doc_id]

    def export_markdown(self, doc_id: str) -> str:
        self.calls.append(("export_markdown", {"doc_id": doc_id}))
        return self.export_markdown_results[doc_id]


class FakeDocmostClient(DocmostClient):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.get_space_id_result: str = "space-1"
        self.import_zip_result: str = "import-job-1"
        self.get_import_job_result: dict[str, Any] = {"status": "success"}

    def get_space_id(self, space_slug: str) -> str:
        self.calls.append(("get_space_id", {"space_slug": space_slug}))
        return self.get_space_id_result

    def get_import_job(self, import_job_id: str) -> dict[str, Any]:
        self.calls.append(("get_import_job", {"import_job_id": import_job_id}))
        return self.get_import_job_result

    def import_zip(self, *, space_id: str, filename: str, content: bytes) -> str:
        self.calls.append(("import_zip", {"space_id": space_id, "filename": filename, "content": content}))
        return self.import_zip_result


class FakeGoogleRequest:
    def __init__(self, result: Any) -> None:
        self._result = result

    def execute(self) -> Any:
        return self._result


class FakeGoogleFilesResource:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.get_results: dict[str, dict[str, str]] = {}
        self.list_pages: dict[str | None, dict[str, Any]] = {}
        self.export_results: dict[str, bytes] = {}

    def get(self, **kwargs: Any) -> FakeGoogleRequest:
        self.calls.append(("get", kwargs))
        return FakeGoogleRequest(self.get_results[kwargs["fileId"]])

    def list(self, **kwargs: Any) -> FakeGoogleRequest:
        self.calls.append(("list", kwargs))
        return FakeGoogleRequest(self.list_pages[kwargs["pageToken"]])

    def export(self, **kwargs: Any) -> FakeGoogleRequest:
        self.calls.append(("export", kwargs))
        return FakeGoogleRequest(self.export_results[kwargs["mimeType"]])


class FakeGoogleDriveService:
    def __init__(self) -> None:
        self.files_resource = FakeGoogleFilesResource()

    def files(self) -> FakeGoogleFilesResource:
        return self.files_resource


class DocmostPages:
    def __init__(self) -> None:
        self._client = httpx.Client(base_url=config.DOCMOST_URL, timeout=30)
        self._client.post(
            "/api/auth/login", json={"email": config.DOCMOST_EMAIL, "password": config.DOCMOST_PASSWORD}
        ).raise_for_status()
        self.space_id = self._post("/api/spaces/info", {"spaceId": config.DOCMOST_SPACE_SLUG})["id"]

    def root_pages(self) -> list[dict[str, Any]]:
        return self._post("/api/pages/sidebar-pages", {"spaceId": self.space_id})["items"]

    def child_pages(self, page_id: str) -> list[dict[str, Any]]:
        return self._post("/api/pages/sidebar-pages", {"spaceId": self.space_id, "pageId": page_id})["items"]

    def content(self, page_id: str) -> dict[str, Any]:
        return self._post("/api/pages/info", {"pageId": page_id})["content"]

    def delete(self, page_id: str) -> None:
        self._post("/api/pages/delete", {"pageId": page_id, "permanentlyDelete": True})

    def _post(self, path: str, body: dict[str, Any]) -> Any:
        response = self._client.post(path, json=body)
        response.raise_for_status()
        return response.json().get("data")


@pytest.fixture()
def fake_drive_client() -> FakeDriveClient:
    return FakeDriveClient()


@pytest.fixture()
def fake_docmost_client() -> FakeDocmostClient:
    return FakeDocmostClient()


@pytest.fixture()
def fake_google_drive_service() -> FakeGoogleDriveService:
    return FakeGoogleDriveService()


@pytest.fixture()
def service_with_fake_clients(
    fake_drive_client: FakeDriveClient,
    fake_docmost_client: FakeDocmostClient,
) -> ConversionService:
    return ConversionService(fake_drive_client, fake_docmost_client)


@pytest.fixture()
def service_with_real_docmost_client(
    fake_drive_client: FakeDriveClient,
    docmost_client: DocmostClient,
) -> ConversionService:
    return ConversionService(fake_drive_client, docmost_client)


@pytest.fixture()
def google_drive_client(fake_google_drive_service: FakeGoogleDriveService) -> GoogleDriveClient:
    return GoogleDriveClient(Path("credentials.json"), Path("token.json"), service=fake_google_drive_service)


# Docmost rate-limits logins, so integration tests share one session per test module.
@pytest.fixture(scope="module")
def docmost_client() -> DocmostClient:
    return create_docmost_client(config)


# Docmost rate-limits logins, so integration tests share one session per test module.
@pytest.fixture(scope="module")
def docmost_pages_session() -> DocmostPages:
    return DocmostPages()


@pytest.fixture()
def docmost_pages(docmost_pages_session: DocmostPages) -> Iterator[DocmostPages]:
    existing = {page["id"] for page in docmost_pages_session.root_pages()}
    yield docmost_pages_session
    for page in docmost_pages_session.root_pages():
        if page["id"] not in existing:
            docmost_pages_session.delete(page["id"])


@pytest.fixture()
def wait_for_import_job(docmost_client: DocmostClient) -> WaitForImportJob:
    def wait(import_job_id: str) -> dict[str, Any]:
        import_job: dict[str, Any] = {}
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            import_job = docmost_client.get_import_job(import_job_id)
            if import_job["status"] in ("success", "failed"):
                break
            time.sleep(1)
        return import_job

    return wait


@pytest.fixture()
def build_docmost_client() -> BuildDocmostClient:
    def build(handler: HttpHandler, *, api_key: str | None = None) -> HttpxDocmostClient:
        return HttpxDocmostClient(
            "http://docmost.test",
            api_key=api_key,
            email="user@example.com",
            password="password",
            transport=httpx.MockTransport(handler),
        )

    return build


@pytest.fixture()
def build_zip() -> BuildZip:
    def build(files: dict[str, str | bytes]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for path, content in files.items():
                archive.writestr(path, content)
        return buffer.getvalue()

    return build


@pytest.fixture()
def build_document(fake_drive_client: FakeDriveClient, markdown_export: str, html_export: bytes) -> BuildDocument:
    def build(doc_id: str, name: str) -> DriveItem:
        document = DriveItem(doc_id, name, _GOOGLE_DRIVE_DOCUMENT_MIME_TYPE)
        fake_drive_client.get_item_results[doc_id] = document
        fake_drive_client.export_markdown_results[doc_id] = markdown_export
        fake_drive_client.export_html_results[doc_id] = html_export
        return document

    return build


@pytest.fixture()
def build_drive_file() -> BuildDriveFile:
    def build(file_id: str, mime_type: str) -> dict[str, str]:
        return {"id": file_id, "name": f"Name {file_id}", "mimeType": mime_type}

    return build


@pytest.fixture()
def build_html_document() -> BuildHtmlDocument:
    def build(*paragraphs: str) -> str:
        return "<html><body>" + "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs) + "</body></html>"

    return build


@pytest.fixture()
def build_html_span() -> BuildHtmlSpan:
    def build(text: str, style: str = "") -> str:
        return f'<span style="{style}">{text}</span>'

    return build


@pytest.fixture()
def png() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )


@pytest.fixture()
def drawing() -> bytes:
    return b"drawing-bytes"


@pytest.fixture()
def markdown_export(png: bytes) -> str:
    image = base64.b64encode(png).decode()
    return f"Hello world.\n\n![][image1]\n\n[image1]: <data:image/png;base64,{image}>\n"


@pytest.fixture()
def html_export(build_zip: BuildZip, png: bytes, drawing: bytes) -> bytes:
    html = (
        '<html><body><p><span>Hello world.</span></p><p><img src="images/image1.png" style="width: 10px"></p>'
        '<p><img src="images/image2.png" style="width: 10px"></p></body></html>'
    )
    return build_zip({"Doc.html": html, "images/image1.png": png, "images/image2.png": drawing})


@pytest.fixture()
def google_markdown_export() -> str:
    return (FIXTURES_DIR / "google-export.md").read_text()


@pytest.fixture()
def google_html_export() -> str:
    return (FIXTURES_DIR / "google-export.html").read_text()


@pytest.fixture()
def google_html_export_zip(build_zip: BuildZip, google_html_export: str, png: bytes) -> bytes:
    images = ["image1.png", "image2.png", "image3.jpg", "image4.png"]
    return build_zip({"doc.html": google_html_export} | {f"images/{name}": png for name in images})


@pytest.fixture()
def expected_markdown() -> str:
    return (FIXTURES_DIR / "expected.md").read_text()
