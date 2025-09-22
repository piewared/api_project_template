"""Settings configuration with clear separation of concerns.

This module provides:
- EnvironmentVariables: Simple primitive values from .env files
- ApplicationConfig: Complete application configuration with environment overrides
- ApplicationSettings: Composite object providing both environment variables and config
"""

from __future__ import annotations

import logging
import os
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
    database_url: str = Field(
        default="sqlite:///./database.db", validation_alias="DATABASE_URL"
    )
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    base_url: str = Field(default="http://localhost:8000", validation_alias="BASE_URL")

    # Global OIDC redirect URI (fallback for all providers)
    oidc_redirect_uri: str | None = Field(
        default=None, validation_alias="OIDC_REDIRECT_URI"
    )

    @property
    def oidc_variables(self) -> dict[str, dict[str, str]]:
        """Get OIDC-related environment variables."""

        # Get all environment variables that start with "OIDC_"
        oidc_vars = {
            key: value for key, value in os.environ.items() if key.startswith("OIDC_")
        }

        # The variables have this format: OIDC_<PROVIDER>_CLIENT_ID, OIDC_<PROVIDER>_CLIENT_SECRET, OIDC_<PROVIDER>_REDIRECT_URI
        # Parse the provider names and group variables accordingly
        parsed_vars = {}
        for key, value in oidc_vars.items():
            parts = key.split("_")
            if len(parts) >= 3:
                provider = parts[1]
                var_type = "_".join(
                    parts[2:]
                ).lower()  # client_id, client_secret, redirect_uri
                if provider not in parsed_vars:
                    parsed_vars[provider] = {}
                parsed_vars[provider][var_type] = value
        return parsed_vars
