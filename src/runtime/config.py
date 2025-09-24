"""Application configuration with default values and complex types.

This module contains non-sensitive configuration that doesn't belong in environment variables.
Complex objects, default business logic settings, and static configuration live here.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

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
    uid_claim: str = "app_uid"  # Custom UID claim mapping to internal user
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
    # Create deep copies to avoid mutation issues between different config instances
    providers = {
        name: provider.model_copy(deep=True)
        for name, provider in DEFAULT_OIDC_PROVIDERS.items()
    }

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
    secret_key: str = Field(default="dev-secret-key")

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
        config.secret_key = env_vars.secret_key

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

        # Reset tracking so only explicitly set fields after this point are tracked
        config.__pydantic_fields_set__ = set()

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


@dataclass
class AppContext:
    """Application context containing configuration and other app-wide state."""

    config: ApplicationConfig


# Global configuration instance
_env_vars = EnvironmentVariables()
_default_config = ApplicationConfig.from_environment(_env_vars)
_default_context = AppContext(config=_default_config)


# Context variable for application context
_app_context: ContextVar[AppContext] = ContextVar(
    "app_context", default=_default_context
)


def get_context() -> AppContext:
    """Get the current application context.

    Returns:
        AppContext: The current application context containing configuration.
    """
    return _app_context.get()


def set_context(context: AppContext) -> Token[AppContext]:
    """Set the current application context.

    Args:
        context: AppContext instance to set as current.
    """
    return _app_context.set(context)


def _recursive_model_dump_exclude_unset(model: BaseModel) -> dict:
    """Recursively dump a Pydantic model with exclude_unset=True for all nested models.

    This function works from the deepest levels up, so that if any nested field
    is explicitly set, the parent field containing that nested model is also included.

    Args:
        model: The Pydantic model to dump

    Returns:
        dict: Dictionary containing only explicitly set fields at all levels
    """
    result = {}

    # Get explicitly set fields at this level
    explicitly_set_fields = model.model_fields_set

    # Check all fields in the model
    for field_name, _field_info in model.__class__.model_fields.items():
        field_value = getattr(model, field_name)

        if isinstance(field_value, BaseModel):
            # Recursively check nested Pydantic models
            nested_result = _recursive_model_dump_exclude_unset(field_value)
            if nested_result:
                # If nested model has explicitly set fields, we need to merge properly
                # Include the full nested model but let the recursive merge handle it
                result[field_name] = field_value.model_dump()
            elif field_name in explicitly_set_fields:
                # If this nested model field was explicitly set at this level, include it
                result[field_name] = field_value.model_dump()
        elif isinstance(field_value, dict):
            # Handle dict fields that might contain Pydantic models
            nested_dict = {}
            has_nested_changes = False
            for key, value in field_value.items():
                if isinstance(value, BaseModel):
                    nested_result = _recursive_model_dump_exclude_unset(value)
                    if nested_result:
                        nested_dict[key] = value.model_dump()
                        has_nested_changes = True
                    else:
                        nested_dict[key] = value.model_dump()
                else:
                    nested_dict[key] = value

            if has_nested_changes or field_name in explicitly_set_fields:
                result[field_name] = nested_dict
        elif field_name in explicitly_set_fields:
            # Regular field that was explicitly set
            result[field_name] = field_value

    return result


def _recursive_dict_merge(base_dict: dict, override_dict: dict) -> dict:
    """Recursively merge two dictionaries from deepest levels up.

    Args:
        base_dict: The base dictionary to merge into
        override_dict: The override dictionary to merge from

    Returns:
        dict: The merged dictionary
    """
    result = base_dict.copy()

    for key, value in override_dict.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = _recursive_dict_merge(result[key], value)
        else:
            # Override or new key
            result[key] = value

    return result


@contextmanager
def with_context(config_override: ApplicationConfig | dict | None = None, **kwargs):
    """Context manager for temporarily overriding the application context.

    This function merges the override configuration with the current context,
    allowing for partial overrides that inherit non-overridden values from
    the parent context.

    Args:
        config_override: Optional ApplicationConfig instance or dict containing override values.
                        If ApplicationConfig, nested fields are properly merged with inheritance.
                        If dict, only specified keys are treated as overrides.
        **kwargs: Additional override values as keyword arguments.

    Example:
        # Using dict overrides (recommended for partial overrides)
        with with_context({'log_level': 'DEBUG', 'environment': 'prod'}):
            config = get_config()
            assert config.log_level == 'DEBUG'     # Overridden
            assert config.environment == 'prod'    # Overridden

        # Using keyword arguments (recommended for single overrides)
        with with_context(log_level='INFO'):
            config = get_config()
            assert config.log_level == 'INFO'      # Overridden

        # Using ApplicationConfig (properly merges nested configurations)
        override_config = ApplicationConfig()
        override_config.jwt.uid_claim = 'custom_uid'  # Only this field changes
        with with_context(override_config):
            config = get_config()
            # config.jwt.uid_claim is 'custom_uid', other jwt fields inherited
    """
    # Handle kwargs first
    if kwargs:
        # Convert kwargs to dict and merge with any dict override
        override_dict = {}
        if isinstance(config_override, dict):
            override_dict.update(config_override)
        elif config_override is not None:
            raise ValueError("Cannot use kwargs with ApplicationConfig override")
        override_dict.update(kwargs)

        # Use dict merging approach
        current_config = get_context().config
        merged_config = current_config.model_copy(update=override_dict)

        token = set_context(replace(get_context(), config=merged_config))
        try:
            yield
        finally:
            _app_context.reset(token)
        return

    if config_override is None:
        # No overrides, just yield current context
        yield
        return

    current_config = get_context().config

    if isinstance(config_override, dict):
        # Use Pydantic's model_copy with update for simple dict merging
        merged_config = current_config.model_copy(update=config_override)
    elif isinstance(config_override, ApplicationConfig):
        # Get only explicitly set fields recursively using our custom function
        override_dict = _recursive_model_dump_exclude_unset(config_override)

        # Merge with current config using recursive merge
        base_dict = current_config.model_dump()
        merged_dict = _recursive_dict_merge(base_dict, override_dict)

        # Handle validation aliases - convert field names to aliases where needed
        alias_mapping = {
            'database_url': 'DATABASE_URL',
            'redis_url': 'REDIS_URL',
            'base_url': 'BASE_URL'
        }
        
        # Convert field names to aliases for Pydantic validation
        for field_name, alias_name in alias_mapping.items():
            if field_name in merged_dict:
                merged_dict[alias_name] = merged_dict.pop(field_name)

        # Create new ApplicationConfig from merged dict
        merged_config = ApplicationConfig.model_validate(merged_dict)
    else:
        raise ValueError(
            f"config_override must be dict, ApplicationConfig, or None, got {type(config_override)}"
        )

    token = set_context(replace(get_context(), config=merged_config))
    try:
        yield
    finally:
        _app_context.reset(token)


def get_config() -> ApplicationConfig:
    """Convenience function to get the current configuration.

    Returns:
        ApplicationConfig: The current configuration from the app context.
    """
    return get_context().config
