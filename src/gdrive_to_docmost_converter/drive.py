import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from loguru import logger

from gdrive_to_docmost_converter.config import ConverterConfig

_GOOGLE_DRIVE_DOCUMENT_MIME_TYPE = "application/vnd.google-apps.document"
_GOOGLE_DRIVE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
_GOOGLE_DRIVE_AUTH_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_GOOGLE_DRIVE_URL_ID_PATTERNS = [
    # Id in the path: docs.google.com/document/d/<id>/edit and drive.google.com/drive/folders/<id>
    re.compile(r"/(?:d|folders)/([\w-]+)"),
    # Id in the query string: drive.google.com/open?id=<id>
    re.compile(r"[?&]id=([\w-]+)"),
]


@dataclass
class DriveItem:
    id: str
    name: str
    mime_type: str

    @property
    def is_document(self) -> bool:
        return self.mime_type == _GOOGLE_DRIVE_DOCUMENT_MIME_TYPE

    @property
    def is_folder(self) -> bool:
        return self.mime_type == _GOOGLE_DRIVE_FOLDER_MIME_TYPE


def extract_google_drive_file_id(value: str) -> str:
    for pattern in _GOOGLE_DRIVE_URL_ID_PATTERNS:
        match = pattern.search(value)
        if match:
            return match.group(1)
    return value


class DriveClient(ABC):
    @abstractmethod
    def get_folder(self, folder_id: str) -> list[DriveItem]: ...

    @abstractmethod
    def get_item(self, item_id: str) -> DriveItem: ...

    @abstractmethod
    def export_html(self, doc_id: str) -> bytes: ...

    @abstractmethod
    def export_markdown(self, doc_id: str) -> str: ...


class GoogleDriveClient(DriveClient):
    def __init__(self, credentials_path: Path, token_path: Path, service: Any = None) -> None:
        self._credentials_path = credentials_path
        self._token_path = token_path
        self._service = service

    def get_folder(self, folder_id: str) -> list[DriveItem]:
        query = f"'{folder_id}' in parents and trashed = false"
        items: list[DriveItem] = []
        page_token = None

        while True:
            response = (
                self._get_service()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            items += [DriveItem(file["id"], file["name"], file["mimeType"]) for file in response.get("files", [])]
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return [item for item in items if item.is_document or item.is_folder]

    def get_item(self, item_id: str) -> DriveItem:
        file = self._get_service().get(fileId=item_id, fields="id, name, mimeType", supportsAllDrives=True).execute()
        return DriveItem(file["id"], file["name"], file["mimeType"])

    def export_html(self, doc_id: str) -> bytes:
        logger.info("Exporting document '{doc_id}' as html", doc_id=doc_id)
        return self._get_service().export(fileId=doc_id, mimeType="application/zip").execute()

    def export_markdown(self, doc_id: str) -> str:
        logger.info("Exporting document '{doc_id}' as markdown", doc_id=doc_id)
        return self._get_service().export(fileId=doc_id, mimeType="text/markdown").execute().decode()

    def _get_service(self) -> Any:
        if self._service is None:
            self._service = build("drive", "v3", credentials=self._get_credentials())
        return self._service.files()

    def _get_credentials(self) -> Credentials:
        credentials = None
        if self._token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(self._token_path), _GOOGLE_DRIVE_AUTH_SCOPES)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(self._credentials_path), _GOOGLE_DRIVE_AUTH_SCOPES)
                credentials = flow.run_local_server(port=0)
            self._token_path.write_text(credentials.to_json())

        # The desktop-app flow always yields oauth2 user credentials, the stub's union is too wide.
        return credentials  # pyright: ignore[reportReturnType]


def create_drive_client(config: ConverterConfig) -> DriveClient:
    return GoogleDriveClient(config.GOOGLE_CREDENTIALS_PATH, config.GOOGLE_TOKEN_PATH)
