import httpx

from .conftest import BuildDocmostClient


class TestHttpxDocmostClient:
    def test_api_key_is_sent_as_bearer_token_instead_of_logging_in(
        self, build_docmost_client: BuildDocmostClient
    ) -> None:
        # Arrange
        requests: list[tuple[str, str | None]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append((request.url.path, request.headers.get("Authorization")))
            return httpx.Response(200, json={"data": {"id": "id"}})

        docmost_client = build_docmost_client(handler, api_key="secret")

        # Act
        docmost_client.get_space_id("general")

        # Assert
        assert requests == [("/api/spaces/info", "Bearer secret")]

    def test_logs_in_once_without_an_api_key(self, build_docmost_client: BuildDocmostClient) -> None:
        # Arrange
        paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            paths.append(request.url.path)
            return httpx.Response(200, json={"data": {"id": "id"}})

        docmost_client = build_docmost_client(handler)

        # Act
        docmost_client.get_space_id("general")
        docmost_client.get_import_job("job")

        # Assert
        assert paths == ["/api/auth/login", "/api/spaces/info", "/api/file-tasks/info"]
