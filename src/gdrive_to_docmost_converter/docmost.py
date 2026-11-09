from abc import ABC, abstractmethod
from typing import Any

import httpx
from loguru import logger

from gdrive_to_docmost_converter.config import ConverterConfig


class DocmostClient(ABC):
    @abstractmethod
    def get_space_id(self, space_slug: str) -> str: ...

    @abstractmethod
    def get_import_job(self, import_job_id: str) -> dict[str, Any]: ...

    @abstractmethod
    def import_zip(self, *, space_id: str, filename: str, content: bytes) -> str: ...


class HttpxDocmostClient(DocmostClient):
    def __init__(
        self,
        url: str,
        *,
        api_key: str | None = None,
        email: str | None = None,
        password: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._email = email
        self._password = password

        # API keys (business and enterprise licenses) replace the login
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        self._client = httpx.Client(base_url=url, timeout=60, transport=transport, headers=headers)
        self._is_authenticated = api_key is not None

    def get_space_id(self, space_slug: str) -> str:
        self._ensure_client_is_authenticated()

        # The endpoint's spaceId parameter also accepts a slug, the server falls back to a case-insensitive slug match
        # for any value that is not a UUID.
        response = self._client.post("/api/spaces/info", json={"spaceId": space_slug})
        response.raise_for_status()

        return response.json()["data"]["id"]

    def get_import_job(self, import_job_id: str) -> dict[str, Any]:
        self._ensure_client_is_authenticated()

        response = self._client.post("/api/file-tasks/info", json={"fileTaskId": import_job_id})
        response.raise_for_status()

        return response.json()["data"]

    def import_zip(self, *, space_id: str, filename: str, content: bytes) -> str:
        self._ensure_client_is_authenticated()

        logger.info("Importing '{filename}' into space '{space_id}'", filename=filename, space_id=space_id)

        response = self._client.post(
            "/api/pages/import-zip",
            files={"file": (filename, content, "application/zip")},
            data={"spaceId": space_id, "source": "generic"},
        )
        response.raise_for_status()

        return response.json()["data"]["id"]

    def _ensure_client_is_authenticated(self) -> None:
        if self._is_authenticated:
            return

        # Without an API key, the import endpoints of the open-source core accept the JWT cookie set by a regular login.
        response = self._client.post("/api/auth/login", json={"email": self._email, "password": self._password})
        response.raise_for_status()

        self._is_authenticated = True


def create_docmost_client(config: ConverterConfig) -> DocmostClient:
    return HttpxDocmostClient(
        config.DOCMOST_URL,
        api_key=config.DOCMOST_API_KEY,
        email=config.DOCMOST_EMAIL,
        password=config.DOCMOST_PASSWORD,
    )
