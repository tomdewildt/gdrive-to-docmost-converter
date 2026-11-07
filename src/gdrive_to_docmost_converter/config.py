from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ConverterConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONV_", env_file=".env", env_file_encoding="utf-8")

    DOCMOST_URL: str
    DOCMOST_EMAIL: str
    DOCMOST_PASSWORD: str
    DOCMOST_SPACE_SLUG: str
    GOOGLE_CREDENTIALS_PATH: Path
    GOOGLE_TOKEN_PATH: Path


config = ConverterConfig()  # type: ignore
