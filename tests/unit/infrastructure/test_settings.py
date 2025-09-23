"""Unit tests for runtime settings and configuration."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from src.runtime.config import (
    DEFAULT_OIDC_PROVIDERS,
    ApplicationConfig,
    OIDCProviderConfig,
    main_config,
)
from src.runtime.settings import EnvironmentVariables


class TestEnvironmentVariables:
    """Tests for the EnvironmentVariables class."""

    def test_default_values(self):
        """Should have sensible defaults when no environment variables are set."""
        with patch.dict(os.environ, {}, clear=True):
            env_vars = EnvironmentVariables()

            assert env_vars.environment == "development"
            assert env_vars.log_level == "INFO"
            assert env_vars.database_url == "sqlite:///./database.db"
            assert env_vars.redis_url is None
            assert env_vars.base_url == "http://localhost:8000"
            assert env_vars.oidc_redirect_uri is None

    def test_environment_variable_loading(self):
        """Should load values from environment variables."""
        test_env = {
            "ENVIRONMENT": "production",
            "LOG_LEVEL": "DEBUG",
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379",
            "BASE_URL": "https://api.example.com",
            "OIDC_REDIRECT_URI": "https://api.example.com/auth/callback",
        }

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()

            assert env_vars.environment == "production"
            assert env_vars.log_level == "DEBUG"
            assert env_vars.database_url == "postgresql://user:pass@localhost/db"
            assert env_vars.redis_url == "redis://localhost:6379"
            assert env_vars.base_url == "https://api.example.com"
            assert env_vars.oidc_redirect_uri == "https://api.example.com/auth/callback"

    def test_oidc_variables_parsing_empty(self):
        """Should return empty dict when no OIDC variables are set."""
        with patch.dict(os.environ, {}, clear=True):
            env_vars = EnvironmentVariables()
            assert env_vars.oidc_variables == {}

    def test_oidc_variables_parsing_single_provider(self):
        """Should parse OIDC variables for a single provider."""
        test_env = {
            "OIDC_GOOGLE_CLIENT_ID": "google-client-id",
            "OIDC_GOOGLE_CLIENT_SECRET": "google-client-secret",
            "OIDC_GOOGLE_REDIRECT_URI": "https://example.com/auth/google",
        }

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()
            oidc_vars = env_vars.oidc_variables

            assert "google" in oidc_vars
            assert oidc_vars["google"]["client_id"] == "google-client-id"
            assert oidc_vars["google"]["client_secret"] == "google-client-secret"
            assert (
                oidc_vars["google"]["redirect_uri"] == "https://example.com/auth/google"
            )

    def test_oidc_variables_parsing_multiple_providers(self):
        """Should parse OIDC variables for multiple providers."""
        test_env = {
            "OIDC_GOOGLE_CLIENT_ID": "google-client-id",
            "OIDC_GOOGLE_CLIENT_SECRET": "google-client-secret",
            "OIDC_MICROSOFT_CLIENT_ID": "ms-client-id",
            "OIDC_MICROSOFT_CLIENT_SECRET": "ms-client-secret",
            "OIDC_CUSTOM_PROVIDER_CLIENT_ID": "custom-client-id",
        }

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()
            oidc_vars = env_vars.oidc_variables

            assert "google" in oidc_vars
            assert "microsoft" in oidc_vars
            assert "custom_provider" in oidc_vars

            assert oidc_vars["google"]["client_id"] == "google-client-id"
            assert oidc_vars["microsoft"]["client_id"] == "ms-client-id"
            assert oidc_vars["custom_provider"]["client_id"] == "custom-client-id"


class TestApplicationConfig:
    """Tests for the ApplicationConfig class."""

    def test_default_config(self):
        """Should have sensible defaults."""
        config = ApplicationConfig()

        # Check basic defaults
        assert config.environment == "development"
        assert config.log_level == "INFO"
        assert config.database_url == "sqlite:///./database.db"

        # Check nested config defaults
        assert config.jwt.allowed_algorithms == ["RS256", "RS512", "ES256", "ES384"]
        assert config.cors.origins == ["http://localhost:3000", "http://localhost:3001"]
        assert config.session.max_age == 86400
        assert config.rate_limit.enabled is True

    def test_environment_specific_config_development(self):
        """Should apply development-specific settings."""
        env_vars = EnvironmentVariables()
        config = ApplicationConfig.from_environment(
            env_vars, environment_override="development"
        )

        assert config.environment == "development"
        assert config.rate_limit.enabled is False  # Disabled in dev
        assert config.session.secure_cookies is False

    def test_environment_specific_config_production(self):
        """Should apply production-specific settings."""
        env_vars = EnvironmentVariables()
        config = ApplicationConfig.from_environment(
            env_vars, environment_override="production"
        )

        assert config.environment == "production"
        assert config.session.secure_cookies is True  # Enabled in prod
        assert config.cors.origins == []  # Must be explicitly configured

    def test_environment_specific_config_test(self):
        """Should apply test-specific settings."""
        env_vars = EnvironmentVariables()
        config = ApplicationConfig.from_environment(
            env_vars, environment_override="test"
        )

        assert config.environment == "test"
        assert config.rate_limit.enabled is False  # Disabled in test
        assert config.session.max_age == 300  # 5 minutes for tests

    def test_environment_variable_overrides(self):
        """Should override config values with environment variables."""
        test_env = {
            "ENVIRONMENT": "production",
            "LOG_LEVEL": "DEBUG",
            "DATABASE_URL": "postgresql://prod:pass@db.example.com/myapp",
            "REDIS_URL": "redis://redis.example.com:6379",
            "BASE_URL": "https://api.myapp.com",
            "OIDC_REDIRECT_URI": "https://api.myapp.com/auth/callback",
        }

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()
            config = ApplicationConfig.from_environment(env_vars)

            assert config.environment == "production"
            assert config.log_level == "DEBUG"
            assert config.database_url == "postgresql://prod:pass@db.example.com/myapp"
            assert config.redis_url == "redis://redis.example.com:6379"
            assert config.base_url == "https://api.myapp.com"
            assert (
                config.oidc.global_redirect_uri == "https://api.myapp.com/auth/callback"
            )


class TestOIDCYamlLoading:
    """Tests for OIDC YAML configuration loading."""

    def test_load_yaml_config_missing_file(self):
        """Should return empty dict when YAML file doesn't exist."""
        with patch("src.runtime.config.Path") as mock_path:
            mock_path.return_value.exists.return_value = False

            from src.runtime.config import _load_oidc_yaml_config

            result = _load_oidc_yaml_config()
            assert result == {}

    def test_load_yaml_config_valid_file(self):
        """Should load YAML config when file exists and is valid."""
        yaml_content = {
            "custom_provider": {
                "authorization_endpoint": "https://auth.custom.com/authorize",
                "token_endpoint": "https://auth.custom.com/token",
                "issuer": "https://auth.custom.com",
            },
            "google": {
                "scopes": ["openid", "profile"]  # Override default scopes
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(yaml_content, f)
            yaml_file = Path(f.name)

        try:
            with patch("src.runtime.config.Path") as mock_path:
                mock_path_instance = Mock()
                mock_path_instance.exists.return_value = True

                # Create a context manager mock for file operations
                file_context = Mock()
                file_context.__enter__ = Mock(return_value=yaml_file.open())
                file_context.__exit__ = Mock(return_value=None)
                mock_path_instance.open.return_value = file_context
                mock_path.return_value = mock_path_instance

                from src.runtime.config import _load_oidc_yaml_config

                result = _load_oidc_yaml_config()

                assert "custom_provider" in result
                assert "google" in result
                assert result["custom_provider"]["issuer"] == "https://auth.custom.com"
                assert result["google"]["scopes"] == ["openid", "profile"]
        finally:
            yaml_file.unlink()

    def test_load_yaml_config_invalid_yaml(self):
        """Should return empty dict and log warning for invalid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            yaml_file = Path(f.name)

        try:
            with patch("src.runtime.config.Path") as mock_path:
                mock_path_instance = Mock()
                mock_path_instance.exists.return_value = True

                # Create a context manager mock for file operations
                file_context = Mock()
                file_context.__enter__ = Mock(return_value=yaml_file.open())
                file_context.__exit__ = Mock(return_value=None)
                mock_path_instance.open.return_value = file_context
                mock_path.return_value = mock_path_instance

                from src.runtime.config import _load_oidc_yaml_config

                result = _load_oidc_yaml_config()
                assert result == {}
        finally:
            yaml_file.unlink()


class TestOIDCProviderConfiguration:
    """Tests for OIDC provider configuration and merging."""

    def test_default_providers_loaded(self):
        """Should load default OIDC providers."""
        from src.runtime.config import _get_oidc_providers

        providers = _get_oidc_providers()

        assert "google" in providers
        assert "microsoft" in providers

        # Check Google defaults
        google = providers["google"]
        assert (
            google.authorization_endpoint
            == "https://accounts.google.com/o/oauth2/v2/auth"
        )
        assert google.issuer == "https://accounts.google.com"
        assert google.scopes == ["openid", "profile", "email"]

        # Check Microsoft defaults
        microsoft = providers["microsoft"]
        assert (
            microsoft.authorization_endpoint
            == "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        )
        assert microsoft.issuer == "https://login.microsoftonline.com"

    def test_yaml_overrides_default_provider(self):
        """Should override default provider settings with YAML config."""
        yaml_content = {
            "google": {
                "scopes": ["openid", "profile"],  # Override default scopes
                "issuer": "https://custom.google.com",  # Override issuer
            }
        }

        with patch(
            "src.runtime.config._load_oidc_yaml_config", return_value=yaml_content
        ):
            from src.runtime.config import _get_oidc_providers

            providers = _get_oidc_providers()

            google = providers["google"]
            assert google.scopes == ["openid", "profile"]
            assert google.issuer == "https://custom.google.com"
            # Other fields should remain unchanged
            assert (
                google.authorization_endpoint
                == "https://accounts.google.com/o/oauth2/v2/auth"
            )

    def test_yaml_adds_custom_provider(self):
        """Should add new providers from YAML config."""
        yaml_content = {
            "custom_provider": {
                "authorization_endpoint": "https://auth.custom.com/authorize",
                "token_endpoint": "https://auth.custom.com/token",
                "issuer": "https://auth.custom.com",
                "scopes": ["openid", "email"],
            }
        }

        with patch(
            "src.runtime.config._load_oidc_yaml_config", return_value=yaml_content
        ):
            from src.runtime.config import _get_oidc_providers

            providers = _get_oidc_providers()

            assert "custom_provider" in providers
            custom = providers["custom_provider"]
            assert custom.authorization_endpoint == "https://auth.custom.com/authorize"
            assert custom.issuer == "https://auth.custom.com"
            assert custom.scopes == ["openid", "email"]

    def test_yaml_invalid_provider_ignored(self):
        """Should ignore invalid provider configs in YAML."""
        yaml_content = {
            "invalid_provider": {"missing_required_fields": True},
            "google": {"scopes": ["openid", "profile"]},
        }

        with patch(
            "src.runtime.config._load_oidc_yaml_config", return_value=yaml_content
        ):
            from src.runtime.config import _get_oidc_providers

            providers = _get_oidc_providers()

            # Should still have google (valid override)
            assert "google" in providers
            # Invalid provider should be ignored, not crash
            assert "invalid_provider" not in providers


class TestOIDCEnvironmentOverrides:
    """Tests for OIDC environment variable overrides."""

    @pytest.fixture(autouse=True)
    def mock_yaml_loading(self):
        """Mock YAML loading to prevent interference from real oidc-providers.yaml file."""
        # Also ensure clean environment state between tests
        original_environ = os.environ.copy()
        try:
            with patch("src.runtime.config._load_oidc_yaml_config", return_value={}):
                yield
        finally:
            # Restore original environment to ensure no test contamination
            os.environ.clear()
            os.environ.update(original_environ)

    def test_oidc_client_credentials_override_default_provider(self):
        """Should override client credentials for default providers."""
        test_env = {
            "OIDC_GOOGLE_CLIENT_ID": "my-google-client-id",
            "OIDC_GOOGLE_CLIENT_SECRET": "my-google-secret",
            "OIDC_GOOGLE_REDIRECT_URI": "https://myapp.com/auth/google",
        }

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()
            config = ApplicationConfig.from_environment(env_vars)

            google_provider = config.oidc.providers["google"]
            assert google_provider.client_id == "my-google-client-id"
            assert google_provider.client_secret == "my-google-secret"
            assert google_provider.redirect_uri == "https://myapp.com/auth/google"

            # Other fields should remain from defaults
            assert (
                google_provider.authorization_endpoint
                == "https://accounts.google.com/o/oauth2/v2/auth"
            )
            assert google_provider.issuer == "https://accounts.google.com"

    def test_oidc_partial_credentials_override(self):
        """Should handle partial environment variable overrides."""
        test_env = {
            "OIDC_GOOGLE_CLIENT_ID": "my-google-client-id",
            # No client_secret or redirect_uri
        }

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()
            config = ApplicationConfig.from_environment(env_vars)

            google_provider = config.oidc.providers["google"]
            assert google_provider.client_id == "my-google-client-id"
            assert google_provider.client_secret is None  # Should remain None
            assert google_provider.redirect_uri is None  # Should remain None

    def test_oidc_multiple_providers_override(self):
        """Should override multiple providers independently."""
        test_env = {
            "OIDC_GOOGLE_CLIENT_ID": "google-client-id",
            "OIDC_GOOGLE_CLIENT_SECRET": "google-secret",
            "OIDC_MICROSOFT_CLIENT_ID": "ms-client-id",
            "OIDC_MICROSOFT_CLIENT_SECRET": "ms-secret",
        }

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()
            config = ApplicationConfig.from_environment(env_vars)

            google_provider = config.oidc.providers["google"]
            microsoft_provider = config.oidc.providers["microsoft"]

            assert google_provider.client_id == "google-client-id"
            assert google_provider.client_secret == "google-secret"
            assert microsoft_provider.client_id == "ms-client-id"
            assert microsoft_provider.client_secret == "ms-secret"

    def test_oidc_custom_provider_from_yaml_with_env_override(self):
        """Should combine YAML custom provider with environment overrides."""
        yaml_content = {
            "auth0": {
                "authorization_endpoint": "https://myapp.auth0.com/authorize",
                "token_endpoint": "https://myapp.auth0.com/oauth/token",
                "issuer": "https://myapp.auth0.com/",
                "scopes": ["openid", "profile", "email"],
            }
        }

        test_env = {
            "OIDC_AUTH0_CLIENT_ID": "auth0-client-id",
            "OIDC_AUTH0_CLIENT_SECRET": "auth0-secret",
        }

        with patch(
            "src.runtime.config._load_oidc_yaml_config", return_value=yaml_content
        ):
            with patch.dict(os.environ, test_env, clear=True):
                env_vars = EnvironmentVariables()
                config = ApplicationConfig.from_environment(env_vars)

                assert "auth0" in config.oidc.providers
                auth0_provider = config.oidc.providers["auth0"]

                # Should have YAML config
                assert (
                    auth0_provider.authorization_endpoint
                    == "https://myapp.auth0.com/authorize"
                )
                assert auth0_provider.issuer == "https://myapp.auth0.com/"
                assert auth0_provider.scopes == ["openid", "profile", "email"]

                # Should have environment overrides
                assert auth0_provider.client_id == "auth0-client-id"
                assert auth0_provider.client_secret == "auth0-secret"

    def test_oidc_provider_without_client_id_excluded(self):
        """Should exclude providers that don't have client_id set."""
        # No environment variables set, so no client_id for any provider
        with patch.dict(os.environ, {}, clear=True):
            env_vars = EnvironmentVariables()
            config = ApplicationConfig.from_environment(env_vars)

            # Default providers should still be present but without credentials
            assert "google" in config.oidc.providers
            assert "microsoft" in config.oidc.providers

            google_provider = config.oidc.providers["google"]
            assert google_provider.client_id is None
            assert google_provider.client_secret is None

    def test_global_redirect_uri_fallback(self):
        """Should use global redirect URI when provider-specific one is not set."""
        test_env = {
            "OIDC_REDIRECT_URI": "https://myapp.com/auth/callback",
            "OIDC_GOOGLE_CLIENT_ID": "google-client-id",
        }

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()
            config = ApplicationConfig.from_environment(env_vars)

            assert config.oidc.global_redirect_uri == "https://myapp.com/auth/callback"

            google_provider = config.oidc.providers["google"]
            assert google_provider.client_id == "google-client-id"


class TestConfigIntegration:
    """Integration tests for the complete configuration system."""

    def test_complete_configuration_flow(self):
        """Should handle complete configuration with all sources."""
        yaml_content = {
            "custom_provider": {
                "authorization_endpoint": "https://auth.custom.com/authorize",
                "token_endpoint": "https://auth.custom.com/token",
                "issuer": "https://auth.custom.com",
            },
            "google": {
                "scopes": ["openid", "profile"]  # Override default
            },
        }

        test_env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql://prod:pass@db.example.com/app",
            "BASE_URL": "https://api.myapp.com",
            "OIDC_REDIRECT_URI": "https://api.myapp.com/auth/callback",
            "OIDC_GOOGLE_CLIENT_ID": "prod-google-client-id",
            "OIDC_GOOGLE_CLIENT_SECRET": "prod-google-secret",
            "OIDC_CUSTOM_PROVIDER_CLIENT_ID": "custom-client-id",
            "OIDC_CUSTOM_PROVIDER_CLIENT_SECRET": "custom-secret",
        }

        with patch(
            "src.runtime.config._load_oidc_yaml_config", return_value=yaml_content
        ):
            with patch.dict(os.environ, test_env, clear=True):
                env_vars = EnvironmentVariables()
                config = ApplicationConfig.from_environment(env_vars)

                # Environment overrides should be applied
                assert config.environment == "production"
                assert (
                    config.database_url == "postgresql://prod:pass@db.example.com/app"
                )
                assert config.base_url == "https://api.myapp.com"

                # Production-specific config should be applied
                assert config.session.secure_cookies is True
                assert config.cors.origins == []

                # OIDC global config
                assert (
                    config.oidc.global_redirect_uri
                    == "https://api.myapp.com/auth/callback"
                )

                # Google provider: default + YAML override + env credentials
                google_provider = config.oidc.providers["google"]
                assert google_provider.scopes == ["openid", "profile"]  # From YAML
                assert google_provider.client_id == "prod-google-client-id"  # From env
                assert google_provider.client_secret == "prod-google-secret"  # From env
                assert (
                    google_provider.authorization_endpoint
                    == "https://accounts.google.com/o/oauth2/v2/auth"
                )  # From default

                # Custom provider: YAML + env credentials
                custom_provider = config.oidc.providers["custom_provider"]
                assert (
                    custom_provider.authorization_endpoint
                    == "https://auth.custom.com/authorize"
                )  # From YAML
                assert custom_provider.client_id == "custom-client-id"  # From env
                assert custom_provider.client_secret == "custom-secret"  # From env

    def test_property_access_methods(self):
        """Should provide convenient property access to nested configs."""
        env_vars = EnvironmentVariables()
        config = ApplicationConfig.from_environment(env_vars)

        # Test convenience properties
        assert config.cors_origins == config.cors.origins
        assert config.allowed_algorithms == config.jwt.allowed_algorithms
        assert config.audiences == config.jwt.audiences
        assert config.uid_claim == config.jwt.uid_claim
        assert config.session_max_age == config.session.max_age
        assert config.oidc_providers == config.oidc.providers
