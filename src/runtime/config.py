"""Application configuration with default values and complex types.

This module contains non-sensitive configuration that doesn't belong in environment variables.
Complex objects, default business logic settings, and static configuration live here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class OIDCProviderConfig(BaseModel):
    """OIDC provider configuration."""

    client_id: str | None = Field(description="Client ID for the OIDC provider.", default=None)
    client_secret: str | None = Field(description="Client secret for the OIDC provider.", default=None)
    authorization_endpoint: str = Field(description="OIDC authorization endpoint URL.")
    token_endpoint: str = Field(description="OIDC token endpoint URL.")
    userinfo_endpoint: str | None = Field(description="OIDC userinfo endpoint URL.", default=None)
    end_session_endpoint: str | None = Field(description="OIDC end session endpoint URL. Used to log out users.", default=None)
    issuer: str | None = Field(description="Expected JWT issuer for this provider.", default=None)
    jwks_uri: str | None = Field(description="JWKS endpoint for JWT validation.", default=None)
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"], description="OIDC scopes to request during authentication.")
    redirect_uri: str | None = Field(description="Redirect URI for this provider.", default=None)


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


class ApplicationConfig(BaseModel):
    """Main application configuration containing all subsystem configs."""

    jwt: JWTConfig = Field(default_factory=JWTConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)

    def for_environment(self, env: str) -> ApplicationConfig:
        """Return environment-specific configuration."""
        config = self.model_copy(deep=True)

        if env == "production":
            config.session.secure_cookies = True
            config.cors.origins = []  # Must be explicitly configured in production

        elif env == "development":
            config.rate_limit.enabled = False  # Disable rate limiting in dev

        elif env == "test":
            config.rate_limit.enabled = False
            config.session.max_age = 300  # 5 minutes for tests

        return config


# Default OIDC provider configurations
# These can be overridden by environment-specific settings
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


# Create default application configuration
app_config = ApplicationConfig()
