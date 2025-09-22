"""Environment-based settings configuration.

This module handles only simple environment variables (strings, numbers, booleans).
Complex application configuration lives in config.py.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .config import DEFAULT_OIDC_PROVIDERS, OIDCProviderConfig, app_config

logger = logging.getLogger(__name__)

def _load_oidc_yaml_config() -> dict[str, dict]:
    """Load OIDC provider overrides from YAML file."""
    yaml_path = Path("oidc-providers.yaml")
    if yaml_path.exists():
        try:
            with yaml_path.open() as f:
                config = yaml.safe_load(f) or {}
                return config
        except (yaml.YAMLError, OSError) as e:
            # Log warning but don't fail - continue with defaults
            print(f"Warning: Could not load oidc-providers.yaml: {e}")
    return {}


class EnvironmentSettings(BaseSettings):
    """Settings that come from environment variables."""

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

    # Secrets
    secret_key: str | None = Field(default=None, validation_alias="SECRET_KEY")
    jwt_secret: str | None = Field(default=None, validation_alias="JWT_SECRET")

    # Global OIDC redirect URI (fallback for all providers)
    oidc_redirect_uri: str | None = Field(default=None, validation_alias="OIDC_REDIRECT_URI")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",  # Ignore extra fields for now (legacy migration)
    )

    def get_oidc_providers(self) -> dict[str, OIDCProviderConfig]:
        """Get complete OIDC provider configuration merging defaults, YAML overrides, and environment credentials."""
        providers = {}

        # Load YAML overrides
        yaml_config = _load_oidc_yaml_config()

        # Start with defaults and merge with YAML config
        all_provider_names = set(DEFAULT_OIDC_PROVIDERS.keys()) | set(yaml_config.keys())

        for name in all_provider_names:
            # Get base config (default or create from YAML for new providers)
            if name in DEFAULT_OIDC_PROVIDERS:
                base_config = DEFAULT_OIDC_PROVIDERS[name]
            else:
                # New provider defined only in YAML
                yaml_provider = yaml_config.get(name, {})
                if not yaml_provider:
                    continue
                try:
                    base_config = OIDCProviderConfig(
                        client_id="",  # Will be injected from environment
                        redirect_uri=f"{self.base_url}/web/callback",  # Default
                        **yaml_provider
                    )
                except Exception as e:
                    print(f"Warning: Invalid YAML config for provider '{name}': {e}")
                    continue

            # Apply YAML overrides if present
            yaml_overrides = yaml_config.get(name, {})
            if yaml_overrides:
                try:
                    base_config = base_config.model_copy(update=yaml_overrides)
                except Exception as e:
                    print(f"Warning: Could not apply YAML overrides for provider '{name}': {e}")

            # Look for environment-specific client credentials
            # Use dynamic environment variable lookup for any provider
            env_var_prefix = f"OIDC_{name.upper()}_"
            client_id = os.getenv(f"{env_var_prefix}CLIENT_ID")
            client_secret = os.getenv(f"{env_var_prefix}CLIENT_SECRET")

            # Redirect URI priority: provider-specific → global OIDC_REDIRECT_URI → base config default
            redirect_uri = (
                os.getenv(f"{env_var_prefix}REDIRECT_URI") or
                self.oidc_redirect_uri or
                base_config.redirect_uri
            )

            if client_id:  # Only include provider if client_id is configured
                # Create final config with environment credentials
                providers[name] = base_config.model_copy(update={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                })

        return providers

    def validate_runtime(self) -> None:
        """Validate configuration for the current environment."""
        if self.environment == "production":
            if not self.secret_key:
                raise ValueError("SECRET_KEY must be configured in production")
            if self.database_url.startswith("sqlite://"):
                raise ValueError("SQLite is not recommended for production")
            if not self.redis_url:
                raise ValueError("REDIS_URL must be configured in production")
        elif self.environment == "development":
            if self.secret_key is None:
                logger.warning("SECRET_KEY is not set; using default insecure key for development")
            if self.database_url.startswith("sqlite://"):
                logger.warning("Using SQLite database in development")

        if self.redis_url and not (
            self.redis_url.startswith("redis://")
            or self.redis_url.startswith("rediss://")
        ):
            raise ValueError("REDIS_URL must be a redis:// or rediss:// URL")


# Create settings instance
env_settings = EnvironmentSettings()

# Get environment-specific application config
settings = app_config.for_environment(env_settings.environment)


# Expose commonly used values for backward compatibility
class Settings:
    """Unified settings interface combining environment and application config."""

    # Environment settings
    environment = env_settings.environment
    log_level = env_settings.log_level
    database_url = env_settings.database_url
    redis_url = env_settings.redis_url
    base_url = env_settings.base_url
    secret_key = env_settings.secret_key
    jwt_secret = env_settings.jwt_secret

    # Application config (computed from environment)
    allowed_algorithms = settings.jwt.allowed_algorithms
    audiences = settings.jwt.audiences
    uid_claim = settings.jwt.uid_claim
    role_claim = settings.jwt.role_claim
    scope_claim = settings.jwt.scope_claim
    clock_skew = settings.jwt.clock_skew
    cors_origins = settings.cors.origins
    session_max_age = settings.session.max_age
    rate_limit_requests = settings.rate_limit.requests
    rate_limit_window = settings.rate_limit.window
    rate_limit_enabled = settings.rate_limit.enabled

    @property
    def oidc_providers(self) -> dict[str, OIDCProviderConfig]:
        """Get OIDC providers configuration."""
        # Create fresh environment settings to pick up any env var changes
        fresh_env_settings = EnvironmentSettings()
        return fresh_env_settings.get_oidc_providers()

    def validate_runtime(self) -> None:
        """Validate runtime configuration."""
        return env_settings.validate_runtime()


# Create global settings instance
settings = Settings()
