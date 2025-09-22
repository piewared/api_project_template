"""Runtime configuration settings for the application."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OIDCProviderConfig(BaseModel):
    """OIDC provider configuration."""

    client_id: str
    client_secret: str | None = None
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str | None = None
    end_session_endpoint: str | None = None
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    redirect_uri: str


def _parse_list(value: str | list[str]) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    value = value.strip()
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [x.strip() for x in value.split(",") if x.strip()]


class Settings(BaseSettings):
    # JWT / OIDC
    issuer_jwks_map: dict[str, str] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("JWT_ISSUER_JWKS_MAP", "ISSUER_JWKS_MAP"),
    )
    allowed_algorithms_str: str | list[str] = Field(
        default="RS256,RS512,ES256,ES384",
        validation_alias=AliasChoices("JWT_ALLOWED_ALGOS", "ALLOWED_ALGORITHMS"),
    )
    audiences_str: str | list[str] = Field(
        default="api://default",
        validation_alias=AliasChoices("JWT_AUDIENCES", "AUDIENCES"),
    )
    uid_claim: str | None = Field(
        default="https://your.app/uid",
        validation_alias=AliasChoices("JWT_UID_CLAIM", "UID_CLAIM"),
    )
    role_claim: str | None = Field(
        default="roles",
        validation_alias=AliasChoices("JWT_ROLE_CLAIM", "ROLE_CLAIM"),
    )
    scope_claim: str | None = Field(
        default="scope",
        validation_alias=AliasChoices("JWT_SCOPE_CLAIM", "SCOPE_CLAIM"),
    )
    clock_skew: int = Field(
        default=60,
        validation_alias=AliasChoices("JWT_CLOCK_SKEW", "CLOCK_SKEW"),
    )

    # App / infra
    database_url: str = Field(
        default="sqlite:///./database.db", validation_alias="DATABASE_URL"
    )
    cors_origins_str: str | list[str] = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )

    environment: Literal["development", "production", "test"] = Field(
        default="development"
    )
    log_level: str = Field(default="INFO")

    # Rate limiting / Redis
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    rate_limit_requests: int = Field(default=5)
    rate_limit_window: int = Field(default=60)

    jwt_secret: str | None = Field(default=None, validation_alias="JWT_SECRET")

    # BFF/Session configuration
    secret_key: str | None = Field(default=None, validation_alias="SECRET_KEY")
    session_max_age: int = Field(
        default=86400, validation_alias="SESSION_MAX_AGE"
    )  # 24 hours
    base_url: str = Field(default="http://localhost:8000", validation_alias="BASE_URL")
    oidc_providers: dict[str, OIDCProviderConfig] = Field(
        default_factory=dict, validation_alias="OIDC_PROVIDERS"
    )
    oidc_client_id: str | None = Field(default=None, validation_alias="OIDC_CLIENT_ID")
    oidc_client_secret: str | None = Field(
        default=None, validation_alias="OIDC_CLIENT_SECRET"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
    )

    @computed_field
    @property
    def allowed_algorithms(self) -> list[str]:
        return _parse_list(self.allowed_algorithms_str)

    @allowed_algorithms.setter
    def allowed_algorithms(self, value: str | list[str]) -> None:
        if isinstance(value, list):
            self.allowed_algorithms_str = ",".join(value)
        else:
            self.allowed_algorithms_str = value

    @computed_field
    @property
    def audiences(self) -> list[str]:
        return _parse_list(self.audiences_str)

    @audiences.setter
    def audiences(self, value: str | list[str]) -> None:
        if isinstance(value, list):
            self.audiences_str = ",".join(value)
        else:
            self.audiences_str = value

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        return _parse_list(self.cors_origins_str)

    @cors_origins.setter
    def cors_origins(self, value: str | list[str]) -> None:
        if isinstance(value, list):
            self.cors_origins_str = ",".join(value)
        else:
            self.cors_origins_str = value

    @field_validator("oidc_providers", mode="before")
    @classmethod
    def _parse_oidc_providers(
        cls, value: dict[str, OIDCProviderConfig] | str | None
    ) -> dict[str, OIDCProviderConfig]:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return {k: OIDCProviderConfig(**v) for k, v in parsed.items()}
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        if value is None:
            return {}
        if isinstance(value, dict):
            # Check if values are already OIDCProviderConfig instances
            if all(isinstance(v, OIDCProviderConfig) for v in value.values()):
                return value
            # Otherwise, convert dict values to OIDCProviderConfig
            return {
                k: OIDCProviderConfig(**v) if isinstance(v, dict) else v
                for k, v in value.items()
            }
        raise TypeError("oidc_providers must be provided as a dict or JSON string")

    @field_validator("issuer_jwks_map", mode="before")
    @classmethod
    def _parse_issuer_map(cls, value: dict[str, str] | str | None) -> dict[str, str]:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                out: dict[str, str] = {}
                for part in (p for p in value.split(";") if p):
                    try:
                        iss, jwks = part.split("|", 1)
                        out[iss.strip()] = jwks.strip()
                    except Exception:
                        continue
                return out
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        raise TypeError("issuer_jwks_map must be provided as a dict or JSON string")

    def validate_runtime(self) -> None:
        if self.environment == "production":
            if not self.issuer_jwks_map:
                raise ValueError(
                    "JWT_ISSUER_JWKS_MAP must be configured in production and not empty"
                )
            if not self.audiences:
                raise ValueError("JWT_AUDIENCES must be configured in production")
            if not self.database_url:
                raise ValueError("DATABASE_URL must be configured in production")
        if self.redis_url and not (
            self.redis_url.startswith("redis://")
            or self.redis_url.startswith("rediss://")
        ):
            raise ValueError("REDIS_URL must be a redis:// or rediss:// URL")


settings = Settings()
