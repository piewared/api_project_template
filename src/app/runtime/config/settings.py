import logging
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class EnvironmentVariables(BaseSettings):
    """Simple primitive values loaded from environment variables and .env files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    # Environment and deployment
    environment: Literal["development", "production", "test"] = Field(
        default="development"
    )
    log_level: str = Field(default="INFO")

    # Infrastructure URLs
    database_url: str = Field(default="sqlite:///./database.db")
    redis_url: str | None = Field(default=None)
    temporal_url: str | None = Field(default=None)
    base_url: str = Field(default="http://localhost:8000")


    # Global OIDC redirect URI (fallback for all providers)
    oidc_redirect_uri: str | None = Field(default=None)
