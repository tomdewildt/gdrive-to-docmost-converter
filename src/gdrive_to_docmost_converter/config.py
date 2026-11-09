from pathlib import Path

from pydantic import model_validator
from pydantic_core import PydanticCustomError
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConverterConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONV_", env_file=".env", env_file_encoding="utf-8")

    DOCMOST_URL: str
    DOCMOST_API_KEY: str | None = None
    DOCMOST_EMAIL: str | None = None
    DOCMOST_PASSWORD: str | None = None
    DOCMOST_SPACE_SLUG: str
    GOOGLE_CREDENTIALS_PATH: Path
    GOOGLE_TOKEN_PATH: Path

    @model_validator(mode="after")
    def _ensure_docmost_credentials_are_set(self) -> "ConverterConfig":
        if self.DOCMOST_API_KEY or (self.DOCMOST_EMAIL and self.DOCMOST_PASSWORD):
            return self
        raise PydanticCustomError(
            "missing_docmost_credentials",
            "Set 'CONV_DOCMOST_API_KEY', or 'CONV_DOCMOST_EMAIL' and 'CONV_DOCMOST_PASSWORD'",
        )


config = ConverterConfig()  # type: ignore
