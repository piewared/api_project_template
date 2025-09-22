"""Application configuration with default values and complex types.

This module contains non-sensitive configuration that doesn't belong in environment variables.
Complex objects, default business logic settings, and static configuration live here.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import yaml
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .settings import EnvironmentVariables


logger = logging.getLogger(__name__)


class OIDCProviderConfig(BaseModel):
    """OIDC provider configuration."""

    client_id: str | None = Field(
        description="Client ID for the OIDC provider.", default=None
    )
    client_secret: str | None = Field(
        description="Client secret for the OIDC provider.", default=None
    )
    authorization_endpoint: str = Field(description="OIDC authorization endpoint URL.")
    token_endpoint: str = Field(description="OIDC token endpoint URL.")
    userinfo_endpoint: str | None = Field(
        description="OIDC userinfo endpoint URL.", default=None
    )
    end_session_endpoint: str | None = Field(
        description="OIDC end session endpoint URL. Used to log out users.",
        default=None,
    )
    issuer: str | None = Field(
        description="Expected JWT issuer for this provider.", default=None
    )
    jwks_uri: str | None = Field(
        description="JWKS endpoint for JWT validation.", default=None
    )
    scopes: list[str] = Field(
        default_factory=lambda: ["openid", "profile", "email"],
        description="OIDC scopes to request during authentication.",
    )
    redirect_uri: str | None = Field(
        description="Redirect URI for this provider.", default=None
    )


# Default OIDC provider configurations
# These serve as templates that can be overridden by YAML config and environment variables
DEFAULT_OIDC_PROVIDERS: dict[str, OIDCProviderConfig] = {
    "google": OIDCProviderConfig(
        authorization_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token",
        userinfo_endpoint="https://openidconnect.googleapis.com/v1/userinfo",
        end_session_endpoint="https://accounts.google.com/logout",
        issuer="https://accounts.google.com",
        jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
        scopes=["openid", "profile", "email"],
    ),
    "microsoft": OIDCProviderConfig(
        authorization_endpoint="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_endpoint="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        userinfo_endpoint="https://graph.microsoft.com/oidc/userinfo",
        end_session_endpoint="https://login.microsoftonline.com/common/oauth2/v2.0/logout",
        issuer="https://login.microsoftonline.com",  # Base issuer pattern for Microsoft
        jwks_uri="https://login.microsoftonline.com/common/discovery/v2.0/keys",
        scopes=["openid", "profile", "email"],
    ),
}


class JWTConfig(BaseModel):
    """JWT validation configuration."""

    allowed_algorithms: list[str] = Field(default=["RS256", "RS512", "ES256", "ES384"])
    audiences: list[str] = Field(default=["api://default"])
    uid_claim: str = "sub"  # Standard OIDC claim
    role_claim: str = "roles"
    scope_claim: str = "scope"
    clock_skew: int = 60  # seconds


class CORSConfig(BaseModel):
    """CORS configuration for the application."""

    origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"]
    )
    allow_credentials: bool = True
    allow_methods: list[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )
    allow_headers: list[str] = Field(default=["*"])


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    requests: int = 100  # requests per window
    window: int = 3600  # 1 hour in seconds
    enabled: bool = True


class SessionConfig(BaseModel):
    """Session management configuration."""

    max_age: int = 86400  # 24 hours
    secure_cookies: bool = False  # Will be overridden in production
    same_site: str = "lax"
    csrf_protection: bool = True


def _load_oidc_yaml_config() -> dict[str, dict]:
    """Load OIDC provider overrides from YAML file."""
    yaml_path = Path("oidc-providers.yaml")
    if yaml_path.exists():
        try:
            with yaml_path.open() as f:
                config = yaml.safe_load(f) or {}
                return config
        except (yaml.YAMLError, OSError) as e:
            logger.warning(f"Could not load oidc-providers.yaml: {e}")
    return {}


def _get_oidc_providers() -> dict[str, OIDCProviderConfig]:
    """Load OIDC provider overrides from YAML file and merge with defaults."""
    yaml_config = _load_oidc_yaml_config()
    providers = DEFAULT_OIDC_PROVIDERS.copy()

    for name, config in yaml_config.items():
        if name in providers:
            # Update existing provider config with YAML values
            for key, value in config.items():
                if hasattr(providers[name], key):
                    setattr(providers[name], key, value)
        else:
            # Add new provider from YAML
            try:
                providers[name] = OIDCProviderConfig(**config)
            except Exception as e:
                logger.warning(f"Invalid OIDC provider config for '{name}': {e}")

    return providers


class OIDCConfig(BaseModel):
    """OIDC authentication configuration."""

    providers: dict[str, OIDCProviderConfig] = Field(
        default_factory=_get_oidc_providers
    )

    global_redirect_uri: str | None = Field(
        description="Global fallback redirect URI for all providers", default=None
    )


class ApplicationConfig(BaseModel):
    """Main application configuration containing all subsystem configs."""

    # Application-wide settings
    environment: Literal["development", "production", "test"] = Field(
        default="development"
    )
    log_level: str = Field(default="INFO")

    database_url: str = Field(
        default="sqlite:///./database.db", validation_alias="DATABASE_URL"
    )
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    base_url: str = Field(default="http://localhost:8000", validation_alias="BASE_URL")

    # Subsystem configurations
    jwt: JWTConfig = Field(default_factory=JWTConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    oidc: OIDCConfig = Field(default_factory=OIDCConfig)

    @classmethod
    def from_environment(
        cls,
        env_vars: EnvironmentVariables,
        environment_override: Literal["development", "production", "test"]
        | None = None,
    ) -> ApplicationConfig:
        """Create ApplicationConfig with environment-specific overrides from EnvironmentVariables.

        This method creates a base ApplicationConfig and applies environment-specific settings,
        then applies environment variable overrides to primitive fields in the nested configs.
        The merge/de-conflict process happens at creation time, not runtime.

        Args:
            env_vars: EnvironmentVariables instance to use for overrides. If None, creates a new one.
            environment: Target environment name. If None, uses env_vars.environment.
        """

        target_env = environment_override or env_vars.environment

        # Create base config with environment-specific defaults
        config = ApplicationConfig()
        if target_env == "production":
            config.session.secure_cookies = True
            config.cors.origins = []  # Must be explicitly configured in production

        elif target_env == "development":
            config.rate_limit.enabled = False  # Disable rate limiting in dev

        elif target_env == "test":
            config.rate_limit.enabled = False
            config.session.max_age = 300  # 5 minutes for tests

        # Override main application settings with environment variables
        config.environment = target_env
        config.log_level = env_vars.log_level
        config.database_url = env_vars.database_url
        config.redis_url = env_vars.redis_url
        config.base_url = env_vars.base_url

        # Update the OIDC provider configs with environment variable overrides
        for name, provider in config.oidc.providers.items():
            if name not in env_vars.oidc_variables:
                continue

            oidc_vars = env_vars.oidc_variables[name]

            if "client_id" in oidc_vars:
                provider.client_id = oidc_vars["client_id"]

            if "client_secret" in oidc_vars:
                provider.client_secret = oidc_vars["client_secret"]

            if "redirect_uri" in oidc_vars:
                provider.redirect_uri = oidc_vars["redirect_uri"]

        # Apply environment variable overrides to specific fields in sub-config models
        config.oidc.global_redirect_uri = env_vars.oidc_redirect_uri

        return config

    # CORS configuration properties
    @property
    def cors_origins(self) -> list[str]:
        return self.cors.origins

    # JWT configuration properties
    @property
    def allowed_algorithms(self) -> list[str]:
        return self.jwt.allowed_algorithms

    @property
    def audiences(self) -> list[str]:
        return self.jwt.audiences

    @property
    def uid_claim(self) -> str:
        return self.jwt.uid_claim

    @property
    def role_claim(self) -> str:
        return self.jwt.role_claim

    @property
    def scope_claim(self) -> str:
        return self.jwt.scope_claim

    @property
    def clock_skew(self) -> int:
        return self.jwt.clock_skew

    # Session configuration properties
    @property
    def session_max_age(self) -> int:
        return self.session.max_age

    # OIDC configuration properties
    @property
    def oidc_providers(self) -> dict[str, OIDCProviderConfig]:
        return self.oidc.providers


# Create global settings instance
_env_vars = EnvironmentVariables()
main_config = ApplicationConfig.from_environment(_env_vars)
