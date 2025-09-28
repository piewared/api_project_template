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
    dev_redis_url: str | None = Field(default=None, validation_alias="DEV_REDIS_URL")

    base_url: str = Field(default="http://localhost:8000", validation_alias="BASE_URL")

    # Security
    secret_key: str = Field(default="dev-secret-key", validation_alias="SECRET_KEY")

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

        # Known OIDC variable suffixes
        known_suffixes = [
            "CLIENT_ID",
            "CLIENT_SECRET",
            "REDIRECT_URI",
            "ISSUER",
            "AUTHORIZATION_ENDPOINT",
            "TOKEN_ENDPOINT",
            "JWKS_URI",
            "END_SESSION_ENDPOINT",
        ]

        for key, value in oidc_vars.items():
            # Remove "OIDC_" prefix
            without_prefix = key[5:]  # Remove "OIDC_"

            # Find which known suffix this variable ends with
            provider = None
            var_type = None

            for suffix in known_suffixes:
                if without_prefix.endswith(suffix):
                    # Provider name is everything before the suffix (minus the connecting underscore)
                    provider = without_prefix[
                        : -len(suffix) - 1
                    ].lower()  # -1 for the underscore
                    var_type = suffix.lower()
                    break

            if provider and var_type:
                if provider not in parsed_vars:
                    parsed_vars[provider] = {}
                parsed_vars[provider][var_type] = value

        return parsed_vars
