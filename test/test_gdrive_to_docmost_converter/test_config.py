from pathlib import Path

import pytest
from pydantic import ValidationError

from gdrive_to_docmost_converter.config import ConverterConfig

_BASE_SETTINGS = {
    "DOCMOST_URL": "http://docmost.test",
    "DOCMOST_SPACE_SLUG": "general",
    "GOOGLE_CREDENTIALS_PATH": Path("credentials.json"),
    "GOOGLE_TOKEN_PATH": Path("token.json"),
    # Constructor values win over the environment, where CI sets the docmost credentials.
    "DOCMOST_API_KEY": None,
    "DOCMOST_EMAIL": None,
    "DOCMOST_PASSWORD": None,
}


class TestConverterConfig:
    @pytest.mark.parametrize(
        "credentials",
        [{}, {"DOCMOST_EMAIL": "user@example.com"}, {"DOCMOST_PASSWORD": "password"}],
        ids=["none", "email-only", "password-only"],
    )
    def test_converter_config_requires_an_api_key_or_email_and_password(self, credentials: dict[str, str]) -> None:
        # Act / Assert
        with pytest.raises(ValidationError, match="CONV_DOCMOST_API_KEY"):
            ConverterConfig(_env_file=None, **(_BASE_SETTINGS | credentials))  # type: ignore[call-arg]

    def test_converter_config_accepts_an_api_key_without_email_and_password(self) -> None:
        # Act
        config = ConverterConfig(_env_file=None, **(_BASE_SETTINGS | {"DOCMOST_API_KEY": "secret"}))  # type: ignore[call-arg]

        # Assert
        assert config.DOCMOST_API_KEY == "secret"
