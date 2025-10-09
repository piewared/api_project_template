"""Pydantic models for parsing the config.yaml configuration file.

This module contains Pydantic models that correspond to the structure of config.yaml.
These models handle validation and type conversion of the YAML configuration data.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def deep_freeze(value: Any) -> Any:
    """Recursively convert mutable containers into hashable equivalents."""
    if isinstance(value, dict):
        return tuple(sorted((k, deep_freeze(v)) for k, v in value.items()))
    elif isinstance(value, (list, tuple)):
        return tuple(deep_freeze(v) for v in value)
    elif isinstance(value, set):
        return frozenset(deep_freeze(v) for v in value)
    else:
        return value  # primitive types are already hashable

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


class RateLimiterConfig(BaseModel):
    """Rate limiter configuration model."""

    requests: int = Field(default=100, description="Number of requests allowed per window")
    window_ms: int = Field(default=60000, description="Time window in milliseconds")
    enabled: bool = Field(default=True, description="Enable rate limiting")
    per_endpoint: bool = Field(default=True, description="Apply rate limiting per endpoint")
    per_method: bool = Field(default=True, description="Apply rate limiting per HTTP method")


class TemporalWorkerConfig(BaseModel):
    """Temporal worker configuration model."""

    enabled: bool = Field(default=True, description="Enable temporal worker")
    activities_per_second: int = Field(default=10, description="Activities per second limit")
    max_concurrent_activities: int = Field(default=100, description="Maximum concurrent activities")
    max_concurrent_workflows: int = Field(default=100, description="Maximum concurrent workflows")
    poll_interval_ms: int = Field(default=1000, description="Poll interval in milliseconds")
    workflow_cache_size: int = Field(default=100, description="Workflow cache size")
    max_workflow_tasks_per_second: int = Field(default=100, description="Maximum workflow tasks per second")
    max_concurrent_workflow_tasks: int = Field(default=100, description="Maximum concurrent workflow tasks")
    sticky_queue_schedule_to_start_timeout_ms: int = Field(
        default=10000, description="Sticky queue schedule to start timeout in milliseconds"
    )
    worker_build_id: str = Field(default="api-worker-1", description="Worker build ID")


class TemporalConfig(BaseModel):
    """Temporal configuration model."""

    enabled: bool = Field(default=True, description="Enable temporal service")
    url: str = Field(default="temporal:7233", description="Temporal server url")
    namespace: str = Field(default="default", description="Temporal namespace")
    task_queue: str = Field(default="default", description="Temporal task queue name")
    worker: TemporalWorkerConfig = Field(default_factory=TemporalWorkerConfig, description="Worker configuration")


class RedisConfig(BaseModel):
    """Redis configuration model."""

    enabled: bool = Field(default=True, description="Enable Redis service")
    url: str = Field(default="", description="Redis connection URL")
    dev_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL for development")


class OIDCProviderConfig(BaseModel):
    """OIDC provider configuration model."""

    openid_configuration_endpoint: str | None = Field(default=None, description="URL to fetch OIDC provider configuration")
    authorization_endpoint: str = Field(description="OIDC authorization endpoint URL")
    token_endpoint: str = Field(description="OIDC token endpoint URL")
    userinfo_endpoint: str | None = Field(default=None, description="OIDC userinfo endpoint URL")
    end_session_endpoint: str | None = Field(default=None, description="OIDC end session endpoint URL")
    issuer: str = Field(description="OIDC issuer URL")
    jwks_uri: str = Field(description="JWKS endpoint for JWT validation")
    scopes: list[str] = Field(
        default_factory=lambda: ["openid", "profile", "email"],
        description="OIDC scopes to request during authentication"
    )
    client_id: str = Field(description="Client ID for the OIDC provider")
    client_secret: str = Field(description="Client secret for the OIDC provider")
    redirect_uri: str = Field(description="Redirect URI for this provider")


class OIDCConfig(BaseModel):
    """OIDC configuration model."""

    providers: dict[str, OIDCProviderConfig] = Field(
        default_factory=dict, description="OIDC provider configurations"
    )
    default_provider: str = Field(default="keycloak", description="Default OIDC provider to use")
    global_redirect_uri: str = Field(
        default="http://localhost:8000/auth/callback",
        description="Global fallback redirect URI for all providers"
    )
    allowed_redirect_hosts: list[str] = Field(
        default_factory=list,
        description="Allowed hosts for absolute redirect URLs (empty = relative only)"
    )
    allowed_audiences: list[str] = Field(
        default_factory=list,
        description="Allowed audiences for validating incoming ID tokens (empty = skip audience check)"
    )


class JWTClaimsConfig(BaseModel):
    """JWT claims mapping configuration."""

    user_id: str = Field(default="sub", description="Claim name for user ID (usually 'sub')")
    email: str = Field(default="email", description="Claim name for email address")
    roles: str = Field(default="roles", description="Claim name for user roles/permissions")
    groups: str = Field(default="groups", description="Claim name for user groups")
    scope: str = Field(default="scope", description="Claim name for OAuth scopes")
    name: str = Field(default="name", description="Claim name for user's full name")
    preferred_username: str = Field(default="preferred_username", description="Claim name for username")


class JWTConfig(BaseModel):
    """JWT validation configuration."""

    allowed_algorithms: list[str] = Field(
        default_factory=lambda: ["RS256", "RS512", "ES256", "ES384"],
        description="JWT algorithms allowed for token validation"
    )
    gen_issuer: str = Field(default="my-api-issuer", description="Issuer name to use when generating tokens")
    audiences: list[str] = Field(default_factory=lambda: ["api://default"], description="JWT audiences that this API accepts")
    clock_skew: int = Field(default=60, description="Clock skew tolerance in seconds")
    verify_signature: bool = Field(default=True, description="Verify JWT signature")
    verify_exp: bool = Field(default=True, description="Verify token expiration")
    verify_nbf: bool = Field(default=True, description="Verify not-before claim")
    verify_iat: bool = Field(default=True, description="Verify issued-at claim")
    require_exp: bool = Field(default=True, description="Require expiration claim")
    require_iat: bool = Field(default=True, description="Require issued-at claim")
    claims: JWTClaimsConfig = Field(
        default_factory=JWTClaimsConfig,
        description="JWT claims mapping configuration"
    )


class LoggingConfig(BaseModel):
    """Logging configuration model."""

    level: str = Field(default="INFO", description="Logging level")
    format: Literal["json", "plain"] = Field(default="json", description="Log format")
    file: str = Field(default="logs/app.log", description="Log file path")
    max_size_mb: int = Field(default=10, description="Maximum log file size in MB")
    backup_count: int = Field(default=5, description="Number of backup log files to keep")


class DatabaseConfig(BaseModel):
    """Database configuration model."""

    url: str = Field(
        default="postgresql+asyncpg://user:password@postgres:5432/app_db",
        description="Database connection URL"
    )
    pool_size: int = Field(default=20, description="Connection pool size")
    max_overflow: int = Field(default=10, description="Maximum pool overflow")
    pool_timeout: int = Field(default=30, description="Pool timeout in seconds")
    pool_recycle: int = Field(default=1800, description="Pool recycle time in seconds")


class AppConfig(BaseModel):
    """Application configuration model."""

    environment: Literal["development", "production", "test"] = Field(
        default="development", description="Application environment"
    )
    host: str = Field(default="localhost", description="Application host")
    port: int = Field(default=8000, description="Application port")
    session_max_age: int = Field(default=3600, description="Session maximum age in seconds")
    session_signing_secret: str | None = Field(default=None, description="Secret for signing session JWTs")
    csrf_signing_secret: str | None = Field(default=None, description="Secret for signing CSRF tokens")
    cors: CORSConfig = Field(default_factory=CORSConfig, description="CORS configuration")

    @property
    def base_url(self) -> str:
        """Construct the base URL from host and port."""
        scheme = "https" if self.environment == "production" else "http"
        return f"{scheme}://{self.host}:{self.port}"


class SecurityConfig(BaseModel):
    """Security configuration for authentication and sessions."""

    # Cookie settings
    secure_cookies: bool = Field(
        default=True, description="Force secure cookies in production"
    )
    cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax", description="SameSite cookie attribute"
    )

    # CSRF protection
    csrf_header_name: str = Field(
        default="X-CSRF-Token", description="Header name for CSRF tokens"
    )
    csrf_token_max_age_hours: int = Field(
        default=24, description="Maximum age for CSRF tokens in hours"
    )

    # Client fingerprinting
    enable_client_fingerprinting: bool = Field(
        default=True, description="Enable client context binding for sessions"
    )
    strict_fingerprinting: bool = Field(
        default=True, description="Require exact fingerprint match"
    )

    # Session security
    auth_session_ttl_seconds: int = Field(
        default=600, description="Auth session TTL (10 minutes)"
    )
    single_use_auth_sessions: bool = Field(
        default=True, description="Invalidate auth sessions after successful callback"
    )


class ConfigData(BaseModel):
    """Root configuration model that matches the config.yaml structure."""


    rate_limiter: RateLimiterConfig = Field(
        default_factory=RateLimiterConfig, description="Rate limiter configuration"
    )
    temporal: TemporalConfig = Field(default_factory=TemporalConfig, description="Temporal configuration")
    redis: RedisConfig = Field(default_factory=RedisConfig, description="Redis configuration")
    oidc: OIDCConfig = Field(default_factory=OIDCConfig, description="OIDC configuration")
    jwt: JWTConfig = Field(default_factory=JWTConfig, description="JWT validation configuration")
    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="Logging configuration")
    database: DatabaseConfig = Field(default_factory=DatabaseConfig, description="Database configuration")
    app: AppConfig = Field(default_factory=lambda: AppConfig(session_signing_secret=None, csrf_signing_secret=None), description="Application configuration")
    security: SecurityConfig = Field(default_factory=SecurityConfig, description="Security configuration")


